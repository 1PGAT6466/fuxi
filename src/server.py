"""
伏羲 Fuxi · 企业知识认知系统 v1.44
==================================
认知架构：大脑(调度) + 感官(执行) + 自省(反思) + 记忆(存储)

v1.44 重构: 启动/路由逻辑委托给 core/startup.py + core/routes.py
"""
import os, sys
from pathlib import Path

# 加载 .env 环境变量
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ[key.strip()] = val.strip().strip('"').strip("'")
    import logging as _early_logging
    _early_logging.getLogger(__name__).info("Loaded .env")

# 确保项目根目录在 sys.path 中
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 统一日志配置
import logging
from logging.handlers import RotatingFileHandler
_log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(_log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        RotatingFileHandler(
            os.path.join(_log_dir, '伏羲·内世界.log'),
            maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('伏羲·内世界')

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from src.config import HOST, PORT, VERSION, CORS_ORIGINS

# ============ 创建 FastAPI 应用 ============
# v1.44 安全修复: 生产环境禁用 OpenAPI/Swagger 文档
# 可通过环境变量 FUXI_ENV=development 启用以便于开发调试
_is_production = os.getenv("FUXI_ENV", "production").lower() == "production"
app = FastAPI(
    title="伏羲·内世界 — 企业知识认知系统",
    version=VERSION,
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
    redirect_slashes=False,
)

# ============ 生命周期事件 (委托给 core/startup.py) ============
from src.core.startup import start_fuxi, stop_fuxi
from src.core.routes import register_all_routes

@app.on_event("startup")
async def startup():
    global _fuxi_instance
    await start_fuxi(app)
    _fuxi_instance = get_fuxi_instance()
    register_all_routes(app)

@app.on_event("shutdown")
async def shutdown():
    await stop_fuxi(app)

# ============ 中间件 ============

# ── 安全响应头中间件 ──
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """安全响应头中间件：为所有 HTTP 响应添加安全头。

    仅在 HTTP 协议下生效，WebSocket 升级请求会跳过（因为不会返回普通 HTTP 响应）。
    检测响应是否为 WebSocket（101 Switching Protocols），避免干扰。
    """
    response = await call_next(request)

    # 跳过 WebSocket 升级响应（status_code 101 = Switching Protocols）
    if response.status_code == 101:
        return response

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    csp_policy = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "x-admin-token", "Authorization"],
)
app.add_middleware(GZipMiddleware, minimum_size=500)

# ============ 请求限流 ============
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
    limiter = None
    logger.warning("[RateLimit] slowapi 未安装，限流禁用")

# ============ 全局异常处理器 ============
# 将 FastAPI 默认的 {detail: "..."} 格式统一转换为 {status: "error", message: "..."}
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse as _JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


@app.exception_handler(StarletteHTTPException)
async def global_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """全局 HTTP 异常处理器 — 统一错误格式"""
    if _is_production:
        message = "请求处理失败" if exc.status_code >= 500 else "请求参数错误"
    else:
        message = str(exc.detail)
    body = {"status": "error", "message": message, "status_code": exc.status_code}
    return _JSONResponse(content=body, status_code=exc.status_code)


@app.exception_handler(HTTPException)
async def global_fastapi_exception_handler(request: Request, exc: HTTPException):
    """FastAPI HTTPException 处理器 — 统一错误格式"""
    headers = getattr(exc, "headers", None)
    if _is_production:
        message = "请求处理失败" if exc.status_code >= 500 else "请求参数错误"
    else:
        message = str(exc.detail)
    body = {"status": "error", "message": message, "status_code": exc.status_code}
    return _JSONResponse(content=body, status_code=exc.status_code, headers=headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Pydantic 验证错误处理器 — 生产环境隐藏内部结构"""
    if _is_production:
        body = {"status": "error", "message": "请求参数验证失败", "status_code": 422}
    else:
        errors = []
        for error in exc.errors():
            loc = ".".join(str(l) for l in error["loc"])
            errors.append({"field": loc, "message": error["msg"], "type": error["type"]})
        body = {"status": "error", "message": "请求参数验证失败", "status_code": 422, "errors": errors}
    return _JSONResponse(content=body, status_code=422)

logger.info("[ErrorHandler] 全局异常处理器已注册 — {detail} → {status, message}")

# ============ v2.1 引擎路由中间件 ============
@app.middleware("http")
async def engine_middleware(request: Request, call_next):
    """检测引擎版本并设置 request.state.engine

    检测来源（优先级从高到低）：
      1. Query 参数 ?engine=v1|v2
      2. Header X-Fuxi-Engine: v1|v2
      3. 环境变量 FUXI_ENGINE（默认 v2）
    """
    engine = request.query_params.get("engine", "")
    if not engine:
        engine = request.headers.get("X-Fuxi-Engine", "")
    if not engine:
        engine = getattr(app.state, "engine", "v2")
    engine = engine.lower()
    if engine not in ("v1", "v2"):
        engine = "v2"  # 默认安全回退
    request.state.engine = engine
    request.state.intent_mode = getattr(app.state, "intent_mode", "rule_based")
    response = await call_next(request)
    if not _is_production:
        response.headers["X-Fuxi-Engine"] = engine
    return response

# ============ 请求指标中间件 ============
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """记录请求指标"""
    import time
    start = time.time()
    try:
        response = await call_next(request)
        duration_ms = (time.time() - start) * 1000
        try:
            from src.infra.request_metrics import get_request_metrics
            get_request_metrics().record_request(duration_ms, response.status_code < 500)
        except (ImportError, AttributeError, OSError) as e:
            logger.warning("请求指标记录失败（正常响应）: %s", e, exc_info=True)
        return response
    except (RuntimeError, OSError, ValueError) as e:
        duration_ms = (time.time() - start) * 1000
        try:
            from src.infra.request_metrics import get_request_metrics
            get_request_metrics().record_request(duration_ms, False)
        except (ImportError, AttributeError, OSError):
            logger.warning("请求指标记录失败（异常响应）", exc_info=True)
        raise

# ============ MCP 工具处理器（从 core/mcp_routes 导入）============
from src.core.mcp_routes import MCP_TOOL_HANDLERS, _init_mcp_handlers

# 向后兼容: _fuxi_instance 旧代码可能从 src.server 导入
from src.core.startup import get_fuxi_instance
_fuxi_instance = None  # 启动后由 startup 事件设置

# ============ 启动 ============
if __name__ == "__main__":
    logger.info(f"伏羲·内世界 API v{VERSION} — http://0.0.0.0:{PORT}")
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
        timeout_keep_alive=120,
        h11_max_incomplete_event_size=524288000,
        workers=1,
        server_header=False,
    )
