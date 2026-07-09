# v1.50 P0 修复 — Wiki路由，从 WikiEngine 实际查询数据
# v1.44 Phase 1 Fix: 新增 POST/PUT/DELETE 端点
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Wiki"])


def _get_wiki_engine():
    """延迟加载 WikiEngine 单例"""
    from src.taiyang.wiki import get_wiki_engine
    return get_wiki_engine()


# ── 任务 B.6: /api/wiki 根路径 — Wiki 首页/目录 ──
@router.get("/api/wiki")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def wiki_home(request: Request = None):
    """Wiki 首页 — 返回目录和页面列表"""
    try:
        engine = _get_wiki_engine()
        pages = engine.list_pages(limit=50)

        # 提取类别
        categories = list(set(p.get("category", "") for p in pages if p.get("category")))

        # 向后兼容格式
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={
                "pages": pages,
                "total": len(pages),
                "categories": categories,
            }, message="获取 Wiki 目录成功")
        return {
            "ok": True,
            "title": "伏羲 Wiki",
            "description": "企业知识认知系统 Wiki",
            "pages": pages,
            "total": len(pages),
            "categories": categories,
        }
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"wiki_home 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


@router.get("/api/wiki/pages")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def wiki_pages(request: Request = None, category: str = "", limit: int = 50):
    """Wiki页面列表 — 从 WikiEngine 实际查询"""
    try:
        engine = _get_wiki_engine()
        pages = engine.list_pages(category=category, limit=limit)

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"pages": pages, "total": len(pages)}, message="获取 Wiki 页面列表成功")
        return {"pages": pages, "total": len(pages)}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"wiki_pages 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


@router.get("/api/wiki/search")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def wiki_search(q: str = Query(""), request: Request = None):
    """Wiki搜索 — 全文搜索标题+内容+标签"""
    try:
        engine = _get_wiki_engine()
        if not q.strip():
            pages = engine.list_pages(limit=20)
        else:
            # 尝试全文搜索
            pages = engine.search_content(q, limit=20)
            if not pages:
                # fallback 标题搜索
                pages = engine.search_by_title(q, limit=20)

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"pages": pages, "total": len(pages)}, message="Wiki 搜索完成")
        return {"pages": pages, "total": len(pages)}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"wiki_search 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


@router.get("/api/wiki/page/{page_id}")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def wiki_page(page_id: str, request: Request = None):
    """Wiki页面详情 — 从 WikiEngine 获取完整页面内容"""
    try:
        engine = _get_wiki_engine()
        page = engine.get_page(page_id)
        if not page:
            return JSONResponse(status_code=404, content={"error": "页面未找到", "detail": f"Wiki 页面 {page_id} 不存在"})

        # 同时获取关联页面
        linked = engine.get_linked_pages(page_id)
        page["linked_pages"] = linked

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data=page, message="获取 Wiki 页面成功")
        return page
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"wiki_page 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


# ============ v1.44 Phase 1 Fix: Wiki 写操作端点 ============

# ── 路径别名: /api/wiki/{id} → /api/wiki/page/{page_id} ──
@router.get("/api/wiki/{page_id:path}")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def wiki_get_by_id(page_id: str, request: Request = None):
    """Wiki 页面详情 — 路径别名 GET /api/wiki/{id}

    与 /api/wiki/page/{page_id} 等效，适配前端 Vue3 wiki.ts 调用。
    注意：为避免路由冲突，此端点需放在所有 /api/wiki/xxx 具体路径之后。
    """
    # 排除已有子路径
    if page_id in ("pages", "search", "page"):
        return JSONResponse(status_code=404, content={"error": "页面未找到"})
    # 排除以 page/ 开头的路径（会由 wiki_page 处理）
    if page_id.startswith("page/"):
        return await wiki_page(page_id[5:], request)
    return await wiki_page(page_id, request)


class WikiCreateRequest(BaseModel):
    title: str
    content: str
    category: str = ""
    tags: list = []
    sources: list = []
    summary: str = ""


@router.post("/api/wiki")
async def wiki_create(body: WikiCreateRequest, request: Request = None):
    """创建 Wiki 页面"""
    try:
        engine = _get_wiki_engine()
        page_id = engine.create_page(
            title=body.title,
            content=body.content,
            category=body.category,
            tags=body.tags,
            sources=body.sources,
            summary=body.summary,
        )
        page = engine.get_page(page_id)

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data=page, message="Wiki 页面创建成功")
        return {"ok": True, "page": page, "message": "Wiki 页面创建成功"}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"wiki_create 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


@router.put("/api/wiki/{page_id}")
async def wiki_update(page_id: str, request: Request):
    """更新 Wiki 页面"""
    try:
        body = await request.json()
        engine = _get_wiki_engine()

        success_flag = engine.update_page(
            page_id=page_id,
            content=body.get("content"),
            summary=body.get("summary"),
            quality_score=body.get("quality_score"),
        )

        if not success_flag:
            return JSONResponse(
                status_code=404,
                content={"error": "页面未找到", "detail": f"Wiki 页面 {page_id} 不存在"}
            )

        page = engine.get_page(page_id)

        _wants_v2 = request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2"
        if _wants_v2:
            from src.api.response import success
            return success(data=page, message="Wiki 页面更新成功")
        return {"ok": True, "page": page, "message": "Wiki 页面更新成功"}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"wiki_update 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


@router.delete("/api/wiki/{page_id}")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def wiki_delete(page_id: str, request: Request = None):
    """删除 Wiki 页面"""
    try:
        engine = _get_wiki_engine()
        deleted = engine.delete_page(page_id)

        if not deleted:
            return JSONResponse(
                status_code=404,
                content={"error": "页面未找到", "detail": f"Wiki 页面 {page_id} 不存在"}
            )

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data=None, message=f"Wiki 页面 {page_id} 已删除")
        return {"ok": True, "message": f"Wiki 页面 {page_id} 已删除"}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"wiki_delete 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})
