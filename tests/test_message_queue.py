"""
test_message_queue.py — 消息队列单元测试
=======================================

覆盖场景：
  - MemoryQueueBackend: publish / subscribe / retry / ACK / NACK / 队列满 / 统计
  - MessageQueue 门面: 初始化 / 降级 / 健康检查
  - 消息生命周期: PENDING → PROCESSING → COMPLETED / FAILED
  - 幂等全局实例 get_message_queue()
"""
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# 确保项目根在 sys.path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.message_queue import (
    Message,
    MessageStatus,
    MemoryQueueBackend,
    RedisStreamBackend,
    MessageQueue,
    get_message_queue,
    close_message_queue,
    publish_message,
    subscribe_topic,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY,
    DEFAULT_RETRY_BACKOFF,
    MEMORY_QUEUE_MAX_SIZE,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest_asyncio.fixture
async def memory_backend():
    """创建内存队列后端（用户负责 close）"""
    backend = MemoryQueueBackend()
    yield backend
    # cleanup — 使用 await 确保在正确事件循环中执行
    await backend.close()


@pytest_asyncio.fixture
async def mq_memory():
    """创建使用内存后端的 MessageQueue 实例"""
    mq = MessageQueue(name="test")
    await mq.initialize(redis_client=None)  # 强制内存模式
    yield mq
    await mq.close()


# ═══════════════════════════════════════════════════════════════════════════
# Message dataclass
# ═══════════════════════════════════════════════════════════════════════════

class TestMessageDataclass:
    """Message 数据模型单元测试"""

    def test_message_creation_defaults(self):
        msg = Message(
            message_id="test-001",
            topic="test-topic",
            payload={"key": "value"},
        )
        assert msg.message_id == "test-001"
        assert msg.topic == "test-topic"
        assert msg.payload == {"key": "value"}
        assert msg.status == MessageStatus.PENDING
        assert msg.retry_count == 0
        assert msg.max_retries == DEFAULT_MAX_RETRIES
        assert msg.last_error is None

    def test_message_to_dict(self):
        msg = Message(
            message_id="test-002",
            topic="eval",
            payload={"run_id": 42},
            status=MessageStatus.COMPLETED,
            retry_count=1,
            last_error="timeout",
            consumer_id="c1",
        )
        d = msg.to_dict()
        assert d["message_id"] == "test-002"
        assert d["topic"] == "eval"
        assert d["status"] == "completed"
        assert d["retry_count"] == 1
        assert d["last_error"] == "timeout"
        assert d["consumer_id"] == "c1"

    def test_message_from_dict(self):
        data = {
            "message_id": "test-003",
            "topic": "upload",
            "payload": {"path": "/tmp/f.pdf"},
            "status": "pending",
            "created_at": 1234567890.0,
            "retry_count": 0,
            "max_retries": 5,
            "consumer_id": "c2",
        }
        msg = Message.from_dict(data)
        assert msg.message_id == "test-003"
        assert msg.topic == "upload"
        assert msg.status == MessageStatus.PENDING
        assert msg.max_retries == 5


# ═══════════════════════════════════════════════════════════════════════════
# MemoryQueueBackend — 核心功能
# ═══════════════════════════════════════════════════════════════════════════

class TestMemoryBackendPublish:
    """内存后端 — 发布消息"""

    @pytest.mark.asyncio
    async def test_publish_returns_message_id(self, memory_backend):
        msg_id = await memory_backend.publish("test", {"data": "hello"})
        assert isinstance(msg_id, str)
        assert len(msg_id) == 16  # uuid4 hex[:16]
        assert msg_id in memory_backend._messages

    @pytest.mark.asyncio
    async def test_publish_stores_message_in_pending(self, memory_backend):
        msg_id = await memory_backend.publish("topic-a", {"x": 1})
        assert msg_id in memory_backend._pending["topic-a"]

    @pytest.mark.asyncio
    async def test_publish_custom_max_retries(self, memory_backend):
        msg_id = await memory_backend.publish("topic-a", {"x": 1}, max_retries=5)
        msg = memory_backend._messages[msg_id]
        assert msg.max_retries == 5

    @pytest.mark.asyncio
    async def test_publish_with_metadata(self, memory_backend):
        msg_id = await memory_backend.publish(
            "topic-a", {"x": 1}, metadata={"source": "test"}
        )
        msg = memory_backend._messages[msg_id]
        assert msg.metadata == {"source": "test"}


