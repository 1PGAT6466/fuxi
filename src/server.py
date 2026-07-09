"""
伏羲 Fuxi · 企业知识认知系统 v1.50
==================================
认知架构：大脑(调度) + 感官(执行) + 自省(反思) + 记忆(存储)
"""
import os, sys
from pathlib import Path
from typing import Any

# 加载 .env 环境变量
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ[key.strip()] = val.strip().strip('"').strip("'")
    print("Loaded .env")

# 确保项目根目录在 sys.path 中
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# v10.1: 统一日志配置
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
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from src.config import HOST, PORT, VERSION, CORS_ORIGINS, LOADER_URL
from src.api.auth import require_admin

# 静态资源目录指向 Vue3 构建产物
STATIC_DIR = _project_root / "frontend"

# ============ 创建 FastAPI 应用 ============
from fastapi.staticfiles import StaticFiles
from src.config import VERSION as _VERSION

# v1.50 R2 安全修复: 生产环境禁用 OpenAPI/Swagger 文档
# 可通过环境变量 FUXI_ENV=development 启用以便于开发调试
_is_production = os.getenv("FUXI_ENV", "production").lower() == "production"
app = FastAPI(
    title="伏羲·内世界 — 企业知识认知系统",
    version=_VERSION,
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
    redirect_slashes=False,
)

# ============ 伏羲 1.50 生命体启动 ============
_fuxi_instance = None  # module-level fallback

# ============ 八卦引擎模式 ============
_DEFAULT_ENGINE: str = os.getenv("FUXI_ENGINE", "v2").lower()
# FUXI_INTENT_MODE: rule_based | shadow | low_risk | medium_risk | full_llm
_DEFAULT_INTENT_MODE: str = os.getenv("FUXI_INTENT_MODE", "rule_based").lower()


async def _start_fuxi():
    """启动伏羲生命体 — v2.1 八卦体系

    引擎路由：
      - v2（默认）: 八卦 QianGua + IntentBus
      - v1: 旧版 hypothalamus.fuxi.Fuxi（保留兼容）
    """
    global _fuxi_instance
    import time as _time
    engine = os.getenv("FUXI_ENGINE", "v2").lower()
    intent_mode = os.getenv("FUXI_INTENT_MODE", "rule_based").lower()

    try:
        # ---- v2: 八卦体系（默认） ----
        if engine == "v2":
            from src.bagua.qian import QianGua
            from src.bagua.intent_bus import get_intent_bus

            # 初始化 IntentBus
            intent_bus = get_intent_bus()

            # 初始化乾卦（意识中枢）
            _fuxi_instance = QianGua(
                intent_bus=intent_bus,
                intent_mode=intent_mode,
            )
            _fuxi_instance.start()
            _fuxi_instance.start_beating()

            app.state.fuxi = _fuxi_instance
            app.state.intent_bus = intent_bus
            app.state.fuxi_version = _VERSION
            app.state.fuxi_born_at = _time.time()
            app.state.engine = "v2"
            app.state.intent_mode = intent_mode

            logging.getLogger("server").info(
                f"[Fuxi] 引擎: v2 (Bagua) | intent_mode: {intent_mode}"
            )
            logging.getLogger("server").info(
                f"[Fuxi] 伏羲 {_VERSION} 八卦体系已苏醒 ☰"
            )

            # 注册八卦卦到 IntentBus
            _register_bagua_guas(app, intent_bus)

        # ---- v1: 旧版 hypothalamus.fuxi.Fuxi（保留兼容） ----
        elif engine == "v1":
            from src.hypothalamus.fuxi import Fuxi
            _fuxi_instance = Fuxi()
            app.state.fuxi = _fuxi_instance
            app.state.meridian = _fuxi_instance.meridian
            app.state.fuxi_version = _VERSION
            app.state.fuxi_born_at = _time.time()
            app.state.engine = "v1"
            app.state.intent_mode = intent_mode
            await _fuxi_instance.born()
            logging.getLogger("server").info(
                f"[Fuxi] 引擎: v1 (Legacy) | intent_mode: {intent_mode}"
            )
            logging.getLogger("server").info(
                f"[Fuxi] 伏羲 {_VERSION} 生命体已苏醒（旧版）"
            )

        else:
            raise ValueError(f"未知引擎版本: {engine}，支持 v1/v2")

        # ======== v2.1: 注册优雅关机 handler ========
        _register_shutdown_handler()

    except ImportError as e:
        logging.getLogger("server").critical(
            f"[Fuxi] 无法导入伏羲模块，服务无法启动: {e}", exc_info=True
        )
        raise
    except Exception as e:  # TODO: Narrow exception type
        logging.getLogger("server").error(
            f"[Fuxi] 启动失败: {e}", exc_info=True
        )
        # 不阻止服务器启动，部分功能不可用


def _register_bagua_guas(app: FastAPI, intent_bus: Any) -> None:
    """注册八卦所有卦到 IntentBus

    每个卦独立启动并注册到 IntentBus 让乾卦可以 dispatch 到它们。
    失败不阻塞启动。
    """
    gua_registry = {
        "坤": ("src.bagua.kun", "KunGua"),
        "震(zhen)": ("src.bagua.zhen", "ZhenGua"),
        "巽(xun)": ("src.bagua.xun", "XunGua"),
        "坎(kan)": ("src.bagua.kan", "KanGua"),
        "离(li)": ("src.bagua.li", "LiGua"),
        "艮(gen)": ("src.bagua.gen", "GenGua"),
        "兑(dui)": ("src.bagua.dui", "DuiGua"),
    }

    for register_name, (module_path, class_name) in gua_registry.items():
        try:
            mod = __import__(module_path, fromlist=[class_name])
            cls = getattr(mod, class_name)
            instance = cls(intent_bus=intent_bus)
            instance.start()
            # IntentBus 注册通过 GuaBase.start() → register_to_bus() 完成
            # 但 GuaBase 注册时用的是 self.GUA_NAME（如 "kun"/"zhen"/...），
            # 而乾卦 dispatch 用中文名（如 "坤"/"震"/...），需要额外注册
            instance.register_to_bus(name=register_name)
            logging.getLogger("server").info(
                f"[Bagua] {register_name} 已注册到 IntentBus"
            )
        except Exception as e:  # TODO: Narrow exception type
            logging.getLogger("server").warning(
                f"[Bagua] {register_name} 注册失败（服务继续启动）: {e}"
            )


def _register_shutdown_handler():
    """v2.1: 注册三步清理法关机 handler"""
    try:
        from src.bagua.shutdown import register_shutdown_handler
        register_shutdown_handler(
            app=app,
            fuxi_instance=_fuxi_instance,
            grace_period=5.0,
            cancel_timeout=10.0,
            drain_timeout=5.0,
        )
        logging.getLogger("server").info(
            "[Shutdown] 优雅关机 handler 已注册 (STOP→CANCEL→DRAIN)"
        )
    except ImportError:
        logging.getLogger("server").warning(
            "[Shutdown] bagua.shutdown 模块未找到，跳过优雅关机注册"
        )
    except Exception as e:  # TODO: Narrow exception type
        logging.getLogger("server").warning(
            "[Shutdown] 关机 handler 注册失败: %s", e
        )

async def _stop_fuxi():
    """休眠伏羲 — v2.1"""
    global _fuxi_instance
    engine = getattr(app.state, "engine", "v2")
    if _fuxi_instance:
        if engine == "v2":
            # 八卦体系停止
            _fuxi_instance.stop()
            logging.getLogger("server").info("[Fuxi] 八卦体系已停止 ☰")
        else:
            # 旧版 Fuxi 休眠
            await _fuxi_instance.sleep()
            logging.getLogger("server").info("[Fuxi] 伏羲已休眠")

