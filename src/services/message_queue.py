"""
伏羲 v1.44 — 消息队列服务（P0 修复）
====================================

基于 Redis Stream 的通用消息队列，支持：
  - publish(topic, message) — 发布消息
  - subscribe(topic, handler) — 订阅消息
  - 消费者组支持
  - 消息确认机制（ACK）
  - 可配置重试逻辑
  - Redis 不可用时自动降级为内存队列

架构对齐：
  - 异步编程模式（asyncio）
  - 与 src/config.py 中的 REDIS_* 配置集成
  - 遵循 src/infra/retry.py 的指数退避风格
  - 断路器兼容（可对 Redis 连接接入 CircuitBreaker）
"""

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 默认重试配置
DEFAULT_MAX_RETRIES: int = 3
DEFAULT_RETRY_DELAY: float = 1.0  # 秒
DEFAULT_RETRY_BACKOFF: float = 2.0
# 消息处理超时（秒）— 超过则视为失败
DEFAULT_PROCESSING_TIMEOUT: float = 300.0
# 消费者组心跳间隔（秒）
DEFAULT_HEARTBEAT_INTERVAL: float = 5.0
# 消费者组 ACK 批量大小
DEFAULT_ACK_BATCH: int = 10
# 队列最大容量（内存模式）
MEMORY_QUEUE_MAX_SIZE: int = 10000
# 已处理消息保留数（内存模式，用于重试/诊断）
MEMORY_PROCESSED_RETENTION: int = 1000


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

class MessageStatus(str, Enum):
    """消息状态枚举"""
    PENDING = "pending"         # 等待交付
    DELIVERED = "delivered"     # 已投递，等待 ACK
    PROCESSING = "processing"   # 正在处理
    COMPLETED = "completed"     # 已确认完成
    FAILED = "failed"           # 处理失败（含重试穷尽）
    DEAD_LETTER = "dead_letter" # 死信（超过最大重试次数）


@dataclass
class Message:
    """单条消息"""
    message_id: str
    topic: str
    payload: Dict[str, Any]
    status: MessageStatus = MessageStatus.PENDING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    retry_count: int = 0
    max_retries: int = DEFAULT_MAX_RETRIES
    last_error: Optional[str] = None
    consumer_id: Optional[str] = None
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "topic": self.topic,
            "payload": self.payload,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "last_error": self.last_error,
            "consumer_id": self.consumer_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        data = dict(data)  # shallow copy
        data["status"] = MessageStatus(data.get("status", "pending"))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# 抽象基类
# ---------------------------------------------------------------------------

class MessageQueueBackend:
    """消息队列后端抽象接口"""

    async def publish(self, topic: str, payload: Dict[str, Any], **kwargs) -> str:
        raise NotImplementedError

    async def subscribe(
        self,
        topic: str,
        handler: Callable[[Dict[str, Any]], Awaitable[Any]],
        consumer_id: Optional[str] = None,
    ) -> None:
        raise NotImplementedError

    async def ack(self, topic: str, message_id: str) -> None:
        raise NotImplementedError

    async def nack(self, topic: str, message_id: str, error: Optional[str] = None) -> None:
        raise NotImplementedError

    async def get_message(self, topic: str, message_id: str) -> Optional[Message]:
        raise NotImplementedError

    async def health_check(self) -> bool:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Redis Stream 后端
# ---------------------------------------------------------------------------

