# PLACEHOLDER: 该服务模块预留扩展，当前无实际逻辑
# v1.50: 已迁移至 src.taiyang.graph_router，此文件仅为向后兼容层
# 新代码请直接使用 src.taiyang.graph_router 或 from src.services import ...
"""
services/graph_router.py — 兼容层（保留：被 query_expansion、results_postprocess、agentic_rag_v2 等引用）
v1.50 HIGH 修复：将 import * 改为显式导入。
"""
from src.taiyang.graph_router import (
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
