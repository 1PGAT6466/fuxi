"""
v2.1 — 统一搜索 API（伏羲令，占位实现）
方案要求：跨服务统一搜索，支持自然语言查询
当前状态：后端占位实现，返回空匹配列表
"""
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter(tags=["统一搜索"])


@router.get("/api/unified-search")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def unified_search(
    request: Request = None,
    q: str = Query("", description="搜索关键词"),
):
    """伏羲令统一搜索（占位实现）"""
    try:
        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        data = {
            "query": q,
            "matches": [],
            "total": 0,
            "took_ms": 0,
            "message": "统一搜索功能开发中",
        }
        if _wants_v2:
            from src.api.response import success
            return success(data=data, message="统一搜索")
        return data
    except Exception as e:
        logger.exception(f"unified_search 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )
