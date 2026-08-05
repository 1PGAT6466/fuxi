"""
通知器模块
支持企微、邮件通知，带模板管理和去重机制
"""

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """通知渠道"""

    WECOM = "wecom"  # 企微
    EMAIL = "email"  # 邮件
    WEBHOOK = "webhook"  # Webhook


@dataclass
class NotificationTemplate:
    """通知模板"""

    id: str
    name: str
    channel: NotificationChannel
    title_template: str
    content_template: str
    enabled: bool = True

    def render(self, context: Dict[str, Any]) -> tuple:
        """渲染模板"""
        title = self.title_template.format(**context)
        content = self.content_template.format(**context)
        return title, content


@dataclass
class NotificationRecord:
    """通知记录"""

    id: str
    channel: NotificationChannel
    template_id: str
    title: str
    content: str
    alert_id: Optional[str]
    alert_level: Optional[str]
    status: str  # "pending", "sent", "failed"
    created_at: datetime
    sent_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class NotifierConfig:
    """通知配置"""

    # 企微配置
    wecom_webhook_url: str = ""
    wecom_mentioned_list: List[str] = field(default_factory=list)

    # 邮件配置
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    email_recipients: List[str] = field(default_factory=list)

    # 通用配置
    notification_cooldown: int = 300  # 通知冷却期（秒）
    max_history: int = 1000
    enable_async: bool = True


class BaseNotifier(ABC):
    """通知器基类"""

    @abstractmethod
    async def send(self, title: str, content: str, **kwargs) -> bool:
        """发送通知"""
        pass

    @abstractmethod
    def get_channel(self) -> NotificationChannel:
        """获取通知渠道"""
        pass


class WecomNotifier(BaseNotifier):
    """企微通知器"""

    def __init__(self, webhook_url: str, mentioned_list: List[str] = None):
        self.webhook_url = webhook_url
        self.mentioned_list = mentioned_list or []

    async def send(self, title: str, content: str, **kwargs) -> bool:
        """发送企微通知"""
        if not self.webhook_url:
            logger.warning("企微webhook未配置")
            return False

        try:
            import aiohttp

            # 构建消息
            message = {"msgtype": "markdown", "markdown": {"content": f"## {title}\n\n{content}"}}

            if self.mentioned_list:
                message["mentioned_list"] = self.mentioned_list

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url, json=message, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        if result.get("errcode") == 0:
                            logger.info(f"企微通知发送成功: {title}")
                            return True
                        else:
                            logger.error(f"企微通知发送失败: {result}")
                            return False
                    else:
                        logger.error(f"企微通知发送失败: HTTP {resp.status}")
                        return False
        except ImportError:
            logger.warning("aiohttp未安装，企微通知不可用")
            return False
        except Exception as e:
            logger.error(f"企微通知发送异常: {e}")
            return False

    def get_channel(self) -> NotificationChannel:
        return NotificationChannel.WECOM


class EmailNotifier(BaseNotifier):
    """邮件通知器"""

    def __init__(self, config: NotifierConfig):
        self.config = config

    async def send(self, title: str, content: str, **kwargs) -> bool:
        """发送邮件通知"""
        if not self.config.smtp_host:
            logger.warning("邮件SMTP未配置")
            return False

        try:
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            import aiosmtplib

            # 创建邮件
            msg = MIMEMultipart()
            msg["From"] = self.config.smtp_user
            msg["To"] = ", ".join(self.config.email_recipients)
            msg["Subject"] = title

            # 添加正文
            msg.attach(MIMEText(content, "html", "utf-8"))

            # 发送邮件
            await aiosmtplib.send(
                msg,
                hostname=self.config.smtp_host,
                port=self.config.smtp_port,
                username=self.config.smtp_user,
                password=self.config.smtp_password,
                use_tls=True,
            )

            logger.info(f"邮件通知发送成功: {title}")
            return True
        except ImportError:
            logger.warning("aiosmtplib未安装，邮件通知不可用")
            return False
        except Exception as e:
            logger.error(f"邮件通知发送异常: {e}")
            return False

    def get_channel(self) -> NotificationChannel:
        return NotificationChannel.EMAIL


