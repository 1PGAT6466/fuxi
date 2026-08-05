"""
monitoring.py - 系统监控
=========================

系统监控和告警。
"""

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("monitoring")

# ============================================================================
# Monitoring — 系统监控
# ============================================================================


class Monitoring:
    """系统监控

    监控系统各组件状态，自动触发告警。

    Attributes:
        metrics:              指标字典
        alerts:               告警字典
        check_interval:       检查间隔（秒）
    """

    def __init__(
        self,
        check_interval: float = 60.0,
    ) -> None:
        self.metrics: Dict[str, Any] = {}
        self.alerts: Dict[str, Any] = {}
        self.check_interval = check_interval

    def record_metric(self, name: str, value: Any, timestamp: Optional[float] = None) -> None:
        """记录指标

        Args:
            name:               指标名称
            value:              指标值
            timestamp:          时间戳
        """
        if timestamp is None:
            timestamp = time.time()

        self.metrics[name] = {
            "value": value,
            "timestamp": timestamp,
        }

        logger.debug(f"记录指标: {name} = {value}")

    def get_metric(self, name: str) -> Optional[Any]:
        """获取指标

        Args:
            name:               指标名称

        Returns:
            指标值，或 None（不存在）
        """
        if name in self.metrics:
            return self.metrics[name]["value"]
        return None

    def trigger_alert(self, name: str, message: str, level: str = "warning") -> None:
        """触发告警

        Args:
            name:               告警名称
            message:            告警消息
            level:              告警级别
        """
        self.alerts[name] = {
            "message": message,
            "level": level,
            "timestamp": time.time(),
        }

        logger.warning(f"触发告警: {name} - {message}")

    def get_alert(self, name: str) -> Optional[Dict[str, Any]]:
        """获取告警

        Args:
            name:               告警名称

        Returns:
            告警信息，或 None（不存在）
        """
        return self.alerts.get(name)

    def clear_alert(self, name: str) -> None:
        """清除告警

        Args:
            name:               告警名称
        """
        if name in self.alerts:
            del self.alerts[name]
            logger.info(f"清除告警: {name}")

    def get_metrics_summary(self) -> Dict[str, Any]:
        """获取指标摘要"""
        return {
            "metrics_count": len(self.metrics),
            "alerts_count": len(self.alerts),
            "metrics": self.metrics,
            "alerts": self.alerts,
        }


# ============================================================================
# 全局单例
# ============================================================================

_monitoring: Optional[Monitoring] = None


def get_monitoring() -> Monitoring:
    """获取全局 Monitoring 单例"""
    global _monitoring
    if _monitoring is None:
        _monitoring = Monitoring()
    return _monitoring