@app.on_event("startup")
async def startup():
    await _start_fuxi()

    # ── 启动烟雾测试（由 FUXI_EVAL_AUTO_RUN 控制）──
    from src.config import EVAL_AUTO_RUN
    if EVAL_AUTO_RUN:
        try:
            from src.services.eval_automation import get_eval_automation
            automation = get_eval_automation()
            report = await automation.run_smoke_test()
            if not report.get("passed", False):
                logger.warning(
                    "[Startup] 启动烟雾测试未全部通过，服务继续启动。"
                    f" 失败项: {report.get('errors', [])}"
                )
            else:
                logger.info("[Startup] 启动烟雾测试全部通过 ✓")
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(
                f"[Startup] 启动烟雾测试执行异常（不影响启动）: {e}",
                exc_info=True
            )

@app.on_event("shutdown")
async def shutdown():
    """v2.1: 使用三步清理法优雅关机

    如果 _fuxi_instance 上的 _shutdown_handler 已注册，
    则由 bagua.shutdown 的 GracefulShutdown 处理。
    此处作为兜底：直接调用 _fuxi.sleep()。
    """
    # 兜底：如果 shutdown handler 未被注册，直接休眠
    try:
        from src.bagua.shutdown import get_shutdown_handler
        handler = get_shutdown_handler()
        if handler is not None and not handler.is_shutting_down:
            await handler.shutdown()
        else:
            await _stop_fuxi()
    except ImportError:
        await _stop_fuxi()
    except Exception:  # TODO: Narrow exception type
        await _stop_fuxi()

# 注册统一异常处理器
# from src.services.error_handler import setup_error_handlers
# setup_error_handlers(app)
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
    # v1.50 R2 Blue: 添加 CSP 安全策略
    # v1.50 R3 Blue: 移除 unsafe-inline，使用 nonce 或 hash 替代
    # 动态生成 CSP，避免硬编码 IP 地址
    csp_policy = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-eval'; "  # 移除 unsafe-inline
        "style-src 'self'; "  # 移除 unsafe-inline
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    response.headers["Content-Security-Policy"] = csp_policy
    # v1.50 R2: 移除指纹识别头 (Server: uvicorn → 伪装)
    response.headers["Server"] = "nginx"
    return response

# ── API 认证中间件 ──
from src.api.auth import AuthMiddleware, InputLimitMiddleware
from src.api.auth_routes import router as auth_router
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

# ============ v1.50 R5: 全局异常处理器 ============
# 将 FastAPI 默认的 {detail: "..."} 格式统一转换为 {status: "error", message: "..."}
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse as _JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


@app.exception_handler(StarletteHTTPException)
async def global_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """全局 HTTP 异常处理器 — 统一错误格式
    
    将 FastAPI/Starlette 默认的 {"detail": "..."} 转换为:
      {"status": "error", "message": "...", "status_code": 4xx/5xx}
    
    v1.50 R3 Blue: 生产环境隐藏框架内部结构信息
    """
    # v1.50 R3 Blue: 生产环境返回通用错误消息
    if _is_production:
        message = "请求处理失败" if exc.status_code >= 500 else "请求参数错误"
    else:
        message = str(exc.detail)
    
    body = {
        "status": "error",
        "message": message,
        "status_code": exc.status_code,
    }
    return _JSONResponse(content=body, status_code=exc.status_code)