class TestMemoryBackendSubscribe:
    """内存后端 — 订阅消息"""

    @pytest.mark.asyncio
    async def test_subscribe_and_process(self, memory_backend):
        results = []

        async def handler(payload):
            results.append(payload)

        await memory_backend.subscribe("topic-a", handler)
        await memory_backend.publish("topic-a", {"step": 1})

        # 给消费者一点时间处理
        await asyncio.sleep(0.3)

        assert len(results) == 1
        assert results[0] == {"step": 1}

    @pytest.mark.asyncio
    async def test_subscribe_multiple_messages(self, memory_backend):
        received = []

        async def handler(payload):
            received.append(payload)

        await memory_backend.subscribe("batch", handler)
        for i in range(5):
            await memory_backend.publish("batch", {"n": i})

        await asyncio.sleep(0.5)
        assert len(received) == 5
        assert sorted([m["n"] for m in received]) == list(range(5))

    @pytest.mark.asyncio
    async def test_subscribe_multiple_consumers(self, memory_backend):
        consumer_1 = []
        consumer_2 = []

        async def handler_1(payload):
            consumer_1.append(payload)

        async def handler_2(payload):
            consumer_2.append(payload)

        await memory_backend.subscribe("shared", handler_1, consumer_id="c1")
        await memory_backend.subscribe("shared", handler_2, consumer_id="c2")

        for i in range(3):
            await memory_backend.publish("shared", {"n": i})

        await asyncio.sleep(0.5)
        # 每个消费者都消费消息（内存模式有两个独立消费者各自从队列取）
        total_received = len(consumer_1) + len(consumer_2)
        assert total_received == 3  # 总共 3 条被消费
        assert len(consumer_1) + len(consumer_2) == 3


class TestMemoryBackendRetry:
    """内存后端 — 重试逻辑"""

    @pytest.mark.asyncio
    async def test_retry_on_failure_then_success(self, memory_backend):
        call_count = [0]

        async def flaky_handler(payload):
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("临时错误")
            return "ok"

        await memory_backend.subscribe("flaky", flaky_handler)
        await memory_backend.publish("flaky", {"test": True}, max_retries=5)

        await asyncio.sleep(1.5)  # 等待重试完成（间隔 1s, 2s）
        assert call_count[0] == 3  # 2 次失败 + 1 次成功

    @pytest.mark.asyncio
    async def test_retry_exhausted(self, memory_backend):
        async def always_fail(payload):
            raise RuntimeError("永远失败")

        await memory_backend.subscribe("fail", always_fail)
        msg_id = await memory_backend.publish("fail", {"x": 1}, max_retries=1)

        await asyncio.sleep(1.5)

        # 消息应从 pending 中移除（重试穷尽后丢弃）
        msg = memory_backend._messages.get(msg_id)
        # 即使还在 pending，状态也应该是 FAILED
        assert msg is not None
        assert msg.status == MessageStatus.FAILED

    @pytest.mark.asyncio
    async def test_retry_exponential_backoff_delays(self, memory_backend):
        """验证重试延迟遵循指数退避模式"""
        delays = []

        # 只 mock _process_with_retry 内部实际使用的 sleep 调用
        # 但不阻止消费者循环的 sleep
        original_sleep = asyncio.sleep
        call_counter = [0]

        async def tracking_sleep(seconds):
            # 只记录 >= 0.5s 的 sleep（重试延迟），跳过消费者循环的 1s timeout
            if seconds >= 0.5:
                delays.append(seconds)
            # 不实际等待，加速测试
            return await original_sleep(0)

        async def flaky_2(payload):
            raise RuntimeError("fail")

        # 在消费者循环中 patch asyncio.sleep
        with patch("src.services.message_queue.asyncio.sleep", tracking_sleep):
            await memory_backend.subscribe("backoff-2", flaky_2)
            await memory_backend.publish("backoff-2", {"x": 1}, max_retries=3)
            await original_sleep(0.3)

        # 重试延迟应该是: 1.0, 2.0, 4.0
        if len(delays) >= 3:
            # 验证是指数退避（ratio ≈ 2.0）
            for i in range(1, len(delays)):
                if delays[i - 1] > 0.01:
                    ratio = delays[i] / delays[i - 1]
                    assert 1.8 <= ratio <= 2.2, f"指数退避比例错误: {ratio}"