class Notifier:
    """通知器管理器"""

    def __init__(self, config: Optional[NotifierConfig] = None):
        self.config = config or NotifierConfig()
        self.templates: Dict[str, NotificationTemplate] = {}
        self.history: List[NotificationRecord] = []
        self._notifiers: Dict[NotificationChannel, BaseNotifier] = {}
        self._cooldown_cache: Dict[str, float] = {}  # key -> timestamp

        # 加载默认模板
        self._load_default_templates()

        # 初始化通知器
        self._init_notifiers()

    def _load_default_templates(self):
        """加载默认通知模板"""
        default_templates = [
            # 企微模板
            NotificationTemplate(
                id="alert_wecom",
                name="告警通知-企微",
                channel=NotificationChannel.WECOM,
                title_template="🚨 [{level}] 告警通知",
                content_template=(
                    "**告警级别**: {level}\n"
                    "**告警规则**: {rule_name}\n"
                    "**当前值**: {current_value}\n"
                    "**阈值**: {threshold}\n"
                    "**告警信息**: {message}\n"
                    "**触发时间**: {created_at}\n\n"
                    "---\n"
                    "请及时处理！"
                ),
            ),
            # 邮件模板
            NotificationTemplate(
                id="alert_email",
                name="告警通知-邮件",
                channel=NotificationChannel.EMAIL,
                title_template="[Fuxi Alert] {level} - {rule_name}",
                content_template=(
                    "<html><body>"
                    "<h2 style='color: {level_color};'>[{level}] 告警通知</h2>"
                    "<table border='1' cellpadding='10' cellspacing='0'>"
                    "<tr><td><b>告警规则</b></td><td>{rule_name}</td></tr>"
                    "<tr><td><b>当前值</b></td><td>{current_value}</td></tr>"
                    "<tr><td><b>阈值</b></td><td>{threshold}</td></tr>"
                    "<tr><td><b>告警信息</b></td><td>{message}</td></tr>"
                    "<tr><td><b>触发时间</b></td><td>{created_at}</td></tr>"
                    "</table>"
                    "<p>请及时处理！</p>"
                    "</body></html>"
                ),
            ),
            # 测试通知模板
            NotificationTemplate(
                id="test_notification",
                name="测试通知",
                channel=NotificationChannel.WECOM,
                title_template="🔔 测试通知",
                content_template=(
                    "**测试通知**\n\n"
                    "时间: {timestamp}\n"
                    "消息: {message}\n\n"
                    "如果你收到这条消息，说明通知功能正常。"
                ),
            ),
        ]

        for template in default_templates:
            self.templates[template.id] = template

    def _init_notifiers(self):
        """初始化通知器"""
        # 企微通知器
        if self.config.wecom_webhook_url:
            self._notifiers[NotificationChannel.WECOM] = WecomNotifier(
                webhook_url=self.config.wecom_webhook_url, mentioned_list=self.config.wecom_mentioned_list
            )

        # 邮件通知器
        if self.config.smtp_host:
            self._notifiers[NotificationChannel.EMAIL] = EmailNotifier(self.config)

    def add_template(self, template: NotificationTemplate):
        """添加通知模板"""
        self.templates[template.id] = template
        logger.info(f"添加通知模板: {template.name}")

    def remove_template(self, template_id: str):
        """移除通知模板"""
        if template_id in self.templates:
            del self.templates[template_id]
            logger.info(f"移除通知模板: {template_id}")

    def get_templates(self, channel: Optional[NotificationChannel] = None) -> List[NotificationTemplate]:
        """获取通知模板"""
        templates = list(self.templates.values())
        if channel:
            templates = [t for t in templates if t.channel == channel]
        return templates

    def _generate_cooldown_key(self, alert_id: str, channel: NotificationChannel) -> str:
        """生成冷却期键"""
        return f"{alert_id}:{channel.value}"

    def _is_in_cooldown(self, alert_id: str, channel: NotificationChannel) -> bool:
        """检查是否在冷却期内"""
        key = self._generate_cooldown_key(alert_id, channel)
        last_time = self._cooldown_cache.get(key)
        if last_time is None:
            return False
        return (time.time() - last_time) < self.config.notification_cooldown

    def _update_cooldown(self, alert_id: str, channel: NotificationChannel):
        """更新冷却期"""
        key = self._generate_cooldown_key(alert_id, channel)
        self._cooldown_cache[key] = time.time()

    def _build_context(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """构建模板上下文"""
        # 级别颜色映射
        level_colors = {
            "P0": "#FF0000",  # 红色
            "P1": "#FF6600",  # 橙色
            "P2": "#FFCC00",  # 黄色
            "P3": "#0066FF",  # 蓝色
        }

        level = alert_data.get("level", "P3")
        context = {
            "level": level,
            "level_color": level_colors.get(level, "#666666"),
            "rule_name": alert_data.get("rule_name", "未知规则"),
            "current_value": alert_data.get("current_value", "N/A"),
            "threshold": alert_data.get("threshold", "N/A"),
            "message": alert_data.get("message", ""),
            "created_at": alert_data.get("created_at", datetime.now().isoformat()),
            "alert_id": alert_data.get("alert_id", ""),
            "timestamp": datetime.now().isoformat(),
        }
        return context

    async def send_notification(
        self,
        alert_data: Dict[str, Any],
        channels: Optional[List[NotificationChannel]] = None,
        template_ids: Optional[Dict[NotificationChannel, str]] = None,
    ) -> List[NotificationRecord]:
        """发送通知"""
        records = []
        alert_id = alert_data.get("alert_id", "")
        context = self._build_context(alert_data)

        # 默认发送到所有已配置的渠道
        if channels is None:
            channels = list(self._notifiers.keys())

        for channel in channels:
            # 检查冷却期
            if self._is_in_cooldown(alert_id, channel):
                logger.debug(f"通知在冷却期内，跳过: {alert_id} -> {channel.value}")
                continue

            # 获取通知器
            notifier = self._notifiers.get(channel)
            if not notifier:
                logger.warning(f"通知器未配置: {channel.value}")
                continue

            # 获取模板
            template_id = None
            if template_ids and channel in template_ids:
                template_id = template_ids[channel]
            else:
                # 使用默认模板
                if channel == NotificationChannel.WECOM:
                    template_id = "alert_wecom"
                elif channel == NotificationChannel.EMAIL:
                    template_id = "alert_email"

            template = self.templates.get(template_id)
            if not template:
                logger.warning(f"通知模板不存在: {template_id}")
                continue

            # 渲染模板
            title, content = template.render(context)

            # 创建记录
            record = NotificationRecord(
                id=f"{alert_id}_{channel.value}_{int(time.time())}",
                channel=channel,
                template_id=template_id,
                title=title,
                content=content,
                alert_id=alert_id,
                alert_level=context.get("level"),
                status="pending",
                created_at=datetime.now(),
            )

            # 发送通知
            try:
                success = await notifier.send(title, content)
                if success:
                    record.status = "sent"
                    record.sent_at = datetime.now()
                    self._update_cooldown(alert_id, channel)
                else:
                    record.status = "failed"
                    record.error = "发送失败"
            except Exception as e:
                record.status = "failed"
                record.error = str(e)
                logger.error(f"通知发送异常: {e}")

            records.append(record)
            self.history.append(record)

        # 清理历史
        if len(self.history) > self.config.max_history:
            self.history = self.history[-self.config.max_history :]

        return records

    async def send_test_notification(
        self, channel: NotificationChannel, message: str = "这是一条测试通知"
    ) -> NotificationRecord:
        """发送测试通知"""
        notifier = self._notifiers.get(channel)
        if not notifier:
            raise ValueError(f"通知器未配置: {channel.value}")

        template = self.templates.get("test_notification")
        if not template:
            raise ValueError("测试通知模板不存在")

        context = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
        }

        title, content = template.render(context)

        record = NotificationRecord(
            id=f"test_{channel.value}_{int(time.time())}",
            channel=channel,
            template_id="test_notification",
            title=title,
            content=content,
            alert_id=None,
            alert_level=None,
            status="pending",
            created_at=datetime.now(),
        )

        try:
            success = await notifier.send(title, content)
            if success:
                record.status = "sent"
                record.sent_at = datetime.now()
            else:
                record.status = "failed"
                record.error = "发送失败"
        except Exception as e:
            record.status = "failed"
            record.error = str(e)

        self.history.append(record)
        return record

    def get_history(
        self, channel: Optional[NotificationChannel] = None, status: Optional[str] = None, limit: int = 100
    ) -> List[NotificationRecord]:
        """获取通知历史"""
        records = self.history

        if channel:
            records = [r for r in records if r.channel == channel]
        if status:
            records = [r for r in records if r.status == status]

        return sorted(records, key=lambda x: x.created_at, reverse=True)[:limit]

    def to_dict(self, record: NotificationRecord) -> Dict[str, Any]:
        """将通知记录转换为字典"""
        return {
            "id": record.id,
            "channel": record.channel.value,
            "template_id": record.template_id,
            "title": record.title,
            "content": record.content,
            "alert_id": record.alert_id,
            "alert_level": record.alert_level,
            "status": record.status,
            "created_at": record.created_at.isoformat(),
            "sent_at": record.sent_at.isoformat() if record.sent_at else None,
            "error": record.error,
        }
