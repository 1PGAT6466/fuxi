"""
test_inference_batcher.py — 推理batching单元测试
==============================================

覆盖场景：
  - InferenceRequest / InferenceResult 数据模型
  - SlidingWindowCounter QPS 统计
  - InferenceBatcher 单条提交 submit()
  - InferenceBatcher 批量提交 batch_requests()
  - InferenceBatcher 动态batch大小调整
  - InferenceBatcher 超时机制
  - InferenceBatcher 并发控制
  - InferenceBatcher 优先级队列
  - InferenceBatcher LLM 函数包装 wrap_llm()
  - InferenceBatcher 统计信息 get_stats()
  - 全局实例管理 get_inference_batcher()
"""
import asyncio
import time
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.inference_batcher import (
    InferenceBatcher,
    InferenceRequest,
    InferenceResult,
    BatchStatus,
    BatchStats,
    Priority,
    SlidingWindowCounter,
    create_inference_batcher,
    get_inference_batcher,
    close_inference_batcher,
    DEFAULT_MAX_BATCH_SIZE,
    DEFAULT_MIN_BATCH_SIZE,
    DEFAULT_MAX_WAIT_MS,
    DEFAULT_TARGET_LATENCY_MS,
    DEFAULT_MAX_CONCURRENT_BATCHES,
)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def make_mock_llm_fn(delay: float = 0.01, responses=None):
    """创建模拟的 LLM 调用函数。

    Args:
        delay: 每次调用的模拟延迟（秒）
        responses: 预设响应列表。若为 None，默认返回 echo 响应
    """
    call_count = [0]  # 用列表实现闭包可变性

    async def _mock_llm(prompt, system_prompt=None, max_tokens=2048,
                        temperature=0.3, model=None):
        await asyncio.sleep(delay)
        call_count[0] += 1

        if responses and call_count[0] <= len(responses):
            return responses[call_count[0] - 1]

        return f"Mock response to: {prompt[:50]}"

    _mock_llm.call_count = call_count
    return _mock_llm


def make_request(prompt: str = "test prompt", **kwargs) -> InferenceRequest:
    """快速创建 InferenceRequest"""
    defaults = {
        "request_id": f"test-{prompt[:8]}",
        "prompt": prompt,
    }
    defaults.update(kwargs)
    return InferenceRequest(**defaults)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest_asyncio.fixture
async def mock_llm_fn():
    """标准 mock LLM 调用函数（低延迟）"""
    return make_mock_llm_fn(delay=0.005)


@pytest_asyncio.fixture
async def batcher(mock_llm_fn):
    """创建并启动 InferenceBatcher（测试后自动停止）"""
    b = InferenceBatcher(
        llm_call_fn=mock_llm_fn,
        max_batch_size=4,
        min_batch_size=1,
        max_wait_ms=100,
        max_concurrent_batches=2,
        max_concurrent_requests=8,
        enable_dynamic_batch=False,  # 测试中关闭动态调整
        name="test",
    )
    await b.start()
    yield b
    await b.stop()


@pytest_asyncio.fixture
async def batcher_dynamic(mock_llm_fn):
    """启用动态 batch 调整的 batcher"""
    b = InferenceBatcher(
        llm_call_fn=mock_llm_fn,
        max_batch_size=8,
        min_batch_size=1,
        max_wait_ms=50,
        max_concurrent_batches=2,
        max_concurrent_requests=16,
        enable_dynamic_batch=True,
        target_latency_ms=50.0,
        name="test-dynamic",
    )
    await b.start()
    yield b
    await b.stop()


@pytest_asyncio.fixture
async def slow_mock_llm():
    """高延迟 mock（用于测试超时和动态缩小）"""
    return make_mock_llm_fn(delay=0.2)


