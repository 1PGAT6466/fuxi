"""
self_rag.py — Self-RAG 检索后校验
检查检索结果的相关性，不通过时触发 CRAG 改写重试
"""
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


async def check_relevance(query: str, docs: List[Dict], threshold: float = 0.3) -> Dict:
    """Self-RAG: 检查检索结果与 query 的相关性
    
    Returns:
        {"is_relevant": bool, "score": float, "reason": str}
    """
    if not docs:
        return {"is_relevant": False, "score": 0, "reason": "无检索结果"}
    
    # 信号 1: 分数阈值
    scores = [float(d.get("score", 0)) for d in docs[:5]]
    avg_score = sum(scores) / max(len(scores), 1)
    
    # 信号 2: 关键词命中率
    query_words = [w for w in query.lower().split() if len(w) > 1]
    if not query_words:
        return {"is_relevant": True, "score": avg_score, "reason": "无有效关键词"}
    
    hit_count = 0
    for d in docs[:5]:
        text = (d.get("text", "") or "").lower()
        if any(w in text for w in query_words):
            hit_count += 1
    
    hit_ratio = hit_count / max(len(docs[:5]), 1)
    
    # 综合评分
    combined_score = avg_score * 0.4 + hit_ratio * 0.6
    
    is_relevant = combined_score >= threshold
    
    if not is_relevant:
        logger.info(f"[Self-RAG] 低相关性: score={combined_score:.2f}, hit_ratio={hit_ratio:.2f}, query='{query[:30]}'")
    
    return {
        "is_relevant": is_relevant,
        "score": round(combined_score, 3),
        "reason": f"avg_score={avg_score:.2f}, hit_ratio={hit_ratio:.2f}"
    }
