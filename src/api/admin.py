# 兼容层 - 管理路由
from fastapi import APIRouter

router = APIRouter(tags=["管理"])

@router.get("/api/admin/stats")
async def admin_stats():
    """管理统计"""
    return {"ok": True, "chunks": 0, "categories": {}}

@router.get("/api/admin/server-status")
async def server_status():
    """服务器状态"""
    import time
    from src.config import START_TIME
    uptime = time.time() - START_TIME
    return {"ok": True, "uptime_seconds": round(uptime), "uptime_hours": round(uptime/3600, 1)}
