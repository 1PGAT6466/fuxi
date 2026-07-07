"""
services/crag_validator.py — CRAG 检索校验环
检索后校验文档质量 → 不通过则改写重试 → 最多 2 轮 → 降级兜底
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

REWRITE_PROMPT = """你是一个搜索改写助手。用户的原始问题是：
"{original_query}"

上一次搜索返回的文档不满足要求，原因是：{reason}

请改写用户问题，使其更容易搜索到相关文档。只输出改写后的问题，不要解释。"""


# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def evaluate_retrieval(query: str, docs: list) -> str:
    """轻量校验：判断检索文档能否回答 query
    
    Returns: "PASS" | "NEED_REWRITE" | "OFF_TOPIC"
    """
    if not docs:
        return "OFF_TOPIC"
    
    # 信号 1：得分阈值 — 优先使用 rerank 分数（0-10），其次原始分数（BM25/RRF）
    raw_scores = [float(d.get("_rerank_score") if d.get("_rerank_score") is not None and d.get("_rerank_score") > 0 else d.get("score", 0)) for d in docs[:5]]
    avg_score = sum(raw_scores) / max(len(docs[:5]), 1)
    if avg_score < 0.5:
        return "NEED_REWRITE"
    
    # 信号 2：文本内容相关性
    query_lower = query.lower()
    hit_count = 0
    for d in docs[:5]:
        text = (d.get('text', '') or '').lower()
        if any(word in text for word in query_lower.split() if len(word) > 1):
            hit_count += 1
    
    if hit_count == 0:
        return "OFF_TOPIC"
    if hit_count < max(len(query_lower.split()), 2) // 2:
        return "NEED_REWRITE"
    
    return "PASS"


async def rewrite_for_retry(original_query: str, reason: str) -> str:
    """失败驱动的问题改写"""
    from src.services.llm import call_ai_raw as call_ai
    prompt = REWRITE_PROMPT.format(original_query=original_query, reason=reason)
    try:
        rewritten = await call_ai(prompt)
        return rewritten.strip().strip('"').strip("'") or original_query
    except Exception as e:
        logger.warning(f"CRAG rewrite failed: {e}, using original query")
        return original_query


async def retrieve_with_correction(query: str, retriever, top_k: int = 20, max_retries: int = 2) -> dict:
    """CRAG 主循环：检索 → 校验 → 改写 → 重试 → 降级
    
    Returns:
        {
            "docs": [...],
            "attempts": 1,
            "degraded": False,
            "verdict": "PASS",
        }
    """
    current_query = query
    history = []
    
    for attempt in range(max_retries + 1):
        docs = await retriever(current_query, top_k)
        
        verdict = await evaluate_retrieval(query, docs)
        history.append({
            "attempt": attempt + 1,
            "query": current_query,
            "docs_count": len(docs),
            "verdict": verdict,
        })
        
        if verdict == "PASS":
            if logger.isEnabledFor(logging.DEBUG):
                logger.info(f"CRAG PASS: attempt {attempt+1} for '{query[:50]}'")
            else:
                logger.info(f"CRAG PASS: attempt {attempt+1}, query_len={len(query)}")
            return {"docs": docs, "attempts": attempt + 1, "degraded": False, "history": history}
        
        if attempt < max_retries:
            reason_map = {
                "NEED_REWRITE": "文档不够精确，缺乏具体细节",
                "OFF_TOPIC": "文档与问题完全无关",
            }
            reason = reason_map.get(verdict, verdict)
            current_query = await rewrite_for_retry(query, reason)
            if logger.isEnabledFor(logging.DEBUG):
                logger.info(f"CRAG RETRY: attempt {attempt+1}/{max_retries} for '{query[:50]}' → '{current_query[:50]}'")
            else:
                logger.info(f"CRAG RETRY: attempt {attempt+1}/{max_retries}, query_len={len(query)}→{len(current_query)}")
    
    # 穷尽重试，降级
    if logger.isEnabledFor(logging.DEBUG):
        logger.warning(f"CRAG DEGRADED: all {max_retries+1} attempts failed for '{query[:50]}'")
    else:
        logger.warning(f"CRAG DEGRADED: all {max_retries+1} attempts failed, query_len={len(query)}")
    return {"docs": docs, "attempts": max_retries + 1, "degraded": True, "history": history}

async def rewrite_and_retry(query: str, bad_docs: list, top_k: int = 10) -> list:
    """CRAG rewrite: LLM rewrites query and retries search. Max 2 retries, then return None (safe fallback)"""
    retries = 0
    while retries < 2:
        try:
            from src.services.llm import call_deepseek
            prompt = f'Original query: {query}\nRewrite this query to improve search results. Output ONLY the rewritten query.'
            new_q = await call_deepseek(prompt, max_tokens=100)
            if not new_q:
                break
            new_q = new_q.strip().strip('"').strip("'")
            if new_q == query:
                retries += 1
                continue
            from src.services.retrieval import hybrid_search
            from src.db.data_store import load_chunks
            results = await hybrid_search(new_q, load_chunks(), top_k=top_k)
            if results:
                return results
        except Exception as e:
            logger.warning(f'[CRAG] Retry {retries+1} failed: {e}')
        retries += 1
    return None