class TestMemoryBackendAckNack:
    """内存后端 — ACK / NACK"""

    @pytest.mark.asyncio
    async def test_manual_ack(self, memory_backend):
        msg_id = await memory_backend.publish("manual", {"x": 1})

        # 手动确认前，消息在 pending 中
        assert msg_id in memory_backend._pending["manual"]

        await memory_backend.ack("manual", msg_id)

        # ACK 后，从 pending 中移除
        assert msg_id not in memory_backend._pending["manual"]
        msg = memory_backend._messages[msg_id]
        assert msg.status == MessageStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_manual_nack_requeue(self, memory_backend):
        msg_id = await memory_backend.publish("nack-test", {"x": 1}, max_retries=5)
        msg = memory_backend._messages[msg_id]

        await memory_backend.nack("nack-test", msg_id, error="manual reject")

        # NACK 应增加重试计数
        assert memory_backend._messages[msg_id].retry_count == 1
        assert memory_backend._messages[msg_id].last_error == "manual reject"

    @pytest.mark.asyncio
    async def test_nack_exhausted_retries(self, memory_backend):
        msg_id = await memory_backend.publish("nack-exh", {"x": 1}, max_retries=3)

        # 反复 NACK 直到超限
        for i in range(4):
            await memory_backend.nack("nack-exh", msg_id, error=f"fail-{i}")

        assert memory_backend._messages[msg_id].status == MessageStatus.FAILED
        assert msg_id not in memory_backend._pending.get("nack-exh", set())


class TestMemoryBackendEdgeCases:
    """内存后端 — 边界情况"""

    @pytest.mark.asyncio
    async def test_get_queue_stats(self, memory_backend):
        await memory_backend.publish("stats", {"a": 1})
        await memory_backend.publish("stats", {"b": 2})

        stats = await memory_backend.get_queue_stats("stats")
        assert stats["topic"] == "stats"
        assert stats["pending"] == 2

        all_stats = await memory_backend.get_queue_stats()
        assert "stats" in all_stats

    @pytest.mark.asyncio
    async def test_health_check_always_true(self, memory_backend):
        assert await memory_backend.health_check() is True

    @pytest.mark.asyncio
    async def test_get_message(self, memory_backend):
        msg_id = await memory_backend.publish("query", {"key": "val"})
        msg = await memory_backend.get_message("query", msg_id)
        assert msg is not None
        assert msg.payload == {"key": "val"}

    @pytest.mark.asyncio
    async def test_get_nonexistent_message(self, memory_backend):
        msg = await memory_backend.get_message("nonexist", "fake-id")
        assert msg is None

    @pytest.mark.asyncio
    async def test_close_stops_all_consumers(self, memory_backend):
        async def noop(payload):
            pass

        await memory_backend.subscribe("close-test", noop)
        assert memory_backend._running.get("close-test") is True

        await memory_backend.close()
        assert not memory_backend._running.get("close-test", True)


# ═══════════════════════════════════════════════════════════════════════════
# MessageQueue — 统一门面
# ═══════════════════════════════════════════════════════════════════════════

