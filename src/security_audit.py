"""
security_audit.py - 安全审计
============================

安全审计日志，记录关键操作。
"""

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("security_audit")

# ============================================================================
# SecurityAudit — 安全审计
# ============================================================================


class SecurityAudit:
    """安全审计

    记录关键操作，包括登录、查询、修改等。

    Attributes:
        audit_log_path:       审计日志路径
        max_log_size:         最大日志大小（字节）
        backup_count:         备份数量
    """

    def __init__(
        self,
        audit_log_path: str = "data/security_audit.log",
        max_log_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
    ) -> None:
        self.audit_log_path = audit_log_path
        self.max_log_size = max_log_size
        self.backup_count = backup_count

        # 配置日志
        self._setup_logging()

    def _setup_logging(self) -> None:
        """配置日志"""
        # 创建日志目录
        import os
        os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)

        # 配置日志处理器
        from logging.handlers import RotatingFileHandler
        handler = RotatingFileHandler(
            self.audit_log_path,
            maxBytes=self.max_log_size,
            backupCount=self.backup_count,
            encoding="utf-8",
        )

        # 配置日志格式
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)

        # 添加处理器
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    def log_login(self, username: str, success: bool, ip_address: Optional[str] = None) -> None:
        """记录登录

        Args:
            username:           用户名
            success:            是否成功
            ip_address:         IP 地址
        """
        status = "成功" if success else "失败"
        logger.info(f"登录: {username} {status} (IP: {ip_address})")

    def log_query(self, username: str, query: str, result_count: int, ip_address: Optional[str] = None) -> None:
        """记录查询

        Args:
            username:           用户名
            query:              查询内容
            result_count:       结果数量
            ip_address:         IP 地址
        """
        logger.info(f"查询: {username} 查询 '{query[:50]}...' 返回 {result_count} 个结果 (IP: {ip_address})")

    def log_modify(self, username: str, action: str, target: str, ip_address: Optional[str] = None) -> None:
        """记录修改

        Args:
            username:           用户名
            action:             操作类型
            target:             目标
            ip_address:         IP 地址
        """
        logger.info(f"修改: {username} {action} {target} (IP: {ip_address})")

    def log_error(self, username: str, error: str, ip_address: Optional[str] = None) -> None:
        """记录错误

        Args:
            username:           用户名
            error:              错误信息
            ip_address:         IP 地址
        """
        logger.error(f"错误: {username} 发生错误 {error} (IP: {ip_address})")


# ============================================================================
# 全局单例
# ============================================================================

_security_audit: Optional[SecurityAudit] = None


def get_security_audit() -> SecurityAudit:
    """获取全局 SecurityAudit 单例"""
    global _security_audit
    if _security_audit is None:
        _security_audit = SecurityAudit()
    return _security_audit
