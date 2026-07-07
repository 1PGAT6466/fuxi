import asyncio
"""
query_expansion — 从 retrieval.py 拆分
1.40 天梯计划 P2：上帝类拆分
"""

"""
services/retrieval.py — 混合检索服务（v10.0）
负责：BM25 + 向量双路召回 → RRF 融合 → 精排 → 去重 → 上下文扩展
"""
import logging; logger = logging.getLogger(__name__)
import re, asyncio
from typing import List, Dict

# v11: Concurrent control for ChromaDB
_VECTOR_SEM = asyncio.Semaphore(8)

try:
    import jieba
    jieba.setLogLevel(20)
except ImportError:
    jieba = None

from src.db.memory_store import get_store
from src.db.vector_store import get_vector_store, embed_texts
from src.services.graph_router import route_to_categories, expand_query_with_synonyms, get_entity_context
from src.config import EMBEDDER_URL
from src.services.synonym_loader import load_synonyms
# 兼容别名
_SYNONYM_MAP = load_synonyms()




def expand_query(query: str) -> str:
    """L1: Query 扩展 — jieba 分词 + 同义词注入"""
    rewritten = query
    try:
        if jieba and len(query) <= 20:
            words = list(jieba.cut_for_search(query))
            tokens = [w for w in words if len(w) >= 1]
            for token in tokens:
                token_lower = token.lower()
                if token_lower in _SYNONYM_MAP:
                    tokens.extend(_SYNONYM_MAP[token_lower][:2])
            rewritten = " ".join(tokens)
    except Exception as e:
        logger.warning("expand_query 操作失败: %s", e, exc_info=True)
    return rewritten


async def llm_rewrite_query(query: str) -> str:
    """L1-P2: LLM 驱动的查询改写 — 消歧、补全、术语标准化
    基于 Milvus RAG 增强指南：Query Rewrite 是 Advanced RAG 的必选项。
    """
    if len(query) < 8:
        return query  # 太短不改写
    try:
        from src.services.llm import call_ai_raw
        prompt = (
            "你是一个工业知识库的查询优化器。把用户的原始查询改写成更适合检索的表达。\n"
            "规则：\n"
            "1. 补充缩写（如 PLC→可编程逻辑控制器，PA66→尼龙66）\n"
            "2. 统一术语（如 伺服马达→伺服电机，模架→注塑模具模架）\n"
            "3. 分割复合问题为关键词组合\n"
            "4. 只输出改写后的查询，不要解释\n\n"
            f"原始查询：{query}\n改写查询："
        )
        rewritten = await asyncio.wait_for(
            call_ai_raw(prompt, max_tokens=80), timeout=10.0
        )
        if rewritten and 3 < len(rewritten.strip()) < 200:
            logger.info(f"[LLM Rewrite] '{query}' → '{rewritten.strip()}'")
            return rewritten.strip()
    except Exception as e:
        logger.warning("llm_rewrite_query 操作失败: %s", e, exc_info=True)
    return query


async def hyde_expand_query(query: str) -> str:
    """HyDE 假设文档生成 — 用 LLM 先生成假设答案，再检索
    基于 Milvus RAG 增强指南：HyDE 弥补 query-document 的语义 Gap。
    """
    # 短查询和事实查询跳过 HyDE（没必要生成假设文档）
    if len(query) < 6 or any(kw in query for kw in ("什么", "怎么", "如何", "方法", "步骤", "定义")):
        return ""  # 语义型查询更适合 HyDE，但这里不做复杂判断
    try:
        from src.services.llm import call_ai_raw
        prompt = (
            "你是一个工业知识库助手。根据用户的问题，写一段简短的回答（100字以内），"
            "就像你已经在知识库中找到了答案一样。这段文字将用于搜索相关文档。\n\n"
            f"问题：{query}\n\n假设回答："
        )
        hyde_response = await asyncio.wait_for(
            call_ai_raw(prompt, max_tokens=150), timeout=10.0
        )
        if hyde_response and len(hyde_response.strip()) > 10:
            if logger.isEnabledFor(logging.DEBUG):
                logger.info(f"[HyDE] generated {len(hyde_response)} chars for '{query[:30]}...'")
            else:
                logger.info(f"[HyDE] generated {len(hyde_response)} chars, query_len={len(query)}")
            return hyde_response.strip()
    except Exception as e:
        logger.warning("hyde_expand_query 操作失败: %s", e, exc_info=True)
    return ""