class RedisStreamBackend(MessageQueueBackend):
    """基于 Redis Stream 的消息队列后端。

    Stream 命名：fuxi:mq:{topic}
    消费者组命名：fuxi:mq:cg:{topic}
    """

    def __init__(self, redis_client, stream_prefix: str = "fuxi:mq"):
        self._redis = redis_client
        self._stream_prefix = stream_prefix
        self._running: Dict[str, bool] = {}  # topic → running flag
        self._consumer_tasks: Dict[str, asyncio.Task] = {}

    # ---- helpers ----

    def _stream_key(self, topic: str) -> str:
        return f"{self._stream_prefix}:{topic}"

    def _group_name(self, topic: str) -> str:
        return f"{self._stream_prefix}:cg:{topic}"

    @staticmethod
    def _message_id() -> str:
        return uuid.uuid4().hex[:16]

    @staticmethod
    def _serialize(msg: Message) -> Dict[str, str]:
        """序列化消息为 Redis Stream field/value 字符串对"""
        return {
            "message_id": msg.message_id,
            "topic": msg.topic,
            "payload": json.dumps(msg.payload, ensure_ascii=False),
            "status": msg.status.value,
            "created_at": str(msg.created_at),
            "retry_count": str(msg.retry_count),
            "max_retries": str(msg.max_retries),
            "last_error": msg.last_error or "",
            "consumer_id": msg.consumer_id or "",
        }

    @staticmethod
    def _deserialize(fields: Dict[bytes, bytes]) -> Message:
        """从 Redis 返回的 bytes 字段反序列化为 Message"""

        def _decode_field(key: str) -> str:
            """Decode a Redis bytes field value to a string.
            
            Handles both str keys (before encoding) and bytes keys (as returned
            by Redis Streams). Returns empty string for missing fields.
            """
            val = fields.get(key.encode() if isinstance(key, str) else key)
            if val is None:
                return ""
            return val.decode() if isinstance(val, bytes) else str(val)

        return Message(
            message_id=_decode_field("message_id") or uuid.uuid4().hex[:16],
            topic=_decode_field("topic"),
            payload=json.loads(_decode_field("payload")) if _decode_field("payload") else {},
            status=MessageStatus(_decode_field("status")) if _decode_field("status") else MessageStatus.PENDING,
            created_at=float(_decode_field("created_at")) if _decode_field("created_at") else time.time(),
            retry_count=int(_decode_field("retry_count")) if _decode_field("retry_count") else 0,
            max_retries=int(_decode_field("max_retries")) if _decode_field("max_retries") else DEFAULT_MAX_RETRIES,
            last_error=_decode_field("last_error") or None,
            consumer_id=_decode_field("consumer_id") or None,
        )

    async def _ensure_group(self, topic: str) -> None:
        """确保消费者组存在"""
        stream_key = self._stream_key(topic)
        group_name = self._group_name(topic)
        try:
            await self._redis.xgroup_create(stream_key, group_name, id="0", mkstream=True)
            logger.info("[MQ:Redis] 消费者组 %s 已创建", group_name)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                logger.error("[MQ:Redis] 创建消费者组 %s 失败: %s", group_name, exc)
                raise

    async def _claim_pending(self, topic: str, consumer_id: str) -> None:
        """认领超时的 pending 消息（消息超时后自动转给其他消费者）"""
        stream_key = self._stream_key(topic)
        group_name = self._group_name(topic)
        try:
            # 查询 pending 消息
            pending = await self._redis.xpending(stream_key, group_name)
            if not pending or pending.get("pending", 0) == 0:
                return
            min_idle_ms = int(DEFAULT_PROCESSING_TIMEOUT * 1000)
            claimed = await self._redis.xautoclaim(
                stream_key, group_name, consumer_id,
                min_idle_time=min_idle_ms,
                count=10,
            )
            if claimed:
                logger.info("[MQ:Redis] 认领 %d 条超时消息 (topic=%s)", len(claimed), topic)
        except Exception:
            # xautoclaim may not exist in all Redis versions / drivers
            logger.debug("[MQ:Redis] xautoclaim 不可用，跳过 pending 认领")

    # ---- publish ----

    async def publish(self, topic: str, payload: Dict[str, Any],
                      max_retries: int = DEFAULT_MAX_RETRIES,
                      metadata: Optional[Dict[str, Any]] = None) -> str:
        """向指定 topic 发布消息，返回 message_id"""
        msg = Message(
            message_id=self._message_id(),
            topic=topic,
            payload=payload,
            max_retries=max_retries,
            metadata=metadata or {},
        )
        fields = self._serialize(msg)
        stream_key = self._stream_key(topic)
        try:
            await self._redis.xadd(stream_key, fields)
            logger.info("[MQ:Redis] 消息已发布 topic=%s id=%s", topic, msg.message_id)
        except Exception as exc:
            logger.error("[MQ:Redis] 发布消息失败 topic=%s: %s", topic, exc)
            raise
        return msg.message_id

    # ---- subscribe ----

    async def subscribe(
        self,
        topic: str,
        handler: Callable[[Dict[str, Any]], Awaitable[Any]],
        consumer_id: Optional[str] = None,
    ) -> None:
        """订阅 topic，使用 handler 异步处理每条消息"""
        await self._ensure_group(topic)
        consumer_id = consumer_id or f"consumer:{topic}:{uuid.uuid4().hex[:8]}"
        self._running[topic] = True
        task = asyncio.ensure_future(
            self._consume_loop(topic, handler, consumer_id)
        )
        self._consumer_tasks[topic] = task
        logger.info("[MQ:Redis] 订阅 topic=%s consumer=%s", topic, consumer_id)

    async def _consume_loop(self, topic: str, handler, consumer_id: str) -> None:
        """消费者主循环"""
        stream_key = self._stream_key(topic)
        group_name = self._group_name(topic)
        block_ms = 5000

        while self._running.get(topic, False):
            try:
                # 定期认领超时的 pending 消息
                await self._claim_pending(topic, consumer_id)

                # 读取新消息
                results = await self._redis.xreadgroup(
                    group_name,
                    consumer_id,
                    {stream_key: ">"},
                    count=DEFAULT_ACK_BATCH,
                    block=block_ms,
                )

                if results:
                    for _stream_name, messages in results:
                        for message_id, fields in messages:
                            if not self._running.get(topic, False):
                                break
                            await self._handle_message(
                                topic, message_id, fields, handler, consumer_id
                            )

            except asyncio.CancelledError:
                logger.info("[MQ:Redis] 消费循环已取消 topic=%s", topic)
                break
            except Exception as exc:
                logger.error("[MQ:Redis] 消费循环异常 topic=%s: %s", topic, exc)
                await asyncio.sleep(1)

    async def _handle_message(
        self,
        topic: str,
        message_id: bytes,
        fields: Dict[bytes, bytes],
        handler,
        consumer_id: str,
    ) -> None:
        """处理单条消息（含重试 + ACK）"""
        msg = self._deserialize(fields)
        msg.consumer_id = consumer_id

        stream_key = self._stream_key(topic)
        group_name = self._group_name(topic)

        # 重试循环
        last_exception = None
        for attempt in range(msg.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    handler(msg.payload),
                    timeout=DEFAULT_PROCESSING_TIMEOUT,
                )
                # 成功 → ACK
                msg.status = MessageStatus.COMPLETED
                await self._redis.xack(stream_key, group_name, message_id)
                logger.debug("[MQ:Redis] ACK topic=%s id=%s", topic, msg.message_id)
                return  # 成功，结束
            except asyncio.TimeoutError:
                last_exception = TimeoutError(f"处理超时 ({DEFAULT_PROCESSING_TIMEOUT}s)")
            except Exception as exc:
                last_exception = exc

            msg.retry_count = attempt + 1
            msg.last_error = str(last_exception)
            msg.updated_at = time.time()

            if attempt < msg.max_retries:
                delay = DEFAULT_RETRY_DELAY * (DEFAULT_RETRY_BACKOFF ** attempt)
                logger.warning(
                    "[MQ:Redis] 重试 %d/%d topic=%s id=%s delay=%.1fs err=%s",
                    attempt + 1, msg.max_retries, topic, msg.message_id,
                    delay, last_exception,
                )
                await asyncio.sleep(delay)
            else:
                # 重试穷尽 → NACK + 死信
                msg.status = MessageStatus.FAILED
                logger.error(
                    "[MQ:Redis] 重试穷尽 topic=%s id=%s err=%s",
                    topic, msg.message_id, last_exception,
                )
                # 记录死信（写入专用 Stream）
                await self._send_to_dead_letter(msg)
                # 确认消息（从 pending 中移除）
                try:
                    await self._redis.xack(stream_key, group_name, message_id)
                except Exception:
                    pass

    async def _send_to_dead_letter(self, msg: Message) -> None:
        """将失败消息写入死信 Stream"""
        dlq_key = f"{self._stream_prefix}:dead_letter"
        fields = self._serialize(msg)
        fields["status"] = MessageStatus.DEAD_LETTER.value
        try:
            await self._redis.xadd(dlq_key, fields, maxlen=10000)
            logger.warning("[MQ:Redis] 死信记录 id=%s topic=%s", msg.message_id, msg.topic)
        except Exception as exc:
            logger.error("[MQ:Redis] 死信写入失败: %s", exc)

    # ---- ACK / NACK ----

    async def ack(self, topic: str, message_id: str) -> None:
        """手动确认消息"""
        stream_key = self._stream_key(topic)
        group_name = self._group_name(topic)
        try:
            await self._redis.xack(stream_key, group_name, message_id)
        except Exception as exc:
            logger.error("[MQ:Redis] ACK 失败 topic=%s id=%s: %s", topic, message_id, exc)

    async def nack(self, topic: str, message_id: str, error: Optional[str] = None) -> None:
        """消极确认（标记失败但不 ACK，由其他消费者重新处理）"""
        logger.warning("[MQ:Redis] NACK topic=%s id=%s err=%s", topic, message_id, error)
        # NACK 不调用 xack，消息保持 pending 状态，将被 xautoclaim 认领

    # ---- query ----

    async def get_message(self, topic: str, message_id: str) -> Optional[Message]:
        """通过 message_id 查询消息（按 Stream ID 查找）"""
        stream_key = self._stream_key(topic)
        try:
            results = await self._redis.xrange(stream_key, min=message_id, max=message_id, count=1)
            if results:
                _, fields = results[0]
                return self._deserialize(fields)
        except Exception as exc:
            logger.error("[MQ:Redis] 查询消息失败: %s", exc)
        return None

    # ---- lifecycle ----

    async def health_check(self) -> bool:
        """检测 Redis 是否可用"""
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """停止所有消费循环"""
        for topic in list(self._running.keys()):
            self._running[topic] = False
        for topic, task in self._consumer_tasks.items():
            task.cancel()
        # gather 等待所有 task 完成
        if self._consumer_tasks:
            await asyncio.gather(*self._consumer_tasks.values(), return_exceptions=True)
        self._consumer_tasks.clear()
        self._running.clear()
        logger.info("[MQ:Redis] 所有消费者已停止")


