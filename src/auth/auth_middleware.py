"""
auth_middleware.py — 伏羲 v2.2 统一认证中间件
=============================================
渐进式安全增强层，与现有 AuthMiddleware + RBAC 系统兼容。

设计原则：
  1. 白名单模式过渡：未明确标记的端点默认放行，不影响现有调用
  2. 双通道认证：JWT Token（浏览器） + API Key（服务间调用）
  3. 与现有 AuthMiddleware 并行：AuthMiddleware 处理全局 JWT 注入，
     此模块提供精细化的端点级权限控制
  4. 降级友好：所有装饰器在 AuthMiddleware 未注入时回退到宽松模式

使用方式：
  # 端点级认证（仅要求登录，不限角色）
  @router.get("/api/admin/data")
  @require_auth
  async def admin_data(request: Request): ...

  # 角色认证
  @router.delete("/api/admin/users/{user_id}")
  @require_role("admin")
  async def delete_user(request: Request): ...

  # 权限认证
  @router.post("/api/documents")
  @require_permission("write")
  async def create_doc(request: Request): ...

  # FastAPI Depends 方式（推荐，用于 router 级别）
  router = APIRouter(dependencies=[Depends(require_auth_dep)])
"""

import logging
import os
from functools import wraps
from typing import Callable, List, Optional, Union

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("auth.middleware")

# ============================================================================
# 配置
# ============================================================================

# 严格模式：true 时，未认证的请求直接拒绝；false 时（过渡模式），仅记录日志
_STRICT_MODE = os.environ.get("FUXI_AUTH_STRICT_MODE", "false").lower() == "true"


# API Key 验证（可从环境变量或数据库加载多个 key）
def _load_api_keys() -> dict:
    """加载 API Key 白名单

    格式: FUXI_API_KEYS="key1:service-a,key2:service-b"
    返回: {key: client_name}
    """
    keys_str = os.environ.get("FUXI_API_KEYS", "")
    keys = {}
    if keys_str:
        for item in keys_str.split(","):
            item = item.strip()
            if ":" in item:
                k, v = item.split(":", 1)
                keys[k.strip()] = v.strip()
            else:
                keys[item] = "unknown"
    return keys


_API_KEYS = _load_api_keys()

# 用于宽松模式下未认证请求的匿名用户标识
_ANONYMOUS_USER = "__anonymous__"


# ============================================================================
# 用户上下文提取
# ============================================================================


async def get_current_user(request: Request) -> dict:
    """FastAPI Depends：从请求中提取当前用户信息

    优先级：
      1. request.state.user（AuthMiddleware 已注入）
      2. Authorization: Bearer <token>（手动解析）
      3. X-API-Key 请求头（服务间调用）
      4. 匿名用户

    Returns:
        {
            "username": str,
            "role": str,
            "roles": List[str],
            "tenant_id": str,
            "is_authenticated": bool,
            "auth_method": str  # "jwt" | "api_key" | "anonymous"
        }
    """
    # 优先使用 AuthMiddleware 注入的用户信息
    username = getattr(request.state, "user", None)
    if username and username != "anonymous":
        return {
            "username": username,
            "role": getattr(request.state, "role", "user"),
            "roles": getattr(request.state, "roles", ["user"]),
            "tenant_id": getattr(request.state, "tenant_id", "default"),
            "is_authenticated": True,
            "auth_method": "jwt",
        }

    # 尝试手动解析 JWT
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from src.api.auth import verify_jwt_token

            token = auth_header[7:]
            payload = verify_jwt_token(token)
            return {
                "username": payload.get("sub", "unknown"),
                "role": payload.get("role", "user"),
                "roles": payload.get("roles", ["user"]),
                "tenant_id": payload.get("tenant_id", "default"),
                "is_authenticated": True,
                "auth_method": "jwt",
            }
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass  # JWT 无效，继续尝试其他方式

    # 尝试 API Key
    api_key = request.headers.get("X-API-Key", "")
    if api_key and api_key in _API_KEYS:
        client_name = _API_KEYS[api_key]
        return {
            "username": f"api:{client_name}",
            "role": "admin",  # API Key 默认管理员权限
            "roles": ["admin"],
            "tenant_id": request.headers.get("X-Tenant-Id", "default"),
            "is_authenticated": True,
            "auth_method": "api_key",
        }

    # 匿名用户
    return {
        "username": _ANONYMOUS_USER,
        "role": "viewer",
        "roles": ["viewer"],
        "tenant_id": "default",
        "is_authenticated": False,
        "auth_method": "anonymous",
    }


# ============================================================================
# FastAPI Depends 工厂（推荐用于 router 级别）
# ============================================================================


