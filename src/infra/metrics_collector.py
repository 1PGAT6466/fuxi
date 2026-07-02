"""
metrics_collector.py — 指标收集
系统指标 + 业务指标
"""
import time
import logging
from typing import Dict, List
from collections import deque

logger = logging.getLogger("infra.metrics_collector")


class MetricsCollector:
    """指标收集器"""

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self._metrics = {}
        self._counters = {}
        self._gauges = {}
        self._histograms = {}

    def increment_counter(self, name: str, value: int = 1):
        """增加计数器"""
        if name not in self._counters:
            self._counters[name] = 0
        self._counters[name] += value

    def set_gauge(self, name: str, value: float):
        """设置仪表盘"""
        self._gauges[name] = value

    def record_histogram(self, name: str, value: float):
        """记录直方图"""
        if name not in self._histograms:
            self._histograms[name] = deque(maxlen=self.max_history)
        self._histograms[name].append(value)

    def get_counter(self, name: str) -> int:
        """获取计数器值"""
        return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> float:
        """获取仪表盘值"""
        return self._gauges.get(name, 0.0)

    def get_histogram_stats(self, name: str) -> Dict:
        """获取直方图统计"""
        if name not in self._histograms or not self._histograms[name]:
            return {"count": 0, "avg": 0, "min": 0, "max": 0}

        values = list(self._histograms[name])
        return {
            "count": len(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
        }

    def get_all_metrics(self) -> Dict:
        """获取所有指标"""
        return {
            "counters": self._counters.copy(),
            "gauges": self._gauges.copy(),
            "histograms": {name: self.get_histogram_stats(name) for name in self._histograms},
        }


# 全局指标收集器
_metrics_collector: MetricsCollector = None


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标收集器"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
