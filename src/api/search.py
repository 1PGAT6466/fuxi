"""
routers/search.py — 搜索路由（v10.0）
负责：/api/search, /api/search-history, /api/images/*
"""
import asyncio
from src.services.audit import log_audit
import logging
logger = logging.getLogger(__name__)
import os, time, json, hashlib

from datetime import datetime
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from src.config import KB_IMAGES_DIR, DATA_DIR
from src.db.data_store import load_chunks, log_search, search_history, load_graph
from src.services.retrieval import hybrid_search
from src.services.query_router import route_query, DIRECT_REPLIES
from src.db.memory_store import get_store

router = APIRouter(tags=["搜索"])



@router.get("/api/search")
async def search(q: str = Query(...), top_k: int = 15, page: int = 1, page_size: int = 8,
                 category: str = Query(""), file_type: str = Query(""),
                 date_from: str = Query(""), date_to: str = Query("")):
    """混合检索（BM25 + 向量 + RRF + Rerank）"""
    t0 = time.time()
    log_audit("search", query=q)
    # D5: metrics
    from src.services.metrics import inc_counter, observe_histogram
    
    # RAG 3.0: 入口层缓存
    try:
        from src.services.cache import get_cache as _cache_get, set_cache as _cache_set
        cached = await _cache_get(q, category, top_k)
        if cached:
            # metrics: 缓存命中
            from src.services.metrics import record_search, record_cache
            record_cache(hit=True, level="L1")
            record_search("success", time.time()-t0, len(cached))
            return {"results": cached[:page_size], "query": q, "page": 1, "page_size": page_size,
                    "total": len(cached), "total_pages": 1, "has_more": False, "_from_cache": True}
    except Exception as e:

        logger.warning("suppressed exception", exc_info=True)
    route_info = route_query(q)
    if route_info["action"] == "direct":
        return {
            "results": [{
                "text": DIRECT_REPLIES.get(route_info["route"], DIRECT_REPLIES["chat"]),
                "score": 10, "file_name": "系统回复",
                "text_preview": DIRECT_REPLIES["chat"][:100]
            }],
            "query": q, "page": 1, "page_size": 1, "total": 1,
            "total_pages": 1, "has_more": False, "_route": route_info["route"]
        }
    strategy = route_info.get("strategy", {})
    if not category and strategy.get("category_weight"):
        category = strategy["category_weight"]
    # v11.40 P1.3: Query 改写层 — 已集成到 retrieval.py llm_rewrite_query
    _search_q = q  # LLM rewrite is now done inside hybrid_search pipeline
    # CRAG 校验环包装
    async def _search_with_rewrite(rewritten_q, k, skip_cache=False):
        try:
            return await asyncio.wait_for(
                hybrid_search(rewritten_q, load_chunks(), category, file_type, date_from, date_to, k, skip_cache=skip_cache),
                timeout=15.0
            )
        except (asyncio.TimeoutError, Exception):
            return []
    
    try:
        from src.services.crag import retrieve_with_correction
        crag_result = await retrieve_with_correction(
            query=q,
            retriever=lambda qq, kk=top_k: _search_with_rewrite(qq, kk, skip_cache=True),
            top_k=top_k,
            max_retries=1
        )
        results = crag_result["docs"]
        if crag_result["degraded"]:
            inc_counter("kb_crag_degraded_total")
    except Exception as e:
        import logging; logging.getLogger(__name__).exception("Exception in routers/search.py")
        import traceback, logging
        logging.getLogger(__name__).error(f'hybrid_search failed: {e}\n{traceback.format_exc()}')
        try:
            results = await hybrid_search(q, load_chunks(), category, file_type, date_from, date_to, top_k)
        except Exception as e2:
            import logging; logging.getLogger(__name__).exception("Exception in routers/search.py")
            logging.getLogger(__name__).error(f'hybrid_search retry also failed: {e2}')
            results = []
    # P1.1.2: Self-RAG 相关性校验
    try:
        from src.services.self_rag import check_relevance
        sr = await check_relevance(q, results)
        if not sr["is_relevant"]:
            logger.info(f"[Self-RAG] 低相关性，触发 CRAG 改写: {sr['reason']}")
            from src.services.crag import retrieve_with_correction
            crag_result = await retrieve_with_correction(
                query=q,
                retriever=lambda qq, kk=top_k: _search_with_rewrite(qq, kk, skip_cache=True),
                top_k=top_k,
                max_retries=1
            )
            if crag_result["docs"]:
                results = crag_result["docs"]
    except Exception as e:
        logger.warning(f"[Self-RAG] 校验失败，使用原始结果: {e}")
    
    inc_counter("kb_search_requests_total")
    observe_histogram("kb_search_latency_seconds", time.time() - t0)
    # P3.5: 记录搜索经验（异步，不阻塞返回）
    try:
        from src.services.memory import record_experience
        record_experience(
            action="search",
            detail=f"query={q[:80]} results={len(results)} ms={round((time.time()-t0)*1000,1)}",
            outcome="ok" if len(results)>0 else "empty",
            tags=["search", f"count:{len(results)}"]
        )
    except Exception as e:

        logger.warning("suppressed exception", exc_info=True)
    log_search(q, len(results), (time.time() - t0) * 1000,
               [{"hash": r.get("file_hash", ""), "idx": r.get("chunk_index", 0),
                 "score": r.get("score", 0), "file": r.get("file_name", "")}
                for r in results[:5]])
    start = (page - 1) * page_size
    paged = results[start:start + page_size]
    
    # P0-1: 父子分块 — 命中子块时自动附上父块完整上下文
    # P0-1: parent lookup via MemoryStore (no need for extra import)
    for r in paged:
        chunk_type = r.get('chunk_type', '')
        original_parent_index = r.get('parent_idx', r.get('parent_id'))
        if chunk_type == 'child' and original_parent_index is not None:
            # 查找同一文档的父块（按 parent_idx）
            try:
                parent_candidates = get_store().get_by_hash(r.get('file_hash', ''))
                for pc in parent_candidates:
                    pc_type = pc.get('chunk_type', '')
                    pc_parent_idx = pc.get('parent_idx', -1)
                    if pc_type == 'parent' and pc_parent_idx == original_parent_index:
                        r['parent_context'] = pc.get('text', '')[:3000]
                        r['parent_section'] = pc.get('section_path', '')
                        break
            except Exception:
                logger.warning(f"[search] suppressed exception", exc_info=True)
                pass
    
    if paged:
        _has_rerank = any(r.get("_rerank_score", 0) > 0 for r in paged)
        if _has_rerank:
            _scores = [r.get("_rerank_score", 0) for r in paged]
            _low_confidence = all(s < 3.5 and s >= 0 for s in _scores)
        else:
            _low_confidence = False
        if _low_confidence:
            # 不阻断结果，仅标记低置信度警告
            for r in paged:
                r["_low_confidence"] = True
    

    # P0: 三层分离 — wiki_results / chunk_results / graph_context
    wiki_hits = [r for r in paged if r.get("_source") == "wiki"]
    chunk_hits = [r for r in paged if r.get("_source") != "wiki"]
    
    # 图谱上下文（从第一个 wiki hit 或 chunk 提取）
    graph_ctx = {"entities": [], "categories": [], "wiki_links": []}
    for r in paged[:5]:
        if r.get("_wiki_id"):
            graph_ctx["wiki_links"].append({
                "wiki_id": r["_wiki_id"],
                "title": r.get("_wiki_title", ""),
                "similarity": r.get("score", 0)
            })
        if r.get("category") and r["category"] not in graph_ctx["categories"]:
            graph_ctx["categories"].append(r["category"])
    if route_info.get("entities"):
        graph_ctx["entities"] = route_info["entities"]
    
    tp = max(1, (len(results) + page_size - 1) // page_size)
    
    # RAG 3.0: 写入缓存
    try:
        await _cache_set(q, results, category, top_k)
    except Exception as e:

        logger.warning("suppressed exception", exc_info=True)
    # 低置信度检测 & 反思标记
    reflection = {"needs_retry": False, "suggestions": []}
    if len(results) == 0:
        reflection["needs_retry"] = True
        reflection["suggestions"].append("零结果：建议缩短查询词或更换关键词")
    elif all(r.get('score', 0) < 3.0 for r in results[:3]):
        reflection["needs_retry"] = True
        reflection["suggestions"].append("低分结果：建议扩宽检索范围")
    
    # Wiki 推荐卡片（搜索结果关联 Wiki 知识）
    wiki_recommend = []
    for wh in wiki_hits[:3]:
        wiki_recommend.append({
            "id": wh.get("_wiki_id", ""),
            "title": wh.get("_wiki_title", wh.get("text", "")[:60]),
            "category": wh.get("category", ""),
            "similarity": round(wh.get("score", 0), 2)
        })
    
    return {
        "wiki_results": wiki_hits,
        "chunk_results": chunk_hits,
        "wiki_recommend": wiki_recommend,
        "graph_context": graph_ctx,
        "reflection": reflection,
        "query": q, "page": page, "page_size": page_size,
        "total": len(results), "total_pages": tp, "has_more": page < tp,
        "_route": route_info["route"],
        "_rewritten_query": _search_q if _search_q != q else None,
    }



@router.get("/api/search/chunk/{file_name}")
async def view_chunk(file_name: str, chunk_index: int = 0):
    from urllib.parse import unquote
    fname = unquote(file_name)
    # Try SQLite store first (v11.40+), fallback to JSON
    store = get_store()
    try:
        chunks = store.get_by_file_name(fname)
        if chunks:
            chunk = chunks[min(chunk_index, len(chunks)-1)]
            return {
                "file_name": chunk.get("file_name", fname),
                "chunk_index": chunk.get("chunk_index", 0),
                "text": chunk.get("text", ""),
                "category": chunk.get("category", ""),
                "file_hash": chunk.get("file_hash", ""),
            }
    except Exception:
        logger.warning(f"[search] suppressed exception", exc_info=True)
        pass
    # Fallback to JSON
    chunks = [x for x in load_chunks() if x.get("file_name") == fname]
    if not chunks:
        raise HTTPException(status_code=404, detail=f"Not found: {fname}")
    chunk = next((x for x in chunks if x.get("chunk_index") == chunk_index), chunks[0])
    return {
        "file_name": chunk.get("file_name"),
        "chunk_index": chunk.get("chunk_index", 0),
        "text": chunk.get("text", ""),
        "category": chunk.get("category", ""),
        "file_hash": chunk.get("file_hash", ""),
    }

@router.get("/api/search/summarize")
async def summarize_chunk(file_name: str = Query(...), chunk_index: int = Query(0)):
    from urllib.parse import unquote
    from src.services.llm import call_ai
    fname = unquote(file_name)
    chunks = [x for x in load_chunks() if x.get("file_name") == fname and x.get("chunk_index") == chunk_index]
    if not chunks:
        chunks = [x for x in load_chunks() if x.get("file_name") == fname]
    if not chunks:
        raise HTTPException(status_code=404)
    text = chunks[0].get("text", "")[:2000]
    prompt = f"请用1-3句话精炼总结以下文档片段，提取关键数据，中文输出，不超过100字：\n{text}"
    try:
        summary = await call_ai(prompt)
        return {"summary": summary, "ok": True}
    except Exception:
        return {"summary": text[:200] + "...", "ok": False, "fallback": True}

@router.get("/api/search-history")
async def api_search_history():
    """搜索历史（近 7 天）"""
    return search_history()


@router.get("/api/images/{img_name}")
async def serve_image(img_name: str):
    """图片服务（原始/缩略图）"""
    if ".." in img_name or "/" in img_name:
        raise HTTPException(status_code=400)
    thumb_path = os.path.join(KB_IMAGES_DIR, "thumbs", img_name)
    if os.path.isfile(thumb_path):
        return FileResponse(thumb_path, media_type="image/jpeg")
    img_path = os.path.join(KB_IMAGES_DIR, img_name)
    if not os.path.isfile(img_path):
        raise HTTPException(status_code=404, detail=f"图片不存在: {img_name}")
    import mimetypes
    mime, _ = mimetypes.guess_type(img_path)
    return FileResponse(img_path, media_type=mime or "image/png")
