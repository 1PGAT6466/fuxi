# v1.50 统一响应格式 — 认证路由
# v1.44 Phase 1 Fix: 新增 refresh/logout 端点
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
import bcrypt
import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["认证"])

# v1.50 R2: 敏感用户名黑名单 — 防止账号冒充和社会工程攻击
_BLOCKED_USERNAMES = {
    "administrator", "root", "system", "superuser",
    "moderator", "operator", "support", "security", "fuxi",
    "api", "bot", "service", "manager", "owner", "master",
    "webmaster", "sysadmin", "audit", "backup", "guest",
}

# v1.50 R3 Blue: 密码复杂度校验 — 至少8字符，包含大写、小写、数字
# v1.50 R3 Blue: 生产环境不暴露密码策略详情，只返回通用错误消息
import re as _re
import os as _os

_IS_PRODUCTION = _os.getenv("FUXI_ENV", "production").lower() == "production"

def _validate_password_strength(password: str) -> tuple[bool, str]:
    """验证密码强度。返回 (是否通过, 错误消息)。
    
    要求:
    - 至少 8 个字符
    - 至少包含 1 个大写字母
    - 至少包含 1 个小写字母
    - 至少包含 1 个数字
    
    v1.50 R3 Blue: 生产环境只返回通用错误消息，不暴露密码策略详情
    """
    if len(password) < 8:
        if _IS_PRODUCTION:
            return False, "密码不符合要求"
        return False, "密码长度至少需要 8 个字符"
    if not _re.search(r'[A-Z]', password):
        if _IS_PRODUCTION:
            return False, "密码不符合要求"
        return False, "密码必须包含至少一个大写字母"
    if not _re.search(r'[a-z]', password):
        if _IS_PRODUCTION:
            return False, "密码不符合要求"
        return False, "密码必须包含至少一个小写字母"
    if not _re.search(r'[0-9]', password):
        if _IS_PRODUCTION:
            return False, "密码不符合要求"
        return False, "密码必须包含至少一个数字"
    return True, ""

def _is_username_blocked(username: str) -> bool:
    """检查用户名是否在黑名单中（不区分大小写）"""
    lower = username.lower().strip()
    if lower in _BLOCKED_USERNAMES:
        return True
    # 检查包含 root/system 的变形（admin 已从黑名单移除，允许使用）
    if any(blocked in lower for blocked in ["root", "system"]):
        return True
    return False

# v2.1: 登录频率限制（SQLite 持久化，重启不丢失）
# v1.50 R3 Blue: 调整登录频率限制为更严格的值（10次/5分钟）
_MAX_LOGIN_ATTEMPTS = 10
_LOGIN_WINDOW_SEC = 300
_login_attempts: dict = defaultdict(list)  # 内存缓存，用于快速检查

# v1.50 R3 Blue: 账号锁定机制 — 防止暴力破解
_MAX_ACCOUNT_ATTEMPTS = 5  # 同一账号5次失败后锁定
_ACCOUNT_LOCKOUT_SEC = 900  # 锁定15分钟
_account_attempts: dict = defaultdict(list)  # 账号维度的失败记录

# v1.50 R2 Blue: 注册频率限制 — 每IP每小时最多3次注册
_MAX_REGISTER_ATTEMPTS = 3
_REGISTER_WINDOW_SEC = 3600
_register_attempts: dict = defaultdict(list)


def _get_login_rate_db_path():
    """获取登录限流 SQLite 数据库路径"""
    from pathlib import Path
    from src.config import DATA_DIR
    db_dir = Path(DATA_DIR)
    db_dir.mkdir(parents=True, exist_ok=True)
    return str(db_dir / "login_rate.db")


def _check_login_rate(ip: str) -> bool:
    """检查登录频率是否在限制内，返回 True 表示允许
    
    v1.50 R5: 统一使用 data_service.py 的连接管理，消除散落的 sqlite3.connect
    """
    try:
        from src.data_service import check_login_rate
        return check_login_rate(
            ip,
            max_attempts=_MAX_LOGIN_ATTEMPTS,
            window_sec=_LOGIN_WINDOW_SEC
        )
    except Exception as e:
        logger.warning(f"登录限流存储异常，回退到内存模式: {e}")
        # 回退：内存模式
        now = time.time()
        attempts = _login_attempts[ip]
        attempts = [t for t in attempts if now - t < _LOGIN_WINDOW_SEC]
        _login_attempts[ip] = attempts
        if len(attempts) >= _MAX_LOGIN_ATTEMPTS:
            return False
        attempts.append(now)
        return True


