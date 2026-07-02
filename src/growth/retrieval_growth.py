"""
retrieval_growth.py — 太阳成长
检索效果监控
"""
import logging
from typing import Dict

logger = logging.getLogger("growth.retrieval")


class RetrievalGrowth:
    """太阳检索效果成长"""

    def __init__(self, engine):
        self.engine = engine
        self._search_count = 0
        self._cache_hits = 0

    async def record_search(self, results_count: int, cache_hit: bool = False, duration_ms: float = 0):
        """记录检索事件"""
        self._search_count += 1
        if cache_hit:
            self._cache_hits += 1

        await self.engine.record_event(
            symbol="taiyang",
            metric="search_result_count",
            value=float(results_count),
            context={"cache_hit": cache_hit, "duration_ms": duration_ms}
        )

    def get_stats(self) -> Dict:
        return {
            "search_count": self._search_count,
            "cache_hits": self._cache_hits,
            "cache_hit_rate": self._cache_hits / max(self._search_count, 1),
        }
