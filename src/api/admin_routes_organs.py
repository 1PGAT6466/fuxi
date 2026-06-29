"""
/admin/api/admin — 器官状态、活动日志相关 API
"""
from fastapi import APIRouter
import time, logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin-organs"])


@router.get("/api/admin/organ-status")
async def organ_status():
    """器官实时状态"""
    try:
        from src.server import _fuxi_instance
        meridian = _fuxi_instance.meridian if _fuxi_instance else None
        if meridian is None:
            return {"ok": False, "error": "meridian not initialized"}
        stats = meridian.stats()
        organs = []
        for oid, info in meridian._organs.items():
            organs.append({
                "id": oid,
                "name": info.name,
                "emoji": info.emoji,
                "alive": meridian.is_alive(oid),
                "last_heartbeat_ago": round(time.time() - info.last_heartbeat, 1),
                "description": info.description,
            })
        return {
            "ok": True,
            "total_organs": len(organs),
            "alive_count": sum(1 for o in organs if o["alive"]),
            "organs": organs,
            "meridian_stats": stats,
        }
    except Exception as e:
        logger.warning(f"Organ status error: {e}")
        return {"ok": False, "error": str(e)}


@router.get("/api/admin/recent-activities")
async def recent_activities():
    """最近经络信号活动"""
    try:
        from src.server import _fuxi_instance
        meridian = _fuxi_instance.meridian if _fuxi_instance else None
        if meridian is None:
            return {"ok": False, "error": "meridian not initialized", "activities": []}
        history = meridian.get_history(20)
        return {"ok": True, "count": len(history), "activities": history}
    except Exception as e:
        logger.warning(f"Recent activities error: {e}")
        return {"ok": False, "error": str(e), "activities": []}


@router.get("/api/admin/upload-trend")
async def upload_trend():
    """上传趋势"""
    return {"ok": True, "trend": []}


@router.get("/api/admin/error-logs")
async def error_logs():
    """错误日志"""
    return {"ok": True, "logs": []}


@router.get("/api/admin/ai-search-logs")
async def ai_search_logs(page: int = 1, page_size: int = 200):
    """AI 搜索日志"""
    from src.db.data_store import search_history
    try:
        history = search_history(limit=1000)
        return {"ok": True, "total": len(history), "page": page, "logs": history}
    except Exception as e:
        logger.warning(f"Search logs error: {e}")
        return {"ok": False, "error": str(e), "logs": []}