def _check_account_lockout(username: str) -> tuple[bool, int]:
    """检查账号是否被锁定，返回 (是否允许, 剩余锁定秒数)
    
    v1.50 R3 Blue: 基于账号的锁定机制，防止暴力破解
    """
    now = time.time()
    cutoff = now - _ACCOUNT_LOCKOUT_SEC
    
    # 清理过期记录
    _account_attempts[username] = [
        t for t in _account_attempts[username] if t > cutoff
    ]
    
    attempts = _account_attempts[username]
    if len(attempts) >= _MAX_ACCOUNT_ATTEMPTS:
        # 计算剩余锁定时间
        oldest = min(attempts)
        remaining = int(_ACCOUNT_LOCKOUT_SEC - (now - oldest))
        return False, max(0, remaining)
    
    return True, 0


def _record_failed_attempt(username: str):
    """记录登录失败尝试"""
    _account_attempts[username].append(time.time())


def _clear_failed_attempts(username: str):
    """清除登录失败记录（登录成功时调用）"""
    _account_attempts.pop(username, None)


def _check_register_rate(ip: str) -> bool:
    """检查注册频率是否在限制内，返回 True 表示允许
    
    限制：每IP每小时最多3次注册。
    使用内存存储，重启后重置（可接受的行为）。
    """
    now = time.time()
    attempts = _register_attempts[ip]
    attempts = [t for t in attempts if now - t < _REGISTER_WINDOW_SEC]
    _register_attempts[ip] = attempts
    if len(attempts) >= _MAX_REGISTER_ATTEMPTS:
        return False
    attempts.append(now)
    return True


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, stored: str) -> bool:
    """验证密码 — v2.1: 仅支持 bcrypt，旧版 SHA-256 格式已强制迁移"""
    if stored.startswith("$2b$"):
        return bcrypt.checkpw(password.encode(), stored.encode())
    # v2.1: 旧版 SHA-256 格式不再支持，强制用户通过管理员重置密码
    logger.warning("检测到旧版密码格式，已拒绝登录。请管理员为该用户重置密码。")
    return False

class LoginRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not v or len(v.strip()) < 1 or len(v.strip()) > 64:
            raise ValueError("用户名长度必须在1-64字符之间")
        # v1.50 R2: 检查敏感用户名
        if _is_username_blocked(v.strip()):
            raise ValueError("该用户名不可用，请选择其他用户名")
        return v.strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        # v1.50 R3 Blue: 登录时仅校验长度（不影响已有弱密码用户登录）
        if not v or len(v) < 6 or len(v) > 128:
            raise ValueError("密码长度必须在6-128字符之间")
        return v


class RegisterRequest(BaseModel):
    """v1.50 R2: 注册需要邮箱字段；v1.50 R3: 使用独立的密码复杂度验证"""
    username: str
    password: str
    email: Optional[str] = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not v or len(v.strip()) < 1 or len(v.strip()) > 64:
            raise ValueError("用户名长度必须在1-64字符之间")
        if _is_username_blocked(v.strip()):
            raise ValueError("该用户名不可用，请选择其他用户名")
        return v.strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        # v1.50 R3 Blue: 注册时严格校验密码复杂度
        if not v or len(v) < 8 or len(v) > 128:
            raise ValueError("密码长度必须在8-128字符之间")
        valid, msg = _validate_password_strength(v)
        if not valid:
            raise ValueError(msg)
        return v

@router.post("/login")
def login(body: LoginRequest, request: Request = None):
    """用户登录 — v1.50 统一响应格式支持，v2.1 速率限制
    
    v1.50 R3 Blue: 增加账号锁定机制，防止暴力破解
    """
    from src.api.response import success, error, unauthorized, server_error
    try:
        from src.api.auth import create_jwt_token
        import json
        from pathlib import Path
        
        # v2.1: 登录速率限制检查（IP维度）
        client_ip = request.client.host if request and request.client else "127.0.0.1"
        if not _check_login_rate(client_ip):
            return unauthorized("登录尝试过于频繁，请稍后再试")
        
        # v1.50 R3 Blue: 账号锁定检查
        account_allowed, lockout_remaining = _check_account_lockout(body.username)
        if not account_allowed:
            return unauthorized(f"账号已被锁定，请{lockout_remaining}秒后再试")
        
        from src.config import DATA_DIR as CONFIG_DATA_DIR
        users_file = Path(CONFIG_DATA_DIR) / "users.json"
        if users_file.exists():
            users = json.loads(users_file.read_text(encoding="utf-8"))
        else:
            users = {}
        
        user = users.get(body.username)
        if not user:
            # v1.50 R3 Blue: 记录失败尝试（即使用户不存在也记录，防止用户名枚举）
            _record_failed_attempt(body.username)
            return unauthorized("用户名或密码错误")
        
        stored = user.get("password", "")
        if not _verify_password(body.password, stored):
            # v1.50 R3 Blue: 记录失败尝试
            _record_failed_attempt(body.username)
            return unauthorized("用户名或密码错误")
        
        # v1.50 R3 Blue: 登录成功，清除失败记录
        _clear_failed_attempts(body.username)
        
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
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"login 失败: {e}")
        return server_error("登录服务异常")

