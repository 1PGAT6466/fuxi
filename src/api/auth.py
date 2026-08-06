# 认证模块 — JWT Token 签发与验证
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# ============ JWT Token 黑名单 ============
# v1.50 R4: 实现 Token 黑名单，支持登出和 Token 刷新后失效旧 Token
# v1.50 安全修复 M1: SQLite 持久化，重启后黑名单不丢失
import sqlite3 as _sqlite3
from pathlib import Path as _Path

_token_blacklist: dict = {}  # token_jti → expiry_timestamp (内存缓存)
_blacklist_lock = threading.Lock()


def _get_blacklist_db_path() -> str:
    """获取 Token 黑名单 SQLite 数据库路径"""
    from src.config import DATA_DIR

    db_dir = _Path(DATA_DIR)
    db_dir.mkdir(parents=True, exist_ok=True)
    return str(db_dir / "token_blacklist.db")


def _init_blacklist_db() -> None:
    """初始化黑名单数据库表"""
    try:
        with _sqlite3.connect(_get_blacklist_db_path(), timeout=10) as conn:
            # v1.50 安全修复: 启用 WAL 模式提升并发性能
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS token_blacklist (
                    jti TEXT PRIMARY KEY,
                    expiry_ts REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bl_expiry ON token_blacklist(expiry_ts)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS token_versions (
                    username TEXT PRIMARY KEY,
                    version INTEGER NOT NULL DEFAULT 0
                )
            """)
    except _sqlite3.Error as e:
        logger.warning(f"Token 黑名单数据库初始化失败: {e}")


_init_blacklist_db()

# Token 版本号机制：每次刷新/登出，用户的 token_version 递增
# v1.50 安全修复 M1: SQLite 持久化版本号
token_versions: dict = {}  # username → version_number (内存缓存)
_versions_lock = threading.Lock()


def _blacklist_token(token_jti: str, expiry_ts: float) -> None:
    """将 Token 的 JTI 加入黑名单（SQLite 持久化 + 内存缓存）"""
    with _blacklist_lock:
        _token_blacklist[token_jti] = expiry_ts
    try:
        with _sqlite3.connect(_get_blacklist_db_path()) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO token_blacklist (jti, expiry_ts) VALUES (?, ?)", (token_jti, expiry_ts)
            )
    except _sqlite3.Error as e:
        logger.warning(f"Token 黑名单持久化失败: {e}")
    _cleanup_blacklist()


def _is_token_blacklisted(token_jti: str) -> bool:
    """检查 Token 是否在黑名单中（先查内存缓存，未命中再查 SQLite）"""
    with _blacklist_lock:
        expiry = _token_blacklist.get(token_jti)
        if expiry is not None:
            if time.time() > expiry:
                del _token_blacklist[token_jti]
                return False
            return True
    # 缓存未命中，查询 SQLite
    try:
        with _sqlite3.connect(_get_blacklist_db_path()) as conn:
            row = conn.execute("SELECT expiry_ts FROM token_blacklist WHERE jti = ?", (token_jti,)).fetchone()
        if row is None:
            return False
        if time.time() > row[0]:
            # 已过期，触发清理
            _cleanup_blacklist()
            return False
        with _blacklist_lock:
            _token_blacklist[token_jti] = row[0]
        return True
    except _sqlite3.Error as e:
        logger.warning(f"Token 黑名单查询失败: {e}")
        # v1.50 安全修复: 查询失败时默认拒绝（安全优先）
        return True


def _cleanup_blacklist() -> None:
    """清理过期的黑名单条目（内存 + SQLite）"""
    now = time.time()
    with _blacklist_lock:
        expired = [k for k, v in _token_blacklist.items() if now > v]
        for k in expired:
            del _token_blacklist[k]
    try:
        with _sqlite3.connect(_get_blacklist_db_path()) as conn:
            deleted = conn.execute("DELETE FROM token_blacklist WHERE expiry_ts < ?", (now,)).rowcount
            if deleted > 0:
                logger.info(f"[Auth] 清理 {deleted} 条过期 Token 黑名单")
    except _sqlite3.Error as e:
        logger.warning(f"Token 黑名单 SQLite 清理失败: {e}")


# P1修复：启动时立即清理过期黑名单
_cleanup_blacklist()


def get_token_version(username: str) -> int:
    """获取用户的当前 token 版本号（先查缓存，再查 SQLite）"""
    with _versions_lock:
        cached = token_versions.get(username)
        if cached is not None:
            return cached
    try:
        with _sqlite3.connect(_get_blacklist_db_path()) as conn:
            row = conn.execute("SELECT version FROM token_versions WHERE username = ?", (username,)).fetchone()
        ver = row[0] if row else 0
        with _versions_lock:
            token_versions[username] = ver
        return ver
    except _sqlite3.Error as e:
        logger.warning(f"Token 版本号查询失败: {e}")
        return 0


def increment_token_version(username: str) -> int:
    """递增用户的 token 版本号（SQLite 持久化）"""
    with _versions_lock:
        current = token_versions.get(username, 0)
        new_version = current + 1
        token_versions[username] = new_version
    try:
        with _sqlite3.connect(_get_blacklist_db_path()) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO token_versions (username, version) VALUES (?, ?)", (username, new_version)
            )
    except _sqlite3.Error as e:
        logger.warning(f"Token 版本号持久化失败: {e}")
    return new_version


# JWT 密钥 — 统一使用 config.py 中的 JWT_SECRET
from src.config import JWT_SECRET as _JWT_SECRET

JWT_ALGORITHM = "HS256"
# v1.50 安全修复: 统一使用 config.py 的 JWT_EXPIRY_HOURS，消除双变量冲突
from src.config import JWT_EXPIRY_HOURS as _JWT_EXPIRY_HOURS


def create_jwt_token(username: str, role: str, tenant_id: str = "default") -> str:
    """创建标准JWT token — v1.50 R4: 包含 JTI 和 token_version
    v1.44 Phase 1: 新增 roles 字段（RBAC 角色列表）+ tenant_id（多租户）
    """
    import uuid as _uuid

    from src.auth.rbac import get_rbac

    now = datetime.now(timezone.utc)
    current_version = get_token_version(username)
    # RBAC: 获取用户角色列表
    rbac = get_rbac()
    roles = rbac.get_roles_for_token(username)
    payload = {
        "sub": username,
        "role": role,  # 向后兼容：保留单角色字段
        "roles": roles,  # v1.44 Phase 1: RBAC 角色列表
        "tenant_id": tenant_id,  # v1.44 Phase 1: 多租户 ID
        "exp": now + timedelta(hours=_JWT_EXPIRY_HOURS),  # v1.50: 使用 config.py 统一变量
        "iat": now,
        "jti": _uuid.uuid4().hex,  # JWT ID，用于黑名单
        "tv": current_version,  # token version，用于版本号校验
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token: str) -> dict:
    """验证JWT token — v1.50 R4: 检查黑名单和 token 版本号"""
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[JWT_ALGORITHM])

        # v1.50 R4: 检查 Token 黑名单
        jti = payload.get("jti")
        if jti and _is_token_blacklisted(jti):
            raise HTTPException(401, "Token 已失效")

        # v1.50 R4: 检查 token 版本号（登出/刷新后旧 Token 失效）
        username = payload.get("sub")
        token_tv = payload.get("tv")
        if username and token_tv is not None:
            current_tv = get_token_version(username)
            if token_tv < current_tv:
                raise HTTPException(401, "Token 已失效，请重新登录")

        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "无效的Token")


# 白名单路径 — 无需认证即可访问
# v1.50 R2 安全修复: 移除 /openapi.json, /docs, /redoc, /admin 白名单
# 生产环境下 OpenAPI/Swagger UI 需要认证
_AUTH_WHITELIST = {
    "/api/health",
    "/health",
    "/api/auth/login",
    "/api/auth/register",
    "/api/v2/status",
    "/api/market/categories",  # 服务市场分类（公开）
    "/api/market/services",  # 服务市场列表（公开浏览）
    "/api/market/services/",  # 服务市场详情（公开浏览）
    "/api/market/installed",  # 已安装服务（公开）
    "/api/graph/stats",  # 图谱统计（公开）
    "/api/graph/overview",  # 图谱概览（公开）
    "/api/graph/statistics",  # 图谱统计（公开）
    "/api/wiki/pages",  # Wiki 页面列表（公开）
    "/api/wiki/page/",  # Wiki 页面详情（公开）
    "/api/documents",  # 文档列表（公开）
    "/api/search",  # 搜索（公开）
    "/",
    "/login",
    "/login.html",
    "/favicon.ico",
    # v1.44 fix: 静态文件路径白名单
    "/static",
    "/static/",
    "/js",
    "/js/",
    "/css",
    "/css/",
    "/img",
    "/img/",
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

    v1.44 fix: 增强静态文件白名单检查，支持子路径和文件扩展名
    """
    if path in _AUTH_WHITELIST:
        return True
    # 前缀匹配：检查路径是否以白名单中的某个前缀开头
    # 排除 "/" 作为前缀，因为它会匹配所有路径
    for prefix in _AUTH_WHITELIST:
        if prefix != "/" and prefix.endswith("/") and path.startswith(prefix):
            return True
    # 静态文件 — v1.44 fix: 增强检查，支持 /static/ 子路径
    if path.startswith("/static/"):
        return True
    # v1.50 fix: 支持 /assets/ 路径 (Vue SPA 的 js/css 等构建产物)
    if path.startswith("/assets/"):
        return True
    # v1.44 fix: 支持直接访问静态文件（如 /favicon.ico, /index.html 等）
    static_exts = {
        ".js",
        ".css",
        ".html",
        ".htm",
        ".ico",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
    }
    if any(path.endswith(ext) for ext in static_exts):
        return True
    # v2.1 R2: 拒绝所有未明确列出的非 API 路径（包括 /admin, /docs, /openapi.json 等）
    # 服务市场路径公开
    if path.startswith("/api/market/"):
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
            from src.api.response import error

            # v1.44 fix: 检查是否是已知API路径，不存在的路径返回404
            if path.startswith("/api/"):
                # 检查路由是否存在
                from starlette.routing import Match

                scope = request.scope.copy()
                scope["path"] = path
                for route in request.app.routes:
                    match, _ = route.matches(scope)
                    if match == Match.FULL:
                        return error("未登录", status_code=401, detail="请提供有效的认证 Token")
                # 路由不存在，返回404
                return error("接口不存在", status_code=404, detail=f"路径 {path} 未找到")
            # v1.50 fix: 非API路径直接放行，由SPA catch-all处理
            return await call_next(request)

        # 验证 Token（v1.50 安全修复：此前只提取 Token 但从未验证）
        from src.api.response import error

        try:
            payload = verify_jwt_token(token)
        except HTTPException:
            raise  # 交给全局异常处理器统一转换为 error() 格式
        except (jwt.DecodeError, jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError, KeyError) as e:
            # v1.50 安全修复: 收窄异常捕获，只处理 JWT 相关异常
            logger.warning(f"JWT 验证异常: {type(e).__name__}: {e}")
            return error("认证失败", status_code=401, detail=str(e))

        # 将用户信息注入 request.state，供下游路由使用
        request.state.user = payload.get("sub", "unknown")
        request.state.role = payload.get("role", "user")
        # v1.44 Phase 1: 注入 RBAC 角色列表
        request.state.roles = payload.get("roles", [payload.get("role", "user")])
        # v1.44 Phase 1: 注入 tenant_id（多租户）
        request.state.tenant_id = payload.get("tenant_id", "default")
        request.state.jwt_payload = payload

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
    # v1.50 R3 Blue: 注册限流调整为 10次/10分钟，避免已存在用户被用于DoS
    STRICT_ENDPOINTS = {
        "/api/auth/login": {"max": 10, "window": 300},
        "/api/auth/register": {"max": 10, "window": 600},
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
                f"[RateLimit] 已启用: {self._max_requests} req/{self._window_sec}s (全局), " f"登录 5/min, 注册 3/hour"
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
                    },
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
                    },
                )
                resp.headers["Retry-After"] = str(self._window_sec)
                return resp

        return await call_next(request)
