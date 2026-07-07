# 兼容层 - 评测路由
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["评测"])

@router.get("/api/evaluation/overview")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def evaluation_overview(request: Request = None):
    """评测概览"""
    try:
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"search_stats": {}, "rag_eval": {}, "test_cases_count": 0}, message="评测概览")
        return {"search_stats": {}, "rag_eval": {}, "test_cases_count": 0}
    except Exception as e:
        logger.exception(f"evaluation_overview 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})