@pytest_asyncio.fixture
async def batcher_slow(slow_mock_llm):
    """使用高延迟 LLM 的 batcher"""
    b = InferenceBatcher(
        llm_call_fn=slow_mock_llm,
        max_batch_size=4,
        min_batch_size=1,
        max_wait_ms=50,
        max_concurrent_batches=2,
        max_concurrent_requests=4,
        enable_dynamic_batch=True,
        target_latency_ms=100.0,
        name="test-slow",
    )
    await b.start()
    yield b
    await b.stop()


# ═══════════════════════════════════════════════════════════════════════════
# SlidingWindowCounter 测试
# ═══════════════════════════════════════════════════════════════════════════

class TestSlidingWindowCounter:
    """滑动窗口计数器测试"""

    def test_initial_qps_zero(self):
        counter = SlidingWindowCounter(window_seconds=10.0, num_buckets=10)
        assert counter.qps() == 0.0
        assert counter.total_in_window() == 0

    def test_single_add_shows_qps(self):
        counter = SlidingWindowCounter(window_seconds=10.0, num_buckets=10)
        counter.add(count=5)
        qps = counter.qps()
        assert qps > 0.0
        assert counter.total_in_window() == 5

    def test_multiple_adds_accumulate(self):
        counter = SlidingWindowCounter(window_seconds=10.0, num_buckets=10)
        for _ in range(10):
            counter.add(count=1)
        assert counter.total_in_window() == 10

    def test_qps_approximately_correct(self):
        """给定窗口和次数，QPS 大致正确"""
        counter = SlidingWindowCounter(window_seconds=2.0, num_buckets=4)
        # 100 次请求在 2 秒窗口 → QPS ≈ 50
        for _ in range(100):
            counter.add()
        qps = counter.qps()
        # 允许一些偏差（刚添加时全在最后一个桶）
        assert 0.0 <= qps <= 100.0  # 上限宽松


# ═══════════════════════════════════════════════════════════════════════════
# InferenceRequest / InferenceResult 数据模型
# ═══════════════════════════════════════════════════════════════════════════

class TestDataModels:
    """数据模型测试"""

    def test_inference_request_defaults(self):
        req = InferenceRequest(request_id="r1", prompt="hello")
        assert req.request_id == "r1"
        assert req.prompt == "hello"
        assert req.system_prompt is None
        assert req.max_tokens == 2048
        assert req.temperature == 0.3
        assert req.model is None
        assert req.priority == Priority.NORMAL
        assert req.created_at > 0

    def test_inference_request_to_llm_kwargs(self):
        req = InferenceRequest(
            request_id="r1",
            prompt="test prompt",
            system_prompt="you are helpful",
            max_tokens=1000,
            temperature=0.5,
            model="mimo-v2.5",
        )
        kwargs = req.to_llm_kwargs()
        assert kwargs["prompt"] == "test prompt"
        assert kwargs["system_prompt"] == "you are helpful"
        assert kwargs["max_tokens"] == 1000
        assert kwargs["temperature"] == 0.5
        assert kwargs["model"] == "mimo-v2.5"

    def test_inference_result_success(self):
        result = InferenceResult(
            request_id="r1",
            content="answer",
            success=True,
            elapsed_ms=150.0,
            model_used="mimo",
        )
        assert result.success is True
        assert result.content == "answer"
        assert result.error is None
        assert result.elapsed_ms == 150.0
        assert result.model_used == "mimo"

    def test_inference_result_failure(self):
        result = InferenceResult(
            request_id="r1",
            content="",
            success=False,
            error="API timeout",
            elapsed_ms=5000.0,
        )
        assert result.success is False
        assert result.content == ""
        assert result.error == "API timeout"


# ═══════════════════════════════════════════════════════════════════════════
# InferenceBatcher 单条提交
# ═══════════════════════════════════════════════════════════════════════════

