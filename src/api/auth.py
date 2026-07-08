# 认证模块 — JWT Token 签发与验证
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import os, logging
import jwt
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# JWT 密钥 — 生产环境必须设置环境变量 FUXI_JWT_SECRET
_JWT_SECRET = os.environ.get("FUXI_JWT_SECRET")
if not _JWT_SECRET:
    raise RuntimeError(
        "FUXI_JWT_SECRET 环境变量未设置！"
        "请在 .env 或系统环境变量中设置安全的 JWT 密钥。"
        "示例: FUXI_JWT_SECRET=<至少32字符的随机字符串>"
    )

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.environ.get("FUXI_JWT_EXPIRE_HOURS", "24"))


def create_jwt_token(username: str, role: str) -> str:
    """创建标准JWT token"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "role": role,
        "exp": now + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": now
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token: str) -> dict:
    """验证JWT token，成功返回 payload，失败抛出 HTTPException"""
    try:
        return jwt.decode(token, _JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "无效的Token")


# 白名单路径 — 无需认证即可访问
# 安全修复 (CWE-306): 移除了 /api/system/stats（泄露系统信息）
_AUTH_WHITELIST = {
    "/api/health",
    "/api/auth/login",
    "/api/auth/register",
    "/api/v2/status",
    "/",
    "/login",
    "/admin",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/metrics",
}


def _is_whitelisted(path: str) -> bool:
    """判断路径是否在白名单中"""
    if path in _AUTH_WHITELIST:
        return True
    # 静态文件
    if path.startswith("/static/"):
        return True
    # 非 API 路径（前端页面）
    if not path.startswith("/api/"):
        return True
    return False


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT 认证中间件 — 验证所有 /api/ 请求的 Bearer Token"""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # CORS preflight OPTIONS 请求直接放行
        if request.method == "OPTIONS":
            return await call_next(request)

        # 白名单路径直接放行
        if _is_whitelisted(path):
            return await call_next(request)

        # 提取 Token
        token = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]

        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "未登录"}
            )

        # 验证 Token（v1.50 安全修复：此前只提取 Token 但从未验证）
        try:
            payload = verify_jwt_token(token)
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail}
            )
        except Exception as e:
            logger.warning(f"JWT 验证异常: {e}")
            return JSONResponse(
                status_code=401,
                content={"detail": "认证失败"}
            )

        # 将用户信息注入 request.state，供下游路由使用
        request.state.user = payload.get("sub", "unknown")
        request.state.role = payload.get("role", "user")

        return await call_next(request)

# ============ 管理员角色校验依赖 ============

def require_admin(request: Request):
    """FastAPI 依赖函数：校验当前请求是否来自管理员。

    用法：在路由中添加 Depends(require_admin)，例如：
        @router.get("/api/admin/users", dependencies=[Depends(require_admin)])

    AuthMiddleware 已将 JWT payload 中的 role 注入 request.state.role，
    此函数仅做二次校验。如果 AuthMiddleware 未注入 role（白名单绕过），
    默认拒绝（因 admin API 不应在白名单中）。
    """
    role = getattr(request.state, "role", None)
    if role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")


class InputLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        return await call_next(request)
