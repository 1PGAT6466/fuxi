"""
integrated_search.py — Phase 5.5: 三方协同检索
文档检索 + 知识图谱 + Wiki 融合
"""
import logging, json
from typing import Dict, List

logger = logging.getLogger(__name__)


async def integrated_search(query: str, top_k: int = 10) -> Dict:
    """
    三方协同检索：
    1. 向量+BM25 混合检索（碎片级）
    2. 知识图谱查询（关系级）
    3. Wiki 召回（总结级）
    """
    results = {}
    
    # 1. 文档混合检索
    try:
        from src.services.retrieval import hybrid_search
        from src.db.data_store import load_chunks
        doc_results = await hybrid_search(query, load_chunks(), top_k=top_k)
        results["documents"] = doc_results[:top_k]
    except Exception as e:
        logger.warning(f"[Integrated] Doc search failed: {e}")
        results["documents"] = []
    
    # 2. 知识图谱
    try:
        from src.services.graph_router import get_entity_context
        graph_ctx = get_entity_context(query)
        results["graph"] = {"context": graph_ctx} if graph_ctx else {}
    except Exception as e:
        logger.warning(f"[Integrated] Graph search failed: {e}")
        results["graph"] = {}
    
    # 3. Wiki 召回
    try:
        from src.services.wiki import get_wiki_engine
        we = get_wiki_engine()
        wiki_results = we.search_content(query, limit=3)
        results["wiki"] = wiki_results
    except Exception as e:
        logger.warning(f"[Integrated] Wiki search failed: {e}")
        results["wiki"] = []
    
    # 融合上下文
    context_parts = []
    for r in results.get("documents", [])[:5]:
        context_parts.append(f"[Doc] {r.get('file_name', '?')}: {r.get('text', '')[:300]}")
    
    if results.get("graph", {}).get("context"):
        context_parts.append(f"[知识图谱] {results['graph']['context'][:500]}")
    
    for w in results.get("wiki", [])[:2]:
        context_parts.append(f"[Wiki] {w.get('title', '?')}: {w.get('content', '')[:300]}")
    
    results["merged_context"] = "\n\n---\n\n".join(context_parts)
    results["total_count"] = len(results.get("documents", [])) + len(results.get("wiki", []))
    
    return results