@router.post("/register")
def register(body: RegisterRequest, request: Request = None):
    """用户注册 — v1.50 R2: 添加邮箱字段和敏感用户名检查"""
    from src.api.response import success, error, server_error
    try:
        import json, time
        from pathlib import Path
        
        # v1.50 R2 Blue: 注册速率限制检查
        client_ip = request.client.host if request and request.client else "127.0.0.1"
        if not _check_register_rate(client_ip):
            raise HTTPException(429, "注册请求过于频繁，请稍后再试（每小时最多3次）")
        
        from src.config import DATA_DIR as CONFIG_DATA_DIR
        users_file = Path(CONFIG_DATA_DIR) / "users.json"
        if users_file.exists():
            users = json.loads(users_file.read_text(encoding="utf-8"))
        else:
            users = {}
        
        # v1.50 R2: 敏感用户名黑名单检查
        if _is_username_blocked(body.username):
            raise HTTPException(400, "该用户名不可用，请选择其他用户名")
        
        if body.username in users:
            raise HTTPException(400, "用户名已存在")
        
        users[body.username] = {
            "password": _hash_password(body.password),
            "role": "user",
            "display_name": body.username,
            "email": body.email or "",
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
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"register 失败: {e}")
        return server_error("注册服务异常", detail=str(e))


# ============ v1.44 Phase 1 Fix: Token 刷新 & 登出 ============

class RefreshRequest(BaseModel):
    token: Optional[str] = None  # 可选，不传则从 Authorization header 获取


@router.post("/refresh")
async def auth_refresh(body: RefreshRequest = None, request: Request = None):
    """JWT Token 刷新端点 — v1.50 R4: 旧 Token 失效（黑名单机制）

    从 Authorization header 或请求体获取当前 token，验证后签发新 token。
    旧 token 被加入黑名单，立即失效。
    """
    from src.api.response import success, unauthorized, server_error
    try:
        from src.api.auth import (
            create_jwt_token, verify_jwt_token,
            _blacklist_token, increment_token_version
        )

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

        # v1.50 R4: 将旧 Token 加入黑名单
        old_jti = payload.get("jti")
        old_exp = payload.get("exp")
        if old_jti and old_exp:
            _blacklist_token(old_jti, old_exp)
        # 同时递增 token 版本号，使所有旧版本 Token 失效
        increment_token_version(username)
        
        # 签发新 token（会使用新的版本号）
        new_token = create_jwt_token(username, role)

        # v2 格式支持
        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            return success(data={"token": new_token, "username": username, "role": role}, message="Token 已刷新")
        return {"token": new_token, "username": username, "role": role}

    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"auth_refresh 失败: {e}")
        return server_error("Token 刷新服务异常", detail=str(e))


@router.post("/logout")
async def auth_logout(request: Request = None):
    """用户登出端点 — v1.50 R4: 实现真正的 Token 失效（JWT 黑名单）

    将当前 Token 加入黑名单，并递增用户的 token 版本号，
    使该用户的所有旧 Token 立即失效。
    """
    from src.api.response import success
    try:
        from src.api.auth import (
            _blacklist_token, increment_token_version
        )
        
        # 获取用户信息用于日志和黑名单
        username = getattr(request.state, "user", "anonymous") if request else "anonymous"
        
        # v1.50 R4: 将当前 Token 加入黑名单
        if request:
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                token = auth[7:]
                try:
                    import jwt as _jwt
                    # 解码但不验证签名（因为中间件已验证过）
                    payload = _jwt.decode(token, options={"verify_signature": False})
                    jti = payload.get("jti")
                    exp = payload.get("exp")
                    if jti and exp:
                        _blacklist_token(jti, exp)
                except Exception:
                    pass  # Token 解析失败不影响登出流程
        
        # v1.50 R4: 递增 token 版本号，使所有旧版本 Token 失效
        if username != "anonymous":
            increment_token_version(username)
        
        logger.info(f"用户 {username} 已登出")

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            return success(data=None, message="已登出")
        return {"ok": True, "message": "已登出"}

    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"auth_logout 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)}
        )
