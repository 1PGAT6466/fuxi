"""
performance.py — P1 监控指标体系

提供：
1. Prometheus 指标导出（prometheus_client 可选）
2. 延迟 P50/P95/P99 统计
3. 内存趋势监控
4. 错误率统计

用法（在 FastAPI app 中挂载）:
    from src.middleware.performance import PerformanceMiddleware, setup_performance_monitoring
    app.add_middleware(PerformanceMiddleware)
    setup_performance_monitoring(app)
"""

import time
import os
import threading
from typing import Dict, List, Optional

# ── Prometheus 集成（可选依赖） ──
try:
    from prometheus_client import (
        Counter, Histogram, Gauge, generate_latest,
        CONTENT_TYPE_LATEST, CollectorRegistry,
    )
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False
    # 降级：使用内存统计
    Counter = Histogram = Gauge = None
    CollectorRegistry = None
    CONTENT_TYPE_LATEST = "text/plain"


# ── 内存统计 ──
def _get_process_memory_bytes() -> int:
    """获取当前进程内存使用（字节）"""
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss
    except ImportError:
        return -1


# ── 延迟统计（滑动窗口） ──
class LatencyTracker:
    """延迟追踪器：P50/P95/P99 计算"""
    
    def __init__(self, window_size: int = 1000):
        self._window_size = window_size
        self._latencies: List[float] = []
        self._lock = threading.Lock()
    
    def record(self, latency_ms: float):
        """记录一次延迟"""
        with self._lock:
            self._latencies.append(latency_ms)
            if len(self._latencies) > self._window_size:
                self._latencies = self._latencies[-self._window_size:]
    
    def get_percentiles(self) -> Dict[str, float]:
        """获取 P50/P95/P99"""
        with self._lock:
            if not self._latencies:
                return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "avg": 0.0, "count": 0}
            
            sorted_lat = sorted(self._latencies)
            n = len(sorted_lat)
            
            def percentile(pct: float) -> float:
                idx = int(n * pct / 100)
                idx = min(idx, n - 1)
                return sorted_lat[idx]
            
            return {
                "p50": round(percentile(50), 2),
                "p95": round(percentile(95), 2),
                "p99": round(percentile(99), 2),
                "avg": round(sum(self._latencies) / n, 2),
                "min": round(min(self._latencies), 2),
                "max": round(max(self._latencies), 2),
                "count": n,
            }
    
    def reset(self):
        """重置统计"""
        with self._lock:
            self._latencies.clear()


# ── 内存趋势监控 ──
class MemoryTracker:
    """内存趋势监控"""
    
    def __init__(self, sample_interval: int = 30, max_samples: int = 120):
        self._sample_interval = sample_interval
        self._max_samples = max_samples
        self._samples: List[Dict] = []  # [{timestamp, memory_mb}]
        self._lock = threading.Lock()
        self._start_time = time.time()
        self._total_samples = 0
    
    def sample(self):
        """采集一次内存样本"""
        mem_bytes = _get_process_memory_bytes()
        mem_mb = mem_bytes / (1024 * 1024) if mem_bytes > 0 else -1.0
        
        sample = {
            "timestamp": time.time(),
            "memory_mb": round(mem_mb, 2),
        }
        
        with self._lock:
            self._samples.append(sample)
            self._total_samples += 1
            if len(self._samples) > self._max_samples:
                self._samples = self._samples[-self._max_samples:]
    
    def get_stats(self) -> Dict:
        """获取内存统计"""
        with self._lock:
            if not self._samples:
                current_mb = _get_process_memory_bytes() / (1024 * 1024)
                return {
                    "current_mb": round(current_mb, 2) if current_mb > 0 else -1,
                    "samples": [],
                    "trend": "unknown",
                }
            
            mem_values = [s["memory_mb"] for s in self._samples if s["memory_mb"] > 0]
            
            if not mem_values:
                return {"current_mb": -1, "samples": [], "trend": "unknown"}
            
            # 计算趋势：比较最近5个和之前5个的均值
            half = len(mem_values) // 2
            if half >= 5:
                recent_avg = sum(mem_values[-5:]) / 5
                older_avg = sum(mem_values[:5]) / 5
                if recent_avg > older_avg * 1.1:
                    trend = "increasing"
                elif recent_avg < older_avg * 0.9:
                    trend = "decreasing"
                else:
                    trend = "stable"
            else:
                trend = "insufficient_data"
            
            return {
                "current_mb": mem_values[-1],
                "avg_mb": round(sum(mem_values) / len(mem_values), 2),
                "min_mb": round(min(mem_values), 2),
                "max_mb": round(max(mem_values), 2),
                "sample_count": len(self._samples),
                "total_samples": self._total_samples,
                "trend": trend,
                "uptime_seconds": round(time.time() - self._start_time, 1),
            }


