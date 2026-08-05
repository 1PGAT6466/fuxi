"""
伏羲 v1.50 — 收藏管理 API

提供用户收藏内容的增删改查、置顶管理。

API 端点：
  POST   /api/favorites              — 添加收藏
  GET    /api/favorites              — 获取收藏列表
  DELETE /api/favorites/{id}         — 删除收藏
  PUT    /api/favorites/toggle-pin   — 切换置顶
  PATCH  /api/favorites/{id}         — 更新收藏

数据存储：SQLite (chunks.db → favorites 表)
"""

import asyncio
import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from src.api.auth import require_admin
from src.api.response import error, server_error, success
from src.config import DATA_DIR
from src.data_service import _connect, _ensure_dir

logger = logging.getLogger(__name__)

router = APIRouter(tags=["收藏管理"])

# ═══════════════════════════════════════════
# 数据库初始化
# ═══════════════════════════════════════════

_FAVORITES_DB = _ensure_dir(DATA_DIR / "favorites.db")


def _ensure_favorites_table():
    """确保 favorites 表存在"""
    with _connect(str(_FAVORITES_DB)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT 'anonymous',
                title TEXT NOT NULL,
                url TEXT,
                content TEXT,
                category TEXT DEFAULT 'default',
                tags TEXT DEFAULT '[]',
                is_pinned INTEGER DEFAULT 0,
                created_at REAL,
                updated_at REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fav_user ON favorites(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fav_pinned ON favorites(user_id, is_pinned)")
        conn.commit()


def _get_user_id(request: Request) -> str:
    """从请求中获取用户 ID"""
    return getattr(request.state, "user", "anonymous")


# ═══════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════


@router.post("/api/favorites")
async def add_favorite(request: Request) -> JSONResponse:
    """添加收藏"""
    try:
        body = await request.json()
        user_id = _get_user_id(request)
        title = body.get("title", "").strip()
        if not title:
            return error("标题不能为空", status_code=400)

        fav_id = body.get("id", str(uuid.uuid4()))
        now = time.time()

        await asyncio.to_thread(_ensure_favorites_table)
        await asyncio.to_thread(
            _insert_favorite,
            fav_id,
            user_id,
            title,
            body.get("url", ""),
            body.get("content", ""),
            body.get("category", "default"),
            json.dumps(body.get("tags", []), ensure_ascii=False),
            1 if body.get("is_pinned") else 0,
            now,
            now,
        )
        logger.info(f"[favorites] {user_id} 添加收藏: {title}")
        return success(data={"id": fav_id, "title": title}, message="收藏已添加")
    except Exception as e:
        logger.exception(f"add_favorite 失败: {e}")
        return server_error(detail=str(e))


def _insert_favorite(fav_id, user_id, title, url, content, category, tags, is_pinned, created_at, updated_at):
    with _connect(str(_FAVORITES_DB)) as conn:
        conn.execute(
            """
            INSERT INTO favorites (id, user_id, title, url, content, category, tags, is_pinned, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (fav_id, user_id, title, url, content, category, tags, is_pinned, created_at, updated_at),
        )
        conn.commit()


@router.get("/api/favorites")
async def get_favorites(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    category: str = Query(None),
):
    """获取收藏列表（置顶在前，按创建时间倒序）"""
    try:
        user_id = _get_user_id(request)
        await asyncio.to_thread(_ensure_favorites_table)

        offset = (page - 1) * page_size
        items, total = await asyncio.to_thread(_query_favorites, user_id, category, page_size, offset)
        return success(
            data={"items": items, "total": total, "page": page, "page_size": page_size},
            message="收藏列表",
        )
    except Exception as e:
        logger.exception(f"get_favorites 失败: {e}")
        return server_error(detail=str(e))


def _query_favorites(user_id, category, limit, offset):
    with _connect(str(_FAVORITES_DB)) as conn:
        # v2.2: 使用完全参数化查询，防止 SQL 注入
        conditions = ["user_id = ?"]
        params = [user_id]
        if category:
            conditions.append("category = ?")
            params.append(category)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        total_row = conn.execute(f"SELECT COUNT(*) FROM favorites {where_clause}", params).fetchone()
        total = total_row[0] if total_row else 0

        rows = conn.execute(
            f"SELECT * FROM favorites {where_clause} ORDER BY is_pinned DESC, created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["tags"] = json.loads(item.get("tags", "[]") or "[]")
            item["is_pinned"] = bool(item.get("is_pinned"))
            items.append(item)
        return items, total


@router.delete("/api/favorites/{fav_id}")
async def delete_favorite(fav_id: str, request: Request) -> JSONResponse:
    """删除收藏"""
    try:
        user_id = _get_user_id(request)
        await asyncio.to_thread(_ensure_favorites_table)
        deleted = await asyncio.to_thread(_delete_favorite, fav_id, user_id)
        if deleted:
            return success(message="收藏已删除")
        return error("收藏不存在", status_code=404)
    except Exception as e:
        logger.exception(f"delete_favorite 失败: {e}")
        return server_error(detail=str(e))


def _delete_favorite(fav_id, user_id):
    with _connect(str(_FAVORITES_DB)) as conn:
        cursor = conn.execute("DELETE FROM favorites WHERE id = ? AND user_id = ?", (fav_id, user_id))
        conn.commit()
        return cursor.rowcount > 0


@router.put("/api/favorites/toggle-pin")
async def toggle_pin(request: Request) -> JSONResponse:
    """切换收藏置顶状态"""
    try:
        body = await request.json()
        fav_id = body.get("id")
        if not fav_id:
            return error("缺少 id 参数", status_code=400)

        user_id = _get_user_id(request)
        await asyncio.to_thread(_ensure_favorites_table)
        result = await asyncio.to_thread(_toggle_pin_favorite, fav_id, user_id)
        if result is None:
            return error("收藏不存在", status_code=404)
        return success(data={"id": fav_id, "is_pinned": result}, message="置顶状态已切换")
    except Exception as e:
        logger.exception(f"toggle_pin 失败: {e}")
        return server_error(detail=str(e))


def _toggle_pin_favorite(fav_id, user_id):
    with _connect(str(_FAVORITES_DB)) as conn:
        row = conn.execute("SELECT is_pinned FROM favorites WHERE id = ? AND user_id = ?", (fav_id, user_id)).fetchone()
        if not row:
            return None
        new_pinned = 0 if row["is_pinned"] else 1
        conn.execute(
            "UPDATE favorites SET is_pinned = ?, updated_at = ? WHERE id = ?", (new_pinned, time.time(), fav_id)
        )
        conn.commit()
        return bool(new_pinned)


@router.patch("/api/favorites/{fav_id}")
async def update_favorite(fav_id: str, request: Request) -> JSONResponse:
    """更新收藏内容"""
    try:
        body = await request.json()
        user_id = _get_user_id(request)
        await asyncio.to_thread(_ensure_favorites_table)

        # 构建动态更新
        allowed = ["title", "url", "content", "category", "tags"]
        updates = {}
        for key in allowed:
            if key in body:
                if key == "tags":
                    updates["tags"] = json.dumps(body["tags"], ensure_ascii=False)
                else:
                    updates[key] = body[key]

        if not updates:
            return error("没有可更新的字段", status_code=400)

        updates["updated_at"] = time.time()
        result = await asyncio.to_thread(_update_favorite, fav_id, user_id, updates)
        if result:
            return success(data={"id": fav_id}, message="收藏已更新")
        return error("收藏不存在", status_code=404)
    except Exception as e:
        logger.exception(f"update_favorite 失败: {e}")
        return server_error(detail=str(e))


def _update_favorite(fav_id, user_id, updates: dict):
    with _connect(str(_FAVORITES_DB)) as conn:
        # 先检查是否存在
        row = conn.execute("SELECT id FROM favorites WHERE id = ? AND user_id = ?", (fav_id, user_id)).fetchone()
        if not row:
            return False
        # 安全修复: 白名单验证列名
        SAFE_COLUMNS = {"title", "content", "category", "tags", "is_pinned"}
        invalid = set(updates.keys()) - SAFE_COLUMNS
        if invalid:
            raise ValueError(f"Invalid columns: {invalid}")
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [fav_id]
        conn.execute(f"UPDATE favorites SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return True


logger.info("[favorites] 收藏 API 已加载")
