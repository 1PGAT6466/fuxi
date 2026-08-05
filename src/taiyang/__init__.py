# src/taiyang/__init__.py
"""太阳·筑基 — 精炼排序中枢

架构说明 (v2.2):
  检索链路已按八卦分工：
    巽卦 (XunGua): 外部搜索（Brave Search API + URL 抓取 + 交叉验证）
                   和本地 ChromaDB 向量检索 (_search_internal)
    坎卦 (KanGua): 检索质量控制（质量评分、免疫过滤、低质清理）
                   注意：坎卦侧重"过滤/减噪"而非"融合/排序"

  RRF 融合和多跳检索仍由 taiyang/ 原生模块提供：
    - taiyang.fusion          → RRF 多路融合
    - taiyang.retrieval       → hybrid_search（完整 L0-L5 检索链）
    - taiyang.rerank          → Cross-encoder 精排
    - taiyang.multi_hop       → 多跳推理检索

  推荐使用方式：
    # 完整 RAG 检索（推荐）
    from src.taiyang.retrieval import hybrid_search
    results = await hybrid_search(query, top_k=10)

    # 外部搜索
    from src.bagua.xun import XunGua
    results = await xun.search_external("Python 3.12 release notes")

    # 免疫过滤
    from src.bagua.kan import KanGua
    clean = kan.filter_by_immune_memory(raw_results)
"""

from src.bagua.xun import XunGua as ExternalSearchBridge
from src.bagua.kan import KanGua as QualityFilterBridge

from .retrieval import hybrid_search, event_search  # 保留旧入口兼容
from .retrieval import TaiyangRetrieval              # 太阳检索管线实例

try:
    from .fusion import rrf_fusion                       # RRF 融合（无卦对应）
except ImportError:
    rrf_fusion = None

try:
    from .rerank import rerank_local as rerank           # 本地精排
except ImportError:
    rerank = None

try:
    from .multi_hop import multi_hop_search               # 多跳检索（无卦对应）
except ImportError:
    multi_hop_search = None

# Phase B 新增模块（伏羲检索架构融合）
# NOTE(F-1): 模块文件名为 entity_guided_recall（"recall" 体现数据面定位），
# 公开 API 函数名为 entity_guided_search（"search" 体现对外检索语义）。
# 两者命名来自不同抽象层次：recall=架构层、search=API 层。保留此命名差异作为架构文档化的有意设计。
from .entity_guided_recall import entity_guided_search, EntityGuidedRecall  # 任务 2
from .entity_guided_recall import entity_guided_search as entity_guided_recall
from .sag_pipeline import execute_sag_pipeline, SAGPipeline  # 任务 3

__all__ = [
    # 桥接
    "ExternalSearchBridge",
    "QualityFilterBridge",
    # 核心检索
    "hybrid_search",
    "event_search",
    "TaiyangRetrieval",
    # 融合与排序
    "rrf_fusion",
    "rerank",
    # 高级检索
    "multi_hop_search",
    "entity_guided_search",
    "entity_guided_recall",
    "EntityGuidedRecall",
    # SAG 管线
    "execute_sag_pipeline",
    "SAGPipeline",
]
