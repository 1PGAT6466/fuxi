"""
伏羲 v1.44 — Dashboard API 模块

实现：
- GET /api/dashboard/stats - 获取统计
- GET /api/dashboard/activity - 获取最近活动
- GET /api/dashboard/system - 获取系统资源
- GET /api/dashboard/insights - 获取数据洞察
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from src.api.response import error, server_error, success
from src.auth.rbac import get_current_user_role, require_role

logger = logging.getLogger("api.dashboard")

router = APIRouter()


@router.get("/api/dashboard/stats")
async def get_dashboard_stats(request: Request):
    """获取仪表板统计"""
    try:
        # 从 tasks.db 获取任务统计
        import sqlite3
        from pathlib import Path

        from src.config import DATA_DIR

        tasks_db = Path(DATA_DIR) / "tasks.db"
        stats = {"pending": 0, "in_progress": 0, "completed": 0, "failed": 0, "total": 0}

        if tasks_db.exists():
            conn = sqlite3.connect(str(tasks_db))
            cursor = conn.cursor()

            # 检查 tasks 表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
            if cursor.fetchone():
                cursor.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
                for row in cursor.fetchall():
                    status, count = row
                    if status in stats:
                        stats[status] = count
                    stats["total"] += count

            conn.close()

        return success(data=stats)
    except Exception as e:
        logger.error(f"获取仪表板统计失败: {e}")
        return server_error(detail=str(e))


@router.get("/api/dashboard/activity")
async def get_dashboard_activity(request: Request):
    """获取最近活动/任务"""
    try:
        # 从 tasks.db 获取最近任务
        import sqlite3
        from pathlib import Path

        from src.config import DATA_DIR

        tasks_db = Path(DATA_DIR) / "tasks.db"
        recent_tasks = []

        if tasks_db.exists():
            conn = sqlite3.connect(str(tasks_db))
            cursor = conn.cursor()

            # 获取所有表名
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            if "tasks" in tables:
                cursor.execute("""
                    SELECT id, title, type, status, progress, created_at, completed_at, '系统', 'normal'
                    FROM tasks
                    ORDER BY created_at DESC
                    LIMIT 10
                """)

                for row in cursor.fetchall():
                    recent_tasks.append(
                        {
                            "id": str(row[0]) if row[0] else "",
                            "name": row[1] or "",
                            "type": row[2] or "",
                            "status": row[3] or "pending",
                            "progress": row[4] or 0,
                            "createdAt": row[5] or "",
                            "updatedAt": row[6] or "",
                            "createdBy": row[7] or "系统",
                            "priority": row[8] or "normal",
                        }
                    )

            conn.close()

        return success(data={"recent_tasks": recent_tasks, "total": len(recent_tasks)})
    except Exception as e:
        logger.error(f"获取最近活动失败: {e}")
        return server_error(detail=str(e))


@router.get("/api/dashboard/system")
async def get_dashboard_system(request: Request):
    """获取系统资源状态"""
    try:
        import psutil

        # CPU 信息
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()

        # 内存信息
        memory = psutil.virtual_memory()

        # 磁盘信息
        disk = psutil.disk_usage("/")

        return success(
            data={
                "cpu": {"usage": cpu_percent, "cores": cpu_count, "temperature": None},  # 需要额外硬件支持
                "memory": {
                    "used": f"{memory.used / (1024**3):.1f} GB",
                    "total": f"{memory.total / (1024**3):.1f} GB",
                    "usagePercent": memory.percent,
                },
                "disk": {
                    "used": f"{disk.used / (1024**3):.1f} GB",
                    "total": f"{disk.total / (1024**3):.1f} GB",
                    "usagePercent": disk.percent,
                },
            }
        )
    except Exception as e:
        logger.error(f"获取系统资源失败: {e}")
        return server_error(detail=str(e))


@router.get("/api/dashboard/insights")
async def get_dashboard_insights(request: Request):
    """获取数据洞察"""
    try:
        # 这里可以实现数据洞察逻辑
        # 目前返回空数据
        return success(
            data={
                "trends": [],
                "anomalies": [],
                "insights": [],
                "healthScore": 100,
                "updatedAt": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"获取数据洞察失败: {e}")
        return server_error(detail=str(e))
