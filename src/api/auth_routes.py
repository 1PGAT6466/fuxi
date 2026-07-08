# v1.50 统一响应格式 — 认证路由
# v1.44 Phase 1 Fix: 新增 refresh/logout 端点
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import hashlib
import bcrypt
import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["认证"])

# v2.1: 登录频率限制
_MAX_LOGIN_ATTEMPTS = 5
_LOGIN_WINDOW_SEC = 60
_login_attempts: dict = defaultdict(list)


def _check_login_rate(ip: str) -> bool:
    """检查登录频率是否在限制内，返回 True 表示允许"""
    now = time.time()
    attempts = _login_attempts[ip]
    # 清理过期记录
    attempts = [t for t in attempts if now - t < _LOGIN_WINDOW_SEC]
    _login_attempts[ip] = attempts
    if len(attempts) >= _MAX_LOGIN_ATTEMPTS:
        return False
    attempts.append(now)
    return True


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, stored: str) -> bool:
    if stored.startswith("$2b$"):
        return bcrypt.checkpw(password.encode(), stored.encode())
    elif "$" in stored:
        salt, h = stored.split("$", 1)
        if hashlib.sha256(f"{salt}:{password}".encode()).hexdigest() == h:
            return True
    return False

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(body: LoginRequest, request: Request = None):
    """用户登录 — v1.50 统一响应格式支持"""
    from src.api.response import success, error, unauthorized, server_error
    try:
        from src.api.auth import create_jwt_token
        import json
        from pathlib import Path
        
        from src.config import DATA_DIR as CONFIG_DATA_DIR
        users_file = Path(CONFIG_DATA_DIR) / "users.json"
        if users_file.exists():
            users = json.loads(users_file.read_text(encoding="utf-8"))
        else:
            users = {}
        
        user = users.get(body.username)
        if not user:
            raise HTTPException(401, "用户名或密码错误")
        
        stored = user.get("password", "")
        if not _verify_password(body.password, stored):
            raise HTTPException(401, "用户名或密码错误")
        
        if not stored.startswith("$2b$"):
            user["password"] = _hash_password(body.password)
            users_file.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
        
        token = create_jwt_token(body.username, user.get("role", "user"))
        
        # 向后兼容: 默认返回旧格式 {token, username, role, display_name}
        # v2 格式: {status: "success", message: "ok", data: {token, username, role, display_name}}
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            return success(data={
                "token": token,
                "username": body.username,
                "role": user.get("role", "user"),
                "display_name": user.get("display_name", body.username)
            }, message="登录成功")
        # 默认旧格式
        return {"token": token, "username": body.username, "role": user.get("role", "user"), "display_name": user.get("display_name", body.username)}
    except HTTPException as e:
        raise
    except Exception as e:
        logger.exception(f"login 失败: {e}")
        return server_error("登录服务异常", detail=str(e))

@router.post("/register")
def register(body: LoginRequest, request: Request = None):
    """用户注册 — v1.50 统一响应格式支持"""
    from src.api.response import success, error, bad_request, server_error
    try:
        import json, time
        from pathlib import Path
        
        from src.config import DATA_DIR as CONFIG_DATA_DIR
        users_file = Path(CONFIG_DATA_DIR) / "users.json"
        if users_file.exists():
            users = json.loads(users_file.read_text(encoding="utf-8"))
        else:
            users = {}
        
        if body.username in users:
            raise HTTPException(400, "用户名已存在")
        
        users[body.username] = {
            "password": _hash_password(body.password),
            "role": "user",
            "display_name": body.username,
            "created_at": time.time()
        }
        
        users_file.parent.mkdir(parents=True, exist_ok=True)
        users_file.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
        
        # 向后兼容: 默认返回旧格式 {ok, username}
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            return success(data={"username": body.username}, message="注册成功")
        return {"ok": True, "username": body.username}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"register 失败: {e}")
        return server_error("注册服务异常", detail=str(e))


# ============ v1.44 Phase 1 Fix: Token 刷新 & 登出 ============

class RefreshRequest(BaseModel):
    token: Optional[str] = None  # 可选，不传则从 Authorization header 获取


@router.post("/refresh")
async def auth_refresh(body: RefreshRequest = None, request: Request = None):
    """JWT Token 刷新端点

    从 Authorization header 或请求体获取当前 token，验证后签发新 token。
    旧 token 在有效期内仍可使用，但建议客户端切换到新 token。
    """
    from src.api.response import success, error, unauthorized, server_error
    try:
        from src.api.auth import create_jwt_token, verify_jwt_token

        # 获取 token：优先从 Authorization header，其次从请求体
        token = None
        if request:
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                token = auth[7:]
        if not token and body and body.token:
            token = body.token

        if not token:
            return unauthorized("缺少认证 token", "请在 Authorization header 或请求体中提供 token")

        # 验证旧 token
        try:
            payload = verify_jwt_token(token)
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail}
            )

        username = payload.get("sub", "unknown")
        role = payload.get("role", "user")

        # 签发新 token
        new_token = create_jwt_token(username, role)

        # v2 格式支持
        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            return success(data={"token": new_token, "username": username, "role": role}, message="Token 已刷新")
        return {"token": new_token, "username": username, "role": role}

    except Exception as e:
        logger.exception(f"auth_refresh 失败: {e}")
        return server_error("Token 刷新服务异常", detail=str(e))


@router.post("/logout")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def auth_logout(request: Request = None):
    """用户登出端点

    当前为无状态 JWT，登出仅做标记（实际撤销需靠 token 过期自然失效）。
    后续可集成 token 黑名单机制。
    """
    from src.api.response import success
    try:
        # 获取用户信息用于日志
        username = getattr(request.state, "user", "anonymous") if request else "anonymous"
        logger.info(f"用户 {username} 已登出")

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            return success(data=None, message="已登出")
        return {"ok": True, "message": "已登出"}

    except Exception as e:
        logger.exception(f"auth_logout 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)}
        )
