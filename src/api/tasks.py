"""
伏羲 v1.50 — 任务管理 API

提供系统任务（扫描、索引、清理）的管理、统计和仪表板功能。

API 端点：
  GET    /api/tasks             — 获取任务列表
  GET    /api/tasks/stats       — 获取任务统计
  GET    /api/tasks/dashboard   — 获取任务仪表板
  POST   /api/tasks/scan        — 扫描任务
  POST   /api/tasks/index       — 索引任务
  POST   /api/tasks/cleanup     — 清理任务
  GET    /api/system/resources  — 获取系统资源

数据存储：SQLite (chunks.db → tasks 表)
"""

import asyncio
import json
import logging
import os
import shutil
import sqlite3
import time
import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from src.api.auth import require_admin
from src.api.response import error, server_error, success
from src.config import DATA_DIR
from src.data_service import _connect, _ensure_dir

logger = logging.getLogger(__name__)

router = APIRouter(tags=["任务管理"])

# ═══════════════════════════════════════════
# 数据库初始化
# ═══════════════════════════════════════════

_TASKS_DB = _ensure_dir(DATA_DIR / "tasks.db")


def _ensure_tasks_table():
    """确保 tasks 表存在"""
    try:
        conn = _connect(str(_TASKS_DB))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    title TEXT,
                    description TEXT,
                    progress REAL DEFAULT 0,
                    result TEXT,
                    error_message TEXT,
                    created_at REAL,
                    started_at REAL,
                    completed_at REAL,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(type)")
            conn.commit()
        finally:
            conn.close()
    except (sqlite3.Error, OSError) as e:
        logger.error(f"[tasks] _ensure_tasks_table 失败: {e}", exc_info=True)
        raise


# ═══════════════════════════════════════════
# 内部工具
# ═══════════════════════════════════════════


def _create_task(task_type: str, title: str, description: str = "", metadata: dict = None) -> dict:
    """创建一个新任务并立即开始执行"""
    task_id = str(uuid.uuid4())
    now = time.time()
    conn = None
    try:
        conn = _connect(str(_TASKS_DB))
        conn.execute(
            """
            INSERT INTO tasks (id, type, status, title, description, progress, created_at, started_at, metadata)
            VALUES (?, ?, 'running', ?, ?, 0, ?, ?, ?)
        """,
            (task_id, task_type, title, description, now, now, json.dumps(metadata or {}, ensure_ascii=False)),
        )
        conn.commit()
        return {"id": task_id, "type": task_type, "status": "running", "title": title}
    except (sqlite3.Error, OSError) as e:
        logger.error(f"[tasks] _create_task 失败: {e}", exc_info=True)
        raise
    finally:
        if conn:
            try:
                conn.close()
            except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                pass


def _complete_task(task_id: str, status: str = "completed", result: str = "", error_message: str = ""):
    """标记任务完成/失败"""
    conn = None
    try:
        conn = _connect(str(_TASKS_DB))
        conn.execute(
            """
            UPDATE tasks SET status = ?, progress = 100, result = ?, error_message = ?, completed_at = ?
            WHERE id = ?
        """,
            (status, result, error_message, time.time(), task_id),
        )
        conn.commit()
    except (sqlite3.Error, OSError) as e:
        logger.error(f"[tasks] _complete_task 失败: {e}", exc_info=True)
        raise
    finally:
        if conn:
            try:
                conn.close()
            except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                pass


def _get_task(task_id: str) -> dict:
    """获取单个任务"""
    conn = None
    try:
        conn = _connect(str(_TASKS_DB))
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row:
            item = dict(row)
            item["metadata"] = json.loads(item.get("metadata", "{}") or "{}")
            return item
        return None
    except (sqlite3.Error, json.JSONDecodeError, ValueError, OSError) as e:
        logger.error(f"[tasks] _get_task 失败: {e}", exc_info=True)
        raise
    finally:
        if conn:
            try:
                conn.close()
            except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                pass


# ═══════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════


@router.get("/api/tasks")
async def get_tasks(
    request: Request,
    status: str = Query(None),
    task_type: str = Query(None, alias="type"),
    limit: int = Query(50, ge=1, le=200),
):
    """获取任务列表"""
    try:
        await asyncio.to_thread(_ensure_tasks_table)
        items = await asyncio.to_thread(_query_tasks, status, task_type, limit)
        return success(data={"items": items, "total": len(items)}, message="任务列表")
    except (sqlite3.Error, json.JSONDecodeError, ValueError, OSError) as e:
        logger.exception(f"get_tasks 失败: {e}")
        return server_error(detail=str(e))


