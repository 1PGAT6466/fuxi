"""
布局管理 API — 伏羲 v1.50
============================
提供用户自定义仪表板布局的 CRUD、激活、导入/导出功能。
数据存储：SQLite（layouts.db）

端点：
  POST   /api/layouts            — 创建布局
  GET    /api/layouts            — 获取布局列表
  GET    /api/layouts/{id}       — 获取单个布局
  PUT    /api/layouts/{id}       — 更新布局
  DELETE /api/layouts/{id}       — 删除布局
  POST   /api/layouts/{id}/activate — 激活布局
  GET    /api/layouts/export     — 导出布局
  POST   /api/layouts/import     — 导入布局
"""

import json
import logging
import time
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from src.api.auth import require_admin
from src.api.response import error, success

logger = logging.getLogger(__name__)

router = APIRouter(tags=["布局管理"])

# ============ SQLite 存储 ============

_DB_DIR = Path(__file__).parent.parent.parent / "data"
_DB_PATH = str(_DB_DIR / "layouts.db")


def _get_conn():
    """获取 SQLite 连接"""
    import sqlite3

    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table():
    """确保 layouts 表存在"""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS layouts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                user_id TEXT NOT NULL,
                config TEXT NOT NULL DEFAULT '{}',
                is_default INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 0,
                created_at REAL,
                updated_at REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_layouts_user ON layouts(user_id)")
        conn.commit()


_ensure_table()

# ============ Pydantic 模型 ============


class LayoutCreate(BaseModel):
    name: str
    description: str = ""
    config: dict = {}
    is_default: bool = False


class LayoutUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[dict] = None
    is_default: Optional[bool] = None


class LayoutImport(BaseModel):
    name: str
    description: str = ""
    config: dict
    is_default: bool = False


# ============ 辅助函数 ============


def _row_to_dict(row) -> dict:
    """将 SQLite Row 转换为字典"""
    d = dict(row)
    d["config"] = json.loads(d.get("config") or "{}")
    d["is_default"] = bool(d.get("is_default", 0))
    d["is_active"] = bool(d.get("is_active", 0))
    return d


# ============ 端点 ============


@router.post("/api/layouts")
async def create_layout(body: LayoutCreate, request: Request):
    """创建新布局"""
    try:
        user_id = getattr(request.state, "user", "anonymous")
        layout_id = str(uuid.uuid4())
        now = time.time()

        with _get_conn() as conn:
            # 如果设为默认，先取消其他默认布局
            if body.is_default:
                conn.execute(
                    "UPDATE layouts SET is_default = 0 WHERE user_id = ?",
                    (user_id,),
                )

            conn.execute(
                """INSERT INTO layouts
                   (id, name, description, user_id, config, is_default, is_active, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)""",
                (
                    layout_id,
                    body.name,
                    body.description,
                    user_id,
                    json.dumps(body.config, ensure_ascii=False),
                    1 if body.is_default else 0,
                    now,
                    now,
                ),
            )
            conn.commit()

        return success(
            data={"id": layout_id, "name": body.name},
            message="布局创建成功",
        )
    except Exception as e:
        logger.exception("create_layout 失败: %s", e)
        return error("创建布局失败", status_code=500, detail=str(e))


@router.get("/api/layouts")
async def list_layouts(request: Request, page: int = 1, page_size: int = 20):
    """获取当前用户的布局列表"""
    try:
        user_id = getattr(request.state, "user", "anonymous")

        with _get_conn() as conn:
            # 总数
            count_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM layouts WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            total = count_row["cnt"]

            # 分页查询
            offset = (page - 1) * page_size
            rows = conn.execute(
                "SELECT * FROM layouts WHERE user_id = ? ORDER BY is_active DESC, updated_at DESC LIMIT ? OFFSET ?",
                (user_id, page_size, offset),
            ).fetchall()

        items = [_row_to_dict(r) for r in rows]

        return success(
            data={
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            },
            message="布局列表",
        )
    except Exception as e:
        logger.exception("list_layouts 失败: %s", e)
        return error("获取布局列表失败", status_code=500, detail=str(e))


@router.get("/api/layouts/export")
async def export_layouts(request: Request):
    """导出当前用户的所有布局"""
    try:
        user_id = getattr(request.state, "user", "anonymous")

        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM layouts WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()

        items = [_row_to_dict(r) for r in rows]
        # 导出时移除 id 和 user_id（导入时重新生成）
        for item in items:
            item.pop("id", None)
            item.pop("user_id", None)

        return success(
            data={"layouts": items, "count": len(items)},
            message="布局导出成功",
        )
    except Exception as e:
        logger.exception("export_layouts 失败: %s", e)
        return error("导出布局失败", status_code=500, detail=str(e))


