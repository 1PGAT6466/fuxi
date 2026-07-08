"""
v2.1 — 通知中心 API（占位实现）
方案要求：通知中心 API，支持通知列表、标记已读、推送配置
当前状态：后端占位实现，返回空列表
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter(tags=["通知中心"])


@router.get("/api/notifications")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def list_notifications(
    request: Request = None,
    page: int = 1,
    page_size: int = 20,
    unread_only: bool = False,
):
    """获取通知列表（占位实现）"""
    try:
        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        data = {
            "notifications": [],
            "unread_count": 0,
            "total": 0,
            "page": page,
            "page_size": page_size,
        }
        if _wants_v2:
            from src.api.response import success
            return success(data=data, message="通知列表")
        return data
    except Exception as e:
        logger.exception(f"list_notifications 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


@router.put("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, request: Request = None):
    """标记通知已读（占位实现）"""
    return {"ok": True, "id": notification_id, "read": True}


@router.put("/api/notifications/read-all")
async def mark_all_notifications_read(request: Request = None):
    """标记全部已读（占位实现）"""
    return {"ok": True, "read_all": True}