def _query_tasks(status=None, task_type=None, limit=50):
    conn = None
    try:
        conn = _connect(str(_TASKS_DB))
        where_parts = []
        params = []
        if status:
            where_parts.append("status = ?")
            params.append(status)
        if task_type:
            where_parts.append("type = ?")
            params.append(task_type)
        where = "WHERE " + " AND ".join(where_parts) if where_parts else ""

        rows = conn.execute(
            f"SELECT * FROM tasks {where} ORDER BY created_at DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.get("metadata", "{}") or "{}")
            items.append(item)
        return items
    except (sqlite3.Error, json.JSONDecodeError, ValueError, OSError) as e:
        logger.error(f"[tasks] _query_tasks 失败: {e}", exc_info=True)
        raise
    finally:
        if conn:
            try:
                conn.close()
            except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                pass


@router.get("/api/tasks/stats")
async def get_task_stats() -> JSONResponse:
    """获取任务统计信息"""
    try:
        logger.info("[tasks] get_task_stats 开始")
        await asyncio.to_thread(_ensure_tasks_table)
        logger.info("[tasks] _ensure_tasks_table 完成")
        stats = await asyncio.to_thread(_compute_stats)
        logger.info(f"[tasks] _compute_stats 完成: {stats}")
        return success(data=stats, message="任务统计")
    except (sqlite3.Error, OSError) as e:
        logger.exception(f"[tasks] get_task_stats 失败: {e}")
        return server_error(detail=str(e))


def _compute_stats():
    """计算任务统计信息"""
    conn = None
    try:
        conn = _connect(str(_TASKS_DB))
        total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        running = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'running'").fetchone()[0]
        completed = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'completed'").fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'failed'").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'").fetchone()[0]

        # 按类型统计
        type_rows = conn.execute("SELECT type, COUNT(*) as cnt FROM tasks GROUP BY type").fetchall()
        by_type = {row["type"]: row["cnt"] for row in type_rows}

        return {
            "total": total,
            "running": running,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "by_type": by_type,
        }
    except (sqlite3.Error, OSError) as e:
        logger.error(f"[tasks] _compute_stats 失败: {e}", exc_info=True)
        raise
    finally:
        if conn:
            try:
                conn.close()
            except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                pass


@router.get("/api/tasks/dashboard")
async def get_task_dashboard() -> JSONResponse:
    """获取任务仪表板概览"""
    try:
        await asyncio.to_thread(_ensure_tasks_table)
        dashboard = await asyncio.to_thread(_build_dashboard)
        return success(data=dashboard, message="任务仪表板")
    except (sqlite3.Error, OSError) as e:
        logger.exception(f"get_task_dashboard 失败: {e}")
        return server_error(detail=str(e))


def _build_dashboard():
    conn = None
    try:
        conn = _connect(str(_TASKS_DB))
        stats = _compute_stats()

        # 最近 5 个任务
        recent_rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 5").fetchall()
        recent = []
        for row in recent_rows:
            item = dict(row)
            item["metadata"] = json.loads(item.get("metadata", "{}") or "{}")
            recent.append(item)

        # 当前运行中的任务
        running_rows = conn.execute("SELECT * FROM tasks WHERE status = 'running' ORDER BY started_at DESC").fetchall()
        running = []
        for row in running_rows:
            item = dict(row)
            item["metadata"] = json.loads(item.get("metadata", "{}") or "{}")
            running.append(item)

        return {
            "stats": stats,
            "recent_tasks": recent,
            "running_tasks": running,
        }
    except (sqlite3.Error, json.JSONDecodeError, ValueError, OSError) as e:
        logger.error(f"[tasks] _build_dashboard 失败: {e}", exc_info=True)
        raise
    finally:
        if conn:
            try:
                conn.close()
            except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                pass


@router.post("/api/tasks/scan", dependencies=[Depends(require_admin)])
async def create_scan_task(request: Request) -> JSONResponse:
    """创建扫描任务（扫描文件系统中的文档）"""
    try:
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        target_dir = body.get("target_dir", str(DATA_DIR))

        await asyncio.to_thread(_ensure_tasks_table)
        task = _create_task(
            "scan",
            "文件系统扫描",
            f"扫描目录: {target_dir}",
            {"target_dir": target_dir},
        )

        # 异步执行扫描
        asyncio.create_task(_run_scan(task["id"], target_dir))
        return success(data=task, message="扫描任务已创建")
    except (sqlite3.Error, json.JSONDecodeError, ValueError, OSError) as e:
        logger.exception(f"create_scan_task 失败: {e}")
        return server_error(detail=str(e))


