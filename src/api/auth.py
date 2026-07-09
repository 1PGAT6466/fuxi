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
# v1.50 R2 安全修复: 移除 /openapi.json, /docs, /redoc, /admin 白名单
# 生产环境下 OpenAPI/Swagger UI 需要认证
_AUTH_WHITELIST = {
    "/api/health",
    "/api/auth/login",
    "/api/auth/register",
    "/api/v2/status",
    "/",
    "/login",
    "/favicon.ico",
}

# 生产环境判断
_IS_PRODUCTION = os.environ.get("FUXI_ENV", "production").lower() == "production"

# 开发环境保留 OpenAPI 文档访问
if not _IS_PRODUCTION:
    _AUTH_WHITELIST.update({"/docs", "/redoc", "/openapi.json"})
    logger.info("[Auth] 开发环境: OpenAPI/Swagger 文档无需认证")
else:
    logger.info("[Auth] 生产环境: OpenAPI/Swagger 文档需要认证")


def _is_whitelisted(path: str) -> bool:
    """判断路径是否在白名单中
    
    v1.50 R2 安全修复: 不再对非 /api/ 路径全部放行，
    仅对明确列出的白名单路径放行。防止 /openapi.json、/docs、/redoc 等
    无需认证即可暴露完整 API Schema。
    """
    if path in _AUTH_WHITELIST:
        return True
    # 静态文件
    if path.startswith("/static/"):
        return True
    # v2.1 R2: 拒绝所有未明确列出的非 API 路径（包括 /admin, /docs, /openapi.json 等）
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
        except Exception as e:  # TODO: Narrow exception type
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
    """请求速率限制中间件 — v1.50 R2 修复
    
    使用滑动窗口算法对全局 API 请求进行速率限制。
    配置:
      - FUXI_RATE_LIMIT_REQUESTS: 每个窗口最大请求数（默认 60）
      - FUXI_RATE_LIMIT_WINDOW_SEC: 窗口秒数（默认 60）
      - FUXI_RATE_LIMIT_ENABLED: 是否启用限流（默认 true）
    """
    
    # 特殊端点的更严格限制
    STRICT_ENDPOINTS = {
        "/api/auth/login": {"max": 5, "window": 60},
        "/api/auth/register": {"max": 3, "window": 3600},
    }
    
    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        self._enabled = os.environ.get("FUXI_RATE_LIMIT_ENABLED", "true").lower() == "true"
        self._max_requests = int(os.environ.get("FUXI_RATE_LIMIT_REQUESTS", "60"))
        self._window_sec = int(os.environ.get("FUXI_RATE_LIMIT_WINDOW_SEC", "60"))
        self._limiters: dict = {}  # key → SlidingWindowRateLimiter
        import threading
        self._lock = threading.Lock()
        if self._enabled:
            logger.info(
                f"[RateLimit] 已启用: {self._max_requests} req/{self._window_sec}s (全局), "
                f"登录 5/min, 注册 3/hour"
            )
        else:
            logger.warning("[RateLimit] 速率限制已禁用（FUXI_RATE_LIMIT_ENABLED=false）")
    
    def _get_limiter(self, key: str, max_req: int, window: int):
        """获取或创建限流器"""
        if key not in self._limiters:
            with self._lock:
                if key not in self._limiters:
                    from src.infra.rate_limiter import SlidingWindowRateLimiter
                    self._limiters[key] = SlidingWindowRateLimiter(max_req, window)
        return self._limiters[key]
    
    async def dispatch(self, request: Request, call_next):
        if not self._enabled:
            return await call_next(request)
        
        path = request.url.path
        
        # 检查严格端点限制
        strict_config = self.STRICT_ENDPOINTS.get(path)
        if strict_config:
            limiter = self._get_limiter(f"strict:{path}", strict_config["max"], strict_config["window"])
            if not limiter.acquire():
                from fastapi.responses import JSONResponse
                retry_after = strict_config["window"]
                resp = JSONResponse(
                    status_code=429,
                    content={
                        "detail": "请求过于频繁，请稍后再试",
                        "retry_after_seconds": retry_after,
                    }
                )
                resp.headers["Retry-After"] = str(retry_after)
                return resp
            return await call_next(request)
        
        # 仅对 /api/ 路径进行全局限流
        if path.startswith("/api/"):
            ip = request.client.host if request.client else "unknown"
            limiter = self._get_limiter(f"global:{ip}", self._max_requests, self._window_sec)
            if not limiter.acquire():
                from fastapi.responses import JSONResponse
                resp = JSONResponse(
                    status_code=429,
                    content={
                        "detail": "请求过多，请稍后再试",
                        "retry_after_seconds": self._window_sec,
                    }
                )
                resp.headers["Retry-After"] = str(self._window_sec)
                return resp
        
        return await call_next(request)
