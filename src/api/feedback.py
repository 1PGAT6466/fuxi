# 兼容层 - 反馈路由
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["反馈"])

@router.get("/api/feedback/weekly")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def feedback_weekly(request: Request = None):
    """每周反馈"""
    try:
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"feedbacks": []}, message="每周反馈")
        return {"feedbacks": []}
    except Exception as e:
        logger.exception(f"feedback_weekly 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})

@router.post("/api/feedback")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def feedback(request: Request = None):
    """提交反馈"""
    try:
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"ok": True}, message="反馈提交成功")
        return {"ok": True}
    except Exception as e:
        logger.exception(f"feedback 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})