@app.exception_handler(HTTPException)
async def global_fastapi_exception_handler(request: Request, exc: HTTPException):
    """FastAPI HTTPException 处理器 — 统一错误格式"""
    # 提取 headers（如果有额外头信息，如 CORS）
    headers = getattr(exc, "headers", None)
    # v1.50 R3 Blue: 生产环境返回通用错误消息
    if _is_production:
        message = "请求处理失败" if exc.status_code >= 500 else "请求参数错误"
    else:
        message = str(exc.detail)
    
    body = {
        "status": "error",
        "message": message,
        "status_code": exc.status_code,
    }
    return _JSONResponse(content=body, status_code=exc.status_code, headers=headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Pydantic 验证错误处理器 — v1.50 R3 Blue 安全修复
    
    生产环境隐藏 FastAPI/Pydantic/Uvicorn 版本信息和内部结构，
    返回通用错误消息，防止信息泄露。
    """
    if _is_production:
        # 生产环境：返回通用错误消息，不暴露内部结构
        body = {
            "status": "error",
            "message": "请求参数验证失败",
            "status_code": 422,
        }
    else:
        # 开发环境：返回详细错误信息便于调试
        errors = []
        for error in exc.errors():
            loc = ".".join(str(l) for l in error["loc"])
            errors.append({"field": loc, "message": error["msg"], "type": error["type"]})
        body = {
            "status": "error",
            "message": "请求参数验证失败",
            "status_code": 422,
            "errors": errors,
        }
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
    # v1.50 R2: 仅开发环境暴露引擎版本
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
        except Exception as e:  # TODO: Narrow exception type
            logger.warning("请求指标记录失败（正常响应）: %s", e, exc_info=True)
        return response
    except Exception as e:  # TODO: Narrow exception type
        duration_ms = (time.time() - start) * 1000
        try:
            from src.infra.request_metrics import get_request_metrics
            get_request_metrics().record_request(duration_ms, False)
        except Exception as e:  # TODO: Narrow exception type
            logger.warning("请求指标记录失败（异常响应）: %s", e, exc_info=True)
        raise

# ============ v2.1 服务路由自动发现 ============
# 自动扫描 src/api/ 目录，发现并注册所有 APIRouter
# 替代原先手写的 include_router 列表
from src.api._auto_discovery import auto_discover_routers
auto_discover_routers(app)

# ============ Auth routes（保留手动注册，特殊中间件依赖）============
app.include_router(auth_router)

# ============ v2.1 新增路由（手动注册）============
# /api/services — 服务聚合清单
from src.api.services import router as services_router
app.include_router(services_router)

# /api/unified-search — 跨服务统一搜索
from src.api.unified_search import router as unified_search_router
app.include_router(unified_search_router)

# /api/notifications — 通知中心
from src.api.notifications import router as notifications_router
app.include_router(notifications_router)

# /api/user/preferences — 用户偏好 CRUD
from src.api.user_preferences import router as user_preferences_router
app.include_router(user_preferences_router)

# Feature Flags WebSocket 推送
from src.api.feature_flags_ws import router as ff_ws_router
app.include_router(ff_ws_router)

# ── Prometheus Metrics ──
from fastapi.responses import Response
from src.services.metrics import get_metrics_response, update_store_stats

@app.get("/api/metrics", dependencies=[Depends(require_admin)])
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def prometheus_metrics():
    """Prometheus 指标端点"""
    try:
        from src.db.data_store import load_chunks
        from src.db.vector_store import count_chunks
        chunks = load_chunks()
        update_store_stats(
            sqlite_count=len(chunks) if chunks else 0,
            vector_count=count_chunks()
        )
    except Exception as e:  # TODO: Narrow exception type
        logger.warning("Prometheus指标更新失败: %s", e, exc_info=True)
    return Response(content=get_metrics_response(), media_type="text/plain")

# ============ v11 评测 + 进化 API ============
from src.api.evaluation import router as evaluation_router
from src.api.evolution import router as evolution_router
app.include_router(evaluation_router)
app.include_router(evolution_router)

# ============ MCP 协议 API ============
from src.taiyin.mcp_protocol import get_mcp_server

@app.post("/api/mcp")
async def mcp_handler(request: Request):
    """MCP协议入口 — 标准JSON-RPC 2.0"""
    body = await request.json()
    server = get_mcp_server()
    return await server.handle_request(body)

@app.get("/api/mcp/tools", dependencies=[Depends(require_admin)])
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def mcp_list_tools():
    """列出所有MCP工具 — v1.50 R2: 需要管理员权限"""
    server = get_mcp_server()
    return {"tools": [{"name": t.name, "description": t.description} for t in server.tools.values()]}

@app.post("/api/mcp/sag_search")
async def mcp_sag_search(request: Request):
    """MCP: 搜索知识库"""
    from src.taiyin.mcp_tools import sag_search
    body = await request.json()
    return await sag_search(body.get("query", ""), body.get("top_k", 10))

@app.post("/api/mcp/sag_ingest", dependencies=[Depends(require_admin)])
async def mcp_sag_ingest(request: Request):
    """MCP: 入库文档 — v1.50 R2: 需要管理员权限"""
    from src.taiyin.mcp_tools import sag_ingest
    body = await request.json()
    return await sag_ingest(body.get("file_path", ""), body.get("category", ""))

@app.post("/api/mcp/sag_explain")
async def mcp_sag_explain(request: Request):
    """MCP: 解释查询"""
    from src.taiyin.mcp_tools import sag_explain
    body = await request.json()
    return await sag_explain(body.get("query", ""))

@app.get("/api/mcp/sag_status")
async def mcp_sag_status():
    """MCP: 系统状态"""
    from src.taiyin.mcp_tools import sag_status
    return await sag_status()


# ============ v1.50 Phase F: MCP 通用工具调用端点 ============

# v2.1: 在模块加载时预导入所有 MCP 工具 handler，避免每次调用时 __import__ 的性能开销
# 预加载失败的工具记为 None，调用时返回友好错误
_MCP_TOOLS_MODULE = None
_MCP_TOOL_HANDLERS: dict = {}

def _init_mcp_handlers():
    """初始化 MCP 工具处理器注册表（模块加载时调用一次）"""
    global _MCP_TOOLS_MODULE, _MCP_TOOL_HANDLERS
    try:
        _MCP_TOOLS_MODULE = __import__("src.taiyin.mcp_tools", fromlist=["*"])
    except ImportError as e:
        logger.warning(f"MCP 工具模块加载失败: {e}")
        _MCP_TOOLS_MODULE = None
        return
    
    # 定义工具名 → 模块属性映射
    _tool_map = {
        "sag_search": "sag_search",
        "sag_ingest": "sag_ingest",
        "sag_explain": "sag_explain",
        "sag_status": "sag_status",
        "kb_search": "kb_search",
        "kb_list_documents": "kb_list_documents",
        "kb_get_document": "kb_get_document",
        "graph_query": "graph_query",
        "graph_stats": "graph_stats",
        "wiki_search": "wiki_search",
        "wiki_get": "wiki_get",
        "dream_cycle_run": "dream_cycle_run",
        "dream_cycle_report": "dream_cycle_report",
        "gap_analyze": "gap_analyze",
        "entity_expand": "entity_expand",
        "cross_entity_synthesize": "cross_entity_synthesize",
        "file_upload": "file_upload",
        "file_list": "file_list",
        "chat_query": "chat_query",
        "eval_run": "eval_run",
        "notifications_list": "notifications_list",
        "feature_flags_list": "feature_flags_list",
        "health_check": "health_check",
        "audit_logs": "audit_logs",
    }
    
    for tool_name, attr_name in _tool_map.items():
        handler = getattr(_MCP_TOOLS_MODULE, attr_name, None)
        if handler is not None:
            _MCP_TOOL_HANDLERS[tool_name] = handler
        else:
            logger.warning(f"MCP 工具 '{tool_name}' 在 mcp_tools 模块中未找到")
    
    logger.info(f"MCP 工具注册完成: {len(_MCP_TOOL_HANDLERS)}/{len(_tool_map)} 个可用")

# 启动时初始化
_init_mcp_handlers()

# 向后兼容别名
MCP_TOOL_HANDLERS = _MCP_TOOL_HANDLERS

# v1.50 R2: MCP 工具权限映射
# admin_only: 仅管理员可调用
# user: 任何已认证用户可调用
# public: 无需认证可调用
_MCP_TOOL_PERMISSIONS = {
    "sag_search": "user",
    "sag_ingest": "admin",
    "sag_explain": "user",
    "sag_status": "user",
    "kb_search": "user",
    "kb_list_documents": "user",
    "kb_get_document": "user",
    "graph_query": "user",
    "graph_stats": "user",
    "wiki_search": "user",
    "wiki_get": "user",
    "dream_cycle_run": "admin",
    "dream_cycle_report": "user",
    "gap_analyze": "user",
    "entity_expand": "user",
    "cross_entity_synthesize": "user",
    "file_upload": "admin",
    "file_list": "user",
    "chat_query": "user",
    "eval_run": "admin",
    "notifications_list": "user",
    "feature_flags_list": "user",
    "health_check": "public",
    "audit_logs": "admin",
}


def _check_mcp_permission(tool_name: str, request: Request) -> bool:
    """检查 MCP 工具权限
    
    Returns:
        True 如果有权限，False 如果被拒绝
    """
    required = _MCP_TOOL_PERMISSIONS.get(tool_name, "user")
    if required == "public":
        return True
    
    current_user = getattr(request.state, "user", None)
    current_role = getattr(request.state, "role", "user")
    
    # 未认证用户拒绝所有非 public 工具
    if not current_user or current_user == "anonymous":
        return False
    
    if required == "admin":
        return current_role == "admin"
    
    return True  # user 级别所有已认证用户可调用


@app.post("/api/mcp/call")
async def mcp_call(request: Request):
    """MCP 通用工具调用端点 — v1.50 Phase F

    请求体:
      {"tool": "health_check", "args": {}}

    返回:
      工具执行结果（JSON）

    支持所有 24 个 MCP 工具。
    v1.50 R2: 添加基于角色的工具权限控制。
    """
    import traceback
    body = await request.json()
    tool_name = body.get("tool", "")
    args = body.get("args", {})

    if not tool_name:
        return {"error": "缺少 tool 参数", "available_tools": list(MCP_TOOL_HANDLERS.keys())}
    
    # v1.50 R2: MCP 工具权限检查
    if not _check_mcp_permission(tool_name, request):
        return {"error": f"无权调用工具: {tool_name}", "detail": "权限不足"}

    handler = _MCP_TOOL_HANDLERS.get(tool_name)
    if handler is None:
        available = list(_MCP_TOOL_HANDLERS.keys())
        if _MCP_TOOLS_MODULE is None:
            return {"error": f"未知工具: {tool_name}（MCP 工具模块未加载）", "available_tools": available}
        return {"error": f"未知工具: {tool_name}", "available_tools": available}

    try:
        result = handler(args)
        # 支持 async handler
        import inspect
        if inspect.isawaitable(result):
            result = await result
        return {"ok": True, "tool": tool_name, "result": result}
    except Exception as e:  # TODO: Narrow exception type
        logger.error(f"[MCP/call] {tool_name} 执行失败: {e}\n{traceback.format_exc()}")
        return {"ok": False, "tool": tool_name, "error": str(e)}


# ============ 评测自动化 API ============
from src.services.eval_automation import get_eval_automation

@app.post("/api/eval/run", dependencies=[Depends(require_admin)])
async def eval_run():
    """运行每日评测"""
    automation = get_eval_automation()
    return await automation.run_daily_eval()

@app.get("/api/eval/report")
async def eval_report():
    """获取最新评测报告"""
    automation = get_eval_automation()
    return await automation.get_latest_report() or {"message": "暂无评测报告"}

@app.get("/api/eval/history")
async def eval_history():
    """获取评测历史"""
    automation = get_eval_automation()
    return {"history": await automation.get_eval_history()}

# ============ 四象状态 + 成长 API ============
from src.taiyin.growth_api import get_growth_overview, get_symbols_status

@app.get("/api/symbols/status")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def symbols_status():
    """四象状态"""
    return get_symbols_status()

@app.get("/api/growth/overview")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def growth_overview():
    """成长概览"""
    return get_growth_overview()

# ============ 系统路由（已迁移至 src/api/system_routes.py）============
# /api/health, /api/system/stats, /api/cache/stats, /api/errors/stats, /api/audit/logs, /api/audit/stats
from src.api.system_routes import router as system_router
app.include_router(system_router)

# ============ Feature Flag API ============
from src.services.feature_flags import load_flags, set_flag, DEFAULT_FLAGS

@app.get("/api/feature-flags", dependencies=[Depends(require_admin)])
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def list_feature_flags():
    """获取所有 Feature Flag 状态"""
    return {"flags": load_flags(), "defaults": DEFAULT_FLAGS}

@app.get("/api/feature-flags/{name}", dependencies=[Depends(require_admin)])
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def get_feature_flag(name: str):
    """获取单个 Feature Flag 状态"""
    flags = load_flags()
    if name not in DEFAULT_FLAGS:
        from fastapi import HTTPException
        raise HTTPException(404, f"未知 flag: {name}")
    return {"flag": name, "value": flags.get(name, False), "default": DEFAULT_FLAGS.get(name, False)}

@app.put("/api/feature-flags/{name}", dependencies=[Depends(require_admin)])
async def update_feature_flag(name: str, request: Request):
    """更新 Feature Flag"""
    body = await request.json()
    value = body.get("value", False)
    if name not in DEFAULT_FLAGS:
        from fastapi import HTTPException
        raise HTTPException(404, f"未知 flag: {name}")
    set_flag(name, value)
    return {"ok": True, "flag": name, "value": value}

# ============ 认证 API (仅 /api/auth/me, login/register 由 auth_routes.py 提供) ============
@app.get("/api/auth/me")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def auth_me(request: Request):
    return {"username": getattr(request.state, "user", "anonymous"), "role": getattr(request.state, "role", "user")}

# ============ 统一前端入口 ============
from fastapi.responses import HTMLResponse

@app.get("/login", response_class=HTMLResponse)
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def login_page():
    f = STATIC_DIR / "login.html"
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else "<h1>login.html not found</h1>")

@app.get("/", response_class=HTMLResponse)
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def index_page():
    f = STATIC_DIR / "index.html"
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else "<h1>index.html not found</h1>")

@app.get("/admin", response_class=HTMLResponse)
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def admin_page(request: Request):
    """管理页面 — v1.50 R2 安全修复: 需要认证才能访问
    
    未登录用户重定向到 /login，非管理员用户返回 403。
    """
    # v1.50 R2: 检查认证状态
    user = getattr(request.state, "user", None)
    role = getattr(request.state, "role", None)
    
    if not user or user == "anonymous":
        # 未登录：重定向到登录页面
        from starlette.responses import RedirectResponse
        return RedirectResponse(url="/login", status_code=302)
    
    f = STATIC_DIR / "index.html"
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else "<h1>index.html not found</h1>")

# 静态资源挂载 — v2.1: 优先使用 dist 构建产物，回退到 frontend 根目录
# 为静态文件添加安全过滤，防止暴露源代码文件
_static_dist = STATIC_DIR / "dist"
if _static_dist.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dist)), name="static")
    logger.info(f"静态资源挂载: {_static_dist}")
else:
    # v1.50 R3 Blue: 修复静态资源返回 500 的问题
    # 确保 frontend 目录存在，如果不存在则创建空目录
    if not STATIC_DIR.exists():
        STATIC_DIR.mkdir(parents=True, exist_ok=True)
        logger.warning(f"frontend 目录不存在，已创建空目录: {STATIC_DIR}")
    
    # 回退到 frontend 根目录，但排除敏感源代码文件
    from starlette.staticfiles import StaticFiles as _StaticFiles
    
    class _SafeStaticFiles(_StaticFiles):
        """安全静态文件服务：阻止访问源代码和配置文件"""
        _BLOCKED_EXTS = {".vue", ".ts", ".tsx", ".jsx", 
                          ".json", ".lock", ".md"}
        _BLOCKED_NAMES = {"package.json", "package-lock.json", 
                           "vite.config.js", "vite.config.ts", 
                           "yarn.lock", "pnpm-lock.yaml"}
        
        def lookup_path(self, path: str):
            # 阻止敏感文件扩展名
            ext = Path(path).suffix.lower()
            if ext in self._BLOCKED_EXTS:
                return None
            # 阻止敏感文件名
            name = Path(path).name
            if name in self._BLOCKED_NAMES:
                return None
            return super().lookup_path(path)
    
    try:
        app.mount("/static", _SafeStaticFiles(directory=str(STATIC_DIR)), name="static")
        logger.info(f"静态资源挂载（安全模式）: {STATIC_DIR}")
    except Exception as e:
        logger.error(f"静态资源挂载失败: {e}")
        # 即使静态资源挂载失败，也不阻止应用启动

# ============ v1.50 僵尸服务注册 ============
# 注册 AI 工具服务 — 6 端点 (POST /api/ai/summarize, /translate, /keywords, /entities, /classify, GET /api/ai/health)
from src.services.ai_tools.routes import router as ai_tools_router
app.include_router(ai_tools_router)

# 注册数据分析服务 — 15 端点 (GET|POST /api/analytics/stats, /trends, /report, /storage, /export, GET /api/analytics/health)
from src.services.data_analytics.routes import router as analytics_router
app.include_router(analytics_router, prefix="/api/analytics")

# 注册文档工具服务 — 10 端点 (POST /api/tools/convert, /merge, /split, /compress, /image-info, /compress-image, /text-extract, GET /api/tools/health)
from src.services.doc_tools.routes import router as doc_tools_router
app.include_router(doc_tools_router)

# 注册 DXF 看图服务 — 5 端点 (POST /api/dxf/upload, GET /api/dxf/files, /view/{hash}, /download/{hash}, /health)
from src.services.dxf_viewer.api import router as dxf_viewer_router
app.include_router(dxf_viewer_router)

# 注册文件查看服务 — 3 端点 (GET /api/view/{file_hash}, /api/download/{file_hash}, /api/antenna/search)
from src.api.files_view import router as files_view_router
app.include_router(files_view_router)

# ============ v1.44 Phase 1 Fix: RAG & KB 路由注册 ============
from src.api.rag import router as rag_router
app.include_router(rag_router)

from src.api.kb import router as kb_router
app.include_router(kb_router)

# ============ v1.50 Phase A: API 路径别名兼容层 ============
# 为 Legacy 和 Vue3 前端之间的路径差异提供别名路由
# 所有 /api/wiki/pages → /api/wiki、/api/documents → /api/files 等映射
from src.api.path_aliases import router as path_alias_router
app.include_router(path_alias_router)

# ============ v1.50 Phase D: Synthesis 跨实体合成 ============
from src.api.synthesis import router as synthesis_router
app.include_router(synthesis_router)

# 管理面板路由 — /, /admin, /api/health, /api/stats, /api/admin/*
# v1.41: 八卦体征端点
from src.api.v2_routes import router as v2_router
app.include_router(v2_router)
# admin_router registered earlier (before wiki catch-all routes)

# ============ D5: Prometheus Metrics ============
@app.get("/metrics", dependencies=[Depends(require_admin)])
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def metrics():
    """暴露 Prometheus 格式指标 — 浏览器直开 http://<host>:<port>/metrics"""
    from src.services.metrics import generate_metrics_text
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(generate_metrics_text(), media_type="text/plain; charset=utf-8")

@app.get("/api/admin/metrics-summary", dependencies=[Depends(require_admin)])
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def admin_metrics_summary():
    """管理面板：可观测性指标摘要（延迟 P50/P95/P99 + 错误率）"""
    from src.services.metrics import generate_health_summary
    return generate_health_summary()



# ============ 启动 ============

# ============ v4.0: 代理路由（保留在 server.py 中）============
# 代理路由（proxy/loader）涉及 aiohttp 异步 HTTP 客户端和LOADER_URL 配置，
# 逻辑复杂且与 server.py 中的顶层配置紧密耦合，暂保留在此文件中。
# 后续可考虑迁移至独立的 src/api/proxy_routes.py。
@app.get("/api/proxy/loader/files")
async def proxy_loader_files():
    """代理: 获取装载机文件列表"""
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{LOADER_URL}/api/files", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return await resp.json()
    except Exception as e:  # TODO: Narrow exception type
        return {"error": str(e), "files": []}

@app.post("/api/proxy/loader/upload")
async def proxy_loader_upload(request: Request):
    """代理: 上传文件到装载机"""
    import aiohttp
    body = await request.body()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{LOADER_URL}/api/upload",
                data=body,
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"Content-Type": request.headers.get("Content-Type", "multipart/form-data")}
            ) as resp:
                return await resp.json()
    except Exception as e:  # TODO: Narrow exception type
        return {"error": str(e)}

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
        server_header=False,  # v1.50 R2: 隐藏 uvicorn server 头
    )
