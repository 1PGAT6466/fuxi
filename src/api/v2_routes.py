# 兼容层 - v2路由
import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["v2"])


@router.get("/api/v2/status")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def v2_status():
    """v2状态"""
    from src.api.response import server_error

    try:
        return {"status": "ok"}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"v2_status 失败: {e}")
        return server_error(detail=str(e))
