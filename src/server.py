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
app = FastAPI(
    title="伏羲·内世界 — 企业知识认知系统",
    version=_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
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
            from src.bagua.intent_bus import IntentBus, get_intent_bus

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
    except Exception as e:
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
        except Exception as e:
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
    except Exception as e:
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
        except Exception as e:
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
    except Exception:
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
    limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
except ImportError:
    limiter = None

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
        except Exception as e:
            logger.warning("Exception 失败: %s", e, exc_info=True)
        return response
    except Exception as e:
        duration_ms = (time.time() - start) * 1000
        try:
            from src.infra.request_metrics import get_request_metrics
            get_request_metrics().record_request(duration_ms, False)
        except Exception as e:
            logger.warning("Exception 失败: %s", e, exc_info=True)
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

@app.get("/api/metrics")
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
    except Exception as e:
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

@app.get("/api/mcp/tools")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def mcp_list_tools():
    """列出所有MCP工具"""
    server = get_mcp_server()
    return {"tools": [{"name": t.name, "description": t.description} for t in server.tools.values()]}

@app.post("/api/mcp/sag_search")
async def mcp_sag_search(request: Request):
    """MCP: 搜索知识库"""
    from src.taiyin.mcp_tools import sag_search
    body = await request.json()
    return await sag_search(body.get("query", ""), body.get("top_k", 10))

@app.post("/api/mcp/sag_ingest")
async def mcp_sag_ingest(request: Request):
    """MCP: 入库文档"""
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

# MCP 工具处理器注册表 — 直接 map tool_name → handler
MCP_TOOL_HANDLERS = {
    "sag_search": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["sag_search"]).sag_search(
        query=args.get("query", ""), top_k=args.get("top_k", 10)),
    "sag_ingest": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["sag_ingest"]).sag_ingest(
        file_path=args.get("file_path", ""), category=args.get("category", "")),
    "sag_explain": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["sag_explain"]).sag_explain(
        query=args.get("query", "")),
    "sag_status": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["sag_status"]).sag_status(),
    "kb_search": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["kb_search"]).kb_search(
        query=args.get("query", ""), top_k=args.get("top_k", 5), mode=args.get("mode", "semantic")),
    "kb_list_documents": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["kb_list_documents"]).kb_list_documents(),
    "kb_get_document": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["kb_get_document"]).kb_get_document(
        doc_id=args.get("doc_id", "")),
    "graph_query": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["graph_query"]).graph_query(
        entity=args.get("entity", ""), source=args.get("source", ""),
        target=args.get("target", ""), edge_type=args.get("edge_type", ""),
        min_confidence=float(args.get("min_confidence", 0.0)), limit=int(args.get("limit", 100))),
    "graph_stats": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["graph_stats"]).graph_stats(),
    "wiki_search": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["wiki_search"]).wiki_search(
        q=args.get("q", ""), category=args.get("category", ""), limit=int(args.get("limit", 20))),
    "wiki_get": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["wiki_get"]).wiki_get(
        page_id=args.get("page_id", "")),
    "dream_cycle_run": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["dream_cycle_run"]).dream_cycle_run(),
    "dream_cycle_report": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["dream_cycle_report"]).dream_cycle_report(),
    "gap_analyze": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["gap_analyze"]).gap_analyze(
        query=args.get("query", ""), topic=args.get("topic", "")),
    "entity_expand": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["entity_expand"]).entity_expand(
        entity_name=args.get("entity_name", ""), top_k=int(args.get("top_k", 10))),
    "cross_entity_synthesize": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["cross_entity_synthesize"]).cross_entity_synthesize(
        entity_a=args.get("entity_a", ""), entity_b=args.get("entity_b", "")),
    "file_upload": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["file_upload"]).file_upload(
        file_path=args.get("file_path", ""), category=args.get("category", "")),
    "file_list": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["file_list"]).file_list(
        page=int(args.get("page", 1)), page_size=int(args.get("page_size", 50))),
    "chat_query": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["chat_query"]).chat_query(
        query=args.get("query", ""), history=args.get("history", [])),
    "eval_run": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["eval_run"]).eval_run(
        dataset=args.get("dataset", ""), test_name=args.get("test_name", "")),
    "notifications_list": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["notifications_list"]).notifications_list(
        page=int(args.get("page", 1)), page_size=int(args.get("page_size", 20)),
        unread_only=bool(args.get("unread_only", False))),
    "feature_flags_list": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["feature_flags_list"]).feature_flags_list(),
    "health_check": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["health_check"]).health_check(),
    "audit_logs": lambda args: __import__("src.taiyin.mcp_tools", fromlist=["audit_logs"]).audit_logs(
        user=args.get("user", ""), action=args.get("action", ""),
        days=int(args.get("days", 1)), limit=int(args.get("limit", 100))),
}


