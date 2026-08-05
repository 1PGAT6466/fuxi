"""
伏羲 v1.44 — 用户 API 模块

实现：
- GET /api/user/preferences - 获取用户偏好
- PUT /api/user/preferences - 更新用户偏好
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from src.api.response import error, not_found, server_error, success
from src.auth.rbac import get_current_username, require_role

logger = logging.getLogger("api.user")

router = APIRouter()


@router.get("/api/user/preferences")
@require_role("user")
async def get_user_preferences(request: Request):
    """获取用户偏好设置"""
    try:
        username = get_current_username(request)

        # 从 user_preferences 目录获取用户偏好
        from src.config import DATA_DIR

        preferences_dir = Path(DATA_DIR) / "user_preferences"
        preferences_file = preferences_dir / f"{username}.json"

        preferences = {}
        if preferences_file.exists():
            preferences = json.loads(preferences_file.read_text(encoding="utf-8"))

        return success(data=preferences)
    except Exception as e:
        logger.error(f"获取用户偏好失败: {e}")
        return server_error(detail=str(e))


@router.put("/api/user/preferences")
@require_role("user")
async def update_user_preferences(request: Request):
    """更新用户偏好设置"""
    try:
        username = get_current_username(request)
        body = await request.json()

        # 从 user_preferences 目录获取用户偏好
        from src.config import DATA_DIR

        preferences_dir = Path(DATA_DIR) / "user_preferences"
        preferences_dir.mkdir(parents=True, exist_ok=True)
        preferences_file = preferences_dir / f"{username}.json"

        # 读取现有偏好
        preferences = {}
        if preferences_file.exists():
            preferences = json.loads(preferences_file.read_text(encoding="utf-8"))

        # 更新偏好
        preferences.update(body)

        # 保存偏好
        preferences_file.write_text(json.dumps(preferences, ensure_ascii=False, indent=2), encoding="utf-8")

        return success(data=preferences, message="偏好设置已更新")
    except Exception as e:
        logger.error(f"更新用户偏好失败: {e}")
        return server_error(detail=str(e))
