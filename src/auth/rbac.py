"""
rbac.py — 伏羲 v1.44 Phase 1: 基于 Casbin 的 RBAC 权限系统
=============================================================

角色定义：
  - admin:  系统管理员，拥有全部权限
  - user:   普通用户，可读写文档
  - viewer: 只读用户，仅可查看

权限定义：
  - read:   读取文档/搜索
  - write:  创建/修改文档
  - delete: 删除文档
  - admin:  管理端点（用户管理、团队管理、系统配置）

Casbin RBAC 模型（基于角色继承）：
  admin  → read, write, delete, admin
  user   → read, write
  viewer → read
"""

import logging
from typing import Optional, List, Set
from functools import wraps

import casbin

logger = logging.getLogger(__name__)

# ============================================================================
# 角色与权限定义
# ============================================================================

# 默认角色列表
ROLES = ("admin", "user", "viewer")

# 默认权限列表
PERMISSIONS = ("read", "write", "delete", "admin")

# 角色-权限映射（Casbin policy 格式）
_ROLE_POLICIES = [
    # role, permission
    ("admin", "read"),
    ("admin", "write"),
    ("admin", "delete"),
    ("admin", "admin"),
    ("user", "read"),
    ("user", "write"),
    ("viewer", "read"),
]

# Casbin RBAC 模型字符串
_MODEL_TEXT = """
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act

[role_definition]
g = _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = g(r.sub, p.sub) && r.obj == p.obj && r.act == p.act
"""

# ============================================================================
# RBAC 管理器
# ============================================================================


class RBAC:
    """基于 Casbin 的 RBAC 权限管理器

    单例模式，通过 get_rbac() 获取全局实例。
    """

    def __init__(self):
        self._model = casbin.Model()
        self._model.load_model_from_text(_MODEL_TEXT)
        self._enforcer = casbin.Enforcer(self._model)
        self._user_roles: dict = {}  # username → set of roles
        self._load_policies()
        logger.info("[RBAC] Casbin RBAC 已初始化，角色: %s", ", ".join(ROLES))

    def _load_policies(self):
        """加载默认角色-权限策略"""
        for role, perm in _ROLE_POLICIES:
            self._enforcer.add_policy(role, "api", perm)
        logger.debug("[RBAC] 已加载 %d 条默认策略", len(_ROLE_POLICIES))

    def assign_role(self, username: str, role: str) -> bool:
        """为用户分配角色

        Args:
            username: 用户名
            role:     角色名（必须在 ROLES 中）

        Returns:
            是否成功
        """
        if role not in ROLES:
            logger.warning("[RBAC] 无效角色: %s", role)
            return False

        if username not in self._user_roles:
            self._user_roles[username] = set()

        if role in self._user_roles[username]:
            return True  # 幂等

        self._user_roles[username].add(role)
        self._enforcer.add_role_for_user(username, role)
        logger.info("[RBAC] 用户 %s 分配角色: %s", username, role)
        return True

    def revoke_role(self, username: str, role: str) -> bool:
        """撤销用户角色

        Args:
            username: 用户名
            role:     角色名

        Returns:
            是否成功
        """
        if username not in self._user_roles or role not in self._user_roles[username]:
            return False

        self._user_roles[username].discard(role)
        self._enforcer.delete_role_for_user(username, role)
        logger.info("[RBAC] 用户 %s 撤销角色: %s", username, role)
        return True

    def get_user_roles(self, username: str) -> List[str]:
        """获取用户的所有角色

        Args:
            username: 用户名

        Returns:
            角色列表
        """
        # 优先从内存缓存返回
        if username in self._user_roles:
            return list(self._user_roles[username])

        # 兜底：从 users.json 读取
        return self._load_roles_from_db(username)

    def _load_roles_from_db(self, username: str) -> List[str]:
        """从 users.json 加载用户角色（兜底机制）

        读取 users.json 中的 role 字段，转换为 RBAC 角色。
        旧格式：{"role": "admin"} → 映射到 RBAC 角色 "admin"
        新格式：{"roles": ["admin", "user"]} → 直接使用
        """
        try:
            import json
            from pathlib import Path
            from src.config import DATA_DIR
            users_file = Path(DATA_DIR) / "users.json"
            if not users_file.exists():
                return ["viewer"]  # 默认只读

            users = json.loads(users_file.read_text(encoding="utf-8"))
            user = users.get(username, {})

            # 新格式：roles 字段
            if "roles" in user and isinstance(user["roles"], list):
                roles = [r for r in user["roles"] if r in ROLES]
                if roles:
                    self._user_roles[username] = set(roles)
                    for r in roles:
                        self._enforcer.add_role_for_user(username, r)
                    return roles

            # 旧格式：单个 role 字段 → 映射
            legacy_role = user.get("role", "user")
            mapped = self._map_legacy_role(legacy_role)
            self._user_roles[username] = {mapped}
            self._enforcer.add_role_for_user(username, mapped)
            return [mapped]

        except Exception as e:
            logger.warning("[RBAC] 加载用户角色失败: %s，返回默认 viewer", e)
            return ["viewer"]

    @staticmethod
    def _map_legacy_role(role: str) -> str:
        """将旧版单角色映射到 RBAC 角色"""
        mapping = {"admin": "admin", "user": "user", "viewer": "viewer"}
        return mapping.get(role, "user")

    def check_permission(self, username: str, permission: str) -> bool:
        """检查用户是否拥有指定权限

        Args:
            username:   用户名
            permission: 权限名（read/write/delete/admin）

        Returns:
            是否允许
        """
        if permission not in PERMISSIONS:
            logger.warning("[RBAC] 检查无效权限: %s", permission)
            return False

        # 先确保角色已加载
        if username not in self._user_roles:
            self._load_roles_from_db(username)

        return self._enforcer.enforce(username, "api", permission)

    def has_role(self, username: str, role: str) -> bool:
        """检查用户是否拥有指定角色

        Args:
            username: 用户名
            role:     角色名

        Returns:
            是否拥有该角色
        """
        if username not in self._user_roles:
            self._load_roles_from_db(username)
        return role in self._user_roles.get(username, set())

    def get_roles_for_token(self, username: str) -> List[str]:
        """获取用户角色列表，用于 JWT token 签发

        Args:
            username: 用户名

        Returns:
            角色列表（至少包含一个角色）
        """
        roles = self.get_user_roles(username)
        return roles if roles else ["viewer"]

    def reload_user(self, username: str):
        """重新加载用户角色（用户角色变更后调用）

        Args:
            username: 用户名
        """
        if username in self._user_roles:
            old_roles = self._user_roles[username]
            for r in old_roles:
                self._enforcer.delete_role_for_user(username, r)
            del self._user_roles[username]
        self._load_roles_from_db(username)
        logger.info("[RBAC] 已重新加载用户 %s 的角色", username)


