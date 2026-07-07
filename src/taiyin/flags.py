"""
flags.py — 太阴·Feature Flag 管理 (3+1)
v1.50 合并：现在委托到 src.services.feature_flags，本模块保留为兼容壳。
所有 import `from src.taiyin.flags import …` 仍然工作，API 签名不变。
"""
import logging
from typing import Dict

logger = logging.getLogger("taiyin.flags")

# 委托到统一主源
from src.services.feature_flags import (
    load_flags,
    save_flags,
    set_flag,
    is_enabled,
    get_all_flags,
    DEFAULT_FLAGS,
)
