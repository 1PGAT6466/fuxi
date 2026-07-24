"""
symbol_base.py — 四象基类
不继承 OrganBase，避免八卦/五行/天干元数据
"""
import logging
import time
from typing import Dict, Any

logger = logging.getLogger("symbol_base")


class SymbolBase:
    """四象基类 — 经络注册 + 心跳 + 状态上报"""

    def __init__(self, meridian, symbol_id: str, name: str, emoji: str, description: str):
        self.meridian = meridian
        self.symbol_id = symbol_id
        self.name = name
        self.emoji = emoji
        self.description = description
        self._status = "idle"
        self._last_activity = time.time()
        self._metrics: Dict[str, Any] = {}

        # 注册到经络（Meridian.register_symbol 接受 symbol_id 和 instance 两个参数）
        meridian.register_symbol(symbol_id, self)
        logger.info(f"[{symbol_id}] {emoji} {name} 已注册")
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

    async def heartbeat(self):
        """心跳上报"""
        self.meridian.heartbeat(self.symbol_id)

    def get_status(self) -> dict:
        """返回象的健康状态"""
        return {
            "symbol": self.symbol_id,
            "alive": self.meridian.is_alive(self.symbol_id),
            "status": self._status,
            "heartbeat_ago": self.meridian.last_heartbeat_ago(self.symbol_id),
            "metrics": self._get_metrics(),
        }

    def _get_metrics(self) -> dict:
        """子类实现，返回各自的指标"""
        return self._metrics

    # DEPRECATED: 未使用，v1.50 标记待删除
    def _set_status(self, status: str):
        """设置状态（idle/processing/error）"""
        self._status = status
        self._last_activity = time.time()
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
# DEPRECATED: 未使用，v1.50 标记待删除

    async def _handle_growth_rollback(self, signal):
        """处理成长引擎的回滚信号"""
        param = signal.payload.get("param")
        reason = signal.payload.get("reason")
        logger.warning(f"[{self.symbol_id}] 收到回滚信号: {param}，原因: {reason}")
        # 子类实现具体回滚逻辑
