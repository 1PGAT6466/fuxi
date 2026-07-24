"""
伏羲 v1.44 — 推理batching服务（P2 增强）
=========================================

基于异步编程模式的推理请求批量处理引擎，提供：
  - batch_requests(requests) — 批量处理LLM推理请求
  - 动态batch大小调整（根据QPS和延时自适应）
  - 超时机制：最大等待时间控制
  - 并发控制：最大并发数 + 信号量保护
  - 与现有 call_llm / call_llm_fast 无缝集成

架构对齐：
  - 异步编程模式（asyncio）
  - 与 src/services/llm.py 的 Fallback 链兼容
  - 遵循 src/infra/retry.py 的指数退避风格
  - 与 src/services/message_queue.py 的统计风格一致

设计理念：
  - 使用滑动窗口统计实时QPS，动态调整 batch_size
  - 超时时间到期后立即提交当前批次，不等待填满
  - 通过 Semaphore 控制并发，防止下游 API 过载
  - 支持优先级队列：高优先请求跳过排队，直接执行
"""

import asyncio
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, TypeVar

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 类型别名
# ---------------------------------------------------------------------------
T = TypeVar("T")
LLMCallFn = Callable[..., Awaitable[str]]
BatchResultSelector = Callable[[List[Dict[str, Any]]], List[str]]

# ---------------------------------------------------------------------------
# 配置常量
# ---------------------------------------------------------------------------

# 批次控制
DEFAULT_MAX_BATCH_SIZE: int = 8       # 每批最多请求数
DEFAULT_MIN_BATCH_SIZE: int = 1       # 每批最少请求数
DEFAULT_MAX_WAIT_MS: int = 200        # 最大等待时间（毫秒）
DEFAULT_BATCH_TIMEOUT: float = 30.0   # 批次整体超时（秒）

# 动态调整
DEFAULT_TARGET_LATENCY_MS: float = 500.0  # 目标P95延迟（毫秒）
DEFAULT_SCALE_UP_THRESHOLD: float = 0.6   # 延迟 < 目标*阈值 → 放大batch
DEFAULT_SCALE_DOWN_THRESHOLD: float = 1.2 # 延迟 > 目标*阈值 → 缩小batch
DEFAULT_BATCH_SIZE_STEP: int = 1          # 每次调整步长

# 并发控制
DEFAULT_MAX_CONCURRENT_BATCHES: int = 4   # 同时最多进行中的批次
DEFAULT_MAX_CONCURRENT_REQUESTS: int = 16 # 同时最多进行中的单请求

# 滑动窗口（QPS 统计）
QPS_WINDOW_SECONDS: float = 10.0          # QPS 统计滑动窗口（秒）
QPS_WINDOW_BUCKETS: int = 20              # 窗口内的桶数

