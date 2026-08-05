"""
伏羲 v1.50 — 搜索服务层
=====================
Service layer for search operations: chunk search, hybrid search, KB search.
"""
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


async def search_chunks(
    query: str,
    top_k: int = 5,
    mode: str = "semantic",
    score_threshold: float = 0.0,
    tenant_id: str = "default",
) -> List[Dict[str, Any]]:
    """搜索 chunks，优先使用 taiyang retrieval，失败回退到 ChromaDB 直接搜索
    v1.44 R2: 多租户隔离 — 传递 tenant_id 到检索层
    """
    results: List[Dict[str, Any]] = []

    # 尝试 taiyang retrieval
    try:
        from src.taiyang.retrieval import search_chunks as _taiyang_search
        return _taiyang_search(
            query=query,
            top_k=top_k,
            mode=mode,
            score_threshold=score_threshold,
        )
    except ImportError:
        pass
    except Exception as e:  # TODO: Narrow exception type (Appropriate exception types)
        logger.warning(f"taiyang.retrieval 调用失败: {e}")

    # 回退：ChromaDB 直接搜索
    try:
        from src.db.vector_store import get_vector_store, embed_texts
        vs = get_vector_store()
        if vs:
            # 获取查询向量
            q_emb = await embed_texts([query])
            if q_emb and q_emb[0]:
                # v1.44 R2: 租户隔离 — 使用 where 子句
                where_filter = {"tenant_id": tenant_id} if tenant_id != "default" else None
                raw = vs.query(q_emb[0], n_results=top_k, where=where_filter)
                if raw and not raw.get("error"):
                    ids = raw.get("ids", [[]])[0]
                    distances = raw.get("distances", [[]])[0]
                    metadatas = raw.get("metadatas", [[]])[0]
                    documents = raw.get("documents", [[]])[0]
                    for i, (id, dist, meta, doc) in enumerate(zip(ids, distances, metadatas, documents)):
                        sim = 1.0 - float(dist)
                        results.append({
                            "id": id,
                            "text": doc or meta.get("text", ""),
                            "score": round(sim * 10, 2),
                            "metadata": meta,
                            "source": meta.get("source", meta.get("file_name", "")),
                            "file_name": meta.get("file_name", meta.get("source", "")),
                        })
    except Exception as e2:  # TODO: Narrow exception type (ValueError, RuntimeError)
        logger.warning(f"vector_store 回退失败: {e2}")

    return results


async def hybrid_search(
    query: str,
    top_k: int = 15,
    granularity: str = "chunk",
    tenant_id: str = "default",
) -> Dict[str, Any]:
    """混合搜索：combines wiki + chunk results
    v1.44 R2: 多租户隔离 — 传递 tenant_id 到检索层
    """
    try:
        from src.taiyang.retrieval import hybrid_search as _taiyang_hybrid, event_search

        if granularity == "event":
            event_result = await event_search(query, top_k=top_k, tenant_id=tenant_id)
            results = event_result.get("mapped_chunks", [])
        else:
            results = await _taiyang_hybrid(query, top_k=top_k, granularity=granularity, tenant_id=tenant_id)

        wiki_hits = [r for r in results if r.get("_source") == "wiki"]
        chunk_hits = [r for r in results if r.get("_source") != "wiki"]
        merged = wiki_hits + chunk_hits

        return {
            "wiki_results": wiki_hits,
            "chunk_results": chunk_hits,
            "results": merged,
            "query": query,
            "total": len(results),
        }
    except ImportError as e:
        logger.warning(f"taiyang.retrieval 不可用: {e}")
        return {"wiki_results": [], "chunk_results": [], "results": [], "query": query, "total": 0}
    except Exception as e:  # TODO: Narrow exception type (redis.RedisError, ConnectionError)
        logger.warning(f"hybrid_search 失败: {e}")
        return {"wiki_results": [], "chunk_results": [], "results": [], "query": query, "total": 0, "error": str(e)}


def search_knowledge_graph(entity: Optional[str] = None) -> Dict[str, Any]:
    """搜索知识图谱"""
    from src.db.data_store import load_graph

    data = load_graph()
    nodes = data.get("nodes", {})
    edges = data.get("edges", [])

    if entity:
        filtered_nodes = {k: v for k, v in nodes.items() if entity.lower() in k.lower()}
        return {"nodes": filtered_nodes, "edges": edges}
    return {"nodes": nodes, "edges": edges}
