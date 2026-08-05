"""
协作功能 API — 伏羲 v1.50
============================
提供协作房间的创建、管理、参与者查询和历史记录功能。
数据存储：SQLite（collaboration.db）

端点：
  GET    /api/collaboration/rooms              — 获取房间列表
  POST   /api/collaboration/rooms              — 创建房间
  GET    /api/collaboration/rooms/{id}         — 获取房间详情
  DELETE /api/collaboration/rooms/{id}         — 删除房间
  GET    /api/collaboration/rooms/{id}/participants — 获取参与者
  GET    /api/collaboration/history            — 获取协作历史
"""

import json
import logging
import time
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from src.api.response import error, success

logger = logging.getLogger(__name__)

router = APIRouter(tags=["协作"])

# ============ SQLite 存储 ============

_DB_DIR = Path(__file__).parent.parent.parent / "data"
_DB_PATH = str(_DB_DIR / "collaboration.db")


def _get_conn():
    """获取 SQLite 连接"""
    import sqlite3

    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables():
    """确保协作相关表存在"""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rooms (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                owner_id TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                max_participants INTEGER DEFAULT 10,
                config TEXT DEFAULT '{}',
                created_at REAL,
                updated_at REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT DEFAULT 'member',
                joined_at REAL,
                left_at REAL DEFAULT NULL,
                FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS collaboration_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT DEFAULT '{}',
                timestamp REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_participants_room ON participants(room_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_participants_user ON participants(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_room ON collaboration_history(room_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_user ON collaboration_history(user_id)")
        conn.commit()


_ensure_tables()

# ============ Pydantic 模型 ============


class RoomCreate(BaseModel):
    name: str
    description: str = ""
    max_participants: int = 10
    config: dict = {}


# ============ 辅助函数 ============


def _row_to_dict(row) -> dict:
    """将 SQLite Row 转换为字典"""
    d = dict(row)
    d["config"] = json.loads(d.get("config") or "{}")
    return d


def _log_history(room_id: str, user_id: str, action: str, details: dict = None):
    """记录协作历史"""
    try:
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO collaboration_history
                   (room_id, user_id, action, details, timestamp)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    room_id,
                    user_id,
                    action,
                    json.dumps(details or {}, ensure_ascii=False),
                    time.time(),
                ),
            )
            conn.commit()
    except Exception as e:
        logger.warning("记录协作历史失败: %s", e)


# ============ 端点 ============


@router.get("/api/collaboration/rooms")
async def list_rooms(request: Request, page: int = 1, page_size: int = 20, status: str = "active"):
    """获取协作房间列表"""
    try:
        user_id = getattr(request.state, "user", "anonymous")

        with _get_conn() as conn:
            # 总数
            count_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM rooms WHERE owner_id = ? AND status = ?",
                (user_id, status),
            ).fetchone()
            total = count_row["cnt"]

            # 分页查询
            offset = (page - 1) * page_size
            rows = conn.execute(
                """SELECT * FROM rooms
                   WHERE owner_id = ? AND status = ?
                   ORDER BY updated_at DESC
                   LIMIT ? OFFSET ?""",
                (user_id, status, page_size, offset),
            ).fetchall()

        items = [_row_to_dict(r) for r in rows]

        # 为每个房间添加参与者数量
        with _get_conn() as conn:
            for item in items:
                count = conn.execute(
                    "SELECT COUNT(*) as cnt FROM participants WHERE room_id = ? AND left_at IS NULL",
                    (item["id"],),
                ).fetchone()
                item["participant_count"] = count["cnt"]

        return success(
            data={
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            },
            message="房间列表",
        )
    except Exception as e:
        logger.exception("list_rooms 失败: %s", e)
        return error("获取房间列表失败", status_code=500, detail=str(e))


@router.post("/api/collaboration/rooms")
async def create_room(body: RoomCreate, request: Request):
    """创建协作房间"""
    try:
        user_id = getattr(request.state, "user", "anonymous")
        room_id = str(uuid.uuid4())
        now = time.time()

        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO rooms
                   (id, name, description, owner_id, status, max_participants, config, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?)""",
                (
                    room_id,
                    body.name,
                    body.description,
                    user_id,
                    body.max_participants,
                    json.dumps(body.config, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            # 创建者自动成为参与者（owner 角色）
            conn.execute(
                """INSERT INTO participants (room_id, user_id, role, joined_at)
                   VALUES (?, ?, 'owner', ?)""",
                (room_id, user_id, now),
            )
            conn.commit()

        _log_history(room_id, user_id, "room_created", {"name": body.name})

        return success(
            data={"id": room_id, "name": body.name},
            message="房间创建成功",
        )
    except Exception as e:
        logger.exception("create_room 失败: %s", e)
        return error("创建房间失败", status_code=500, detail=str(e))


@router.get("/api/collaboration/rooms/{room_id}")
async def get_room(room_id: str, request: Request):
    """获取房间详情"""
    try:
        user_id = getattr(request.state, "user", "anonymous")

        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM rooms WHERE id = ?",
                (room_id,),
            ).fetchone()

        if not row:
            return error("房间不存在", status_code=404)

        room = _row_to_dict(row)

        # 获取参与者列表
        with _get_conn() as conn:
            participants = conn.execute(
                """SELECT user_id, role, joined_at, left_at
                   FROM participants
                   WHERE room_id = ?
                   ORDER BY joined_at""",
                (room_id,),
            ).fetchall()

        room["participants"] = [dict(p) for p in participants]
        room["active_participant_count"] = sum(1 for p in room["participants"] if p["left_at"] is None)

        return success(data=room, message="房间详情")
    except Exception as e:
        logger.exception("get_room 失败: %s", e)
        return error("获取房间详情失败", status_code=500, detail=str(e))


@router.delete("/api/collaboration/rooms/{room_id}")
async def delete_room(room_id: str, request: Request):
    """删除协作房间（软删除：标记为 deleted）"""
    try:
        user_id = getattr(request.state, "user", "anonymous")

        with _get_conn() as conn:
            existing = conn.execute(
                "SELECT * FROM rooms WHERE id = ? AND owner_id = ?",
                (room_id, user_id),
            ).fetchone()

            if not existing:
                return error("房间不存在或无权限删除", status_code=404)

            conn.execute(
                "UPDATE rooms SET status = 'deleted', updated_at = ? WHERE id = ?",
                (time.time(), room_id),
            )
            conn.commit()

        _log_history(room_id, user_id, "room_deleted")

        return success(message="房间已删除")
    except Exception as e:
        logger.exception("delete_room 失败: %s", e)
        return error("删除房间失败", status_code=500, detail=str(e))


@router.get("/api/collaboration/rooms/{room_id}/participants")
async def get_participants(room_id: str, request: Request):
    """获取房间参与者列表"""
    try:
        user_id = getattr(request.state, "user", "anonymous")

        # 验证房间存在
        with _get_conn() as conn:
            room = conn.execute(
                "SELECT * FROM rooms WHERE id = ?",
                (room_id,),
            ).fetchone()

        if not room:
            return error("房间不存在", status_code=404)

        # 获取参与者
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT user_id, role, joined_at, left_at
                   FROM participants
                   WHERE room_id = ?
                   ORDER BY joined_at""",
                (room_id,),
            ).fetchall()

        participants = [dict(r) for r in rows]
        active = [p for p in participants if p["left_at"] is None]

        return success(
            data={
                "participants": participants,
                "active_count": len(active),
                "total_count": len(participants),
            },
            message="参与者列表",
        )
    except Exception as e:
        logger.exception("get_participants 失败: %s", e)
        return error("获取参与者列表失败", status_code=500, detail=str(e))


