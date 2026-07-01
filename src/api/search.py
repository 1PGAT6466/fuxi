# 兼容层 - 搜索路由
from fastapi import APIRouter, Query

router = APIRouter(tags=["搜索"])

@router.get("/api/search")
async def search(q: str = Query(...), top_k: int = 15, page: int = 1, page_size: int = 8):
    """搜索端点"""
    try:
        from src.taiyang.retrieval import hybrid_search
        results = await hybrid_search(q, top_k=top_k)
        wiki_hits = [r for r in results if r.get("_source") == "wiki"]
        chunk_hits = [r for r in results if r.get("_source") != "wiki"]
        return {
            "wiki_results": wiki_hits,
            "chunk_results": chunk_hits,
            "query": q,
            "page": page,
            "page_size": page_size,
            "total": len(results),
        }
    except Exception as e:
        return {"wiki_results": [], "chunk_results": [], "query": q, "error": str(e)}

@router.get("/api/search-history")
async def search_history():
    return []
