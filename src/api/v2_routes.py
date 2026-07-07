# 兼容层 - v2路由
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["v2"])

@router.get("/api/v2/status")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def v2_status():
    """v2状态"""
    try:
        return {"status": "ok"}
    except Exception as e:
        logger.exception(f"v2_status 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})