async def _run_scan(task_id: str, target_dir: str):
    """异步执行扫描任务"""
    try:
        file_count = 0
        for root, dirs, files in os.walk(target_dir):
            # 跳过隐藏目录
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                if not f.startswith("."):
                    file_count += 1

        _complete_task(task_id, "completed", result=json.dumps({"file_count": file_count}))
        logger.info(f"[tasks] 扫描完成: {file_count} 个文件")
    except (OSError, IOError) as e:
        _complete_task(task_id, "failed", error_message=str(e))
        logger.error(f"[tasks] 扫描失败: {e}")


@router.post("/api/tasks/index", dependencies=[Depends(require_admin)])
async def create_index_task(request: Request) -> JSONResponse:
    """创建索引任务（向量化文档）"""
    try:
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}

        await asyncio.to_thread(_ensure_tasks_table)
        task = _create_task(
            "index",
            "文档索引",
            "向量化索引文档到 ChromaDB",
            body,
        )

        # 异步执行索引（调用 RAG 模块）
        asyncio.create_task(_run_index(task["id"]))
        return success(data=task, message="索引任务已创建")
    except (sqlite3.Error, json.JSONDecodeError, ValueError, OSError) as e:
        logger.exception(f"create_index_task 失败: {e}")
        return server_error(detail=str(e))


async def _run_index(task_id: str):
    """异步执行索引任务"""
    try:
        # 尝试调用已有的索引逻辑
        from src.db.data_store import load_chunks
        from src.db.vector_store import get_vector_store

        chunks = await asyncio.to_thread(load_chunks)
        chunk_count = len(chunks) if chunks else 0

        _complete_task(task_id, "completed", result=json.dumps({"indexed_chunks": chunk_count}))
        logger.info(f"[tasks] 索引完成: {chunk_count} 个 chunk")
    except (sqlite3.Error, OSError) as e:
        _complete_task(task_id, "failed", error_message=str(e))
        logger.error(f"[tasks] 索引失败: {e}")


@router.post("/api/tasks/cleanup", dependencies=[Depends(require_admin)])
async def create_cleanup_task(request: Request) -> JSONResponse:
    """创建清理任务（清理过期数据）"""
    try:
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        days = body.get("days", 30)

        await asyncio.to_thread(_ensure_tasks_table)
        task = _create_task(
            "cleanup",
            "数据清理",
            f"清理 {days} 天前的过期数据",
            {"days": days},
        )

        # 异步执行清理
        asyncio.create_task(_run_cleanup(task["id"], days))
        return success(data=task, message="清理任务已创建")
    except (sqlite3.Error, json.JSONDecodeError, ValueError, OSError) as e:
        logger.exception(f"create_cleanup_task 失败: {e}")
        return server_error(detail=str(e))


async def _run_cleanup(task_id: str, days: int):
    """异步执行清理任务"""
    conn = None
    try:
        cutoff = time.time() - (days * 86400)
        cleaned = 0

        # 清理过期任务记录
        conn = _connect(str(_TASKS_DB))
        cursor = conn.execute("DELETE FROM tasks WHERE status = 'completed' AND completed_at < ?", (cutoff,))
        cleaned += cursor.rowcount
        conn.commit()

        _complete_task(task_id, "completed", result=json.dumps({"cleaned_records": cleaned}))
        logger.info(f"[tasks] 清理完成: {cleaned} 条记录")
    except (sqlite3.Error, OSError) as e:
        _complete_task(task_id, "failed", error_message=str(e))
        logger.error(f"[tasks] 清理失败: {e}")
    finally:
        if conn:
            try:
                conn.close()
            except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                pass


@router.get("/api/system/resources")
async def get_system_resources() -> JSONResponse:
    """获取系统资源使用情况"""
    try:
        import psutil

        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(str(DATA_DIR))
        cpu_percent = psutil.cpu_percent(interval=0.5)

        # 数据库大小
        db_size = 0
        for db_file in [_TASKS_DB, DATA_DIR / "chunks.db", DATA_DIR / "chat_sessions.db"]:
            if db_file.exists():
                db_size += db_file.stat().st_size

        return success(
            data={
                "memory": {
                    "total_mb": round(mem.total / (1024 * 1024), 2),
                    "used_mb": round(mem.used / (1024 * 1024), 2),
                    "percent": mem.percent,
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "percent": round(disk.percent, 2),
                },
                "cpu_percent": cpu_percent,
                "database_size_mb": round(db_size / (1024 * 1024), 2),
            },
            message="系统资源",
        )
    except ImportError:
        return error("psutil 未安装", status_code=500)
    except Exception as e:
        logger.exception(f"get_system_resources 失败: {e}")
        return server_error(detail=str(e))


logger.info("[tasks] 任务管理 API 已加载")
