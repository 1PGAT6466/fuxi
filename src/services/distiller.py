"""
services/distiller.py — 知识蒸馏兼容层（v1.50）
重定向到 src.shaoyang.distiller，提供 Yggdrasil 世界树蒸馏引擎。

包括：实体分类、实体类型识别、增量蒸馏、断点恢复、批量保存。
"""

import logging
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)

# ============================================================
# 从实际实现重导出所有公共 API
# ============================================================
from src.shaoyang.distiller import (  # noqa: F401
    classify,
    distill_sync,
    save_batch,
    load_state,
    save_state,
    run_full,
    get_distill_state,
)

__all__ = [
    "classify",
    "distill_sync",
    "save_batch",
    "load_state",
    "save_state",
    "run_full",
    "get_distill_state",
]
