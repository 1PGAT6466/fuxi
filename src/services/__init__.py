"""
services/__init__.py — 兼容层（v1.50 四象架构迁移中）

所有旧的 `from src.services.xxx import yyy` 仍然工作。
四象重构后，这些 import 会重导出到新的位置。

迁移状态：
  少阳（shaoyang）：消化 — 已迁移 ✅
  太阳（taiyang）：精炼 — 已迁移 ✅
  少阴（shaoyin）：决策 — 已迁移 ✅
  太阴（taiyin）：接口 — 已迁移 ✅

注意：10 个空包装 service 文件（distiller, graph_router, graph_traversal,
multimodal, parsers, relation_builder, security, synonym_loader, table_parser,
wiki）已标记为 PLACEHOLDER，仅保留 import 转发，未来版本将统一删除。

其余 21 个 service 文件（agentic_rag_v2, cache, embedder, evaluator,
eval_automation, eval_dataset, eval_pipeline, eval_updater, evolver,
feature_flags, feedback_store, knowledge_lifecycle, learner, llm, memory,
metrics, online_eval, output_aligner, query_expansion, query_router,
results_postprocess, retrieval, table_view）包含实际业务逻辑，保留不动。
"""

# 少阳（消化）
from src.shaoyang.pipeline import ShaoyangPipeline
from src.shaoyang.extractor import SAGExtractor
from src.shaoyang.kg_extractor import extract_entities_llm, extract_relations_llm
from src.shaoyang.relation_builder import build_relations_from_chunks, auto_build_relations
from src.shaoyang.semantic_chunker import chunk_text
from src.shaoyang.auto_classifier import classify_by_vectors

# 太阳（精炼）
from src.taiyang.retrieval import hybrid_search, TaiyangRetrieval
from src.taiyang.fusion import rrf_fusion, weighted_fusion_adjust
from src.taiyang.rerank import rerank
from src.taiyang.multi_hop import multi_hop_search, SAGMultiHopSearch, seed_score
from src.taiyang.dynamic_alpha import get_dynamic_alpha
from src.taiyang.synonym_loader import load_synonyms
from src.taiyang.cache import get_cache, clear_cache, get_cache_stats
from src.taiyang.l5_crag import L5CRAGExecutor

# 少阴（决策）
from src.shaoyin.brain import ShaoyinBrain
from src.shaoyin.strategy import select_strategy
from src.shaoyin.validator import YinAgent
from src.shaoyin.query_router import classify_query
from src.shaoyin.smart_self_rag import SmartSelfRAG
from src.shaoyin.crag_corrector import CRAGCorrector
from src.shaoyin.judge import judge_answer
from src.shaoyin.fact_check import fact_check, extract_claims, verify_claim
from src.shaoyin.query_resolver import resolve_query, compress_history

# 太阴（接口）
from src.taiyin.server import TaiyinServer
# v2.1: 懒加载打破与 services.feature_flags 的循环引用
# from src.taiyin.flags import load_flags, set_flag, is_enabled
# → 改为通过 __getattr__ 触发（PEP 562）
def __getattr__(name):
    if name in ("load_flags", "set_flag", "is_enabled"):
        from src.taiyin.flags import load_flags, set_flag, is_enabled as _is_enabled
        _mapping = {"load_flags": load_flags, "set_flag": set_flag, "is_enabled": _is_enabled}
        globals()[name] = _mapping[name]
        return _mapping[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
from src.taiyin.security import sanitize_user_input, check_rate_limit, audit_log_entry
from src.taiyin.error_handler import (
    DuplicateFileError, EmbedderUnavailableError, GraphUnavailableError,
    HTTPException, IndexingTimeoutError, InvalidQueryError, KbError,
    LlmUnavailableError, ParseError
)
from src.taiyin.metrics import generate_health_summary, generate_latest
from src.taiyin.growth_api import get_growth_overview, get_symbols_status

# 基础设施
from src.infra.symbol_base import SymbolBase
from src.infra.protocol import SymbolRequest, SymbolResponse
from src.infra.llm import call_ai
from src.infra.trace_logger import TraceLogger
from src.infra.meridian_monitor import MeridianMonitor

# 成长引擎
from src.growth.engine import GrowthEngine

# 数据模型
from src.models import Chunk, Event, Entity, Relation

# Pipeline
from src.pipeline.unified import UnifiedPipeline