@app.post("/api/mcp/call")
async def mcp_call(request: Request):
    """MCP 通用工具调用端点 — v1.50 Phase F

    请求体:
      {"tool": "health_check", "args": {}}

    返回:
      工具执行结果（JSON）

    支持所有 24 个 MCP 工具。
    """
    import traceback
    body = await request.json()
    tool_name = body.get("tool", "")
    args = body.get("args", {})

    if not tool_name:
        return {"error": "缺少 tool 参数", "available_tools": list(MCP_TOOL_HANDLERS.keys())}

    handler = MCP_TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return {"error": f"未知工具: {tool_name}", "available_tools": list(MCP_TOOL_HANDLERS.keys())}

    try:
        result = handler(args)
        # 支持 async handler
        import inspect
        if inspect.isawaitable(result):
            result = await result
        return {"ok": True, "tool": tool_name, "result": result}
    except Exception as e:
        logger.error(f"[MCP/call] {tool_name} 执行失败: {e}\n{traceback.format_exc()}")
        return {"ok": False, "tool": tool_name, "error": str(e)}


# ============ 评测自动化 API ============
from src.services.eval_automation import get_eval_automation

@app.post("/api/eval/run")
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

# ============ v2.1 新增：通知中心 + 统一搜索 + 用户偏好 ============
from src.api.notifications import router as notifications_router
app.include_router(notifications_router)

from src.api.unified_search import router as unified_search_router
app.include_router(unified_search_router)

from src.api.user_preferences import router as user_prefs_router
app.include_router(user_prefs_router)

# ============ Feature Flag API ============
from src.services.feature_flags import load_flags, set_flag, DEFAULT_FLAGS

@app.get("/api/feature-flags")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def list_feature_flags():
    """获取所有 Feature Flag 状态"""
    return {"flags": load_flags(), "defaults": DEFAULT_FLAGS}

@app.get("/api/feature-flags/{name}")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def get_feature_flag(name: str):
    """获取单个 Feature Flag 状态"""
    flags = load_flags()
    if name not in DEFAULT_FLAGS:
        from fastapi import HTTPException
        raise HTTPException(404, f"未知 flag: {name}")
    return {"flag": name, "value": flags.get(name, False), "default": DEFAULT_FLAGS.get(name, False)}

@app.put("/api/feature-flags/{name}")
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
from fastapi.responses import HTMLResponse, FileResponse

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
async def admin_page():
    f = STATIC_DIR / "index.html"
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else "<h1>index.html not found</h1>")

# 静态资源挂载
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

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

# ============ v1.50 Phase D: Synthesis 跨实体合成 ============
from src.api.synthesis import router as synthesis_router
app.include_router(synthesis_router)

# 管理面板路由 — /, /admin, /api/health, /api/stats, /api/admin/*
# v1.41: 八卦体征端点
from src.api.v2_routes import router as v2_router
app.include_router(v2_router)
# admin_router registered earlier (before wiki catch-all routes)

# ============ D5: Prometheus Metrics ============
@app.get("/metrics")
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
    except Exception as e:
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
    except Exception as e:
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
    )
