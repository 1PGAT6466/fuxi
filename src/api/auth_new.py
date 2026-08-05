"""
伏羲 v1.44 — Auth 扩展 API 模块

实现：
- GET /api/auth/me - 获取当前用户
- GET /api/auth/profile - 获取用户资料

注意：/api/auth/login, /api/auth/register, /api/auth/logout 已在 auth_routes.py 中实现
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from src.api.response import error, not_found, server_error, success, unauthorized
from src.auth.rbac import get_current_user_role, get_current_username, require_role

logger = logging.getLogger("api.auth_new")

router = APIRouter(prefix="/api/auth", tags=["认证扩展"])


@router.get("/me")
@require_role("user")
async def get_current_user(request: Request):
    """获取当前登录用户信息"""
    try:
        username = get_current_username(request)

        # 从 users.json 获取用户信息
        from src.config import DATA_DIR

        users_file = Path(DATA_DIR) / "users.json"

        if not users_file.exists():
            return not_found("用户不存在")

        users = json.loads(users_file.read_text(encoding="utf-8"))

        # users.json 是字典格式，键是用户名
        user = users.get(username)

        if not user:
            return not_found("用户不存在")

        return success(
            data={
                "username": username,
                "role": user.get("role", "user"),
                "created_at": user.get("created_at"),
                "last_login": user.get("last_login"),
                "email": user.get("email", ""),
                "display_name": user.get("display_name", username),
            }
        )
    except Exception as e:
        logger.error(f"获取当前用户失败: {e}")
        return server_error(detail=str(e))


@router.get("/profile")
@require_role("user")
async def get_user_profile(request: Request):
    """获取用户资料"""
    try:
        username = get_current_username(request)

        # 从 users.json 获取用户信息
        from src.config import DATA_DIR

        users_file = Path(DATA_DIR) / "users.json"

        if not users_file.exists():
            return not_found("用户不存在")

        users = json.loads(users_file.read_text(encoding="utf-8"))

        # users.json 是字典格式，键是用户名
        user = users.get(username)

        if not user:
            return not_found("用户不存在")

        # 获取用户偏好
        preferences = {}
        preferences_file = Path(DATA_DIR) / "user_preferences" / f"{username}.json"
        if preferences_file.exists():
            preferences = json.loads(preferences_file.read_text(encoding="utf-8"))

        return success(
            data={
                "username": username,
                "role": user.get("role", "user"),
                "created_at": user.get("created_at"),
                "last_login": user.get("last_login"),
                "email": user.get("email", ""),
                "display_name": user.get("display_name", username),
                "preferences": preferences,
            }
        )
    except Exception as e:
        logger.error(f"获取用户资料失败: {e}")
        return server_error(detail=str(e))
