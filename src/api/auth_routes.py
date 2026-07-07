# v1.50 统一响应格式 — 认证路由
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
