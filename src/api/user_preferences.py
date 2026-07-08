"""
v2.1 — 用户偏好 API（占位实现）
方案要求：用户偏好 CRUD，支持主题、语言、通知设置
当前状态：后端占位实现，返回默认偏好
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user", tags=["用户偏好"])


DEFAULT_PREFERENCES = {
    "theme": "system",
    "language": "zh-CN",
    "notifications_enabled": True,
    "sidebar_collapsed": False,
    "default_engine": "v2",
}


@router.get("/preferences")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def get_user_preferences(request: Request = None):
    """获取当前用户偏好（占位实现）"""
    try:
        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data={"preferences": dict(DEFAULT_PREFERENCES)}, message="用户偏好")
        return {"preferences": dict(DEFAULT_PREFERENCES)}
    except Exception as e:
        logger.exception(f"get_user_preferences 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


@router.put("/preferences")
async def update_user_preferences(request: Request):
    """更新用户偏好（占位实现）"""
    try:
        body = await request.json()
        logger.info(f"[user_preferences] 更新偏好: {body}")
        updated = {**DEFAULT_PREFERENCES, **body}
        return {"preferences": updated, "ok": True}
    except Exception as e:
        logger.exception(f"update_user_preferences 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )
