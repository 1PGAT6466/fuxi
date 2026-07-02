"""
server.py — 太阴·显化 对外接口中枢
合并皮肤(屏障)+三焦(通道)的能力
"""
import logging
from typing import Dict, Any

from src.infra.symbol_base import SymbolBase

logger = logging.getLogger("taiyin.server")


class TaiyinServer(SymbolBase):
    """太阴·显化 — 对外接口中枢"""

    def __init__(self, meridian):
        super().__init__(
            meridian=meridian,
            symbol_id="taiyin",
            name="太阴·显化",
            emoji="🌑",
            description="对外接口中枢：一个入口，一个出口"
        )
        self._request_count = 0
        self._error_count = 0

    def _get_metrics(self) -> dict:
        """返回接口指标"""
        return {
            "request_count": self._request_count,
            "error_count": self._error_count,
            "error_rate": self._error_count / max(self._request_count, 1),
        }
