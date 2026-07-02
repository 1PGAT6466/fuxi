"""
extraction_growth.py — 少阳成长
提取质量监控
"""
import logging
from typing import Dict

logger = logging.getLogger("growth.extraction")


class ExtractionGrowth:
    """少阳提取质量成长"""

    def __init__(self, engine):
        self.engine = engine
        self._extract_count = 0
        self._success_count = 0

    async def record_extraction(self, success: bool, entities_count: int = 0):
        """记录提取事件"""
        self._extract_count += 1
        if success:
            self._success_count += 1

        await self.engine.record_event(
            symbol="shaoyang",
            metric="extraction_success",
            value=1.0 if success else 0.0,
            context={"entities_count": entities_count}
        )

    def get_stats(self) -> Dict:
        return {
            "extract_count": self._extract_count,
            "success_count": self._success_count,
            "success_rate": self._success_count / max(self._extract_count, 1),
        }
