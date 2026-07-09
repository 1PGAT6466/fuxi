"""
v2.1 — 通知中心 API（真实数据版）
数据来源：audit_log 中的用户操作记录 + 运行时事件
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging
import time
import os
import json

logger = logging.getLogger(__name__)

router = APIRouter(tags=["通知中心"])

# 通知持久化路径
_NOTIFICATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "notifications",
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
        seed_count = sum(1 for c in chunks if
                         "test_knowledge" in (c.get("file_name", "") or "").lower()
                         or "malware" in (c.get("file_name", "") or "").lower())
        if len(chunks) == 0:
            notifications.append({
                "id": "sys-empty-db",
                "type": "system",
                "title": "知识库为空",
                "content": "尚未上传任何文档。前往文件管理页面开始上传。",
                "read": False,
                "priority": "high",
                "timestamp": time.time(),
            })
        elif seed_count == len(chunks):
            notifications.append({
                "id": "sys-seed-only",
                "type": "system",
                "title": "仅有示例数据",
                "content": f"当前仅包含 {seed_count} 条示例/测试数据。上传真实业务文档以启用完整功能。",
                "read": False,
                "priority": "medium",
                "timestamp": time.time(),
            })
    except ImportError:
        notifications.append({
            "id": "sys-db-unavailable",
            "type": "system",
            "title": "数据库模块不可用",
            "content": "chunks.db 查询失败，请检查系统状态。",
            "read": False,
            "priority": "critical",
            "timestamp": time.time(),
        })
    except Exception as e:  # TODO: Narrow exception type
        logger.warning(f"生成通知时查询数据失败: {e}")

    # 2. 检查评测状态
    try:
        from src.services.eval_automation import get_eval_automation
        import asyncio
        automation = get_eval_automation()
        # FAKE-ASYNC: 在同步上下文中调用 async 方法
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import asyncio as _asyncio
                report = _asyncio.ensure_future(automation.get_latest_report())
            else:
                report = loop.run_until_complete(automation.get_latest_report())
        except RuntimeError:
            report = None

        if not report or not report.get("timestamp"):
            notifications.append({
                "id": "sys-eval-never",
                "type": "system",
                "title": "评测尚未执行",
                "content": "建议运行评测以建立质量基线。前往评测页面或调用 API /api/eval/run。",
                "read": False,
                "priority": "low",
                "timestamp": time.time(),
            })
    except ImportError:
        pass
    except Exception as e:  # TODO: Narrow exception type
        logger.warning(f"生成评测通知失败: {e}")

    # 3. 检查审计日志
    try:
        from src.infra.audit_log import get_audit_stats
        stats = get_audit_stats(days=1)
        if stats.get("total_entries", 0) > 0:
            notifications.append({
                "id": "sys-audit-activity",
                "type": "info",
                "title": "系统活动摘要",
                "content": f"过去24小时有 {stats['total_entries']} 条操作记录。",
                "read": False,
                "priority": "low",
                "timestamp": time.time(),
            })
    except ImportError:
        pass
    except Exception:  # TODO: Narrow exception type
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
        notifications = _load_notifications()

        if unread_only:
            notifications = [n for n in notifications if not n.get("read", False)]

        total = len(notifications)
        unread_count = sum(1 for n in _load_notifications() if not n.get("read", False))

        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        paged = notifications[max(0, start):end]

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
async def mark_notification_read(notification_id: str, request: Request = None):
    """标记通知已读 — 持久化状态"""
    try:
        notifications = _load_notifications()
        found = False
        for n in notifications:
            if n.get("id") == notification_id:
                n["read"] = True
                n["read_at"] = time.time()
                found = True
                break

        if found:
            _save_notifications(notifications)

        return {"ok": True, "id": notification_id, "read": found}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"mark_notification_read 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


@router.put("/api/notifications/read-all")
async def mark_all_notifications_read(request: Request = None):
    """标记全部已读 — 持久化状态"""
    try:
        notifications = _load_notifications()
        now = time.time()
        count = 0
        for n in notifications:
            if not n.get("read", False):
                n["read"] = True
                n["read_at"] = now
                count += 1

        if count > 0:
            _save_notifications(notifications)

        return {"ok": True, "read_all": True, "marked_count": count}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"mark_all_read 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )
