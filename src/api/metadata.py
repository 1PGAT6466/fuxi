# 兼容层 - 元数据路由
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["元数据"])

@router.get("/api/metadata")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def metadata(request: Request = None):
    """元数据"""
    try:
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"metadata": []}, message="元数据")
        return {"metadata": []}
    except Exception as e:
        logger.exception(f"metadata 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})