def require_auth_dep(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """FastAPI Depends：要求认证

    用法：
        router = APIRouter(dependencies=[Depends(require_auth_dep)])
        或
        @router.get("/api/data", dependencies=[Depends(require_auth_dep)])

    宽松模式：未认证时允许通过（记录警告日志）
    严格模式：未认证时返回 401
    """
    if not user["is_authenticated"]:
        if _STRICT_MODE:
            raise HTTPException(status_code=401, detail="需要认证")
        else:
            logger.warning(
                f"[Auth] 宽松模式：未认证请求 {request.method} {request.url.path} "
                f"（来源: {request.client.host if request.client else 'unknown'}）"
            )


def require_role_dep(role: str):
    """FastAPI Depends 工厂：要求指定角色

    用法：
        router = APIRouter(dependencies=[Depends(require_role_dep("admin"))])

    宽松模式：匿名用户不阻断，由端点自行决定
    严格模式：角色不匹配时返回 403
    """

    def _check(
        request: Request,
        user: dict = Depends(get_current_user),
    ):
        if not user["is_authenticated"]:
            if _STRICT_MODE:
                raise HTTPException(status_code=401, detail="需要认证")
            return

        if role not in user.get("roles", []):
            if _STRICT_MODE:
                raise HTTPException(status_code=403, detail=f"需要 {role} 角色")
            else:
                logger.warning(
                    f"[Auth] 宽松模式：用户 {user['username']} 缺少 {role} 角色，"
                    f"访问 {request.method} {request.url.path}"
                )

    return _check


def require_permission_dep(permission: str):
    """FastAPI Depends 工厂：要求指定权限

    用法：
        @router.post("/api/documents", dependencies=[Depends(require_permission_dep("write"))])
    """

    def _check(
        request: Request,
        user: dict = Depends(get_current_user),
    ):
        if not user["is_authenticated"]:
            if _STRICT_MODE:
                raise HTTPException(status_code=401, detail="需要认证")
            return

        # 通过 RBAC 检查权限
        try:
            from src.auth.rbac import get_rbac

            rbac = get_rbac()
            if not rbac.check_permission(user["username"], permission):
                if _STRICT_MODE:
                    raise HTTPException(status_code=403, detail=f"需要 {permission} 权限")
                else:
                    logger.warning(f"[Auth] 宽松模式：用户 {user['username']} 缺少 {permission} 权限")
        except Exception as e:
            logger.error(f"[Auth] 权限检查异常: {e}")

    return _check


# ============================================================================
# 装饰器风格（用于单个端点标注）
# ============================================================================


def require_auth(func: Callable) -> Callable:
    """装饰器：要求认证（JWT Token 或 API Key）

    用法：
        @router.get("/api/protected")
        @require_auth
        async def protected_endpoint(request: Request): ...

    宽松模式：未认证不阻断，由端点自行判断
    严格模式：返回 401
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # 查找 Request 参数
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break
        if request is None:
            for val in kwargs.values():
                if isinstance(val, Request):
                    request = val
                    break

        if request is None:
            logger.error("[Auth] @require_auth: 未找到 Request 参数，跳过认证")
            return await func(*args, **kwargs)

        auth_header = request.headers.get("Authorization", "")
        api_key = request.headers.get("X-API-Key", "")
        username = getattr(request.state, "user", None)

        is_authenticated = (
            (username and username != "anonymous")
            or auth_header.startswith("Bearer ")
            or (api_key and api_key in _API_KEYS)
        )

        if not is_authenticated:
            if _STRICT_MODE:
                return JSONResponse(
                    status_code=401, content={"status": "error", "message": "需要认证", "status_code": 401}
                )
            else:
                logger.warning(f"[Auth] 宽松模式：未认证访问 {request.method} {request.url.path}")

        return await func(*args, **kwargs)

    return wrapper


def require_role(role: str) -> Callable:
    """装饰器工厂：要求指定角色

    用法：
        @router.delete("/api/admin/users/{uid}")
        @require_role("admin")
        async def delete_user(request: Request, uid: str): ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if request is None:
                for val in kwargs.values():
                    if isinstance(val, Request):
                        request = val
                        break

            if request is None:
                return await func(*args, **kwargs)

            user = await get_current_user(request)

            if not user["is_authenticated"]:
                if _STRICT_MODE:
                    return JSONResponse(
                        status_code=401, content={"status": "error", "message": "需要认证", "status_code": 401}
                    )
                return await func(*args, **kwargs)

            if role not in user.get("roles", []):
                if _STRICT_MODE:
                    return JSONResponse(
                        status_code=403, content={"status": "error", "message": f"需要 {role} 角色", "status_code": 403}
                    )
                else:
                    logger.warning(f"[Auth] 宽松模式：用户 {user['username']} 缺少 {role} 角色")

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_permission(permission: str) -> Callable:
    """装饰器工厂：要求指定权限

    用法：
        @router.post("/api/documents")
        @require_permission("write")
        async def create_doc(request: Request): ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if request is None:
                for val in kwargs.values():
                    if isinstance(val, Request):
                        request = val
                        break

            if request is None:
                return await func(*args, **kwargs)

            user = await get_current_user(request)

            if not user["is_authenticated"]:
                if _STRICT_MODE:
                    return JSONResponse(
                        status_code=401, content={"status": "error", "message": "需要认证", "status_code": 401}
                    )
                return await func(*args, **kwargs)

            try:
                from src.auth.rbac import get_rbac

                rbac = get_rbac()
                if not rbac.check_permission(user["username"], permission):
                    if _STRICT_MODE:
                        return JSONResponse(
                            status_code=403,
                            content={"status": "error", "message": f"需要 {permission} 权限", "status_code": 403},
                        )
                    else:
                        logger.warning(f"[Auth] 宽松模式：用户 {user['username']} 缺少 {permission} 权限")
            except Exception as e:
                logger.error(f"[Auth] 权限检查异常: {e}")

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# ============================================================================
# 审计日志
# ============================================================================


def audit_log(request: Request, user: dict, action: str, target: str = ""):
    """记录受保护操作的审计日志

    Args:
        request: FastAPI Request 对象
        user:    当前用户信息（来自 get_current_user）
        action:  操作描述
        target:  操作目标（可选）
    """
    client_ip = request.client.host if request.client else "unknown"
    logger.info(
        f"[Audit] {user['username']} ({user['auth_method']}) "
        f"from {client_ip} → {action}" + (f" | {target}" if target else "") + f" | {request.method} {request.url.path}"
    )


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    # Depends 风格（推荐用于 router 级别）
    "get_current_user",
    "require_auth_dep",
    "require_role_dep",
    "require_permission_dep",
    # 装饰器风格（用于单个端点）
    "require_auth",
    "require_role",
    "require_permission",
    # 工具函数
    "audit_log",
]