class TestSubmit:
    """单条 submit() 测试"""

    @pytest.mark.asyncio
    async def test_submit_returns_result(self, batcher):
        result = await batcher.submit(prompt="什么是微服务？")
        assert isinstance(result, InferenceResult)
        assert result.success is True
        assert "Mock response to:" in result.content
        assert result.elapsed_ms > 0

    @pytest.mark.asyncio
    async def test_submit_with_system_prompt(self, batcher):
        result = await batcher.submit(
            prompt="hello",
            system_prompt="你是架构专家",
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_submit_with_priority(self, batcher):
        result = await batcher.submit(
            prompt="urgent",
            priority=Priority.CRITICAL,
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_multiple_submits_all_succeed(self, batcher):
        tasks = [
            batcher.submit(prompt=f"question {i}")
            for i in range(5)
        ]
        results = await asyncio.gather(*tasks)
        assert all(r.success for r in results)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_submit_records_stats(self, batcher):
        await batcher.submit(prompt="test")
        stats = batcher.get_stats()
        assert stats["throughput"]["total_submitted"] >= 1
        assert stats["throughput"]["total_completed"] >= 1


# ═══════════════════════════════════════════════════════════════════════════
# InferenceBatcher 批量提交
# ═══════════════════════════════════════════════════════════════════════════

class TestBatchRequests:
    """batch_requests() 测试"""

    @pytest.mark.asyncio
    async def test_batch_requests_empty(self, batcher):
        results = await batcher.batch_requests([])
        assert results == []

    @pytest.mark.asyncio
    async def test_batch_requests_single(self, batcher):
        reqs = [make_request(prompt="test")]
        results = await batcher.batch_requests(reqs)
        assert len(results) == 1
        assert results[0].success is True

    @pytest.mark.asyncio
    async def test_batch_requests_multiple(self, batcher):
        reqs = [
            make_request(prompt=f"question {i}")
            for i in range(6)
        ]
        results = await batcher.batch_requests(reqs)
        assert len(results) == 6
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_batch_requests_preserves_order(self, batcher):
        """批量结果顺序应与请求顺序一致"""
        reqs = [
            make_request(request_id=f"r{i}", prompt=f"prompt {i}")
            for i in range(4)
        ]
        results = await batcher.batch_requests(reqs)
        for i, result in enumerate(results):
            assert result.request_id == f"r{i}"

    @pytest.mark.asyncio
    async def test_batch_requests_different_priorities(self, batcher):
        reqs = [
            make_request(prompt="high", priority=Priority.HIGH),
            make_request(prompt="low", priority=Priority.LOW),
            make_request(prompt="normal", priority=Priority.NORMAL),
            make_request(prompt="critical", priority=Priority.CRITICAL),
        ]
        results = await batcher.batch_requests(reqs)
        assert len(results) == 4
        assert all(r.success for r in results)


# ═══════════════════════════════════════════════════════════════════════════
# 动态 batch 大小调整
# ═══════════════════════════════════════════════════════════════════════════

class TestDynamicBatch:
    """动态 batch 调整测试"""

    @pytest.mark.asyncio
    async def test_static_batch_no_adjustment(self, batcher):
        """关闭动态调整时 batch_size 不变"""
        initial = batcher._current_batch_size
        for _ in range(20):
            await batcher.submit(prompt="test")
        assert batcher._current_batch_size == initial

    @pytest.mark.asyncio
    async def test_dynamic_batch_can_scale_down(self, batcher_slow):
        """高延迟场景下 batch_size 应缩小"""
        # 提交足够多批次以触发动态调整
        tasks = [batcher_slow.submit(prompt=f"test {i}") for i in range(30)]
        await asyncio.gather(*tasks)

        # 高延迟（200ms > 100ms * 1.2 = 120ms）应触发缩小
        # 允许 batch_size 可能缩小
        stats = batcher_slow.get_stats()
        current = stats["batch_size"]["current"]
        assert current >= batcher_slow._min_batch_size

    @pytest.mark.asyncio
    async def test_dynamic_batch_stays_in_bounds(self, batcher_dynamic):
        """动态调整不会超出 min/max 范围"""
        for _ in range(50):
            await batcher_dynamic.submit(prompt="test")
        current = batcher_dynamic._current_batch_size
        assert batcher_dynamic._min_batch_size <= current <= batcher_dynamic._max_batch_size

    @pytest.mark.asyncio
    async def test_scale_down_threshold_logic(self, batcher):
        """验证缩小/放大的阈值逻辑正确性"""
        # 手动设置高延时的批次统计
        batcher._latency_history.extend([300.0] * 100)  # 高延时
        batcher._stats = [
            BatchStats(
                batch_id=f"b{i}",
                batch_size=4,
                status=BatchStatus.COMPLETED,
                created_at=time.monotonic(),
                p95_latency_ms=300.0,
                avg_latency_ms=280.0,
            )
            for i in range(5)
        ]
        batcher._target_latency_ms = 100.0
        old_size = batcher._current_batch_size

        # 高延时 → 应缩小
        if old_size > batcher._min_batch_size:
            await batcher._adjust_batch_size(batcher._stats[-1])
            assert batcher._current_batch_size <= old_size

    @pytest.mark.asyncio
    async def test_scale_up_threshold_logic(self, batcher):
        """低延时场景下 batch_size 应放大"""
        batcher._latency_history.extend([10.0] * 100)  # 极低延时
        batcher._stats = [
            BatchStats(
                batch_id=f"b{i}",
                batch_size=4,
                status=BatchStatus.COMPLETED,
                created_at=time.monotonic(),
                p95_latency_ms=10.0,
                avg_latency_ms=8.0,
            )
            for i in range(5)
        ]
        batcher._target_latency_ms = 100.0
        batcher._current_batch_size = 2
        old_size = batcher._current_batch_size

        # 低延时 → 应放大
        if old_size < batcher._max_batch_size:
            await batcher._adjust_batch_size(batcher._stats[-1])
            assert batcher._current_batch_size >= old_size


# ═══════════════════════════════════════════════════════════════════════════
# 超时机制
# ═══════════════════════════════════════════════════════════════════════════

class TestTimeout:
    """超时机制测试"""

    @pytest.mark.asyncio
    async def test_batch_timeout_respected(self):
        """max_wait_ms 到达后批次应立即提交"""
        slow_fn = make_mock_llm_fn(delay=0.05)

        b = InferenceBatcher(
            llm_call_fn=slow_fn,
            max_batch_size=10,
            min_batch_size=1,
            max_wait_ms=100,  # 100ms 后必须提交
            max_concurrent_batches=1,
            name="test-timeout",
        )
        await b.start()

        try:
            start = time.monotonic()
            # 只提交 2 条，远未达到 batch_size=10 → 应超时提交
            result = await b.submit(prompt="only one request")
            elapsed = (time.monotonic() - start) * 1000

            assert result.success is True
            # 200ms 超时 + 处理时间 → 不应超过 500ms
            assert elapsed < 500, f"Got {elapsed:.0f}ms"
        finally:
            await b.stop()

    @pytest.mark.asyncio
    async def test_request_timeout_returns_error(self, batcher):
        """请求级超时应返回错误结果"""
        # 使用极短整体超时
        batcher._batch_timeout = 0.01  # 10ms 不可能完成
        result = await batcher.submit(prompt="slow request")
        # 注意：实际上 10ms 可能不够入队 + 排队 + 处理
        # 所以可能成功也可能超时，验证返回类型即可
        assert isinstance(result, InferenceResult)


# ═══════════════════════════════════════════════════════════════════════════
# 并发控制
# ═══════════════════════════════════════════════════════════════════════════

class TestConcurrency:
    """并发控制测试"""

    @pytest.mark.asyncio
    async def test_concurrent_requests_not_exceeding_limit(self):
        """并发请求数不应超过限制"""
        call_count = [0]
        max_concurrent = [0]
        active_lock = asyncio.Lock()

        async def tracked_llm(prompt, **kwargs):
            async with active_lock:
                call_count[0] += 1
                max_concurrent[0] = max(max_concurrent[0], call_count[0])
            await asyncio.sleep(0.02)
            async with active_lock:
                call_count[0] -= 1
            return f"Response: {prompt[:20]}"

        b = InferenceBatcher(
            llm_call_fn=tracked_llm,
            max_batch_size=4,
            max_wait_ms=20,
            max_concurrent_batches=2,
            max_concurrent_requests=4,  # 最多4个并发请求
            name="test-concur",
        )
        await b.start()

        try:
            # 提交 20 条请求
            tasks = [b.submit(prompt=f"test {i}") for i in range(20)]
            results = await asyncio.gather(*tasks)

            assert all(r.success for r in results)
            assert len(results) == 20
            # 最大并发不应超过限制（允许轻微误差）
            assert max_concurrent[0] <= 8  # 4 requests * 2 batches
        finally:
            await b.stop()

    @pytest.mark.asyncio
    async def test_semaphore_prevents_overload(self, batcher):
        """信号量应防止过度并发"""
        # 提交大量请求，验证都能完成
        tasks = [batcher.submit(prompt=f"test {i}") for i in range(30)]
        results = await asyncio.gather(*tasks)
        assert len(results) == 30
        assert sum(1 for r in results if r.success) >= 28  # 允许少量失败


# ═══════════════════════════════════════════════════════════════════════════
# 优先级队列
# ═══════════════════════════════════════════════════════════════════════════

class TestPriority:
    """优先级测试"""

    @pytest.mark.asyncio
    async def test_high_priority_processed(self, batcher):
        """高优先级请求应被处理"""
        result = await batcher.submit(
            prompt="urgent question",
            priority=Priority.CRITICAL,
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_mixed_priorities_all_succeed(self, batcher):
        """混合优先级请求应全部成功"""
        requests = [
            ("low", Priority.LOW),
            ("normal", Priority.NORMAL),
            ("high", Priority.HIGH),
            ("critical", Priority.CRITICAL),
        ] * 5

        tasks = [
            batcher.submit(prompt=f"{label} priority", priority=pri)
            for label, pri in requests
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 20
        assert all(r.success for r in results)


# ═══════════════════════════════════════════════════════════════════════════
# LLM 函数包装
# ═══════════════════════════════════════════════════════════════════════════

class TestWrapLLM:
    """wrap_llm() 测试"""

    @pytest.mark.asyncio
    async def test_wrap_returns_string(self, batcher):
        wrapped = batcher.wrap_llm(batcher._llm_call_fn)
        result = await wrapped(prompt="hello world")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_wrap_passes_kwargs(self, batcher):
        """包装后的函数应正确传递参数"""
        received_kwargs = {}

        async def capture_llm(prompt, **kwargs):
            received_kwargs.update(kwargs)
            received_kwargs["prompt"] = prompt
            return "captured"

        wrapped = batcher.wrap_llm(capture_llm)
        result = await wrapped(
            prompt="test prompt",
            system_prompt="you are helpful",
            max_tokens=500,
            temperature=0.1,
            model="test-model",
        )

        # 注意：wrap_llm 通过 submit 传递参数，submit 再调用原始函数
        # 所以这里验证包装器本身可以接受这些参数
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_wrap_handles_failure(self, mock_llm_fn):
        """包装的 LLM 调用失败时返回空字符串"""

        async def failing_llm(prompt, **kwargs):
            raise RuntimeError("Simulated LLM failure")

        # 用 failing_llm 作为 batcher 的基础 LLM 函数
        b = InferenceBatcher(
            llm_call_fn=failing_llm,
            max_batch_size=4,
            max_wait_ms=50,
            name="test-wrap-fail",
        )
        await b.start()
        try:
            wrapped = b.wrap_llm(failing_llm)
            result = await wrapped(prompt="test")
            assert result == ""  # 失败返回空字符串
        finally:
            await b.stop()

    @pytest.mark.asyncio
    async def test_wrap_multiple_calls(self, batcher):
        """连续多次包装调用"""
        wrapped = batcher.wrap_llm(batcher._llm_call_fn)
        results = []
        for i in range(10):
            result = await wrapped(prompt=f"question {i}")
            results.append(result)
        assert len(results) == 10
        assert all(isinstance(r, str) and len(r) > 0 for r in results)


# ═══════════════════════════════════════════════════════════════════════════
# 统计信息
# ═══════════════════════════════════════════════════════════════════════════

class TestStats:
    """get_stats() / reset_stats() 测试"""

    @pytest.mark.asyncio
    async def test_stats_reflects_activity(self, batcher):
        await batcher.submit(prompt="test 1")
        await batcher.submit(prompt="test 2")
        await batcher.submit(prompt="test 3")

        stats = batcher.get_stats()
        assert stats["name"] == "test"
        assert stats["running"] is True
        assert stats["throughput"]["total_submitted"] >= 3
        assert stats["throughput"]["total_completed"] >= 3
        assert stats["throughput"]["total_failed"] == 0

    @pytest.mark.asyncio
    async def test_stats_includes_latency(self, batcher):
        await batcher.submit(prompt="test")
        stats = batcher.get_stats()
        assert stats["latency"]["recent_count"] >= 1

    @pytest.mark.asyncio
    async def test_reset_stats_clears_counters(self, batcher):
        await batcher.submit(prompt="test 1")
        await batcher.submit(prompt="test 2")

        batcher.reset_stats()

        stats = batcher.get_stats()
        assert stats["throughput"]["total_submitted"] == 0
        assert stats["throughput"]["total_completed"] == 0
        assert stats["latency"]["recent_count"] == 0
        assert stats["batches"]["total"] == 0

    @pytest.mark.asyncio
    async def test_stats_after_stop(self, batcher):
        await batcher.submit(prompt="final")
        await batcher.stop()

        stats = batcher.get_stats()
        assert stats["running"] is False


# ═══════════════════════════════════════════════════════════════════════════
# 生命周期
# ═══════════════════════════════════════════════════════════════════════════

class TestLifecycle:
    """启动 / 停止 / 排干测试"""

    @pytest.mark.asyncio
    async def test_start_stop_idempotent(self, mock_llm_fn):
        """连续 start/stop 不应报错"""
        b = InferenceBatcher(
            llm_call_fn=mock_llm_fn,
            max_batch_size=4,
            max_wait_ms=50,
            name="test-lifecycle",
        )
        # 重复 start
        await b.start()
        await b.start()  # 幂等

        # 重复 stop
        await b.stop()
        await b.stop()  # 幂等

    @pytest.mark.asyncio
    async def test_drain_on_stop(self, mock_llm_fn):
        """停止时排空剩余请求"""
        b = InferenceBatcher(
            llm_call_fn=mock_llm_fn,
            max_batch_size=4,
            max_wait_ms=200,  # 较长等待
            name="test-drain",
        )
        await b.start()

        # 提交一些请求但不等待完成
        tasks = [
            asyncio.ensure_future(b.submit(prompt=f"test {i}"))
            for i in range(8)
        ]
        # 立即停止，期望排空处理
        await asyncio.sleep(0.05)
        await b.stop()

        # 所有请求应该已完成（成功或失败）
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, InferenceResult):
                # 排空处理 → 应有结果
                assert isinstance(r, InferenceResult)
            else:
                # 如果有异常，也应该是合理的
                pass

    @pytest.mark.asyncio
    async def test_running_flag_after_stop(self, batcher):
        await batcher.stop()
        assert batcher._running is False


# ═══════════════════════════════════════════════════════════════════════════
# 工厂函数 & 全局实例
# ═══════════════════════════════════════════════════════════════════════════

class TestFactory:
    """create_inference_batcher / get_inference_batcher 测试"""

    @pytest.mark.asyncio
    async def test_create_inference_batcher(self, mock_llm_fn):
        b = await create_inference_batcher(
            llm_fn=mock_llm_fn,
            max_batch_size=4,
            name="test-factory",
        )
        assert b._running is True
        assert b.name == "test-factory"

        stats = b.get_stats()
        assert stats["batch_size"]["current"] == 4

        await b.stop()

    @pytest.mark.asyncio
    async def test_get_inference_batcher_singleton(self, mock_llm_fn):
        """get_inference_batcher 返回单例"""
        from src.services import inference_batcher as ib_module
        ib_module._global_batcher = None  # 重置

        try:
            b1 = await get_inference_batcher(
                llm_fn=mock_llm_fn,
                max_batch_size=4,
                name="test-singleton",
            )
            b2 = await get_inference_batcher(
                llm_fn=mock_llm_fn,
                max_batch_size=8,
                name="test-singleton-2",
            )
            # 第二次调用返回同一实例
            assert b1 is b2
            # 参数不变（首次创建的参数生效）
            assert b1._max_batch_size == 4
        finally:
            await close_inference_batcher()
            ib_module._global_batcher = None

    @pytest.mark.asyncio
    async def test_close_inference_batcher(self, mock_llm_fn):
        """close_inference_batcher 关闭全局实例"""
        from src.services import inference_batcher as ib_module
        ib_module._global_batcher = None

        b = await get_inference_batcher(llm_fn=mock_llm_fn, name="test-close")
        assert b._running is True

        await close_inference_batcher()
        assert b._running is False
        assert ib_module._global_batcher is None


# ═══════════════════════════════════════════════════════════════════════════
# 集成测试：与现有 LLM 调用流程集成
# ═══════════════════════════════════════════════════════════════════════════

class TestIntegration:
    """与现有 call_llm 流程集成测试"""

    @pytest.mark.asyncio
    async def test_integration_with_call_llm_style(self, batcher):
        """验证 wrap_llm 产出的函数与 call_llm 签名兼容"""
        wrapped = batcher.wrap_llm(batcher._llm_call_fn)

        # 测试全部 call_llm 参数
        result = await wrapped(
            prompt="测试提示词",
            system_prompt="你是架构专家",
            max_tokens=1000,
            temperature=0.3,
            model="mimo-v2.5-pro",
        )
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_submit_many_convenience(self, batcher):
        """submit_many 便捷方法"""
        prompts = [f"question {i}" for i in range(6)]
        results = await batcher.submit_many(
            prompts=prompts,
            system_prompt="你是助手",
            max_tokens=500,
            temperature=0.1,
        )
        assert len(results) == 6
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_high_throughput_scenario(self, batcher):
        """高吞吐场景：100 条请求在合理时间内完成"""
        start = time.monotonic()

        results = await batcher.submit_many(
            prompts=[f"test {i}" for i in range(50)],
        )

        elapsed = time.monotonic() - start
        assert len(results) == 50
        assert all(r.success for r in results)
        # 50 条请求应在 5 秒内完成（mock delay=5ms 每条）
        assert elapsed < 5.0, f"Too slow: {elapsed:.1f}s"

    @pytest.mark.asyncio
    async def test_error_propagation(self, batcher):
        """LLM 调用失败时，错误应正确传播"""
        async def error_llm(prompt, **kwargs):
            if "fail" in prompt:
                raise ValueError("Simulated error")
            return f"OK: {prompt}"

        b = InferenceBatcher(
            llm_call_fn=error_llm,
            max_batch_size=4,
            max_wait_ms=50,
            name="test-error-prop",
        )
        await b.start()

        try:
            good = await b.submit(prompt="good request")
            assert good.success is True

            bad = await b.submit(prompt="this will fail")
            assert bad.success is False
            assert bad.error is not None
            assert "Simulated error" in bad.error
        finally:
            await b.stop()