@router.post("/api/layouts/import")
async def import_layouts(body: LayoutImport, request: Request):
    """导入单个布局"""
    try:
        user_id = getattr(request.state, "user", "anonymous")
        layout_id = str(uuid.uuid4())
        now = time.time()

        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO layouts
                   (id, name, description, user_id, config, is_default, is_active, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)""",
                (
                    layout_id,
                    body.name,
                    body.description,
                    user_id,
                    json.dumps(body.config, ensure_ascii=False),
                    1 if body.is_default else 0,
                    now,
                    now,
                ),
            )
            conn.commit()

        return success(
            data={"id": layout_id, "name": body.name},
            message="布局导入成功",
        )
    except Exception as e:
        logger.exception("import_layouts 失败: %s", e)
        return error("导入布局失败", status_code=500, detail=str(e))


@router.get("/api/layouts/{layout_id}")
async def get_layout(layout_id: str, request: Request):
    """获取单个布局"""
    try:
        user_id = getattr(request.state, "user", "anonymous")

        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM layouts WHERE id = ? AND user_id = ?",
                (layout_id, user_id),
            ).fetchone()

        if not row:
            return error("布局不存在", status_code=404)

        return success(data=_row_to_dict(row), message="布局详情")
    except Exception as e:
        logger.exception("get_layout 失败: %s", e)
        return error("获取布局失败", status_code=500, detail=str(e))


@router.put("/api/layouts/{layout_id}")
async def update_layout(layout_id: str, body: LayoutUpdate, request: Request):
    """更新布局"""
    try:
        user_id = getattr(request.state, "user", "anonymous")

        with _get_conn() as conn:
            existing = conn.execute(
                "SELECT * FROM layouts WHERE id = ? AND user_id = ?",
                (layout_id, user_id),
            ).fetchone()

            if not existing:
                return error("布局不存在", status_code=404)

            # 构建更新字段
            updates = {}
            if body.name is not None:
                updates["name"] = body.name
            if body.description is not None:
                updates["description"] = body.description
            if body.config is not None:
                updates["config"] = json.dumps(body.config, ensure_ascii=False)
            if body.is_default is not None:
                updates["is_default"] = 1 if body.is_default else 0
                # 如果设为默认，先取消其他默认布局
                if body.is_default:
                    conn.execute(
                        "UPDATE layouts SET is_default = 0 WHERE user_id = ? AND id != ?",
                        (user_id, layout_id),
                    )

            if not updates:
                return error("没有需要更新的字段", status_code=400)

            updates["updated_at"] = time.time()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [layout_id, user_id]

            conn.execute(
                f"UPDATE layouts SET {set_clause} WHERE id = ? AND user_id = ?",
                values,
            )
            conn.commit()

        return success(message="布局更新成功")
    except Exception as e:
        logger.exception("update_layout 失败: %s", e)
        return error("更新布局失败", status_code=500, detail=str(e))


@router.delete("/api/layouts/{layout_id}")
async def delete_layout(layout_id: str, request: Request):
    """删除布局"""
    try:
        user_id = getattr(request.state, "user", "anonymous")

        with _get_conn() as conn:
            existing = conn.execute(
                "SELECT * FROM layouts WHERE id = ? AND user_id = ?",
                (layout_id, user_id),
            ).fetchone()

            if not existing:
                return error("布局不存在", status_code=404)

            conn.execute(
                "DELETE FROM layouts WHERE id = ? AND user_id = ?",
                (layout_id, user_id),
            )
            conn.commit()

        return success(message="布局已删除")
    except Exception as e:
        logger.exception("delete_layout 失败: %s", e)
        return error("删除布局失败", status_code=500, detail=str(e))


@router.post("/api/layouts/{layout_id}/activate")
async def activate_layout(layout_id: str, request: Request):
    """激活指定布局（同时取消其他布局的激活状态）"""
    try:
        user_id = getattr(request.state, "user", "anonymous")

        with _get_conn() as conn:
            existing = conn.execute(
                "SELECT * FROM layouts WHERE id = ? AND user_id = ?",
                (layout_id, user_id),
            ).fetchone()

            if not existing:
                return error("布局不存在", status_code=404)

            # 取消所有布局的激活状态
            conn.execute(
                "UPDATE layouts SET is_active = 0 WHERE user_id = ?",
                (user_id,),
            )
            # 激活目标布局
            conn.execute(
                "UPDATE layouts SET is_active = 1, updated_at = ? WHERE id = ? AND user_id = ?",
                (time.time(), layout_id, user_id),
            )
            conn.commit()

        return success(
            data={"id": layout_id, "is_active": True},
            message="布局已激活",
        )
    except Exception as e:
        logger.exception("activate_layout 失败: %s", e)
        return error("激活布局失败", status_code=500, detail=str(e))
