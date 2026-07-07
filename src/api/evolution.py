# 兼容层 - 进化路由
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["进化"])

@router.get("/api/evolution/overview")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def evolution_overview(request: Request = None):
    """进化概览"""
    try:
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"evolution": {}}, message="进化概览")
        return {"evolution": {}}
    except Exception as e:
        logger.exception(f"evolution_overview 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})