# 优先级
class Priority(int, Enum):
    """请求优先级枚举"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

class BatchStatus(str, Enum):
    """批次状态"""
    PENDING = "pending"         # 等待填充
    COLLECTING = "collecting"   # 正在收集请求
    PROCESSING = "processing"   # 正在处理
    COMPLETED = "completed"     # 处理完成
    TIMED_OUT = "timed_out"     # 超时
    FAILED = "failed"           # 处理失败


@dataclass
class InferenceRequest:
    """单条推理请求"""
    request_id: str
    prompt: str
    system_prompt: Optional[str] = None
    max_tokens: int = 2048
    temperature: float = 0.3
    model: Optional[str] = None
    priority: Priority = Priority.NORMAL
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_llm_kwargs(self) -> Dict[str, Any]:
        """转为 call_llm 兼容的 kwargs"""
        return {
            "prompt": self.prompt,
            "system_prompt": self.system_prompt,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "model": self.model,
        }


@dataclass
class InferenceResult:
    """单条推理结果"""
    request_id: str
    content: str
    success: bool
    error: Optional[str] = None
    elapsed_ms: float = 0.0
    model_used: Optional[str] = None


@dataclass
class BatchStats:
    """批次统计"""
    batch_id: str
    batch_size: int
    status: BatchStatus
    created_at: float
    submitted_at: Optional[float] = None
    completed_at: Optional[float] = None
    total_elapsed_ms: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# 滑动窗口 QPS 统计
# ---------------------------------------------------------------------------

class SlidingWindowCounter:
    """滑动窗口计数器，用于 QPS 统计。

    将时间窗口划分为多个桶（bucket），每个桶记录一段时间内的请求数。
    过期桶自动淘汰，保证内存占用可控。
    """

    def __init__(self, window_seconds: float = QPS_WINDOW_SECONDS,
                 num_buckets: int = QPS_WINDOW_BUCKETS):
        self._window_seconds = window_seconds
        self._bucket_width = window_seconds / num_buckets
        self._buckets: deque = deque(maxlen=num_buckets)
        self._timestamps: deque = deque(maxlen=num_buckets)
        # 预填充空桶
        now = time.monotonic()
        for i in range(num_buckets):
            self._buckets.append(0)
            self._timestamps.append(now - (num_buckets - i) * self._bucket_width)

    def add(self, count: int = 1) -> None:
        """添加 count 个事件到当前桶"""
        now = time.monotonic()
        self._advance(now)
        self._buckets[-1] += count

    def qps(self) -> float:
        """获取当前 QPS（每秒请求数）"""
        now = time.monotonic()
        self._advance(now)
        total = sum(self._buckets)
        # 只统计窗口内的有效时间
        active_seconds = min(
            self._window_seconds,
            now - self._timestamps[0] if self._timestamps else self._window_seconds,
        )
        if active_seconds <= 0:
            return 0.0
        return total / active_seconds

    def total_in_window(self) -> int:
        """获取窗口内请求总数"""
        now = time.monotonic()
        self._advance(now)
        return sum(self._buckets)

    def _advance(self, now: float) -> None:
        """推进时间线，淘汰过期桶"""
        while self._timestamps and (now - self._timestamps[0]) > self._window_seconds:
            self._timestamps.popleft()
            self._buckets.popleft()

        # 补齐缺失桶
        while len(self._buckets) < self._buckets.maxlen:
            self._buckets.append(0)
            self._timestamps.append(now)
            break  # 每次只补一个桶


# ---------------------------------------------------------------------------
# InferenceBatcher — 核心类
# ---------------------------------------------------------------------------

class InferenceBatcher:
    """推理请求批量处理器。

    核心职责：
      - 收集推理请求，按批次统一提交到 LLM
      - 动态调整 batch_size 以优化吞吐和延时
      - 通过超时和并发控制保护下游 API

    Usage::

        batcher = InferenceBatcher(llm_call_fn=call_llm)
        await batcher.start()

        # 方式1：单条提交
        result = await batcher.submit(
            prompt="什么是微服务？",
            system_prompt="你是后端架构专家",
        )

        # 方式2：批量提交
        requests = [
            InferenceRequest(request_id="r1", prompt="问题1"),
            InferenceRequest(request_id="r2", prompt="问题2"),
        ]
        results = await batcher.batch_requests(requests)

        # 方式3：集成到 call_llm（通过工厂）
        batched_call_llm = batcher.wrap_llm(call_llm)
        answer = await batched_call_llm("你的提示词")

        await batcher.stop()

    Configuration::

        batcher = InferenceBatcher(
            llm_call_fn=call_llm,
            max_batch_size=8,          # 最大批次大小
            min_batch_size=1,          # 最小批次大小
            max_wait_ms=200,           # 最大等待时间（ms）
            max_concurrent_batches=4,  # 最大并发批次数
            max_concurrent_requests=16,# 最大并发请求数
            target_latency_ms=500.0,   # 目标P95延迟
            enable_dynamic_batch=True, # 启用动态batch调整
        )
    """

    def __init__(
        self,
        llm_call_fn: LLMCallFn,
        max_batch_size: int = DEFAULT_MAX_BATCH_SIZE,
        min_batch_size: int = DEFAULT_MIN_BATCH_SIZE,
        max_wait_ms: int = DEFAULT_MAX_WAIT_MS,
        max_concurrent_batches: int = DEFAULT_MAX_CONCURRENT_BATCHES,
        max_concurrent_requests: int = DEFAULT_MAX_CONCURRENT_REQUESTS,
        target_latency_ms: float = DEFAULT_TARGET_LATENCY_MS,
        enable_dynamic_batch: bool = True,
        batch_timeout: float = DEFAULT_BATCH_TIMEOUT,
        name: str = "default",
    ):
        # ---- 外部 LLM 调用函数 ----
        self._llm_call_fn = llm_call_fn

        # ---- 批次控制 ----
        self._max_batch_size = max_batch_size
        self._min_batch_size = min_batch_size
        self._max_wait_seconds = max_wait_ms / 1000.0
        self._batch_timeout = batch_timeout
        self._current_batch_size = max_batch_size  # 动态调整的当前值

        # ---- 并发控制 ----
        self._batch_semaphore = asyncio.Semaphore(max_concurrent_batches)
        self._request_semaphore = asyncio.Semaphore(max_concurrent_requests)

        # ---- 动态调整 ----
        self._enable_dynamic_batch = enable_dynamic_batch
        self._target_latency_ms = target_latency_ms

        # ---- 队列 & 状态 ----
        self._pending_queue: asyncio.Queue = asyncio.Queue()
        self._high_priority_queue: asyncio.Queue = asyncio.Queue()
        self._running: bool = False
        self._collector_task: Optional[asyncio.Task] = None
        self._collector_stop_event: asyncio.Event = asyncio.Event()

        # ---- 统计 ----
        self._qps_counter = SlidingWindowCounter()
        self._latency_history: deque = deque(maxlen=200)  # 最近200次延时
        self._stats: List[BatchStats] = []
        self._total_submitted: int = 0
        self._total_completed: int = 0
        self._total_failed: int = 0

        # ---- 标识 ----
        self.name = name
        self._batch_counter: int = 0

    # =======================================================================
    # 生命周期
    # =======================================================================

    async def start(self) -> None:
        """启动批量处理器（开启收集循环）"""
        if self._running:
            logger.warning("[InferenceBatcher:%s] 已经在运行中", self.name)
            return
        self._running = True
        self._collector_stop_event.clear()
        self._collector_task = asyncio.ensure_future(self._batch_collector())
        logger.info(
            "[InferenceBatcher:%s] 已启动 batch_size=%d max_wait=%dms",
            self.name, self._current_batch_size, int(self._max_wait_seconds * 1000),
        )

    async def stop(self) -> None:
        """停止批量处理器（清空待处理队列）"""
        if not self._running:
            return
        self._running = False
        self._collector_stop_event.set()

        # 等待收集器停止
        if self._collector_task and not self._collector_task.done():
            self._collector_task.cancel()
            try:
                await self._collector_task
            except asyncio.CancelledError:
                pass

        # 处理队列中剩余的请求
        await self._drain_queues()

        logger.info(
            "[InferenceBatcher:%s] 已停止 提交=%d 完成=%d 失败=%d",
            self.name, self._total_submitted, self._total_completed, self._total_failed,
        )

    async def _drain_queues(self) -> None:
        """排空待处理队列，逐一处理"""
        remaining = []
        while not self._high_priority_queue.empty():
            try:
                remaining.append(self._high_priority_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        while not self._pending_queue.empty():
            try:
                remaining.append(self._pending_queue.get_nowait())
            except asyncio.QueueEmpty:
                break

        if remaining:
            logger.info(
                "[InferenceBatcher:%s] 处理剩余 %d 条请求", self.name, len(remaining),
            )
            # 按优先级分批处理
            remaining.sort(key=lambda x: -x["priority"].value)
            for i in range(0, len(remaining), self._current_batch_size):
                batch = remaining[i : i + self._current_batch_size]
                await self._execute_batch(batch)

    # =======================================================================
    # 批量提交入口
    # =======================================================================

    async def submit(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.3,
        model: Optional[str] = None,
        priority: Priority = Priority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> InferenceResult:
        """提交单条推理请求，等待结果返回。

        Args:
            prompt:       提示词
            system_prompt: 系统提示词（可选）
            max_tokens:   最大 token 数
            temperature:  采样温度
            model:        指定模型（可选，使用默认模型）
            priority:     优先级
            metadata:     附加元数据

        Returns:
            InferenceResult — 推理结果
        """
        request = InferenceRequest(
            request_id=uuid.uuid4().hex[:12],
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            model=model,
            priority=priority,
            metadata=metadata or {},
        )
        return await self._enqueue_and_wait(request)

    async def batch_requests(
        self,
        requests: List[InferenceRequest],
    ) -> List[InferenceResult]:
        """批量提交多条推理请求。

        这是面向外部的主要接口，对应任务要求的 batch_requests 方法。

        Args:
            requests: InferenceRequest 列表

        Returns:
            与 requests 顺序一致的结果列表
        """
        if not requests:
            return []

        # 并发入队
        tasks = [
            asyncio.ensure_future(self._enqueue_and_wait(req))
            for req in requests
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理可能的异常
        processed: List[InferenceResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append(InferenceResult(
                    request_id=requests[i].request_id,
                    content="",
                    success=False,
                    error=str(result),
                ))
            else:
                processed.append(result)

        return processed

    async def _enqueue_and_wait(self, request: InferenceRequest) -> InferenceResult:
        """将请求入队并等待结果"""
        future: asyncio.Future = asyncio.get_event_loop().create_future()

        entry = {
            "request": request,
            "future": future,
            "priority": request.priority,
            "enqueued_at": time.monotonic(),
        }

        # 高优先级走快速通道
        if request.priority >= Priority.HIGH:
            await self._high_priority_queue.put(entry)
        else:
            await self._pending_queue.put(entry)

        self._qps_counter.add()
        self._total_submitted += 1

        # 等待结果
        try:
            return await asyncio.wait_for(
                future, timeout=self._batch_timeout + 30.0,
            )
        except asyncio.TimeoutError:
            return InferenceResult(
                request_id=request.request_id,
                content="",
                success=False,
                error=f"请求超时（{self._batch_timeout + 30.0}s）",
            )

    # =======================================================================
    # 批量收集器（核心循环）
    # =======================================================================

    async def _batch_collector(self) -> None:
        """批量收集循环：收集请求 → 提交批次 → 回收结果"""
        while self._running:
            batch = []

            # ---- 阶段1：收集已到达的请求 ----
            batch = await self._collect_batch()

            if not batch:
                continue

            # ---- 阶段2：异步提交批次（不阻塞收集） ----
            asyncio.ensure_future(self._execute_batch(batch))

    async def _collect_batch(self) -> List[Dict[str, Any]]:
        """收集一个批次。

        策略：
          1. 先清空高优队列
          2. 从普通队列取，直到达到 batch_size 或超时
          3. 高优先级请求优先打包
        """
        batch: List[Dict[str, Any]] = []
        batch_start = time.monotonic()
        deadline = batch_start + self._max_wait_seconds

        # ---- 子阶段1：高优队列立即清空 ----
        while not self._high_priority_queue.empty() and len(batch) < self._current_batch_size:
            try:
                entry = self._high_priority_queue.get_nowait()
                batch.append(entry)
            except asyncio.QueueEmpty:
                break

        if len(batch) >= self._current_batch_size:
            return batch

        # ---- 子阶段2：等待普通队列填满或超时 ----
        while len(batch) < self._current_batch_size:
            remaining_time = deadline - time.monotonic()
            if remaining_time <= 0:
                # 超时，立即提交当前批次
                break

            try:
                entry = await asyncio.wait_for(
                    self._pending_queue.get(), timeout=remaining_time,
                )
                batch.append(entry)

                # 拿了普通请求后，再检查高优队列
                while not self._high_priority_queue.empty() and len(batch) < self._current_batch_size:
                    try:
                        high_entry = self._high_priority_queue.get_nowait()
                        batch.append(high_entry)
                    except asyncio.QueueEmpty:
                        break

            except asyncio.TimeoutError:
                # 等待超时，当前批次提交
                break

        return batch

    # =======================================================================
    # 批次执行
    # =======================================================================

    async def _execute_batch(self, batch: List[Dict[str, Any]]) -> None:
        """执行一个批次的推理请求。

        Args:
            batch: [{request, future, priority, enqueued_at}, ...]
        """
        if not batch:
            return

        self._batch_counter += 1
        batch_id = f"batch:{self.name}:{self._batch_counter:06d}"
        batch_start = time.monotonic()

        # 信号量控制并发
        async with self._batch_semaphore:
            stats = BatchStats(
                batch_id=batch_id,
                batch_size=len(batch),
                status=BatchStatus.PROCESSING,
                created_at=batch_start,
                submitted_at=time.monotonic(),
            )

            try:
                # 构建并发执行的任务
                async with self._request_semaphore:
                    tasks = []
                    for entry in batch:
                        req: InferenceRequest = entry["request"]
                        task = self._execute_single_request(req, batch_id)
                        tasks.append(asyncio.ensure_future(task))

                    # 等待所有请求完成
                    batch_results: List[InferenceResult] = await asyncio.gather(
                        *tasks, return_exceptions=True,
                    )

                # 回收结果到 Future
                latencies: List[float] = []
                for entry, result in zip(batch, batch_results):
                    if isinstance(result, Exception):
                        result = InferenceResult(
                            request_id=entry["request"].request_id,
                            content="",
                            success=False,
                            error=str(result),
                        )

                    if not entry["future"].done():
                        entry["future"].set_result(result)

                    if result.success:
                        stats.success_count += 1
                        self._total_completed += 1
                    else:
                        stats.failure_count += 1
                        self._total_failed += 1

                    latencies.append(result.elapsed_ms)

                # 更新批次统计
                batch_completed = time.monotonic()
                stats.completed_at = batch_completed
                stats.total_elapsed_ms = (batch_completed - batch_start) * 1000

                if latencies:
                    latencies_sorted = sorted(latencies)
                    stats.avg_latency_ms = sum(latencies) / len(latencies)
                    # P95 延时
                    p95_idx = int(len(latencies_sorted) * 0.95)
                    p95_idx = min(p95_idx, len(latencies_sorted) - 1)
                    stats.p95_latency_ms = latencies_sorted[p95_idx]

                    # 记录延时历史
                    self._latency_history.extend(latencies)

                stats.status = BatchStatus.COMPLETED
                self._stats.append(stats)

                # ---- 动态调整 batch_size ----
                if self._enable_dynamic_batch:
                    await self._adjust_batch_size(stats)

                logger.info(
                    "[InferenceBatcher:%s] %s size=%d ok=%d fail=%d avg=%.0fms p95=%.0fms total=%.0fms",
                    self.name, batch_id, len(batch),
                    stats.success_count, stats.failure_count,
                    stats.avg_latency_ms, stats.p95_latency_ms,
                    stats.total_elapsed_ms,
                )

            except Exception as exc:
                logger.error(
                    "[InferenceBatcher:%s] 批次执行异常 %s: %s", self.name, batch_id, exc,
                )
                stats.status = BatchStatus.FAILED
                # 通知所有等待的 Future 失败
                for entry in batch:
                    if not entry["future"].done():
                        entry["future"].set_result(InferenceResult(
                            request_id=entry["request"].request_id,
                            content="",
                            success=False,
                            error=f"批次执行失败: {exc}",
                        ))

    async def _execute_single_request(
        self,
        request: InferenceRequest,
        batch_id: str,
    ) -> InferenceResult:
        """执行单条推理请求。

        调用通过构造函数注入的 LLM 调用函数，并记录延时。

        Args:
            request: 推理请求
            batch_id: 所属批次 ID

        Returns:
            InferenceResult
        """
        req_start = time.monotonic()
        try:
            kwargs = request.to_llm_kwargs()
            content = await self._llm_call_fn(**kwargs)
            elapsed = (time.monotonic() - req_start) * 1000

            return InferenceResult(
                request_id=request.request_id,
                content=content,
                success=bool(content),
                elapsed_ms=elapsed,
                model_used=request.model,
            )
        except Exception as exc:
            elapsed = (time.monotonic() - req_start) * 1000
            logger.error(
                "[InferenceBatcher:%s] %s req=%s 失败: %s",
                self.name, batch_id, request.request_id, exc,
            )
            return InferenceResult(
                request_id=request.request_id,
                content="",
                success=False,
                error=str(exc),
                elapsed_ms=elapsed,
            )

    # =======================================================================
    # 动态 batch size 调整
    # =======================================================================

    async def _adjust_batch_size(self, recent_stats: BatchStats) -> None:
        """根据最近批次的 P95 延时，动态调整 batch_size。

        策略：
          - P95延迟 < 目标 * 0.6 → 放大 batch（吞吐有余量）
          - P95延迟 > 目标 * 1.2 → 缩小 batch（延迟过高）
          - 否则保持当前值

        基于多个批次而非单一批次的延时，避免闪烁。
        """
        # 需要至少 3 个批次的数据才能稳定调整
        if len(self._stats) < 3:
            return

        recent_batches = self._stats[-5:]  # 最近5个批次
        recent_latencies = [
            s.p95_latency_ms
            for s in recent_batches
            if s.status == BatchStatus.COMPLETED and s.p95_latency_ms > 0
        ]
        if not recent_latencies:
            return

        avg_p95 = sum(recent_latencies) / len(recent_latencies)

        old_size = self._current_batch_size

        if avg_p95 < self._target_latency_ms * DEFAULT_SCALE_UP_THRESHOLD:
            # 延时远低于目标 → 放大
            new_size = min(
                self._current_batch_size + DEFAULT_BATCH_SIZE_STEP,
                self._max_batch_size,
            )
        elif avg_p95 > self._target_latency_ms * DEFAULT_SCALE_DOWN_THRESHOLD:
            # 延时超过目标 → 缩小
            new_size = max(
                self._current_batch_size - DEFAULT_BATCH_SIZE_STEP,
                self._min_batch_size,
            )
        else:
            new_size = self._current_batch_size

        if new_size != old_size:
            self._current_batch_size = new_size
            logger.info(
                "[InferenceBatcher:%s] 动态调整 batch_size %d→%d (p95_avg=%.0fms target=%.0fms qps=%.1f)",
                self.name, old_size, new_size, avg_p95,
                self._target_latency_ms, self._qps_counter.qps(),
            )

    # =======================================================================
    # LLM 函数包装器
    # =======================================================================

    def wrap_llm(self, llm_fn: LLMCallFn) -> LLMCallFn:
        """将任意 call_llm 风格函数包装为批量版本。

        使用示例::

            from src.services.llm import call_llm
            batch_call_llm = batcher.wrap_llm(call_llm)
            answer = await batch_call_llm("你的提示词", system_prompt="...")

        Args:
            llm_fn: 原始 LLM 调用函数（签名同 call_llm）

        Returns:
            包装后的异步函数
        """

        async def _batched_call(
            prompt: str,
            system_prompt: Optional[str] = None,
            max_tokens: int = 2048,
            temperature: float = 0.3,
            model: Optional[str] = None,
            **kwargs,
        ) -> str:
            result = await self.submit(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                model=model,
            )
            if result.success:
                return result.content
            logger.warning(
                "[InferenceBatcher:%s] 包装调用失败: %s", self.name, result.error,
            )
            return ""

        return _batched_call

    # =======================================================================
    # 统计 & 监控
    # =======================================================================

    def get_stats(self) -> Dict[str, Any]:
        """获取当前统计信息"""
        return {
            "name": self.name,
            "running": self._running,
            "batch_size": {
                "current": self._current_batch_size,
                "min": self._min_batch_size,
                "max": self._max_batch_size,
                "dynamic": self._enable_dynamic_batch,
            },
            "concurrency": {
                "max_batches": self._batch_semaphore._value,
                "max_requests": self._request_semaphore._value,
            },
            "queue": {
                "pending": self._pending_queue.qsize(),
                "high_priority": self._high_priority_queue.qsize(),
            },
            "throughput": {
                "total_submitted": self._total_submitted,
                "total_completed": self._total_completed,
                "total_failed": self._total_failed,
                "qps": round(self._qps_counter.qps(), 2),
            },
            "latency": {
                "recent_avg_ms": round(
                    sum(self._latency_history) / len(self._latency_history), 1,
                ) if self._latency_history else 0.0,
                "recent_count": len(self._latency_history),
            },
            "batches": {
                "total": len(self._stats),
                "last_5": [
                    {
                        "id": s.batch_id,
                        "size": s.batch_size,
                        "status": s.status.value,
                        "avg_ms": round(s.avg_latency_ms, 1),
                        "p95_ms": round(s.p95_latency_ms, 1),
                    }
                    for s in self._stats[-5:]
                ],
            },
        }

    def reset_stats(self) -> None:
        """重置统计（保留运行状态）"""
        self._qps_counter = SlidingWindowCounter()
        self._latency_history.clear()
        self._stats.clear()
        self._total_submitted = 0
        self._total_completed = 0
        self._total_failed = 0

    # =======================================================================
    # 便捷方法
    # =======================================================================

    async def submit_many(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.3,
        priority: Priority = Priority.NORMAL,
    ) -> List[InferenceResult]:
        """快捷批量提交（统一 prompt 参数）。

        Args:
            prompts:       提示词列表
            system_prompt: 统一的系统提示词
            max_tokens:    统一的 max_tokens
            temperature:   统一的 temperature
            priority:      统一的优先级

        Returns:
            结果列表（顺序与 prompts 一致）
        """
        requests = [
            InferenceRequest(
                request_id=uuid.uuid4().hex[:12],
                prompt=p,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                priority=priority,
            )
            for p in prompts
        ]
        return await self.batch_requests(requests)


# ---------------------------------------------------------------------------
# 工厂函数
# ---------------------------------------------------------------------------

async def create_inference_batcher(
    llm_fn: Optional[LLMCallFn] = None,
    **kwargs,
) -> InferenceBatcher:
    """创建并启动 InferenceBatcher 的工厂函数。

    Args:
        llm_fn: LLM 调用函数。若为 None，自动使用 src.services.llm.call_llm
        **kwargs: 传给 InferenceBatcher 的其他参数

    Returns:
        已启动的 InferenceBatcher 实例
    """
    if llm_fn is None:
        from src.services.llm import call_llm as _default_llm
        llm_fn = _default_llm

    batcher = InferenceBatcher(llm_call_fn=llm_fn, **kwargs)
    await batcher.start()
    return batcher


# ---------------------------------------------------------------------------
# 全局实例管理
# ---------------------------------------------------------------------------

_global_batcher: Optional[InferenceBatcher] = None
_batcher_lock = asyncio.Lock()


async def get_inference_batcher(
    llm_fn: Optional[LLMCallFn] = None,
    **kwargs,
) -> InferenceBatcher:
    """获取或创建全局 InferenceBatcher 实例（单例模式）。

    Args:
        llm_fn: LLM 调用函数
        **kwargs: 传给 InferenceBatcher 的参数（仅在首次创建时生效）

    Returns:
        InferenceBatcher 实例
    """
    global _global_batcher
    if _global_batcher is not None and _global_batcher._running:
        return _global_batcher

    async with _batcher_lock:
        if _global_batcher is not None and _global_batcher._running:
            return _global_batcher
        _global_batcher = await create_inference_batcher(llm_fn=llm_fn, **kwargs)
        return _global_batcher


async def close_inference_batcher() -> None:
    """关闭全局 InferenceBatcher 实例"""
    global _global_batcher
    if _global_batcher:
        await _global_batcher.stop()
        _global_batcher = None
