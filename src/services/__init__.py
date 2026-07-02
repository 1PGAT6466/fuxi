"""
services/__init__.py — 兼容层
所有旧的 from src.services.xxx import yyy 仍然工作
四象重构后，这些 import 会重导出到新的位置
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
from src.taiyang.degradation_chain import DegradationChain
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
from src.taiyin.flags import load_flags, set_flag, is_enabled
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
