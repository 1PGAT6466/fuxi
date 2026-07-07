# v1.50 统一响应格式 — 搜索路由
from fastapi import APIRouter, Query, Request

router = APIRouter(tags=["搜索"])

@router.get("/api/search")
async def search(q: str = Query(...), top_k: int = 15, page: int = 1, page_size: int = 8, granularity: str = Query("chunk", description="检索粒度: chunk/event/auto"), request: Request = None):
    """搜索端点 — v1.50 统一响应格式支持
    
    新增 granularity 参数（任务 4）：
      - 'chunk': chunk 粒度检索（默认，向后兼容）
      - 'event': event 粒度检索（返回 event→chunk 映射结果）
      - 'auto': 根据查询复杂度自动选择
    """
    from src.api.response import success, error, server_error
    try:
        from src.taiyang.retrieval import hybrid_search, event_search
        
        if granularity == "event":
            # Event 粒度检索
            event_result = await event_search(q, top_k=top_k)
            results = event_result.get("mapped_chunks", [])
        else:
            # Chunk 粒度（默认）/ auto
            results = await hybrid_search(q, top_k=top_k, granularity=granularity)
        wiki_hits = [r for r in results if r.get("_source") == "wiki"]
        chunk_hits = [r for r in results if r.get("_source") != "wiki"]
        
        # 合并所有结果到 results 字段（前端 Vue3 Search.vue 期待 data.results）
        merged_results = wiki_hits + chunk_hits

        # 向后兼容: 默认返回旧格式 {wiki_results, chunk_results, query, page, page_size, total, results}
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            return success(data={
                "wiki_results": wiki_hits,
                "chunk_results": chunk_hits,
                "results": merged_results,
                "query": q,
                "total": len(results),
            }, message="搜索完成")
        # 默认旧格式 — 同时包含 results 字段以兼容前端 Vue3
        return {
            "wiki_results": wiki_hits,
            "chunk_results": chunk_hits,
            "results": merged_results,
            "query": q,
            "page": page,
            "page_size": page_size,
            "total": len(results),
        }
    except Exception as e:
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            return error("搜索失败", status_code=500, detail=str(e))
        return {"wiki_results": [], "chunk_results": [], "query": q, "error": str(e)}

@router.get("/api/search-history")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def search_history():
    return []
