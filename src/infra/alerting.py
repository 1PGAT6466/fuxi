"""
alerting.py — 监控告警
关键指标监控 + 告警阈值
"""
import logging
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field

try:
    import aiohttp
except ImportError:
    aiohttp = None

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
            "shaoyin_retry_rate": 0.3,
        },
        "warning": {
            "taiyang_latency_p95": 1000,
            "shaoyin_confidence_avg": 0.3,
            "shaoyang_extraction_failure_rate": 0.2,
            "taiyang_cache_hit_rate": 0.1,
        },
        "info": {
            "taiyang_cache_hit_rate": 0.2,
            "shaoyin_confidence_avg": 0.5,
        },
    }

    def __init__(self):
        self._alerts: List[Alert] = []
        self._max_alerts = 1000
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

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


# ---------------------------------------------------------------------------
# v2.1: Webhook 告警发送（兼容 test_infra_components.py）
# ---------------------------------------------------------------------------

def _build_dingtalk_body(title: str, content: str, level: str = "info") -> Dict:
    """构建钉钉机器人 Markdown 消息体"""
    level_emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
    emoji = level_emoji.get(level, "🔵")
    return {
        "msgtype": "markdown",
        "markdown": {
            "title": f"{emoji} [{level.upper()}] {title}",
            "text": f"## {emoji} {title}\n\n{content}\n\n---\n> 告警级别: {level.upper()}"
        }
    }


def _build_feishu_body(title: str, content: str, level: str = "info") -> Dict:
    """构建飞书卡片消息体"""
    color_map = {"critical": "red", "warning": "yellow", "info": "blue"}
    template = color_map.get(level, "blue")
    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"content": f"[{level.upper()}] {title}", "tag": "plain_text"},
                "template": template
            },
            "elements": [
                {"tag": "div", "text": {"tag": "plain_text", "content": content}}
            ]
        }
    }


async def send_webhook(url: str, title: str, message: str, level: str = "info") -> bool:
    """发送 Webhook 告警（钉钉/飞书自动检测）"""
    if aiohttp is None:
        logger.error("aiohttp 未安装，无法发送 Webhook")
        return False
    try:
        if "dingtalk" in url:
            body = _build_dingtalk_body(title, message, level)
        elif "feishu" in url:
            body = _build_feishu_body(title, message, level)
        else:
            body = {"title": title, "content": message, "level": level}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    logger.info(f"Webhook 发送成功: {url}")
                    return True
                else:
                    logger.warning(f"Webhook 发送失败: {resp.status} {await resp.text()}")
                    return False
    except Exception as e:
        logger.error(f"Webhook 发送异常: {e}")
        return False


async def send_alert(title: str, message: str, level: str = "warning") -> bool:
    """发送告警到所有配置的 Webhook 地址"""
    import os
    urls = []
    dt_url = os.environ.get("DINGTALK_WEBHOOK_URL", "")
    fs_url = os.environ.get("FEISHU_WEBHOOK_URL", "")
    if dt_url:
        urls.append(dt_url)
    if fs_url:
        urls.append(fs_url)

    if not urls:
        logger.warning("未配置任何 Webhook URL，告警未发送")
        return False

    results = []
    for url in urls:
        result = await send_webhook(url, title, message, level)
        results.append(result)
    return any(results)