@router.get("/api/collaboration/history")
async def get_history(
    request: Request,
    room_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
):
    """获取协作历史记录"""
    try:
        user_id = getattr(request.state, "user", "anonymous")

        with _get_conn() as conn:
            if room_id:
                # 查询特定房间的历史
                count_row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM collaboration_history WHERE room_id = ?",
                    (room_id,),
                ).fetchone()
                total = count_row["cnt"]

                offset = (page - 1) * page_size
                rows = conn.execute(
                    """SELECT * FROM collaboration_history
                       WHERE room_id = ?
                       ORDER BY timestamp DESC
                       LIMIT ? OFFSET ?""",
                    (room_id, page_size, offset),
                ).fetchall()
            else:
                # 查询用户相关的所有历史
                count_row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM collaboration_history WHERE user_id = ?",
                    (user_id,),
                ).fetchone()
                total = count_row["cnt"]

                offset = (page - 1) * page_size
                rows = conn.execute(
                    """SELECT * FROM collaboration_history
                       WHERE user_id = ?
                       ORDER BY timestamp DESC
                       LIMIT ? OFFSET ?""",
                    (user_id, page_size, offset),
                ).fetchall()

        items = []
        for r in rows:
            d = dict(r)
            d["details"] = json.loads(d.get("details") or "{}")
            items.append(d)

        return success(
            data={
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            },
            message="协作历史",
        )
    except Exception as e:
        logger.exception("get_history 失败: %s", e)
        return error("获取协作历史失败", status_code=500, detail=str(e))