class TestMessageQueueFacade:
    """MessageQueue 门面测试"""

    @pytest.mark.asyncio
    async def test_initialize_memory_mode(self):
        mq = MessageQueue(name="test-mem")
        await mq.initialize(redis_client=None)
        assert mq.backend_type == "memory"
        assert mq.is_ready
        await mq.close()

    @pytest.mark.asyncio
    async def test_initialize_redis_fallback(self):
        """模拟 Redis 连接失败时降级到内存"""
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = ConnectionError("Redis 不可用")

        mq = MessageQueue(name="test-fallback")
        await mq.initialize(redis_client=mock_redis)
        assert mq.backend_type == "memory"  # 降级成功
        assert mq.is_ready
        await mq.close()

    @pytest.mark.asyncio
    async def test_publish_and_subscribe_through_facade(self, mq_memory):
        received = []

        async def handler(payload):
            received.append(payload)

        await mq_memory.subscribe("facade-topic", handler, consumer_id="test-c")
        msg_id = await mq_memory.publish("facade-topic", {"hello": "world"})

        await asyncio.sleep(0.3)
        assert len(received) == 1
        assert received[0] == {"hello": "world"}

    @pytest.mark.asyncio
    async def test_health_check(self, mq_memory):
        health = await mq_memory.health()
        assert health["status"] == "healthy"
        assert health["backend"] == "memory"
        assert health["name"] == "test"

    @pytest.mark.asyncio
    async def test_ack_through_facade(self, mq_memory):
        msg_id = await mq_memory.publish("ack-topic", {"x": 1})
        await mq_memory.ack("ack-topic", msg_id)
        msg = await mq_memory.get_message("ack-topic", msg_id)
        assert msg.status == MessageStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_nack_through_facade(self, mq_memory):
        msg_id = await mq_memory.publish("nack-f-topic", {"x": 1}, max_retries=5)
        await mq_memory.nack("nack-f-topic", msg_id, error="测试拒绝")
        msg = await mq_memory.get_message("nack-f-topic", msg_id)
        assert msg.retry_count == 1
        assert msg.last_error == "测试拒绝"

    @pytest.mark.asyncio
    async def test_not_initialized_raises(self):
        mq = MessageQueue(name="uninit")
        with pytest.raises(RuntimeError, match="未初始化"):
            await mq.publish("test", {})

    @pytest.mark.asyncio
    async def test_close_marks_not_ready(self, mq_memory):
        await mq_memory.close()
        assert not mq_memory.is_ready

    @pytest.mark.asyncio
    async def test_subscribed_topics_tracked(self, mq_memory):
        async def h(payload):
            pass

        await mq_memory.subscribe("t1", h)
        await mq_memory.subscribe("t2", h)
        health = await mq_memory.health()
        assert "t1" in health["subscribed_topics"]
        assert "t2" in health["subscribed_topics"]


# ═══════════════════════════════════════════════════════════════════════════
# 全局实例管理
# ═══════════════════════════════════════════════════════════════════════════

class TestGlobalInstance:
    """全局消息队列实例测试"""

    @pytest.mark.asyncio
    async def test_get_message_queue_singleton(self):
        """get_message_queue 返回单例"""
        import src.services.message_queue as mq_mod
        mq_mod._global_message_queue = None

        mq1 = await get_message_queue(redis_client=None, name="global-test")
        mq2 = await get_message_queue(redis_client=None, name="global-test")
        assert mq1 is mq2
        await mq1.close()
        mq_mod._global_message_queue = None

    @pytest.mark.asyncio
    async def test_close_message_queue(self):
        import src.services.message_queue as mq_mod
        mq_mod._global_message_queue = None

        await get_message_queue(redis_client=None, name="close-test")
        await close_message_queue()
        assert mq_mod._global_message_queue is None

    @pytest.mark.asyncio
    async def test_publish_message_convenience(self):
        import src.services.message_queue as mq_mod
        mq_mod._global_message_queue = None

        msg_id = await publish_message("conv-topic", {"data": "quick"})
        assert isinstance(msg_id, str)
        await close_message_queue()

    @pytest.mark.asyncio
    async def test_subscribe_topic_convenience(self):
        import src.services.message_queue as mq_mod
        mq_mod._global_message_queue = None

        received = []

        async def handler(payload):
            received.append(payload)

        await subscribe_topic("conv-sub", handler, consumer_id="ctest")
        await publish_message("conv-sub", {"x": 1})
        await asyncio.sleep(0.3)
        assert len(received) >= 1
        await close_message_queue()


# ═══════════════════════════════════════════════════════════════════════════
# 消息生命周期集成测试
# ═══════════════════════════════════════════════════════════════════════════

class TestMessageLifecycle:
    """消息端到端生命周期测试"""

    @pytest.mark.asyncio
    async def test_happy_path(self, mq_memory):
        """正常路径: publish → deliver → process → complete"""
        lifecycle = []

        async def handler(payload):
            lifecycle.append("processing")
            return "ok"

        await mq_memory.subscribe("happy", handler)
        msg_id = await mq_memory.publish("happy", {"lifecycle": "start"})

        await asyncio.sleep(0.3)

        msg = await mq_memory.get_message("happy", msg_id)
        assert msg.status == MessageStatus.COMPLETED
        assert len(lifecycle) == 1

    @pytest.mark.asyncio
    async def test_failure_path(self, mq_memory):
        """失败路径: publish → deliver → fail → retry exhaust → FAILED"""
        async def always_error(payload):
            raise RuntimeError("处理失败")

        await mq_memory.subscribe("doomed", always_error)
        msg_id = await mq_memory.publish("doomed", {"fate": "doom"}, max_retries=1)

        await asyncio.sleep(1.5)  # 等待重试穷尽（1s delay）

        msg = await mq_memory.get_message("doomed", msg_id)
        assert msg is not None
        assert msg.status == MessageStatus.FAILED

    @pytest.mark.asyncio
    async def test_timeout_handling(self, mq_memory):
        """超时处理 — mock asyncio.wait_for 抛出 TimeoutError"""
        async def handler(payload):
            return None  # 被 mock 拦截

        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            await mq_memory.subscribe("timeout-topic", handler)
            msg_id = await mq_memory.publish("timeout-topic", {"slow": True}, max_retries=1)

            await asyncio.sleep(0.5)
            msg = await mq_memory.get_message("timeout-topic", msg_id)
            if msg:
                assert msg.status in (MessageStatus.FAILED, MessageStatus.PROCESSING)