# ---------------------------------------------------------------------------
# 内存队列后端（降级方案）
# ---------------------------------------------------------------------------

class MemoryQueueBackend(MessageQueueBackend):
    """纯内存消息队列后端。

    Redis 不可用时自动切换为此后端，保障基本消息投递能力。
    - 基于 asyncio.Queue 实现 FIFO
    - 单进程内有效（无持久化、无分布式）
    - 支持手动 ACK 和重试
    """

    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = defaultdict(lambda: asyncio.Queue(maxsize=MEMORY_QUEUE_MAX_SIZE))
        self._messages: Dict[str, Message] = {}  # message_id → Message（全局索引）
        self._pending: Dict[str, Set[str]] = defaultdict(set)  # topic → set of message_ids
        self._handlers: Dict[str, Dict[str, Callable]] = defaultdict(dict)  # topic → {consumer_id: handler}
        self._running: Dict[str, bool] = {}
        self._consumer_tasks: Dict[str, List[asyncio.Task]] = defaultdict(list)
        self._processed: deque = deque(maxlen=MEMORY_PROCESSED_RETENTION)  # 已处理消息缓存

    # ---- publish ----

    async def publish(self, topic: str, payload: Dict[str, Any],
                      max_retries: int = DEFAULT_MAX_RETRIES,
                      metadata: Optional[Dict[str, Any]] = None) -> str:
        """发布消息到内存队列"""
        msg = Message(
            message_id=uuid.uuid4().hex[:16],
            topic=topic,
            payload=payload,
            max_retries=max_retries,
            metadata=metadata or {},
        )
        self._messages[msg.message_id] = msg
        self._pending[topic].add(msg.message_id)

        queue = self._queues[topic]
        try:
            queue.put_nowait(msg)
        except asyncio.QueueFull:
            logger.warning("[MQ:Memory] 队列已满 topic=%s，丢弃最旧消息", topic)
            # 丢弃最旧消息，腾出空间
            try:
                old = queue.get_nowait()
                old_id = old.message_id
                self._pending[topic].discard(old_id)
                self._messages.pop(old_id, None)
            except asyncio.QueueEmpty:
                pass
            queue.put_nowait(msg)

        logger.info("[MQ:Memory] 消息已发布 topic=%s id=%s", topic, msg.message_id)
        return msg.message_id

    # ---- subscribe ----

    async def subscribe(
        self,
        topic: str,
        handler: Callable[[Dict[str, Any]], Awaitable[Any]],
        consumer_id: Optional[str] = None,
    ) -> None:
        """订阅 topic，新建消费者协程"""
        consumer_id = consumer_id or f"consumer:{topic}:{uuid.uuid4().hex[:8]}"
        self._handlers[topic][consumer_id] = handler
        self._running[topic] = True

        task = asyncio.ensure_future(self._consume_loop(topic, consumer_id))
        self._consumer_tasks[topic].append(task)
        logger.info("[MQ:Memory] 订阅 topic=%s consumer=%s", topic, consumer_id)

    async def _consume_loop(self, topic: str, consumer_id: str) -> None:
        """消费者主循环"""
        queue = self._queues[topic]
        handler = self._handlers[topic][consumer_id]

        while self._running.get(topic, False):
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            if msg is None:
                continue

            # 处理消息（含重试）
            await self._process_with_retry(msg, handler, topic)

    async def _process_with_retry(self, msg: Message, handler, topic: str) -> None:
        """处理消息 + 指数退避重试"""
        msg.status = MessageStatus.PROCESSING
        msg.updated_at = time.time()

        for attempt in range(msg.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    handler(msg.payload),
                    timeout=DEFAULT_PROCESSING_TIMEOUT,
                )
                # 成功
                msg.status = MessageStatus.COMPLETED
                msg.updated_at = time.time()
                self._pending[topic].discard(msg.message_id)
                self._processed.append(msg.message_id)
                logger.debug("[MQ:Memory] ACK topic=%s id=%s", topic, msg.message_id)
                return
            except asyncio.TimeoutError:
                exc = TimeoutError(f"处理超时 ({DEFAULT_PROCESSING_TIMEOUT}s)")
            except Exception as exc:
                pass

            msg.retry_count = attempt + 1
            msg.last_error = str(exc)
            msg.updated_at = time.time()

            if attempt < msg.max_retries:
                delay = DEFAULT_RETRY_DELAY * (DEFAULT_RETRY_BACKOFF ** attempt)
                logger.warning(
                    "[MQ:Memory] 重试 %d/%d topic=%s id=%s delay=%.1fs err=%s",
                    attempt + 1, msg.max_retries, topic, msg.message_id,
                    delay, exc,
                )
                await asyncio.sleep(delay)
            else:
                msg.status = MessageStatus.FAILED
                self._pending[topic].discard(msg.message_id)
                self._processed.append(msg.message_id)
                logger.error(
                    "[MQ:Memory] 重试穷尽 topic=%s id=%s err=%s",
                    topic, msg.message_id, exc,
                )

    # ---- ACK / NACK ----

    async def ack(self, topic: str, message_id: str) -> None:
        """手动确认消息"""
        self._pending[topic].discard(message_id)
        msg = self._messages.get(message_id)
        if msg:
            msg.status = MessageStatus.COMPLETED
            msg.updated_at = time.time()
            self._processed.append(message_id)
        logger.debug("[MQ:Memory] 手动 ACK topic=%s id=%s", topic, message_id)

    async def nack(self, topic: str, message_id: str, error: Optional[str] = None) -> None:
        """手动 NACK — 将消息重新放回队列"""
        msg = self._messages.get(message_id)
        if msg:
            msg.last_error = error
            msg.retry_count += 1
            msg.updated_at = time.time()
            if msg.retry_count <= msg.max_retries:
                # 重新入队
                try:
                    self._queues[topic].put_nowait(msg)
                    logger.warning(
                        "[MQ:Memory] NACK→requeue topic=%s id=%s retry=%d/%d",
                        topic, message_id, msg.retry_count, msg.max_retries,
                    )
                except asyncio.QueueFull:
                    msg.status = MessageStatus.FAILED
                    self._processed.append(message_id)
                    self._pending[topic].discard(message_id)
            else:
                msg.status = MessageStatus.FAILED
                self._processed.append(message_id)
                self._pending[topic].discard(message_id)
                logger.error("[MQ:Memory] NACK 重试穷尽 topic=%s id=%s", topic, message_id)

    # ---- query ----

    async def get_message(self, topic: str, message_id: str) -> Optional[Message]:
        """查询消息（优先活跃，其次已处理缓存）"""
        return self._messages.get(message_id)

    async def get_queue_stats(self, topic: Optional[str] = None) -> Dict[str, Any]:
        """获取队列统计信息"""
        if topic:
            return {
                "topic": topic,
                "queue_size": self._queues[topic].qsize(),
                "pending": len(self._pending.get(topic, set())),
                "consumers": len(self._handlers.get(topic, {})),
            }
        stats = {}
        for t in self._queues:
            stats[t] = {
                "queue_size": self._queues[t].qsize(),
                "pending": len(self._pending.get(t, set())),
                "consumers": len(self._handlers.get(t, {})),
            }
        return stats

    # ---- lifecycle ----

    async def health_check(self) -> bool:
        return True  # 内存模式始终可用

    async def close(self) -> None:
        """停止所有消费者"""
        for topic in list(self._running.keys()):
            self._running[topic] = False
        for tasks in self._consumer_tasks.values():
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        self._consumer_tasks.clear()
        self._running.clear()
        logger.info("[MQ:Memory] 所有消费者已停止")


