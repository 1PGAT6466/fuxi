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
from src.config import HOST, PORT, VERSION

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

# ============ 中间件（委托给 src/middleware.py） ============
from src.middleware import setup_middleware
setup_middleware(app)

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
