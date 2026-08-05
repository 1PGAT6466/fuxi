"""
伏羲 v1.44 — Notifications API 模块

实现：
- GET /api/notifications - 获取通知列表
- POST /api/notifications - 创建通知
- PUT /api/notifications/{id}/read - 标记已读
- PUT /api/notifications/read-all - 全部标记已读
- POST /api/notifications/subscribe - 订阅通知
- POST /api/notifications/unsubscribe - 取消订阅
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from src.api.response import error, not_found, server_error, success
from src.auth.rbac import get_current_username, require_role

logger = logging.getLogger("api.notifications")

router = APIRouter()


def _get_notifications_file(username: str) -> Path:
    """获取用户通知文件路径"""
    from src.config import DATA_DIR

    notifications_dir = Path(DATA_DIR) / "notifications"
    notifications_dir.mkdir(parents=True, exist_ok=True)
    return notifications_dir / f"{username}.json"


def _load_notifications(username: str) -> List[Dict]:
    """加载用户通知"""
    notifications_file = _get_notifications_file(username)
    if notifications_file.exists():
        return json.loads(notifications_file.read_text(encoding="utf-8"))
    return []


def _save_notifications(username: str, notifications: List[Dict]):
    """保存用户通知"""
    notifications_file = _get_notifications_file(username)
    notifications_file.write_text(json.dumps(notifications, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("/api/notifications")
@require_role("user")
async def get_notifications(request: Request):
    """获取通知列表"""
    try:
        username = get_current_username(request)
        notifications = _load_notifications(username)

        return success(data={"items": notifications, "total": len(notifications)})
    except Exception as e:
        logger.error(f"获取通知列表失败: {e}")
        return server_error(detail=str(e))


@router.post("/api/notifications")
@require_role("user")
async def create_notification(request: Request):
    """创建通知"""
    try:
        username = get_current_username(request)
        body = await request.json()

        notifications = _load_notifications(username)

        new_notification = {
            "id": f"notif_{len(notifications) + 1}",
            "title": body.get("title", ""),
            "message": body.get("message", ""),
            "type": body.get("type", "info"),
            "read": False,
            "created_at": datetime.now().isoformat(),
        }

        notifications.append(new_notification)
        _save_notifications(username, notifications)

        return success(data=new_notification, status_code=201)
    except Exception as e:
        logger.error(f"创建通知失败: {e}")
        return server_error(detail=str(e))


@router.put("/api/notifications/{notification_id}/read")
@require_role("user")
async def mark_notification_read(notification_id: str, request: Request):
    """标记通知已读"""
    try:
        username = get_current_username(request)
        notifications = _load_notifications(username)

        for notification in notifications:
            if notification.get("id") == notification_id:
                notification["read"] = True
                _save_notifications(username, notifications)
                return success(data=notification)

        return not_found("通知不存在")
    except Exception as e:
        logger.error(f"标记通知已读失败: {e}")
        return server_error(detail=str(e))


@router.put("/api/notifications/read-all")
@require_role("user")
async def mark_all_notifications_read(request: Request):
    """全部标记已读"""
    try:
        username = get_current_username(request)
        notifications = _load_notifications(username)

        for notification in notifications:
            notification["read"] = True

        _save_notifications(username, notifications)

        return success(message="所有通知已标记为已读")
    except Exception as e:
        logger.error(f"全部标记已读失败: {e}")
        return server_error(detail=str(e))


@router.post("/api/notifications/subscribe")
@require_role("user")
async def subscribe_notifications(request: Request):
    """订阅通知"""
    try:
        username = get_current_username(request)
        body = await request.json()

        # 这里可以实现订阅逻辑
        # 目前简单返回成功
        return success(message="订阅成功")
    except Exception as e:
        logger.error(f"订阅通知失败: {e}")
        return server_error(detail=str(e))


@router.post("/api/notifications/unsubscribe")
@require_role("user")
async def unsubscribe_notifications(request: Request):
    """取消订阅通知"""
    try:
        username = get_current_username(request)
        body = await request.json()

        # 这里可以实现取消订阅逻辑
        # 目前简单返回成功
        return success(message="取消订阅成功")
    except Exception as e:
        logger.error(f"取消订阅通知失败: {e}")
        return server_error(detail=str(e))