# ── 错误率统计 ──
class ErrorRateTracker:
    """错误率统计"""
    
    def __init__(self, window_seconds: int = 300):
        self._window_seconds = window_seconds
        self._successes: List[float] = []  # timestamps
        self._failures: List[float] = []   # timestamps
        self._lock = threading.Lock()
    
    def _cleanup(self):
        """清理过期记录"""
        cutoff = time.time() - self._window_seconds
        self._successes = [t for t in self._successes if t > cutoff]
        self._failures = [t for t in self._failures if t > cutoff]
    
    def record_success(self):
        """记录成功"""
        with self._lock:
            self._successes.append(time.time())
    
    def record_failure(self):
        """记录失败"""
        with self._lock:
            self._failures.append(time.time())
    
    def get_stats(self) -> Dict:
        """获取错误率统计"""
        with self._lock:
            self._cleanup()
            total = len(self._successes) + len(self._failures)
            if total == 0:
                return {
                    "error_rate": 0.0,
                    "total_requests": 0,
                    "successes": 0,
                    "failures": 0,
                    "window_seconds": self._window_seconds,
                }
            return {
                "error_rate": round(len(self._failures) / total * 100, 2),
                "total_requests": total,
                "successes": len(self._successes),
                "failures": len(self._failures),
                "window_seconds": self._window_seconds,
            }
    
    def reset(self):
        """重置"""
        with self._lock:
            self._successes.clear()
            self._failures.clear()


# ── Prometheus 指标注册 ──
if _PROMETHEUS_AVAILABLE:
    _registry = CollectorRegistry()
    
    request_latency = Histogram(
        "fuxi_request_latency_ms",
        "Request latency in milliseconds",
        buckets=(10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000),
        registry=_registry,
    )
    
    request_count = Counter(
        "fuxi_requests_total",
        "Total number of requests",
        registry=_registry,
    )
    
    error_count = Counter(
        "fuxi_errors_total",
        "Total number of errors",
        registry=_registry,
    )
    
    memory_gauge = Gauge(
        "fuxi_memory_bytes",
        "Process memory usage in bytes",
        registry=_registry,
    )
    
    def get_prometheus_metrics() -> bytes:
        """获取 Prometheus 格式指标"""
        return generate_latest(_registry)
else:
    _registry = None
    request_latency = None
    request_count = None
    error_count = None
    memory_gauge = None
    
    def get_prometheus_metrics() -> bytes:
        return b"# prometheus_client not installed\n"


# ── 全局追踪器实例 ──

_latency_tracker = LatencyTracker()
_memory_tracker = MemoryTracker()
_error_tracker = ErrorRateTracker()


def get_latency_tracker() -> LatencyTracker:
    return _latency_tracker


def get_memory_tracker() -> MemoryTracker:
    return _memory_tracker


def get_error_tracker() -> ErrorRateTracker:
    return _error_tracker


def get_all_stats() -> Dict:
    """获取所有监控统计"""
    return {
        "latency": _latency_tracker.get_percentiles(),
        "memory": _memory_tracker.get_stats(),
        "errors": _error_tracker.get_stats(),
    }


def reset_all_stats():
    """重置所有统计"""
    _latency_tracker.reset()
    _error_tracker.reset()


# ── FastAPI 中间件 ──

try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response
    _STARLETTE_AVAILABLE = True
except ImportError:
    BaseHTTPMiddleware = object
    _STARLETTE_AVAILABLE = False

if _STARLETTE_AVAILABLE:
    class PerformanceMiddleware(BaseHTTPMiddleware):
        """性能监控中间件：记录每次请求的延迟和状态"""
        
        async def dispatch(self, request: Request, call_next):
            start_time = time.time()
            
            try:
                response: Response = await call_next(request)
                latency_ms = (time.time() - start_time) * 1000
                
                # 记录延迟
                _latency_tracker.record(latency_ms)
                _error_tracker.record_success()
                
                # Prometheus
                if request_count is not None:
                    request_count.inc()
                if request_latency is not None:
                    request_latency.observe(latency_ms)
                
                return response
                
            except Exception:
                latency_ms = (time.time() - start_time) * 1000
                _error_tracker.record_failure()
                
                if error_count is not None:
                    error_count.inc()
                
                raise
else:
    PerformanceMiddleware = None


async def setup_performance_monitoring(app):
    """在 FastAPI app 上安装性能监控"""
    
    # 挂载 /metrics 端点
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route
    
    async def metrics_endpoint(request):
        return PlainTextResponse(
            get_prometheus_metrics(),
            media_type=CONTENT_TYPE_LATEST,
        )
    
    async def stats_endpoint(request):
        import json
        from starlette.responses import JSONResponse
        return JSONResponse(get_all_stats())
    
    # 添加路由
    app.routes.insert(0, Route("/metrics", metrics_endpoint, methods=["GET"]))
    app.routes.insert(0, Route("/api/performance/stats", stats_endpoint, methods=["GET"]))
    
    # 启动内存采样任务
    import asyncio
    
    async def memory_sampler():
        while True:
            await asyncio.sleep(_memory_tracker._sample_interval)
            _memory_tracker.sample()
            # 更新 Prometheus gauge
            mem_bytes = _get_process_memory_bytes()
            if mem_bytes > 0 and memory_gauge is not None:
                memory_gauge.set(mem_bytes)
    
    app.state._memory_sampler_task = asyncio.create_task(memory_sampler())
    
    import logging
    logger = logging.getLogger("performance")
    logger.info(
        f"[Performance] 监控体系已启动 | "
        f"Prometheus={'可用' if _PROMETHEUS_AVAILABLE else '不可用(prometheus_client 未安装)'} | "
        f"端点: /metrics, /api/performance/stats"
    )
