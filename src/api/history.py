"""
伏羲 v1.50 — 历史记录 API

提供用户访问历史的记录、查询、删除功能。

API 端点：
  POST   /api/history/visit     — 记录访问
  GET    /api/history/recent    — 获取最近访问
  DELETE /api/history/clear     — 清空历史
  DELETE /api/history/{id}      — 删除单条

数据存储：SQLite (chunks.db → visit_history 表)
"""

import asyncio
import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from src.api.response import error, server_error, success
from src.config import DATA_DIR
from src.data_service import _connect, _ensure_dir

logger = logging.getLogger(__name__)

router = APIRouter(tags=["历史记录"])

# ═══════════════════════════════════════════
# 数据库初始化
# ═══════════════════════════════════════════

_HISTORY_DB = _ensure_dir(DATA_DIR / "visit_history.db")


def _ensure_history_table():
    """确保 visit_history 表存在"""
    with _connect(str(_HISTORY_DB)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS visit_history (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT 'anonymous',
                target_type TEXT NOT NULL DEFAULT 'page',
                target_id TEXT,
                title TEXT,
                url TEXT,
                metadata TEXT DEFAULT '{}',
                visited_at REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_user ON visit_history(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_visited ON visit_history(user_id, visited_at)")
        conn.commit()


def _get_user_id(request: Request) -> str:
    return getattr(request.state, "user", "anonymous")


# ═══════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════


@router.post("/api/history")
async def add_history(request: Request) -> JSONResponse:
    """添加访问记录"""
    return await _record_visit_impl(request)


@router.post("/api/history/visit")
async def record_visit(request: Request) -> JSONResponse:
    """记录一次访问（兼容旧接口）"""
    return await _record_visit_impl(request)


async def _record_visit_impl(request: Request):
    """记录访问的内部实现"""
    try:
        body = await request.json()
        user_id = _get_user_id(request)
        title = body.get("title", "").strip()
        if not title:
            return error("标题不能为空", status_code=400)

        entry_id = body.get("id", str(uuid.uuid4()))
        now = body.get("visited_at", time.time())

        await asyncio.to_thread(_ensure_history_table)
        await asyncio.to_thread(
            _insert_visit,
            entry_id,
            user_id,
            body.get("target_type", "page"),
            body.get("target_id", ""),
            title,
            body.get("url", ""),
            json.dumps(body.get("metadata", {}), ensure_ascii=False),
            now,
        )
        logger.info(f"[history] {user_id} 访问: {title}")
        return success(data={"id": entry_id}, message="访问已记录")
    except Exception as e:
        logger.exception(f"record_visit 失败: {e}")
        return server_error(detail=str(e))


def _insert_visit(entry_id, user_id, target_type, target_id, title, url, metadata, visited_at):
    with _connect(str(_HISTORY_DB)) as conn:
        conn.execute(
            """
            INSERT INTO visit_history (id, user_id, target_type, target_id, title, url, metadata, visited_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (entry_id, user_id, target_type, target_id, title, url, metadata, visited_at),
        )
        conn.commit()


@router.get("/api/history")
async def get_history(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    target_type: str = Query(None),
):
    """获取访问历史列表（支持分页）"""
    try:
        user_id = _get_user_id(request)
        await asyncio.to_thread(_ensure_history_table)
        items = await asyncio.to_thread(_query_recent, user_id, page_size * page, target_type)
        total = len(items)
        start = (page - 1) * page_size
        items = items[start : start + page_size]
        return success(data={"items": items, "total": total, "page": page, "page_size": page_size}, message="访问历史")
    except Exception as e:
        logger.exception(f"get_history 失败: {e}")
        return server_error(detail=str(e))


@router.get("/api/history/recent")
async def get_recent_history(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    target_type: str = Query(None),
):
    """获取最近访问记录（兼容旧接口）"""
    try:
        user_id = _get_user_id(request)
        await asyncio.to_thread(_ensure_history_table)
        items = await asyncio.to_thread(_query_recent, user_id, limit, target_type)
        return success(data={"items": items, "total": len(items)}, message="最近访问")
    except Exception as e:
        logger.exception(f"get_recent_history 失败: {e}")
        return server_error(detail=str(e))


def _query_recent(user_id, limit, target_type=None):
    with _connect(str(_HISTORY_DB)) as conn:
        if target_type:
            rows = conn.execute(
                "SELECT * FROM visit_history WHERE user_id = ? AND target_type = ? ORDER BY visited_at DESC LIMIT ?",
                (user_id, target_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM visit_history WHERE user_id = ? ORDER BY visited_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.get("metadata", "{}") or "{}")
            items.append(item)
        return items


@router.delete("/api/history")
async def clear_all_history(request: Request, target_type: str = Query(None)):
    """清空当前用户的访问历史"""
    try:
        user_id = _get_user_id(request)
        await asyncio.to_thread(_ensure_history_table)
        count = await asyncio.to_thread(_clear_user_history, user_id, target_type)
        return success(data={"deleted": count}, message=f"已清空 {count} 条历史记录")
    except Exception as e:
        logger.exception(f"clear_all_history 失败: {e}")
        return server_error(detail=str(e))


@router.delete("/api/history/clear")
async def clear_history(request: Request, target_type: str = Query(None)):
    """清空当前用户的访问历史（兼容旧接口）"""
    try:
        user_id = _get_user_id(request)
        await asyncio.to_thread(_ensure_history_table)
        count = await asyncio.to_thread(_clear_user_history, user_id, target_type)
        return success(data={"deleted": count}, message=f"已清空 {count} 条历史记录")
    except Exception as e:
        logger.exception(f"clear_history 失败: {e}")
        return server_error(detail=str(e))


def _clear_user_history(user_id, target_type=None):
    with _connect(str(_HISTORY_DB)) as conn:
        if target_type:
            cursor = conn.execute(
                "DELETE FROM visit_history WHERE user_id = ? AND target_type = ?", (user_id, target_type)
            )
        else:
            cursor = conn.execute("DELETE FROM visit_history WHERE user_id = ?", (user_id,))
        conn.commit()
        return cursor.rowcount


@router.delete("/api/history/{entry_id}")
async def delete_history_entry(entry_id: str, request: Request) -> JSONResponse:
    """删除单条历史记录"""
    try:
        user_id = _get_user_id(request)
        await asyncio.to_thread(_ensure_history_table)
        deleted = await asyncio.to_thread(_delete_entry, entry_id, user_id)
        if deleted:
            return success(message="记录已删除")
        return error("记录不存在", status_code=404)
    except Exception as e:
        logger.exception(f"delete_history_entry 失败: {e}")
        return server_error(detail=str(e))


def _delete_entry(entry_id, user_id):
    with _connect(str(_HISTORY_DB)) as conn:
        cursor = conn.execute("DELETE FROM visit_history WHERE id = ? AND user_id = ?", (entry_id, user_id))
        conn.commit()
        return cursor.rowcount > 0


logger.info("[history] 历史记录 API 已加载")
