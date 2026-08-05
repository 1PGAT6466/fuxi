"""
services/wiki.py — Wiki 管理兼容层（v1.50）
重定向到 src.taiyang.wiki。
"""

import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

from src.taiyang.wiki import (  # noqa: F401
    WikiEngine,
    get_wiki_engine,
    sync_wiki_vectors,
)

__all__ = [
    "WikiEngine",
    "get_wiki_engine",
    "sync_wiki_vectors",
]
