"""
decision_growth.py — 少阴成长
决策能力监控
"""
import logging
from typing import Dict

logger = logging.getLogger("growth.decision")


class DecisionGrowth:
    """少阴决策能力成长"""

    def __init__(self, engine):
        self.engine = engine
        self._thought_count = 0
        self._retry_count = 0

    async def record_decision(self, confidence: float, retried: bool = False):
        """记录决策事件"""
        self._thought_count += 1
        if retried:
            self._retry_count += 1

        await self.engine.record_event(
            symbol="shaoyin",
            metric="decision_confidence",
            value=confidence,
            context={"retried": retried}
        )

    def get_stats(self) -> Dict:
        return {
            "thought_count": self._thought_count,
            "retry_count": self._retry_count,
            "retry_rate": self._retry_count / max(self._thought_count, 1),
        }
