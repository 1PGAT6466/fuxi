# v1.50 P0 修复 — Wiki路由，从 WikiEngine 实际查询数据
# v1.44 Phase 1 Fix: 新增 POST/PUT/DELETE 端点
# v1.50 R3 Blue Fix: 添加 XSS 输入过滤 + 越权所有权检查
from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
import logging
import html
import re

logger = logging.getLogger(__name__)

# ── v1.50 R3 Blue: XSS 输入过滤 ──
def _sanitize_html(text: str) -> str:
    """对用户输入进行 HTML 实体编码，防止存储型 XSS。
    
    策略：
    1. 先对 HTML 特殊字符进行实体编码（< > & " '）
    2. 移除潜在的 event handler 属性（onerror/onload 等）
    3. 移除 javascript: 协议链接
    
    注意：
    - Markdown 内容中的代码块使用 ``` 或 ` 包裹，这些符号不会被编码
    - 用户提交的原始 HTML 标签会被转义为无害的文本
    """
    if not text:
        return text
    # 1. HTML 实体编码
    sanitized = html.escape(text, quote=True)
    # 2. 移除潜在的事件处理器属性（防御深层注入）
    sanitized = re.sub(r'\bon\w+\s*=', ' data-blocked=', sanitized, flags=re.IGNORECASE)
    # 3. 移除 javascript: 协议
    sanitized = re.sub(r'javascript\s*:', 'blocked:', sanitized, flags=re.IGNORECASE)
    return sanitized


def _get_current_user(request: Request) -> str:
    """从请求中获取当前用户名"""
    return getattr(request.state, 'user', 'anonymous')


def _get_current_role(request: Request) -> str:
    """从请求中获取当前用户角色"""
    return getattr(request.state, 'role', 'user')


def _check_wiki_ownership(page_id: str, request: Request) -> bool:
    """检查当前用户是否有权限操作指定的 Wiki 页面。
    
    规则：
    - admin 角色：可以操作任意页面
    - 普通用户：只能操作自己创建的页面
    - 页面不存在时：允许创建操作通过（由调用方处理）
    """
    role = _get_current_role(request)
    if role == 'admin':
        return True
    # 普通用户需要检查所有权
    engine = _get_wiki_engine()
    page = engine.get_page(page_id)
    if page is None:
        # 页面不存在，放行（后续操作会返回 404）
        return True
    current_user = _get_current_user(request)
    owner = page.get('author', page.get('created_by', ''))
    if not owner:
        # 旧数据没有 author 字段，拒绝非 admin 操作
        logger.warning(f"[Wiki] 页面 {page_id} 无作者信息，拒绝用户 {current_user} 的操作")
        return False
    return owner == current_user

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


# v1.50 R2 Blue: Wiki 内容大小限制 — 防止超大内容 DoS
MAX_WIKI_CONTENT_LENGTH = 1 * 1024 * 1024  # 1MB
MAX_WIKI_TITLE_LENGTH = 200  # 标题最大字符数

class WikiCreateRequest(BaseModel):
    title: str
    content: str
    category: str = ""
    tags: list = []
    sources: list = []
    summary: str = ""

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 2:
            raise ValueError("标题至少需要2个字符")
        if len(stripped) > MAX_WIKI_TITLE_LENGTH:
            raise ValueError(f"标题长度不能超过{MAX_WIKI_TITLE_LENGTH}个字符")
        return stripped

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        if len(v.encode("utf-8")) > MAX_WIKI_CONTENT_LENGTH:
            raise ValueError(f"内容大小不能超过{MAX_WIKI_CONTENT_LENGTH // 1024 // 1024}MB")
        return v


@router.post("/api/wiki")
async def wiki_create(body: WikiCreateRequest, request: Request = None):
    """创建 Wiki 页面 — v1.50 R3: XSS 输入过滤 + 记录作者"""
    try:
        engine = _get_wiki_engine()
        # v1.50 R3 Blue: 对用户输入进行 XSS 过滤
        sanitized_title = _sanitize_html(body.title)
        sanitized_content = _sanitize_html(body.content)
        sanitized_summary = _sanitize_html(body.summary) if body.summary else ""
        sanitized_tags = [_sanitize_html(t) for t in body.tags] if body.tags else []
        
        # v1.50 R3 Blue: 记录当前用户为页面作者
        author = _get_current_user(request) if request else "anonymous"
        
        page_id = engine.create_page(
            title=sanitized_title,
            content=sanitized_content,
            category=body.category,
            tags=sanitized_tags,
            sources=body.sources,
            summary=sanitized_summary,
            author=author,
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
    """更新 Wiki 页面 — v1.50 R3: XSS 输入过滤 + 所有权检查, v1.50 R4: 乐观锁"""
    try:
        # v1.50 R3 Blue: 越权检查 — 验证所有权
        if not _check_wiki_ownership(page_id, request):
            return JSONResponse(
                status_code=403,
                content={"error": "权限不足", "detail": "您只能编辑自己创建的 Wiki 页面"}
            )
        
        body = await request.json()
        engine = _get_wiki_engine()
        
        # v1.50 R2 Blue: Wiki 更新内容大小限制
        raw_content = body.get("content")
        if raw_content and len(raw_content.encode("utf-8")) > MAX_WIKI_CONTENT_LENGTH:
            return JSONResponse(
                status_code=400,
                content={"error": "内容过大", "detail": f"内容大小不能超过{MAX_WIKI_CONTENT_LENGTH // 1024 // 1024}MB"}
            )
        
        # v1.50 R4: 乐观锁 — 检查客户端传来的版本号
        client_version = body.get("version")
        
        # v1.50 R3 Blue: 对用户输入进行 XSS 过滤
        sanitized_content = _sanitize_html(raw_content) if raw_content else None
        raw_summary = body.get("summary")
        sanitized_summary = _sanitize_html(raw_summary) if raw_summary else None

        success_flag = engine.update_page(
            page_id=page_id,
            content=sanitized_content,
            summary=sanitized_summary,
            quality_score=body.get("quality_score"),
            expected_version=client_version,
        )

        if not success_flag:
            # 区分 404 和 409（版本冲突）
            page = engine.get_page(page_id)
            if not page:
                return JSONResponse(
                    status_code=404,
                    content={"error": "页面未找到", "detail": f"Wiki 页面 {page_id} 不存在"}
                )
            # 页面存在但版本不匹配 — 并发冲突
            return JSONResponse(
                status_code=409,
                content={
                    "error": "编辑冲突",
                    "detail": "页面已被其他人修改，请刷新后重试",
                    "current_version": page.get("version", 1)
                }
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
    """删除 Wiki 页面 — v1.50 R3: 所有权检查"""
    try:
        # v1.50 R3 Blue: 越权检查 — 验证所有权
        if not _check_wiki_ownership(page_id, request):
            return JSONResponse(
                status_code=403,
                content={"error": "权限不足", "detail": "您只能删除自己创建的 Wiki 页面"}
            )
        
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