# ---------------------------------------------------------------------------
# MessageQueue — 统一门面
# ---------------------------------------------------------------------------

class MessageQueue:
    """消息队列统一入口。

    自动检测 Redis 可用性：
      - Redis 可用 → RedisStreamBackend（分布式、持久化）
      - Redis 不可用 → MemoryQueueBackend（降级、内存）

    Usage::

        mq = MessageQueue()
        await mq.initialize(redis_client)

        # 发布
        msg_id = await mq.publish("file_upload", {"path": "/tmp/a.pdf"})

        # 订阅
        async def handle_upload(payload):
            print(f"处理文件: {payload['path']}")

        await mq.subscribe("file_upload", handle_upload)

        # 关闭
        await mq.close()
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._backend: Optional[MessageQueueBackend] = None
        self._ready = False
        self._backend_type: str = "unknown"
        self._subscribed_topics: Set[str] = set()

    # ---- properties ----

    @property
    def backend_type(self) -> str:
        return self._backend_type

    @property
    def is_ready(self) -> bool:
        return self._ready

    # ---- initialize ----

    async def initialize(self, redis_client=None) -> None:
        """初始化消息队列。

        Args:
            redis_client: aioredis/redis-py async 客户端实例。
                          如果为 None，直接使用内存模式。
        """
        if redis_client is not None:
            try:
                backend = RedisStreamBackend(redis_client)
                healthy = await backend.health_check()
                if healthy:
                    self._backend = backend
                    self._backend_type = "redis"
                    self._ready = True
                    logger.info("[MQ] 使用 Redis Stream 后端 (name=%s)", self.name)
                    return
            except Exception as exc:
                logger.warning("[MQ] Redis 连接失败，降级为内存队列: %s", exc)

        # 降级到内存队列
        self._backend = MemoryQueueBackend()
        self._backend_type = "memory"
        self._ready = True
        logger.info("[MQ] 使用内存队列后端 (name=%s)", self.name)

    # ---- publish ----

    async def publish(
        self,
        topic: str,
        message: Dict[str, Any],
        max_retries: int = DEFAULT_MAX_RETRIES,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """向指定 topic 发布一条消息。

        Args:
            topic:       消息主题（如 "file_upload"、"eval_run"）
            message:     消息体（任意 JSON-serializable dict）
            max_retries: 最大重试次数（默认 3）
            metadata:    可选的元数据字典

        Returns:
            消息 ID（字符串）
        """
        self._ensure_ready()
        msg_id = await self._backend.publish(
            topic, message, max_retries=max_retries, metadata=metadata
        )
        logger.debug("[MQ] publish topic=%s id=%s backend=%s", topic, msg_id, self._backend_type)
        return msg_id

    # ---- subscribe ----

    async def subscribe(
        self,
        topic: str,
        handler: Callable[[Dict[str, Any]], Awaitable[Any]],
        consumer_id: Optional[str] = None,
    ) -> None:
        """订阅 topic，注册处理函数。

        Args:
            topic:       消息主题
            handler:     异步处理函数 async def handler(payload: dict) -> Any
            consumer_id: 可选的消费者标识，用于消费者组区分
        """
        self._ensure_ready()
        await self._backend.subscribe(topic, handler, consumer_id=consumer_id)
        self._subscribed_topics.add(topic)
        logger.info("[MQ] subscribe topic=%s backend=%s", topic, self._backend_type)

    # ---- ACK / NACK ----

    async def ack(self, topic: str, message_id: str) -> None:
        """手动确认消息已处理完成。"""
        self._ensure_ready()
        await self._backend.ack(topic, message_id)

    async def nack(self, topic: str, message_id: str, error: Optional[str] = None) -> None:
        """手动拒绝消息（将重新投递给其他消费者）。"""
        self._ensure_ready()
        await self._backend.nack(topic, message_id, error)

    # ---- query ----

    async def get_message(self, topic: str, message_id: str) -> Optional[Message]:
        """查询消息状态。"""
        self._ensure_ready()
        return await self._backend.get_message(topic, message_id)

    async def health(self) -> Dict[str, Any]:
        """获取队列健康状态。"""
        if not self._ready:
            return {"status": "not_initialized", "backend": "none"}
        healthy = await self._backend.health_check()
        return {
            "status": "healthy" if healthy else "degraded",
            "backend": self._backend_type,
            "name": self.name,
            "subscribed_topics": sorted(self._subscribed_topics),
        }

    # ---- lifecycle ----

    async def close(self) -> None:
        """关闭消息队列，停止所有消费者。"""
        if self._backend:
            await self._backend.close()
        self._ready = False
        self._subscribed_topics.clear()
        logger.info("[MQ] 已关闭 (name=%s)", self.name)

    def _ensure_ready(self) -> None:
        if not self._ready:
            raise RuntimeError(
                "消息队列未初始化，请先调用 await mq.initialize(redis_client)"
            )


# ---------------------------------------------------------------------------
# 全局实例管理
# ---------------------------------------------------------------------------

# 默认全局消息队列实例（单例）
_global_message_queue: Optional[MessageQueue] = None
_lock = asyncio.Lock()


async def get_message_queue(
    redis_client=None, name: str = "default"
) -> MessageQueue:
    """获取或创建全局消息队列实例。

    幂等调用：首次调用初始化，后续返回已有实例。

    Args:
        redis_client: Redis 异步客户端实例
        name:         实例名称（用于多队列场景）

    Returns:
        MessageQueue 实例
    """
    global _global_message_queue
    if _global_message_queue is not None:
        return _global_message_queue

    async with _lock:
        if _global_message_queue is not None:
            return _global_message_queue
        mq = MessageQueue(name=name)
        # 尝试获取 Redis 客户端
        if redis_client is None:
            redis_client = await _resolve_redis_client()
        await mq.initialize(redis_client)
        _global_message_queue = mq
        return _global_message_queue


async def _resolve_redis_client():
    """从配置自动解析 Redis 客户端。"""
    try:
        from src.config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD
        import redis.asyncio as aioredis

        client = aioredis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD or None,
            socket_connect_timeout=3.0,
            socket_timeout=5.0,
            decode_responses=False,
        )
        # 快速探活
        await client.ping()
        logger.info("[MQ] 自动连接 Redis %s:%d", REDIS_HOST, REDIS_PORT)
        return client
    except Exception as exc:
        logger.warning("[MQ] 自动连接 Redis 失败: %s", exc)
        return None


async def close_message_queue() -> None:
    """关闭全局消息队列。"""
    global _global_message_queue
    if _global_message_queue:
        await _global_message_queue.close()
        _global_message_queue = None


# ---------------------------------------------------------------------------
# 便捷工具函数
# ---------------------------------------------------------------------------

async def publish_message(
    topic: str,
    message: Dict[str, Any],
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> str:
    """快捷发布消息（使用全局实例）。"""
    mq = await get_message_queue()
    return await mq.publish(topic, message, max_retries=max_retries)


async def subscribe_topic(
    topic: str,
    handler: Callable[[Dict[str, Any]], Awaitable[Any]],
    consumer_id: Optional[str] = None,
) -> None:
    """快捷订阅 topic（使用全局实例）。"""
    mq = await get_message_queue()
    await mq.subscribe(topic, handler, consumer_id=consumer_id)
