"""
伏羲 v1.50 — 联网搜索 API
=========================
提供 Tavily 联网搜索的 HTTP 端点。
API Key 未配置时返回友好提示而非报错。
"""
import logging

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from typing import List, Optional

from src.api.response import success, error

logger = logging.getLogger(__name__)

router = APIRouter(tags=["联网搜索"])


class WebSearchBody(BaseModel):
    q: str
    max_results: int = 5
    search_depth: str = "basic"
    include_answer: bool = True
    include_domains: Optional[List[str]] = None
    exclude_domains: Optional[List[str]] = None


@router.get("/api/web-search")
async def web_search_get(
    q: str = Query(..., description="搜索查询"),
    max_results: int = Query(5, ge=1, le=10, description="最大结果数"),
    search_depth: str = Query("basic", description="搜索深度: basic/advanced"),
    include_answer: bool = Query(True, description="是否包含 AI 摘要"),
    request: Request = None,
):
    """联网搜索（GET）"""
    return await _web_search_impl(q, max_results, search_depth, include_answer)


@router.post("/api/web-search")
async def web_search_post(body: WebSearchBody, request: Request = None):
    """联网搜索（POST）"""
    return await _web_search_impl(
        body.q,
        body.max_results,
        body.search_depth,
        body.include_answer,
        body.include_domains,
        body.exclude_domains,
    )


@router.get("/api/web-search/status")
async def web_search_status():
    """查询联网搜索服务状态"""
    from src.services.web_search import is_available
    available = is_available()
    return success(data={
        "available": available,
        "provider": "tavily",
        "message": "联网搜索服务可用" if available else "Tavily API Key 未配置，联网搜索不可用",
    })


async def _web_search_impl(
    q: str,
    max_results: int = 5,
    search_depth: str = "basic",
    include_answer: bool = True,
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None,
):
    """联网搜索实现"""
    from src.services.web_search import search, is_available

    if not is_available():
        return error(
            "联网搜索不可用：Tavily API Key 未配置",
            status_code=503,
            detail="请在环境变量 TAVILY_API_KEY 中配置 Tavily API Key",
        )

    result = await search(
        query=q,
        max_results=max_results,
        search_depth=search_depth,
        include_answer=include_answer,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
    )

    if not result["success"]:
        return error(result["error"], status_code=502)

    return success(data={
        "answer": result["answer"],
        "results": result["results"],
        "query": result["query"],
        "total": len(result["results"]),
    })
