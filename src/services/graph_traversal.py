"""
services/graph_traversal.py — 知识图谱遍历兼容层（v1.50）
重定向到 src.taiyang.graph_traversal。
"""

import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

from src.taiyang.graph_traversal import (  # noqa: F401
    build_adjacency,
    load_graph,
    invalidate_graph_cache,
    multi_hop_traverse,
    find_paths,
    subgraph,
    get_reachable_entities,
)

__all__ = [
    "build_adjacency",
    "load_graph",
    "invalidate_graph_cache",
    "multi_hop_traverse",
    "find_paths",
    "subgraph",
    "get_reachable_entities",
]
