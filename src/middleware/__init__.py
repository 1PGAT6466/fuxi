"""
浼忕静 v1.50 鈥?涓棿浠舵ā鍧?
=======================
浠?server.py 鎷嗗垎: 鎵€鏈変腑闂翠欢閰嶇疆 鈥?瀹夊叏澶淬€佽璇併€丆ORS銆丟Zip銆佸紩鎿庤矾鐢便€佽姹傛寚鏍囥€侀檺娴併€?
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
    """閰嶇疆鎵€鏈変腑闂翠欢"""

    # 鈹€鈹€ 瀹夊叏鍝嶅簲澶?鈹€鈹€
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        """瀹夊叏鍝嶅簲澶翠腑闂翠欢锛氫负鎵€鏈?HTTP 鍝嶅簲娣诲姞瀹夊叏澶淬€?

        浠呭湪 HTTP 鍗忚涓嬬敓鏁堬紝WebSocket 鍗囩骇璇锋眰浼氳烦杩囥€?
        """
        response = await call_next(request)
        if response.status_code == 101:
            return response
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        # v1.50 R2 绗簩杞慨澶? HSTS 浠呭湪 HTTPS 鎴栨槑纭姹傛椂娣诲姞
        # 鍐呯綉 HTTP 鐜涓?HSTS 浼氬鑷存祻瑙堝櫒鎷掔粷鍚庣画杩炴帴
        _forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
        _force_hsts = os.getenv("FUXI_FORCE_HSTS", "").lower() == "true"
        if _forwarded_proto == "https" or _force_hsts:
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

    # 鈹€鈹€ API 璁よ瘉涓棿浠?鈹€鈹€
    from src.api.auth import AuthMiddleware, InputLimitMiddleware
    app.add_middleware(AuthMiddleware)
    app.add_middleware(InputLimitMiddleware)

    # 鈹€鈹€ CORS + GZip 鈹€鈹€
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "x-admin-token", "Authorization"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=500)

    # 鈹€鈹€ 寮曟搸璺敱 鈹€鈹€
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

    # 鈹€鈹€ 璇锋眰鎸囨爣 鈹€鈹€
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
                logger.warning("璇锋眰鎸囨爣璁板綍澶辫触锛堟甯稿搷搴旓級: %s", e, exc_info=True)
            return response
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            try:
                from src.infra.request_metrics import get_request_metrics
                get_request_metrics().record_request(duration_ms, False)
            except (ImportError, AttributeError, TypeError) as e:
                logger.warning("璇锋眰鎸囨爣璁板綍澶辫触锛堝紓甯稿搷搴旓級: %s", e, exc_info=True)
            raise

    # 鈹€鈹€ 璇锋眰闄愭祦 鈹€鈹€
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
        logger.info("[RateLimit] slowapi 闄愭祦宸插惎鐢? 60 req/min (default)")
    except ImportError:
        logger.warning("[RateLimit] slowapi 鏈畨瑁咃紝闄愭祦绂佺敤")
