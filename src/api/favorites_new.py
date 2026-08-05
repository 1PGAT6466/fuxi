"""
伏羲 v1.44 — Favorites API 模块

实现：
- GET /api/favorites - 获取收藏列表
- POST /api/favorites - 添加收藏
- DELETE /api/favorites/{id} - 删除收藏
- PUT /api/favorites/{id}/pin - 置顶/取消置顶
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

logger = logging.getLogger("api.favorites")

router = APIRouter()


def _get_favorites_file(username: str) -> Path:
    """获取用户收藏文件路径"""
    from src.config import DATA_DIR

    favorites_dir = Path(DATA_DIR) / "favorites"
    favorites_dir.mkdir(parents=True, exist_ok=True)
    return favorites_dir / f"{username}.json"


def _load_favorites(username: str) -> List[Dict]:
    """加载用户收藏"""
    favorites_file = _get_favorites_file(username)
    if favorites_file.exists():
        return json.loads(favorites_file.read_text(encoding="utf-8"))
    return []


def _save_favorites(username: str, favorites: List[Dict]):
    """保存用户收藏"""
    favorites_file = _get_favorites_file(username)
    favorites_file.write_text(json.dumps(favorites, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("/api/favorites")
@require_role("user")
async def get_favorites(request: Request):
    """获取收藏列表"""
    try:
        username = get_current_username(request)
        favorites = _load_favorites(username)

        return success(data={"items": favorites, "total": len(favorites)})
    except Exception as e:
        logger.error(f"获取收藏列表失败: {e}")
        return server_error(detail=str(e))


@router.post("/api/favorites")
@require_role("user")
async def add_favorite(request: Request):
    """添加收藏"""
    try:
        username = get_current_username(request)
        body = await request.json()

        favorites = _load_favorites(username)

        new_favorite = {
            "id": f"fav_{len(favorites) + 1}",
            "url": body.get("url", ""),
            "title": body.get("title", ""),
            "description": body.get("description", ""),
            "pinned": False,
            "created_at": datetime.now().isoformat(),
        }

        favorites.append(new_favorite)
        _save_favorites(username, favorites)

        return success(data=new_favorite, status_code=201)
    except Exception as e:
        logger.error(f"添加收藏失败: {e}")
        return server_error(detail=str(e))


@router.delete("/api/favorites/{favorite_id}")
@require_role("user")
async def delete_favorite(favorite_id: str, request: Request):
    """删除收藏"""
    try:
        username = get_current_username(request)
        favorites = _load_favorites(username)

        favorites = [f for f in favorites if f.get("id") != favorite_id]
        _save_favorites(username, favorites)

        return success(message="收藏已删除")
    except Exception as e:
        logger.error(f"删除收藏失败: {e}")
        return server_error(detail=str(e))


@router.put("/api/favorites/{favorite_id}/pin")
@require_role("user")
async def toggle_favorite_pin_by_id(favorite_id: str, request: Request):
    """置顶/取消置顶收藏（按 ID）"""
    try:
        username = get_current_username(request)
        favorites = _load_favorites(username)

        for favorite in favorites:
            if favorite.get("id") == favorite_id:
                favorite["pinned"] = not favorite.get("pinned", False)
                _save_favorites(username, favorites)
                return success(data=favorite)

        return not_found("收藏不存在")
    except Exception as e:
        logger.error(f"置顶收藏失败: {e}")
        return server_error(detail=str(e))


@router.put("/api/favorites/toggle-pin")
@require_role("user")
async def toggle_favorite_pin(request: Request):
    """置顶/取消置顶收藏（兼容前端调用）"""
    try:
        username = get_current_username(request)
        body = await request.json()
        favorite_id = body.get("item_id") or body.get("id")

        if not favorite_id:
            return error("缺少收藏 ID", status_code=400)

        favorites = _load_favorites(username)

        for favorite in favorites:
            if favorite.get("id") == favorite_id:
                favorite["pinned"] = not favorite.get("pinned", False)
                _save_favorites(username, favorites)
                return success(data=favorite)

        return not_found("收藏不存在")
    except Exception as e:
        logger.error(f"置顶收藏失败: {e}")
        return server_error(detail=str(e))
