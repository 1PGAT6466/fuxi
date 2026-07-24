"""
flags.py — 太阴·Feature Flag 管理 (3+1)
v1.50 合并：现在委托到 src.services.feature_flags，本模块保留为兼容壳。
所有 import `from src.taiyin.flags import …` 仍然工作，API 签名不变。
"""
from src.services.feature_flags import (
    load_flags,
    save_flags,
    is_enabled,
    set_flag,
    get_flag,
    list_flags,
    DEFAULT_FLAGS,
    FLAG_FILE,
    _flags,
    _last_load,
    _RELOAD_INTERVAL,
)

__all__ = [
    "load_flags",
    "save_flags", 
    "is_enabled",
    "set_flag",
    "get_flag",
    "list_flags",
    "DEFAULT_FLAGS",
    "FLAG_FILE",
]
