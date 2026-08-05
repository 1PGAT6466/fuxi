"""
services/security.py — 安全模块兼容层（v1.50）
重定向到 src.taiyin.security，提供 Rate Limiting、审计日志、输入净化。
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ============================================================
# 从实际实现重导出所有公共 API
# ============================================================
from src.taiyin.security import (  # noqa: F401
    RateLimiter,
    check_rate_limit,
    audit_log_entry,
    sanitize_xss,
    sanitize_user_input,
)

# 兼容别名（保持旧代码可运行）
__all__ = [
    "RateLimiter",
    "check_rate_limit",
    "audit_log_entry",
    "sanitize_xss",
    "sanitize_user_input",
]
