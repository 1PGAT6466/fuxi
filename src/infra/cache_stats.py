"""
cache_stats.py — 缓存统计
命中率 + 性能监控
"""
import time
import logging
from typing import Dict
from collections import deque

logger = logging.getLogger("infra.cache_stats")


class CacheStats:
    """缓存统计"""

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self._hits = 0
        self._misses = 0
        self._latencies = deque(maxlen=max_history)
        self._start_time = time.time()

    def record_hit(self, latency_ms: float = 0):
        """记录缓存命中"""
        self._hits += 1
        self._latencies.append(latency_ms)

    def record_miss(self, latency_ms: float = 0):
        """记录缓存未命中"""
        self._misses += 1
        self._latencies.append(latency_ms)

    def get_stats(self) -> Dict:
        """获取统计"""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "total": total,
            "hit_rate": round(hit_rate, 3),
            "avg_latency_ms": sum(self._latencies) / len(self._latencies) if self._latencies else 0,
            "uptime_seconds": time.time() - self._start_time,
        }

    def reset(self):
        """重置统计"""
        self._hits = 0
        self._misses = 0
        self._latencies.clear()
        self._start_time = time.time()


# 全局统计实例
_cache_stats: CacheStats = None


def get_cache_stats() -> CacheStats:
    """获取全局缓存统计"""
    global _cache_stats
    if _cache_stats is None:
        _cache_stats = CacheStats()
    return _cache_stats
