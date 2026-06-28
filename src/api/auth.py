"""
auth.py — 统一认证系统 v2.0
JWT Token + 角色区分 (admin/user) + 登录/注册
"""
import os, json, time, hashlib, secrets, logging
from pathlib import Path
from typing import Optional, Dict

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("FUXI_JWT_SECRET", "fuxi-default-secret-change-in-production")
JWT_EXPIRE_HOURS = 24
USERS_FILE = Path(os.getenv("FUXI_DATA_DIR", "data")) / "users.json"

WHITELIST = {
    "/api/health", "/api/metrics", "/api/v2/status",
    "/api/auth/login", "/api/auth/register",
    "/", "/favicon.ico", "/login", "/index.html", "/login.html",
    # 公共查询 API
    "/api/search", "/api/search-history", "/api/chat", "/api/chat/agent", "/api/graph", "/api/graph/entities", "/api/graph/route",
    "/api/wiki", "/api/wiki/list", "/api/wiki/page",
    "/api/graph", "/api/graph/entities",
    "/admin", "/admin/",
}
STATIC_PREFIXES = ("/static/", "/js/", "/css/", "/assets/", "/lib/", "/api/wiki/", "/api/graph/", "/api/search/", "/api/images/")


def _hash_password(password: str, salt: str = "") -> str:
    if not salt:
        salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}${h}"


def _verify_password(password: str, stored: str) -> bool:
    if "$" not in stored:
        return False
    salt, h = stored.split("$", 1)
    return _hash_password(password, salt) == stored


def _load_users() -> Dict:
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    default_admin = {
        "admin": {
            "password": _hash_password("fuxi2024"),
            "role": "admin",
            "display_name": "管理员",
            "created_at": time.time(),
        }
    }
    _save_users(default_admin)
    return default_admin


def _save_users(users: Dict):
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_token(username: str, role: str) -> str:
    import base64
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload_data = {
        "sub": username, "role": role,
        "exp": int(time.time()) + JWT_EXPIRE_HOURS * 3600,
        "iat": int(time.time()),
    }
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip("=")
    sig_input = f"{header}.{payload}"
    sig = hashlib.sha256(f"{sig_input}.{JWT_SECRET}".encode()).hexdigest()[:32]
    return f"{header}.{payload}.{sig}"


def verify_token(token: str) -> Optional[Dict]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        import base64
        payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        sig_input = f"{parts[0]}.{parts[1]}"
        expected_sig = hashlib.sha256(f"{sig_input}.{JWT_SECRET}".encode()).hexdigest()[:32]
        if parts[2] != expected_sig:
            return None
        return payload
    except Exception:
        return None


def authenticate_user(username: str, password: str) -> Optional[Dict]:
    users = _load_users()
    user = users.get(username)
    if not user or not _verify_password(password, user["password"]):
        return None
    return {"username": username, "role": user.get("role", "user"), "display_name": user.get("display_name", username)}


def register_user(username: str, password: str, role: str = "user", display_name: str = "") -> Dict:
    users = _load_users()
    if username in users:
        return {"error": "用户名已存在"}
    if len(username) < 3 or len(password) < 6:
        return {"error": "用户名至少3字符，密码至少6字符"}
    users[username] = {
        "password": _hash_password(password),
        "role": role,
        "display_name": display_name or username,
        "created_at": time.time(),
    }
    _save_users(users)
    return {"ok": True, "username": username, "role": role}


class InputLimitMiddleware(BaseHTTPMiddleware):
    MAX_BODY_SIZE = 200_000_000
    MAX_QUERY_LEN = 5000
    async def dispatch(self, request: Request, call_next):
        for key, val in request.query_params.items():
            if len(val) > self.MAX_QUERY_LEN:
                raise HTTPException(400, f"参数 {key} 超长")
        if request.method in ("POST", "PUT"):
            body = await request.body()
            if len(body) > self.MAX_BODY_SIZE:
                raise HTTPException(413, "请求体超长")
        return await call_next(request)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in WHITELIST:
            return await call_next(request)
        if any(path.startswith(p) for p in STATIC_PREFIXES):
            return await call_next(request)
        if not path.startswith("/api/"):
            return await call_next(request)
        token = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
        if not token:
            token = request.query_params.get("token", "")
        if not token:
            raise HTTPException(401, "未登录")
        payload = verify_token(token)
        if not payload:
            raise HTTPException(401, "Token 无效或已过期")
        request.state.user = payload.get("sub", "unknown")
        request.state.role = payload.get("role", "user")
        admin_paths = ["/api/admin/", "/api/feature-flags", "/api/evaluation/", "/api/evolution/"]
        if any(path.startswith(p) for p in admin_paths):
            if request.state.role != "admin":
                raise HTTPException(403, "需要管理员权限")
        return await call_next(request)
