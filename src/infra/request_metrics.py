"""
request_metrics.py — 请求指标
延迟 + 错误率 + 吞吐量
"""
import time
import logging
from typing import Dict, List
from collections import deque

logger = logging.getLogger("infra.request_metrics")


class RequestMetrics:
    """请求指标"""

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self._requests = 0
        self._errors = 0
        self._latencies = deque(maxlen=max_history)
        self._start_time = time.time()

    def record_request(self, latency_ms: float, success: bool = True):
        """记录请求"""
        self._requests += 1
        if not success:
            self._errors += 1
        self._latencies.append(latency_ms)

    def get_stats(self) -> Dict:
        """获取统计"""
        uptime = time.time() - self._start_time
        error_rate = self._errors / self._requests if self._requests > 0 else 0

        return {
            "requests": self._requests,
            "errors": self._errors,
            "error_rate": round(error_rate, 4),
            "avg_latency_ms": sum(self._latencies) / len(self._latencies) if self._latencies else 0,
            "qps": self._requests / uptime if uptime > 0 else 0,
            "uptime_seconds": uptime,
        }

    def get_percentiles(self) -> Dict:
        """获取延迟百分位"""
        if not self._latencies:
            return {"p50": 0, "p90": 0, "p95": 0, "p99": 0}

        sorted_latencies = sorted(self._latencies)
        n = len(sorted_latencies)

        return {
            "p50": sorted_latencies[int(n * 0.5)],
            "p90": sorted_latencies[int(n * 0.9)],
            "p95": sorted_latencies[int(n * 0.95)],
            "p99": sorted_latencies[min(int(n * 0.99), n - 1)],
        }


# 全局指标实例
_request_metrics: RequestMetrics = None


def get_request_metrics() -> RequestMetrics:
    """获取全局请求指标"""
    global _request_metrics
    if _request_metrics is None:
        _request_metrics = RequestMetrics()
    return _request_metrics
