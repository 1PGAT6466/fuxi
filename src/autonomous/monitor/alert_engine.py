"""
告警引擎模块
基于规则的告警，支持去重、抑制和通知
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AlertLevel(IntEnum):
    """告警级别 - 数值越小优先级越高"""

    P0 = 0  # 紧急
    P1 = 1  # 重要
    P2 = 2  # 警告
    P3 = 3  # 信息


@dataclass
class AlertRule:
    """告警规则"""

    id: str
    name: str
    metric: str
    condition: str  # "gt", "lt", "eq", "gte", "lte"
    threshold: float
    level: AlertLevel
    description: str = ""
    enabled: bool = True
    cooldown: int = 300  # 冷却期（秒）


@dataclass
class Alert:
    """告警实例"""

    id: str
    rule_id: str
    rule_name: str
    level: AlertLevel
    metric: str
    current_value: float
    threshold: float
    message: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    notified: bool = False


class AlertEngine:
    """告警引擎 - 基于规则的告警系统"""

    def __init__(self, config=None):
        from .config import MonitorConfig

        self.config = config or MonitorConfig()
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self._last_alert_time: Dict[str, float] = {}  # rule_id -> last alert time
        self._notifiers: List[Callable] = []

        # 加载预置规则
        self._load_default_rules()

    def _load_default_rules(self):
        """加载预置告警规则"""
        default_rules = [
            AlertRule(
                id="cpu_high",
                name="CPU使用率过高",
                metric="system.cpu.percent",
                condition="gt",
                threshold=self.config.cpu_threshold_warning,
                level=AlertLevel.P2,
                description=f"CPU使用率超过{self.config.cpu_threshold_warning}%",
            ),
            AlertRule(
                id="memory_high",
                name="内存使用率过高",
                metric="system.memory.percent",
                condition="gt",
                threshold=self.config.memory_threshold_warning,
                level=AlertLevel.P2,
                description=f"内存使用率超过{self.config.memory_threshold_warning}%",
            ),
            AlertRule(
                id="disk_high",
                name="磁盘使用率过高",
                metric="system.disk.percent",
                condition="gt",
                threshold=self.config.disk_threshold_warning,
                level=AlertLevel.P1,
                description=f"磁盘使用率超过{self.config.disk_threshold_warning}%",
            ),
            AlertRule(
                id="api_latency_high",
                name="API响应时间过长",
                metric="business.latency_avg",
                condition="gt",
                threshold=self.config.api_latency_threshold,
                level=AlertLevel.P1,
                description=f"API平均响应时间超过{self.config.api_latency_threshold}秒",
            ),
            AlertRule(
                id="api_error_rate_high",
                name="API错误率过高",
                metric="business.error_rate",
                condition="gt",
                threshold=self.config.api_error_rate_threshold,
                level=AlertLevel.P1,
                description=f"API错误率超过{self.config.api_error_rate_threshold}%",
            ),
            AlertRule(
                id="service_unavailable",
                name="服务不可用",
                metric="system.service.status",
                condition="eq",
                threshold=0,
                level=AlertLevel.P0,
                description="关键服务不可用",
            ),
        ]

        for rule in default_rules:
            self.rules[rule.id] = rule

    def add_rule(self, rule: AlertRule):
        """添加告警规则"""
        self.rules[rule.id] = rule
        logger.info(f"添加告警规则: {rule.name}")

    def remove_rule(self, rule_id: str):
        """移除告警规则"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            logger.info(f"移除告警规则: {rule_id}")

    def get_rules(self) -> List[AlertRule]:
        """获取所有告警规则"""
        return list(self.rules.values())

    async def evaluate(self, metrics: Dict[str, float]) -> List[Alert]:
        """评估指标，生成告警"""
        new_alerts = []

        for rule in self.rules.values():
            if not rule.enabled:
                continue

            metric_value = metrics.get(rule.metric)
            if metric_value is None:
                continue

            # 检查条件
            if self._check_condition(metric_value, rule.condition, rule.threshold):
                # 检查冷却期
                if self._is_in_cooldown(rule.id):
                    continue

                # 创建告警
                alert = self._create_alert(rule, metric_value)

                # 检查抑制
                if not self._is_suppressed(alert):
                    new_alerts.append(alert)
                    self.active_alerts[alert.id] = alert
                    self._last_alert_time[rule.id] = time.time()

        # 发送通知
        for alert in new_alerts:
            await self._notify(alert)

        return new_alerts

    def _check_condition(self, value: float, condition: str, threshold: float) -> bool:
        """检查条件"""
        if condition == "gt":
            return value > threshold
        elif condition == "lt":
            return value < threshold
        elif condition == "eq":
            return abs(value - threshold) < 0.001
        elif condition == "gte":
            return value >= threshold
        elif condition == "lte":
            return value <= threshold
        return False

    def _is_in_cooldown(self, rule_id: str) -> bool:
        """检查是否在冷却期内"""
        last_time = self._last_alert_time.get(rule_id)
        if last_time is None:
            return False
        return (time.time() - last_time) < self.config.alert_cooldown

    def _is_suppressed(self, alert: Alert) -> bool:
        """检查是否被高级别告警抑制"""
        for active_alert in self.active_alerts.values():
            if active_alert.metric == alert.metric and active_alert.level < alert.level:
                return True
        return False

    def _create_alert(self, rule: AlertRule, current_value: float) -> Alert:
        """创建告警"""
        return Alert(
            id=f"{rule.id}_{int(time.time())}",
            rule_id=rule.id,
            rule_name=rule.name,
            level=rule.level,
            metric=rule.metric,
            current_value=current_value,
            threshold=rule.threshold,
            message=f"{rule.name}: {current_value:.2f} {rule.condition} {rule.threshold}",
            created_at=datetime.now(),
        )

    async def _notify(self, alert: Alert):
        """发送告警通知"""
        alert.notified = True

        # 记录日志
        log_msg = f"[{alert.level.name}] {alert.message}"
        if alert.level == AlertLevel.P0:
            logger.critical(log_msg)
        elif alert.level == AlertLevel.P1:
            logger.error(log_msg)
        elif alert.level == AlertLevel.P2:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        # 调用通知器
        for notifier in self._notifiers:
            try:
                await notifier(alert)
            except Exception as e:
                logger.error(f"通知发送失败: {e}")

        # 存储历史
        self.alert_history.append(alert)
        if len(self.alert_history) > 10000:
            self.alert_history = self.alert_history[-10000:]

    def resolve_alert(self, alert_id: str):
        """解决告警"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts.pop(alert_id)
            alert.resolved_at = datetime.now()
            logger.info(f"告警已解决: {alert.message}")

    def get_active_alerts(self, level: Optional[AlertLevel] = None) -> List[Alert]:
        """获取活跃告警"""
        alerts = list(self.active_alerts.values())
        if level is not None:
            alerts = [a for a in alerts if a.level == level]
        return sorted(alerts, key=lambda x: x.level)

    def get_alert_history(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        level: Optional[AlertLevel] = None,
        limit: int = 100,
    ) -> List[Alert]:
        """获取告警历史"""
        alerts = self.alert_history

        if start_time:
            alerts = [a for a in alerts if a.created_at >= start_time]
        if end_time:
            alerts = [a for a in alerts if a.created_at <= end_time]
        if level is not None:
            alerts = [a for a in alerts if a.level == level]

        return sorted(alerts, key=lambda x: x.created_at, reverse=True)[:limit]

    def add_notifier(self, notifier: Callable):
        """添加通知器"""
        self._notifiers.append(notifier)

    def to_dict(self, alert: Alert) -> Dict[str, Any]:
        """将告警转换为字典"""
        return {
            "id": alert.id,
            "rule_id": alert.rule_id,
            "rule_name": alert.rule_name,
            "level": alert.level.name,
            "metric": alert.metric,
            "current_value": alert.current_value,
            "threshold": alert.threshold,
            "message": alert.message,
            "created_at": alert.created_at.isoformat(),
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            "notified": alert.notified,
        }
