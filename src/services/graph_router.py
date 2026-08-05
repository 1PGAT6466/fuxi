"""
services/graph_router.py — 知识图谱路由兼容层（v1.50）
重定向到 src.taiyang.graph_router。
"""

import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

from src.taiyang.graph_router import (  # noqa: F401
    validate_graph_relation,
    normalize_entity,
    load_graph,
    route_to_categories,
    fuzzy_match_entity,
    detect_query_intent,
    route_entity_with_neighbors,
    get_entity_context,
    expand_query_with_synonyms,
    multi_hop_search,
)

__all__ = [
    "validate_graph_relation",
    "normalize_entity",
    "load_graph",
    "route_to_categories",
    "fuzzy_match_entity",
    "detect_query_intent",
    "route_entity_with_neighbors",
    "get_entity_context",
    "expand_query_with_synonyms",
    "multi_hop_search",
]
