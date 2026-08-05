"""
伏羲 v1.44 — Layout API 模块

实现：
- GET /api/layouts - 获取布局列表
- POST /api/layouts - 创建布局
- GET /api/layouts/{id} - 获取单个布局
- PUT /api/layouts/{id} - 更新布局
- DELETE /api/layouts/{id} - 删除布局
- POST /api/layouts/{id}/activate - 激活布局
- GET /api/layouts/export - 导出布局
- POST /api/layouts/import - 导入布局
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from src.api.response import error, not_found, server_error, success
from src.auth.rbac import get_current_username, require_role

logger = logging.getLogger("api.layouts")

router = APIRouter()


def _get_layouts_dir() -> Path:
    """获取布局目录"""
    from src.config import DATA_DIR

    layouts_dir = Path(DATA_DIR) / "layouts"
    layouts_dir.mkdir(parents=True, exist_ok=True)
    return layouts_dir


def _get_user_layouts_file(username: str) -> Path:
    """获取用户布局文件"""
    layouts_dir = _get_layouts_dir()
    return layouts_dir / f"{username}.json"


def _load_user_layouts(username: str) -> List[Dict]:
    """加载用户布局"""
    layouts_file = _get_user_layouts_file(username)
    if layouts_file.exists():
        return json.loads(layouts_file.read_text(encoding="utf-8"))
    return []


def _save_user_layouts(username: str, layouts: List[Dict]):
    """保存用户布局"""
    layouts_file = _get_user_layouts_file(username)
    layouts_file.write_text(json.dumps(layouts, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("/api/layouts")
@require_role("user")
async def get_layouts(request: Request):
    """获取布局列表"""
    try:
        username = get_current_username(request)
        layouts = _load_user_layouts(username)

        return success(data={"items": layouts, "total": len(layouts)})
    except Exception as e:
        logger.error(f"获取布局列表失败: {e}")
        return server_error(detail=str(e))


@router.post("/api/layouts")
@require_role("user")
async def create_layout(request: Request):
    """创建布局"""
    try:
        username = get_current_username(request)
        body = await request.json()

        layouts = _load_user_layouts(username)

        new_layout = {
            "id": f"layout_{len(layouts) + 1}",
            "name": body.get("name", ""),
            "description": body.get("description", ""),
            "config": body.get("config", {}),
            "active": False,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        layouts.append(new_layout)
        _save_user_layouts(username, layouts)

        return success(data=new_layout, status_code=201)
    except Exception as e:
        logger.error(f"创建布局失败: {e}")
        return server_error(detail=str(e))


@router.get("/api/layouts/{layout_id}")
@require_role("user")
async def get_layout(layout_id: str, request: Request):
    """获取单个布局"""
    try:
        username = get_current_username(request)
        layouts = _load_user_layouts(username)

        for layout in layouts:
            if layout.get("id") == layout_id:
                return success(data=layout)

        return not_found("布局不存在")
    except Exception as e:
        logger.error(f"获取布局失败: {e}")
        return server_error(detail=str(e))


@router.put("/api/layouts/{layout_id}")
@require_role("user")
async def update_layout(layout_id: str, request: Request):
    """更新布局"""
    try:
        username = get_current_username(request)
        body = await request.json()

        layouts = _load_user_layouts(username)

        for layout in layouts:
            if layout.get("id") == layout_id:
                layout.update(body)
                layout["updated_at"] = datetime.now().isoformat()
                _save_user_layouts(username, layouts)
                return success(data=layout)

        return not_found("布局不存在")
    except Exception as e:
        logger.error(f"更新布局失败: {e}")
        return server_error(detail=str(e))


@router.delete("/api/layouts/{layout_id}")
@require_role("user")
async def delete_layout(layout_id: str, request: Request):
    """删除布局"""
    try:
        username = get_current_username(request)
        layouts = _load_user_layouts(username)

        layouts = [l for l in layouts if l.get("id") != layout_id]
        _save_user_layouts(username, layouts)

        return success(message="布局已删除")
    except Exception as e:
        logger.error(f"删除布局失败: {e}")
        return server_error(detail=str(e))


@router.post("/api/layouts/{layout_id}/activate")
@require_role("user")
async def activate_layout(layout_id: str, request: Request):
    """激活布局"""
    try:
        username = get_current_username(request)
        layouts = _load_user_layouts(username)

        for layout in layouts:
            if layout.get("id") == layout_id:
                layout["active"] = True
                layout["updated_at"] = datetime.now().isoformat()
            else:
                layout["active"] = False

        _save_user_layouts(username, layouts)

        return success(message="布局已激活")
    except Exception as e:
        logger.error(f"激活布局失败: {e}")
        return server_error(detail=str(e))


@router.get("/api/layouts/export")
@require_role("user")
async def export_layouts(request: Request):
    """导出布局"""
    try:
        username = get_current_username(request)
        layouts = _load_user_layouts(username)

        return success(data={"layouts": layouts, "exported_at": datetime.now().isoformat()})
    except Exception as e:
        logger.error(f"导出布局失败: {e}")
        return server_error(detail=str(e))


@router.post("/api/layouts/import")
@require_role("user")
async def import_layouts(request: Request):
    """导入布局"""
    try:
        username = get_current_username(request)
        body = await request.json()

        imported_layouts = body.get("layouts", [])

        layouts = _load_user_layouts(username)

        for layout in imported_layouts:
            # 检查是否已存在
            existing = next((l for l in layouts if l.get("id") == layout.get("id")), None)
            if existing:
                existing.update(layout)
                existing["updated_at"] = datetime.now().isoformat()
            else:
                layout["created_at"] = datetime.now().isoformat()
                layout["updated_at"] = datetime.now().isoformat()
                layouts.append(layout)

        _save_user_layouts(username, layouts)

        return success(data={"imported": len(imported_layouts), "total": len(layouts)}, message="布局导入成功")
    except Exception as e:
        logger.error(f"导入布局失败: {e}")
        return server_error(detail=str(e))
