"""
伏羲 v1.44 — RBAC 权限管理模块

角色定义：
- admin: 管理员，拥有所有权限
- user: 普通用户，拥有读写权限
- guest: 访客，只有读权限

使用示例：
    from src.auth.rbac import require_role, get_rbac

    @router.get("/api/admin/users")
    @require_role("admin")
    async def admin_users(request: Request):
        pass

    @router.get("/api/users/me")
    @require_role("user")
    async def get_me(request: Request):
        pass
"""

import logging
from enum import Enum
from functools import wraps
from typing import List, Optional, Set

from fastapi import HTTPException, Request

logger = logging.getLogger("auth.rbac")


class Role(str, Enum):
    """用户角色枚举"""

    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


# 角色权限映射
ROLE_PERMISSIONS: dict[Role, Set[str]] = {
    Role.ADMIN: {
        # 管理员拥有所有权限
        "*"
    },
    Role.USER: {
        # 普通用户权限
        "read",
        "write",
        "delete_own",
        "upload",
        "chat",
        "search",
        "favorites",
        "history",
        "preferences",
    },
    Role.GUEST: {
        # 访客权限
        "read",
        "search",
    },
}


class RBAC:
    """RBAC 权限管理器"""

    def __init__(self):
        self._role_permissions = ROLE_PERMISSIONS

    def has_permission(self, role: str, permission: str) -> bool:
        """检查角色是否拥有指定权限"""
        try:
            role_enum = Role(role)
        except ValueError:
            logger.warning(f"未知角色: {role}")
            return False

        permissions = self._role_permissions.get(role_enum, set())

        # 管理员拥有所有权限
        if "*" in permissions:
            return True

        return permission in permissions

    def has_any_permission(self, role: str, permissions: List[str]) -> bool:
        """检查角色是否拥有任意一个权限"""
        return any(self.has_permission(role, p) for p in permissions)

    def has_all_permissions(self, role: str, permissions: List[str]) -> bool:
        """检查角色是否拥有所有权限"""
        return all(self.has_permission(role, p) for p in permissions)

    def get_roles_for_token(self, username: str) -> List[str]:
        """获取用户的 JWT token 角色列表"""
        # 从 users.json 获取用户角色
        try:
            import json
            from pathlib import Path

            from src.config import DATA_DIR

            users_file = Path(DATA_DIR) / "users.json"
            if users_file.exists():
                users = json.loads(users_file.read_text(encoding="utf-8"))
                # users.json 是字典格式，键是用户名
                user = users.get(username)
                if user:
                    role = user.get("role", "user")
                    return [role]
        except Exception as e:
            logger.warning(f"获取用户角色失败: {e}")

        # 默认返回 user 角色
        return ["user"]


# 全局 RBAC 实例
_rbac: Optional[RBAC] = None


def get_rbac() -> RBAC:
    """获取 RBAC 单例"""
    global _rbac
    if _rbac is None:
        _rbac = RBAC()
    return _rbac


def require_role(required_role: str):
    """
    角色检查装饰器

    用法：
        @router.get("/api/admin/users")
        @require_role("admin")
        async def admin_users(request: Request):
            pass
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从参数中提取 Request 对象
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if request is None:
                for v in kwargs.values():
                    if isinstance(v, Request):
                        request = v
                        break

            if request is None:
                logger.error("require_role: 无法找到 Request 对象")
                raise HTTPException(status_code=500, detail="服务器内部错误")

            # 获取用户角色
            user_role = getattr(request.state, "role", "guest")

            # 检查权限
            rbac = get_rbac()
            if not rbac.has_permission(user_role, "*") and user_role != required_role:
                # 检查角色层级
                role_hierarchy = {"admin": 3, "user": 2, "guest": 1}
                user_level = role_hierarchy.get(user_role, 0)
                required_level = role_hierarchy.get(required_role, 0)

                if user_level < required_level:
                    logger.warning(f"权限不足: 用户角色 {user_role} 需要 {required_role}")
                    raise HTTPException(status_code=403, detail="权限不足")

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_permission(permission: str):
    """
    权限检查装饰器

    用法：
        @router.post("/api/upload")
        @require_permission("upload")
        async def upload_file(request: Request):
            pass
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从参数中提取 Request 对象
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if request is None:
                for v in kwargs.values():
                    if isinstance(v, Request):
                        request = v
                        break

            if request is None:
                logger.error("require_permission: 无法找到 Request 对象")
                raise HTTPException(status_code=500, detail="服务器内部错误")

            # 获取用户角色
            user_role = getattr(request.state, "role", "guest")

            # 检查权限
            rbac = get_rbac()
            if not rbac.has_permission(user_role, permission):
                logger.warning(f"权限不足: 用户角色 {user_role} 需要权限 {permission}")
                raise HTTPException(status_code=403, detail="权限不足")

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def get_current_user_role(request: Request) -> str:
    """获取当前用户角色"""
    return getattr(request.state, "role", "guest")


def get_current_username(request: Request) -> str:
    """获取当前用户名"""
    return getattr(request.state, "user", "anonymous")
