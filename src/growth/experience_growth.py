"""
experience_growth.py — 太阴成长
接口体验监控
"""
import logging
from typing import Dict

logger = logging.getLogger("growth.experience")


class ExperienceGrowth:
    """太阴接口体验成长"""

    def __init__(self, engine):
        self.engine = engine
        self._request_count = 0
        self._error_count = 0

    async def record_request(self, success: bool, duration_ms: float = 0):
        """记录请求事件"""
        self._request_count += 1
        if not success:
            self._error_count += 1

        await self.engine.record_event(
            symbol="taiyin",
            metric="request_success",
            value=1.0 if success else 0.0,
            context={"duration_ms": duration_ms}
        )

    def get_stats(self) -> Dict:
        return {
            "request_count": self._request_count,
            "error_count": self._error_count,
            "error_rate": self._error_count / max(self._request_count, 1),
        }
