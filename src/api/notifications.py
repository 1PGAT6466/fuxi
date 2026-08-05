"""
v2.1 — 通知中心 API（真实数据版）
数据来源：audit_log 中的用户操作记录 + 运行时事件
"""

import json
import logging
import os
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["通知中心"])

# 通知持久化路径
_NOTIFICATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "notifications",
)
_NOTIFICATIONS_FILE = os.path.join(_NOTIFICATIONS_DIR, "notifications.json")


def _ensure_notifications_dir():
    os.makedirs(_NOTIFICATIONS_DIR, exist_ok=True)


def _load_notifications() -> list:
    """从文件加载通知（如果没有持久化，则从审计日志生成）"""
    _ensure_notifications_dir()
    notifications = []
    if os.path.exists(_NOTIFICATIONS_FILE):
        try:
            with open(_NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
                notifications = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    # 如果没有持久化通知，从审计日志实时生成系统通知
    if not notifications:
        notifications = _generate_system_notifications()

    # 按时间倒序
    notifications.sort(key=lambda n: n.get("timestamp", 0), reverse=True)
    return notifications


def _generate_system_notifications() -> list:
    """从系统状态生成基础通知"""
    notifications = []

    # 1. 检查数据状态
    try:
        from src.db.data_store import load_chunks

        chunks = load_chunks() or []
        seed_count = sum(
            1
            for c in chunks
            if "test_knowledge" in (c.get("file_name", "") or "").lower()
            or "malware" in (c.get("file_name", "") or "").lower()
        )
        if len(chunks) == 0:
            notifications.append(
                {
                    "id": "sys-empty-db",
                    "type": "system",
                    "title": "知识库为空",
                    "content": "尚未上传任何文档。前往文件管理页面开始上传。",
                    "read": False,
                    "priority": "high",
                    "timestamp": time.time(),
                }
            )
        elif seed_count == len(chunks):
            notifications.append(
                {
                    "id": "sys-seed-only",
                    "type": "system",
                    "title": "仅有示例数据",
                    "content": f"当前仅包含 {seed_count} 条示例/测试数据。上传真实业务文档以启用完整功能。",
                    "read": False,
                    "priority": "medium",
                    "timestamp": time.time(),
                }
            )
    except ImportError:
        notifications.append(
            {
                "id": "sys-db-unavailable",
                "type": "system",
                "title": "数据库模块不可用",
                "content": "chunks.db 查询失败，请检查系统状态。",
                "read": False,
                "priority": "critical",
                "timestamp": time.time(),
            }
        )
    except Exception as e:  # TODO: Narrow exception type
        logger.warning(f"生成通知时查询数据失败: {e}")

    # 2. 检查评测状态
    try:
        import asyncio

        from src.services.eval_automation import get_eval_automation

        automation = get_eval_automation()
        # FAKE-ASYNC: 在同步上下文中调用 async 方法
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 事件循环已在运行，无法同步等待异步结果
                report = None
            else:
                report = loop.run_until_complete(automation.get_latest_report())
        except RuntimeError:
            report = None

        if not report or not report.get("timestamp"):
            notifications.append(
                {
                    "id": "sys-eval-never",
                    "type": "system",
                    "title": "评测尚未执行",
                    "content": "建议运行评测以建立质量基线。前往评测页面或调用 API /api/eval/run。",
                    "read": False,
                    "priority": "low",
                    "timestamp": time.time(),
                }
            )
    except ImportError:
        pass
    except Exception as e:  # TODO: Narrow exception type
        logger.warning(f"生成评测通知失败: {e}")

    # 3. 检查审计日志
    try:
        from src.infra.audit_log import get_audit_stats

        stats = get_audit_stats(days=1)
        if stats.get("total_entries", 0) > 0:
            notifications.append(
                {
                    "id": "sys-audit-activity",
                    "type": "info",
                    "title": "系统活动摘要",
                    "content": f"过去24小时有 {stats['total_entries']} 条操作记录。",
                    "read": False,
                    "priority": "low",
                    "timestamp": time.time(),
                }
            )
    except ImportError:
        pass
    except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:  # TODO: Narrow exception type
        pass

    return notifications


def _save_notifications(notifications: list):
    """持久化通知"""
    _ensure_notifications_dir()
    try:
        with open(_NOTIFICATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(notifications, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.warning(f"保存通知失败: {e}")


@router.get("/api/notifications")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def list_notifications(
    request: Request = None,
    page: int = 1,
    page_size: int = 20,
    unread_only: bool = False,
):
    """获取通知列表 — v1.50 真实数据版

    通知来源（按优先级）：
      1. 持久化通知文件 (data/notifications/notifications.json)
      2. 系统状态自动生成（审计日志、数据状态、评测状态）
    """
    try:
        import asyncio as _aio

        notifications = await _aio.to_thread(_load_notifications)

        if unread_only:
            notifications = [n for n in notifications if not n.get("read", False)]

        total = len(notifications)
        unread_count = sum(1 for n in _load_notifications() if not n.get("read", False))

        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        paged = notifications[max(0, start) : end]

        data = {
            "notifications": paged,
            "unread_count": unread_count,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

        # v1.50 R5: 统一返回格式 {status: "ok", data: {...}}
        return {"status": "ok", "data": data}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"list_notifications 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


@router.put("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, request: Request = None) -> JSONResponse:
    """标记通知已读 — 持久化状态"""
    try:
        import asyncio as _aio

        notifications = await _aio.to_thread(_load_notifications)
        found = False
        for n in notifications:
            if n.get("id") == notification_id:
                n["read"] = True
                n["read_at"] = time.time()
                found = True
                break

        if found:
            await _aio.to_thread(_save_notifications, notifications)

        return {"ok": True, "id": notification_id, "read": found}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"mark_notification_read 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


@router.put("/api/notifications/read-all")
async def mark_all_notifications_read(request: Request = None) -> JSONResponse:
    """标记全部已读 — 持久化状态"""
    try:
        import asyncio as _aio

        notifications = await _aio.to_thread(_load_notifications)
        now = time.time()
        count = 0
        for n in notifications:
            if not n.get("read", False):
                n["read"] = True
                n["read_at"] = now
                count += 1

        if count > 0:
            await _aio.to_thread(_save_notifications, notifications)

        return {"ok": True, "read_all": True, "marked_count": count}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"mark_all_read 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


# ============ 通知订阅管理 ============

# 订阅持久化路径
_SUBSCRIPTIONS_FILE = os.path.join(_NOTIFICATIONS_DIR, "subscriptions.json")


def _load_subscriptions() -> dict:
    """加载订阅配置"""
    _ensure_notifications_dir()
    if os.path.exists(_SUBSCRIPTIONS_FILE):
        try:
            with open(_SUBSCRIPTIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_subscriptions(subscriptions: dict):
    """保存订阅配置"""
    _ensure_notifications_dir()
    try:
        with open(_SUBSCRIPTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(subscriptions, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.warning(f"保存订阅配置失败: {e}")


@router.post("/api/notifications/subscribe")
async def subscribe_notification(request: Request = None) -> JSONResponse:
    """订阅通知

    请求体：
      - event_type: str  事件类型（如 "system", "eval", "audit"）
      - channel: str     推送渠道（如 "webhook", "email", "web"）
      - target: str      推送目标（webhook URL、邮箱地址等）
    """
    try:
        import asyncio as _aio

        body = await request.json()
        event_type = body.get("event_type", "").strip()
        channel = body.get("channel", "web").strip()
        target = body.get("target", "").strip()

        if not event_type:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "event_type 不能为空"},
            )

        user_id = getattr(request.state, "user", "anonymous") if hasattr(request, "state") else "anonymous"
        subscriptions = await _aio.to_thread(_load_subscriptions)

        # 生成订阅 ID
        import uuid

        sub_id = str(uuid.uuid4())

        if user_id not in subscriptions:
            subscriptions[user_id] = []

        subscription = {
            "id": sub_id,
            "event_type": event_type,
            "channel": channel,
            "target": target,
            "created_at": time.time(),
            "active": True,
        }
        subscriptions[user_id].append(subscription)

        await _aio.to_thread(_save_subscriptions, subscriptions)

        return {
            "status": "ok",
            "message": "订阅成功",
            "data": {"subscription_id": sub_id, "event_type": event_type},
        }
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"subscribe 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


@router.post("/api/notifications/unsubscribe")
async def unsubscribe_notification(request: Request = None) -> JSONResponse:
    """取消订阅通知

    请求体：
      - subscription_id: str  订阅 ID
    """
    try:
        import asyncio as _aio

        body = await request.json()
        sub_id = body.get("subscription_id", "").strip()

        if not sub_id:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "subscription_id 不能为空"},
            )

        user_id = getattr(request.state, "user", "anonymous") if hasattr(request, "state") else "anonymous"
        subscriptions = await _aio.to_thread(_load_subscriptions)

        user_subs = subscriptions.get(user_id, [])
        found = False
        for sub in user_subs:
            if sub.get("id") == sub_id:
                sub["active"] = False
                sub["unsubscribed_at"] = time.time()
                found = True
                break

        if not found:
            return JSONResponse(
                status_code=404,
                content={"status": "error", "message": "订阅不存在"},
            )

        await _aio.to_thread(_save_subscriptions, subscriptions)

        return {"status": "ok", "message": "已取消订阅", "data": {"subscription_id": sub_id}}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"unsubscribe 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


@router.post("/api/notifications/send")
async def send_notification(request: Request = None) -> JSONResponse:
    """发送通知（管理员专用）

    请求体：
      - event_type: str   事件类型
      - title: str         通知标题
      - content: str       通知内容
      - priority: str      优先级（low/medium/high/critical）
      - target_users: list 目标用户列表（空表示广播）
    """
    try:
        import asyncio as _aio

        from src.api.auth import require_admin

        # 管理员权限检查
        role = getattr(request.state, "role", None) if hasattr(request, "state") else None
        if role != "admin":
            return JSONResponse(
                status_code=403,
                content={"status": "error", "message": "需要管理员权限"},
            )

        body = await request.json()
        event_type = body.get("event_type", "system").strip()
        title = body.get("title", "").strip()
        content = body.get("content", "").strip()
        priority = body.get("priority", "medium").strip()
        target_users = body.get("target_users", [])

        if not title:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "title 不能为空"},
            )

        # 创建通知
        import uuid

        notification = {
            "id": str(uuid.uuid4()),
            "type": event_type,
            "title": title,
            "content": content,
            "read": False,
            "priority": priority,
            "timestamp": time.time(),
            "sender": "admin",
            "target_users": target_users if target_users else "all",
        }

        # 保存通知
        notifications = await _aio.to_thread(_load_notifications)
        notifications.insert(0, notification)
        await _aio.to_thread(_save_notifications, notifications)

        # 检查订阅并推送（webhook 等）
        subscriptions = await _aio.to_thread(_load_subscriptions)
        pushed_count = 0
        for user_id, subs in subscriptions.items():
            for sub in subs:
                if (
                    sub.get("active", False)
                    and sub.get("event_type") == event_type
                    and sub.get("channel") == "webhook"
                    and sub.get("target")
                ):
                    # 异步推送 webhook（不阻塞响应）
                    import asyncio as _asyncio

                    _asyncio.ensure_future(_push_webhook(sub["target"], notification))
                    pushed_count += 1

        return {
            "status": "ok",
            "message": "通知已发送",
            "data": {
                "notification_id": notification["id"],
                "pushed_count": pushed_count,
            },
        }
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"send_notification 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


async def _push_webhook(url: str, notification: dict):
    """推送通知到 webhook"""
    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            payload = {
                "event": "notification",
                "data": notification,
                "timestamp": time.time(),
            }
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status >= 400:
                    logger.warning("Webhook 推送失败 [%s]: HTTP %d", url, resp.status)
    except Exception as e:
        logger.warning("Webhook 推送异常 [%s]: %s", url, e)


@router.get("/api/notifications/preferences")
async def get_notification_preferences() -> JSONResponse:
    """获取通知偏好设置"""
    prefs_file = os.path.join(_NOTIFICATIONS_DIR, "preferences.json")
    if os.path.exists(prefs_file):
        try:
            with open(prefs_file, "r", encoding="utf-8") as f:
                return {"status": "success", "data": json.load(f)}
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass
    # 默认偏好
    default_prefs = {
        "email_enabled": False,
        "push_enabled": True,
        "sound_enabled": True,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
        "categories": {
            "system": True,
            "document": True,
            "knowledge": True,
            "chat": True,
        },
    }
    return {"status": "success", "data": default_prefs}


@router.put("/api/notifications/preferences")
async def update_notification_preferences(request: Request) -> JSONResponse:
    """更新通知偏好设置"""
    body = await request.json()
    prefs_file = os.path.join(_NOTIFICATIONS_DIR, "preferences.json")
    _ensure_notifications_dir()
    try:
        with open(prefs_file, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False, indent=2)
        return {"status": "success", "message": "偏好已更新"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