# ============================================================================
# 全局单例
# ============================================================================

_rbac_instance: Optional[RBAC] = None


def get_rbac() -> RBAC:
    """获取全局 RBAC 实例（单例）"""
    global _rbac_instance
    if _rbac_instance is None:
        _rbac_instance = RBAC()
    return _rbac_instance


def reset_rbac():
    """重置全局 RBAC 实例（仅用于测试）"""
    global _rbac_instance
    _rbac_instance = None


# ============================================================================
# FastAPI 依赖注入 & 装饰器
# ============================================================================

from fastapi import Request, HTTPException


def require_role(role: str):
    """FastAPI 依赖工厂：要求用户拥有指定角色

    用法：
        @router.get("/api/admin/users", dependencies=[Depends(require_role("admin"))])
        async def admin_users(request: Request):
            ...

    Args:
        role: 要求的角色名

    Returns:
        FastAPI 依赖函数
    """
    def _check_role(request: Request):
        username = getattr(request.state, "user", None)
        if not username:
            raise HTTPException(401, "未登录")

        rbac = get_rbac()
        if not rbac.has_role(username, role):
            raise HTTPException(403, f"需要 {role} 角色权限")

    return _check_role


def require_permission(permission: str):
    """FastAPI 依赖工厂：要求用户拥有指定权限

    用法：
        @router.post("/api/documents", dependencies=[Depends(require_permission("write"))])
        async def create_document(request: Request):
            ...

    Args:
        permission: 要求的权限名

    Returns:
        FastAPI 依赖函数
    """
    def _check_permission(request: Request):
        username = getattr(request.state, "user", None)
        if not username:
            raise HTTPException(401, "未登录")

        rbac = get_rbac()
        if not rbac.check_permission(username, permission):
            raise HTTPException(403, f"需要 {permission} 权限")

    return _check_permission
