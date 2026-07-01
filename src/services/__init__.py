"""
services/__init__.py — 兼容层
所有旧的 from src.services.xxx import yyy 仍然工作
四象重构后，这些 import 会重导出到新的位置
"""

# 少阳（消化）
# from src.shaoyang.pipeline import UnifiedPipeline, PipelineResult
# from src.shaoyang.mineru import apply_patches

# 太阳（精炼）
# from src.taiyang.retrieval import hybrid_search, vector_recall
# from src.taiyang.fusion import rrf_fusion, weighted_fusion_adjust
# from src.taiyang.rerank import rerank
# from src.taiyang.cache import get_cache, set_cache
# from src.taiyang.graph import route_to_categories, get_entity_context

# 少阴（决策）
# from src.shaoyin.brain import Brain, Instinct
# from src.shaoyin.composer import compose
# from src.shaoyin.validator import validate
# from src.shaoyin.resolver import resolve_query, compress_history
# from src.shaoyin.router import route_query

# 太阴（接口）
# from src.taiyin.security import sanitize_user_input
# from src.taiyin.flags import load_flags, set_flag, is_enabled
# from src.taiyin.monitor import setup_error_handlers

# Phase 1: 保留原有导入路径，Phase 2 逐步切换到上面的重导出
