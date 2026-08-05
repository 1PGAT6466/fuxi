"""
伏羲 Fuxi · 企业知识认知系统 v1.44
==================================
认知架构：大脑(调度) + 感官(执行) + 自省(反思) + 记忆(存储)

v1.44 重构: 启动/路由逻辑委托给 core/startup.py + core/routes.py
"""

import os
import sys
from pathlib import Path

# 加载 .env 环境变量
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    with open(_env_file, encoding="utf-8-sig") as f:
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

_log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(_log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        RotatingFileHandler(
            os.path.join(_log_dir, "伏羲·内世界.log"), maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("伏羲·内世界")

import uvicorn
from fastapi import FastAPI, Request
from src.config import HOST, PORT, VERSION

# ============ 创建 FastAPI 应用 ============
# v1.50 安全修复: 生产环境启用 OpenAPI/Swagger 文档，便于开发调试
# 可通过环境变量 FUXI_ENV=production 禁用
_is_production = os.getenv("FUXI_ENV", "development").lower() == "production"
app = FastAPI(
    title="伏羲·内世界 — 企业知识认知系统",
    version=VERSION,
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
    redirect_slashes=False,
)

from src.core.routes import register_all_routes

# ============ 生命周期事件 (委托给 core/startup.py) ============
from src.core.startup import start_fuxi, stop_fuxi


@app.on_event("startup")
async def startup():
    global _fuxi_instance
    await start_fuxi(app)
    _fuxi_instance = get_fuxi_instance()

    # 先初始化插件系统（注册插件路由）
    init_plugin_system()

    # 再注册所有路由（包括 SPA catch-all）
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
def global_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """全局 HTTP 异常处理器 — 统一错误格式"""
    if _is_production:
        message = "请求处理失败" if exc.status_code >= 500 else "请求参数错误"
    else:
        message = str(exc.detail)
    body = {"status": "error", "message": message}
    return _JSONResponse(content=body, status_code=exc.status_code)


@app.exception_handler(HTTPException)
def global_fastapi_exception_handler(request: Request, exc: HTTPException):
    """FastAPI HTTPException 处理器 — 统一错误格式"""
    headers = getattr(exc, "headers", None)
    if _is_production:
        message = "请求处理失败" if exc.status_code >= 500 else "请求参数错误"
    else:
        message = str(exc.detail)
    body = {"status": "error", "message": message}
    return _JSONResponse(content=body, status_code=exc.status_code, headers=headers)


@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Pydantic 验证错误处理器 — 生产环境隐藏内部结构"""
    if _is_production:
        body = {"status": "error", "message": "请求参数验证失败"}
    else:
        errors = []
        for error in exc.errors():
            loc = ".".join(str(l) for l in error["loc"])
            errors.append({"field": loc, "message": error["msg"], "type": error["type"]})
        body = {"status": "error", "message": "请求参数验证失败", "errors": errors}
    return _JSONResponse(content=body, status_code=422)


@app.exception_handler(Exception)
def generic_exception_handler(request: Request, exc: Exception):
    """通用异常处理器 — 捕获所有未处理的异常"""
    import traceback

    logger.error(f"[ErrorHandler] 未处理的异常: {exc}")
    logger.error(traceback.format_exc())

    if _is_production:
        body = {"status": "error", "message": "服务器内部错误"}
    else:
        body = {"status": "error", "message": str(exc)}
    return _JSONResponse(content=body, status_code=500)


logger.info("[ErrorHandler] 全局异常处理器已注册 — {detail} → {status, message}")

# ============ MCP 工具处理器（从 core/mcp_routes 导入）============
from src.core.mcp_routes import MCP_TOOL_HANDLERS, _init_mcp_handlers

# 向后兼容: _fuxi_instance 旧代码可能从 src.server 导入
from src.core.startup import get_fuxi_instance

_fuxi_instance = None  # 启动后由 startup 事件设置


# ============ 插件系统初始化 ============
def init_plugin_system():
    """服务器启动时初始化插件系统"""
    try:
        from src.core.plugin_manager import get_plugin_manager

        pm = get_plugin_manager(app)

        # 扫描并注册未注册的插件
        _scan_and_register_plugins(pm)

        # 自动激活已安装的插件
        results = pm.auto_activate_installed()
        if results["activated"]:
            logger.info(f"[PluginSystem] 自动激活插件: {results['activated']}")
        if results["failed"]:
            logger.warning(f"[PluginSystem] 激活失败: {results['failed']}")

        # 存储到 app state 供路由使用
        app.state.plugin_manager = pm

    except Exception as e:
        logger.error(f"[PluginSystem] 初始化失败: {e}")


def _scan_and_register_plugins(pm):
    """扫描插件目录，将未注册的插件注册到数据库"""
    from pathlib import Path

    plugins_dir = pm.plugins_dir
    if not plugins_dir.exists():
        return

    for plugin_dir in plugins_dir.iterdir():
        if not plugin_dir.is_dir():
            continue

        # 检查是否已注册
        existing = pm.registry.get(plugin_dir.name)
        if existing:
            continue

        # 查找 manifest.json
        manifest_path = plugin_dir / "manifest.json"
        if not manifest_path.exists():
            manifest_path = plugin_dir / "src" / "manifest.json"

        if manifest_path.exists():
            try:
                import json

                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                pm.registry.register(manifest, "installed")
                logger.info(f"[PluginSystem] 自动注册插件: {manifest['name']}")
            except Exception as e:
                logger.warning(f"[PluginSystem] 注册插件失败 {plugin_dir.name}: {e}")


# ============ 启动 ============
if __name__ == "__main__":
    logger.info(f"伏羲·内世界 API v{VERSION} — http://0.0.0.0:{PORT}")
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
        timeout_keep_alive=5,
        limit_concurrency=50,
        h11_max_incomplete_event_size=10485760,  # v1.50 R5: 10MB (from 500MB)
        workers=int(os.getenv("FUXI_WORKERS", "1")),
        server_header=False,
    )
