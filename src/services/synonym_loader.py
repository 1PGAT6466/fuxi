"""
services/synonym_loader.py — 同义词加载兼容层（v1.50）
重定向到 src.taiyang.synonym_loader。
"""

import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

from src.taiyang.synonym_loader import (  # noqa: F401
    load_synonyms,
    expand_query_with_synonyms,
    normalize_entity,
)

__all__ = [
    "load_synonyms",
    "expand_query_with_synonyms",
    "normalize_entity",
]
