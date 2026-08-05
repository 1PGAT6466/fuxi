"""
伏羲 v1.50 — 中间件模块
=======================
从 server.py 拆分：所有中间件配置 — 安全头、认证、CORS、GZip、引擎路由、请求指标、限流。
"""

import logging
import os
import time

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
        # v1.50 R2 第二轮修复：HSTS 仅在 HTTPS 或明确要求时添加
        # 内网 HTTP 环境中 HSTS 会导致浏览器拒绝后续连接
        _forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
        _force_hsts = os.getenv("FUXI_FORCE_HSTS", "").lower() == "true"
        if _forwarded_proto == "https" or _force_hsts:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # v1.50 安全修复: CSRF 防护 — 对状态变更请求校验 Origin/Referer
        _path = request.url.path
        if request.method in ("POST", "PUT", "DELETE"):
            origin = request.headers.get("Origin", "")
            referer = request.headers.get("Referer", "")
            allowed = False
            # P1修复：从环境变量读取允许的内网网段，而非硬编码
            _internal_nets = os.getenv("FUXI_INTERNAL_NETS", "172.25.30,172.25.100,192.168").split(",")
            for src in (origin, referer):
                if not src:
                    continue
                if "localhost" in src or "127.0.0.1" in src:
                    allowed = True
                    break
                for net in _internal_nets:
                    if net.strip() and net.strip() in src:
                        allowed = True
                        break
                if allowed:
                    break
            # API Key/Token 认证的请求跳过 CSRF（已通过 Token 验证身份）
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                allowed = True
            if not allowed and _path.startswith("/api/"):
                from fastapi.responses import JSONResponse

                return JSONResponse({"status": "error", "message": "CSRF 校验失败"}, status_code=403)
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
        # 带 hash 的静态资源长期缓存（Vite 产物，文件名变化=内容变化）
        if _path.startswith("/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            # 预压缩文件支持：如果客户端支持 Brotli/Gzip，返回预压缩版本
            accept = request.headers.get("Accept-Encoding", "")
            import os as _os

            _dist = _os.path.join(
                _os.path.dirname(_os.path.abspath(__file__)), "..", "frontend", "vue3-migration", "dist"
            )
            _full = _os.path.join(_dist, _path.lstrip("/"))
            if "br" in accept and _os.path.isfile(_full + ".br"):
                from fastapi.responses import FileResponse

                return FileResponse(
                    _full + ".br",
                    media_type="application/javascript",
                    headers={
                        "Content-Encoding": "br",
                        "Cache-Control": "public, max-age=31536000, immutable",
                        "ETag": response.headers.get("ETag", ""),
                    },
                )
            elif "gzip" in accept and _os.path.isfile(_full + ".gz"):
                from fastapi.responses import FileResponse

                return FileResponse(
                    _full + ".gz",
                    media_type="application/javascript",
                    headers={
                        "Content-Encoding": "gzip",
                        "Cache-Control": "public, max-age=31536000, immutable",
                        "ETag": response.headers.get("ETag", ""),
                    },
                )
        elif _path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=86400"
        return response

    # ── API 认证中间件 ──
    from src.api.auth import AuthMiddleware, InputLimitMiddleware

    app.add_middleware(AuthMiddleware)
    app.add_middleware(InputLimitMiddleware)  # v1.50 安全修复: 启用速率限制

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
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
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
        from slowapi.errors import RateLimitExceeded
        from slowapi.util import get_remote_address

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
