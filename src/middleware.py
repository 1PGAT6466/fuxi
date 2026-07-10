"""
伏羲 v1.50 — 中间件模块
=======================
从 server.py 拆分: 所有中间件配置 — 安全头、认证、CORS、GZip、引擎路由、请求指标、限流。
"""
import time
import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from src.config import CORS_ORIGINS

logger = logging.getLogger("server")

_is_production = os.getenv("FUXI_ENV", "production").lower() == "production"


def setup_middleware(app: FastAPI) -> None:
    """配置所有中间件"""

    # ── 安全响应头 ──
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        """安全响应头中间件：为所有 HTTP 响应添加安全头。

        仅在 HTTP 协议下生效，WebSocket 升级请求会跳过。
        """
        response = await call_next(request)
        if response.status_code == 101:
            return response
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data: blob: https:; "
            "font-src 'self' data: https://fonts.googleapis.com https://fonts.gstatic.com; "
            "connect-src 'self' http://localhost:* ws://localhost:* https:; "
            "frame-ancestors 'none'"
        )
        response.headers["Content-Security-Policy"] = csp_policy
        response.headers["Server"] = "nginx"
        return response

    # ── API 认证中间件 ──
    from src.api.auth import AuthMiddleware, InputLimitMiddleware
    app.add_middleware(AuthMiddleware)
    app.add_middleware(InputLimitMiddleware)

    # ── CORS + GZip ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "x-admin-token", "Authorization"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=500)

    # ── 引擎路由 ──
    @app.middleware("http")
    async def engine_middleware(request: Request, call_next):
        engine = request.query_params.get("engine", "")
        if not engine:
            engine = request.headers.get("X-Fuxi-Engine", "")
        if not engine:
            engine = getattr(app.state, "engine", "v2")
        engine = engine.lower()
        if engine not in ("v1", "v2"):
            engine = "v2"
        request.state.engine = engine
        request.state.intent_mode = getattr(app.state, "intent_mode", "rule_based")
        response = await call_next(request)
        if not _is_production:
            response.headers["X-Fuxi-Engine"] = engine
        return response

    # ── 请求指标 ──
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        start = time.time()
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start) * 1000
            try:
                from src.infra.request_metrics import get_request_metrics
                get_request_metrics().record_request(duration_ms, response.status_code < 500)
            except (ImportError, AttributeError, TypeError) as e:
                logger.warning("请求指标记录失败（正常响应）: %s", e, exc_info=True)
            return response
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            try:
                from src.infra.request_metrics import get_request_metrics
                get_request_metrics().record_request(duration_ms, False)
            except (ImportError, AttributeError, TypeError) as e:
                logger.warning("请求指标记录失败（异常响应）: %s", e, exc_info=True)
            raise

    # ── 请求限流 ──
    try:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.util import get_remote_address
        from slowapi.errors import RateLimitExceeded
        limiter = Limiter(
            key_func=get_remote_address,
            default_limits=["60/minute"],
            headers_enabled=True,
            strategy="fixed-window",
        )
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        logger.info("[RateLimit] slowapi 限流已启用: 60 req/min (default)")
    except ImportError:
        logger.warning("[RateLimit] slowapi 未安装，限流禁用")