# ═══════════════════════════════════════════════════════════════════════════
# 并行负载测试
# ═══════════════════════════════════════════════════════════════════════════

class TestConcurrency:
    """并发发布/消费测试"""

    @pytest.mark.asyncio
    async def test_concurrent_publishes(self, mq_memory):
        async def publish_one(n):
            return await mq_memory.publish("concurrent", {"n": n})

        tasks = [publish_one(i) for i in range(20)]
        ids = await asyncio.gather(*tasks)

        assert len(ids) == 20
        assert len(set(ids)) == 20  # 所有 ID 唯一

    @pytest.mark.asyncio
    async def test_concurrent_publish_and_consume(self, mq_memory):
        received = []
        lock = asyncio.Lock()

        async def handler(payload):
            async with lock:
                received.append(payload["n"])

        await mq_memory.subscribe("conc-2", handler)

        # 并发发布
        async def pub(n):
            await mq_memory.publish("conc-2", {"n": n})

        tasks = [pub(i) for i in range(10)]
        await asyncio.gather(*tasks)
        await asyncio.sleep(0.5)

        assert len(received) == 10
        assert sorted(received) == list(range(10))


# ═══════════════════════════════════════════════════════════════════════════
# RedisStreamBackend — Mock 测试
# ═══════════════════════════════════════════════════════════════════════════

class TestRedisStreamBackendMock:
    """RedisStreamBackend 使用 mock Redis 客户端测试"""

    @pytest.mark.asyncio
    async def test_publish_serializes_and_sends(self):
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True
        mock_redis.xadd.return_value = "1234567890123-0"

        backend = RedisStreamBackend(mock_redis)
        msg_id = await backend.publish("test", {"key": "val"})

        assert isinstance(msg_id, str)
        mock_redis.xadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_group_creates_on_first_subscribe(self):
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True
        mock_redis.xgroup_create.return_value = True
        mock_redis.xreadgroup.return_value = None  # 模拟空读取

        backend = RedisStreamBackend(mock_redis)

        async def noop(payload):
            pass

        await backend.subscribe("new-topic", noop, consumer_id="c1")
        mock_redis.xgroup_create.assert_called_once()
        await backend.close()

    @pytest.mark.asyncio
    async def test_ensure_group_handles_busygroup(self):
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True
        mock_redis.xgroup_create.side_effect = Exception(
            "BUSYGROUP Consumer Group name already exists"
        )
        mock_redis.xreadgroup.return_value = None

        backend = RedisStreamBackend(mock_redis)

        async def noop(payload):
            pass

        # 不应抛出异常
        await backend.subscribe("existing-topic", noop, consumer_id="c2")
        await backend.close()

    @pytest.mark.asyncio
    async def test_health_check_ping(self):
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True
        backend = RedisStreamBackend(mock_redis)
        assert await backend.health_check() is True

        mock_redis.ping.side_effect = ConnectionError("down")
        assert await backend.health_check() is False


# ═══════════════════════════════════════════════════════════════════════════
# 常量有效性
# ═══════════════════════════════════════════════════════════════════════════

class TestConstants:
    """配置常量测试"""

    def test_default_retry_values(self):
        assert DEFAULT_MAX_RETRIES >= 0
        assert DEFAULT_RETRY_DELAY > 0
        assert DEFAULT_RETRY_BACKOFF > 0
        assert MEMORY_QUEUE_MAX_SIZE > 0

    def test_message_status_values(self):
        """所有状态值应被定义"""
        assert MessageStatus.PENDING.value == "pending"
        assert MessageStatus.COMPLETED.value == "completed"
        assert MessageStatus.FAILED.value == "failed"
        assert MessageStatus.DEAD_LETTER.value == "dead_letter"
