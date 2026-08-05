"""
services/relation_builder.py — 关系构建兼容层（v1.50）
重定向到 src.shaoyang.relation_builder。
"""

import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

from src.shaoyang.relation_builder import (  # noqa: F401
    extract_relations_cooccurrence,
    build_relations_from_chunks,
    get_relation_stats,
    auto_build_relations,
)

__all__ = [
    "extract_relations_cooccurrence",
    "build_relations_from_chunks",
    "get_relation_stats",
    "auto_build_relations",
]
