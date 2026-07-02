"""
alerting.py — 监控告警
关键指标监控 + 告警阈值
"""
import logging
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("infra.alerting")


@dataclass
class Alert:
    """告警"""
    level: str  # critical / warning / info
    symbol: str
    metric: str
    value: float
    threshold: float
    message: str
    timestamp: float = field(default_factory=time.time)


class AlertManager:
    """告警管理器"""

    ALERT_THRESHOLDS = {
        "critical": {
            "taiyin_error_rate": 0.05,
            "taiyang_latency_p99": 2000,
        },
        "warning": {
            "taiyang_latency_p95": 1000,
            "shaoyin_confidence_avg": 0.3,
        },
        "info": {
            "taiyang_cache_hit_rate": 0.2,
        },
    }

    def __init__(self):
        self._alerts: List[Alert] = []
        self._max_alerts = 1000

    async def check_metrics(self, metrics: Dict) -> List[Alert]:
        """检查指标并生成告警"""
        new_alerts = []

        for level, thresholds in self.ALERT_THRESHOLDS.items():
            for metric, threshold in thresholds.items():
                value = metrics.get(metric)
                if value is None:
                    continue

                triggered = False
                if level == "critical" and value > threshold:
                    triggered = True
                elif level == "warning":
                    if "latency" in metric and value > threshold:
                        triggered = True
                    elif "confidence" in metric and value < threshold:
                        triggered = True
                elif level == "info" and value < threshold:
                    triggered = True

                if triggered:
                    alert = Alert(
                        level=level,
                        symbol=metric.split("_")[0],
                        metric=metric,
                        value=value,
                        threshold=threshold,
                        message=f"{metric}={value:.2f} {'>' if value > threshold else '<'} {threshold}",
                    )
                    new_alerts.append(alert)
                    self._alerts.append(alert)

        # 限制告警数量
        if len(self._alerts) > self._max_alerts:
            self._alerts = self._alerts[-self._max_alerts:]

        return new_alerts

    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        """获取最近的告警"""
        return [
            {
                "level": a.level,
                "symbol": a.symbol,
                "metric": a.metric,
                "value": a.value,
                "threshold": a.threshold,
                "message": a.message,
                "timestamp": a.timestamp,
            }
            for a in self._alerts[-limit:]
        ]

    def get_alert_count(self) -> Dict[str, int]:
        """获取告警统计"""
        counts = {"critical": 0, "warning": 0, "info": 0}
        for alert in self._alerts:
            counts[alert.level] = counts.get(alert.level, 0) + 1
        return counts


# 全局实例
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """获取全局告警管理器"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager
