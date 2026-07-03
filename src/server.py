"""
伏羲 Fuxi · 企业知识认知系统 v1.50
==================================
认知架构：大脑(调度) + 感官(执行) + 自省(反思) + 记忆(存储)
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
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from src.config import HOST, PORT, VERSION, CORS_ORIGINS, LOADER_URL

# 静态资源目录指向 frontend/
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

async def _start_fuxi():
    """启动伏羲生命体"""
    global _fuxi_instance
    try:
        from src.hypothalamus.fuxi import Fuxi
        _fuxi_instance = Fuxi()
        app.state.fuxi = _fuxi_instance
        app.state.meridian = _fuxi_instance.meridian
        app.state.fuxi_version = _VERSION
        app.state.fuxi_born_at = __import__('time').time()
        await _fuxi_instance.born()
        logging.getLogger("server").info(f"[Fuxi] 伏羲 {_VERSION} 生命体已苏醒")
    except Exception as e:
        logging.getLogger("server").error(f"[Fuxi] 启动失败: {e}")

async def _stop_fuxi():
    """休眠伏羲"""
    global _fuxi_instance
    if _fuxi_instance:
        await _fuxi_instance.sleep()
        logging.getLogger("server").info("[Fuxi] 伏羲已休眠")

@app.on_event("startup")
async def startup():
    await _start_fuxi()

@app.on_event("shutdown")
async def shutdown():
    await _stop_fuxi()

# 注册统一异常处理器
# from src.services.error_handler import setup_error_handlers
# setup_error_handlers(app)
# ============ 中间件 ============
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
        except Exception:
            pass
        return response
    except Exception as e:
        duration_ms = (time.time() - start) * 1000
        try:
            from src.infra.request_metrics import get_request_metrics
            get_request_metrics().record_request(duration_ms, False)
        except Exception:
            pass
        raise

# ============ 注册路由 ============

# 搜索路由 — /api/search, /api/search-history, /api/images/*
from src.api.search import router as search_router
app.include_router(search_router)

# AI 对话路由 — /api/chat, /api/chat/agent
from src.api.chat import router as chat_router
app.include_router(chat_router)

# Auth routes — /api/auth/login, /api/auth/register
app.include_router(auth_router)

# 文档管理路由 — /api/documents/*, /api/raw-store, /api/ingest-batch, /api/reindex, /api/reset
from src.api.documents import router as documents_router

# v10.1: MinerU + Unstructured dual engine
# from src.services.mineru import apply_patches
# apply_patches()
app.include_router(documents_router)

# 知识图谱路由 — /api/graph, /api/graph/path, /api/graph/build, /api/graph/nodes
from src.api.graph import router as graph_router
# 元数据中心路由 — /api/metadata/*
from src.api.metadata import router as metadata_router
app.include_router(metadata_router)

app.include_router(graph_router)

# 反馈与用户路由 — /api/feedback, /api/behavior, /api/user/preferences
from src.api.feedback import router as feedback_router
app.include_router(feedback_router)

# 评测仪表板路由 — /api/dashboard
from src.api.dashboard import router as dashboard_router

# LLM-Wiki + 反馈闭环路由 — /api/wiki/*, /api/feedback/*
from src.api.wiki import router as wiki_router

# ── Prometheus Metrics ──
from fastapi.responses import Response
from src.services.metrics import get_metrics_response, update_store_stats

@app.get("/api/metrics")
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
    except:
        pass
    return Response(content=get_metrics_response(), media_type="text/plain")
from src.api.worldtree import router as worldtree_router
app.include_router(worldtree_router)
# Admin router must be before wiki (wiki has /{wiki_id} catch-all)
from src.api.admin import router as admin_router
app.include_router(admin_router)
app.include_router(wiki_router)
app.include_router(dashboard_router)

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
async def symbols_status():
    """四象状态"""
    return get_symbols_status()

@app.get("/api/growth/overview")
async def growth_overview():
    """成长概览"""
    return get_growth_overview()

# ============ 健康检查 + 系统监控 API ============
@app.get("/api/health")
async def health_check():
    """健康检查"""
    try:
        from src.infra.health_check import get_health_checker
        checker = get_health_checker()
        result = await checker.check_all()
        return result
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/api/system/stats")
async def system_stats():
    """系统统计"""
    try:
        from src.infra.system_monitor import get_system_monitor
        return get_system_monitor().get_system_stats()
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/cache/stats")
async def cache_stats():
    """缓存统计"""
    try:
        from src.infra.cache_stats import get_cache_stats
        return get_cache_stats().get_stats()
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/errors/stats")
async def error_stats():
    """错误统计"""
    try:
        from src.infra.error_tracker import get_error_tracker
        return get_error_tracker().get_error_stats()
    except Exception as e:
        return {"error": str(e)}

# ============ Feature Flag API ============
from src.services.feature_flags import load_flags, set_flag, DEFAULT_FLAGS

@app.get("/api/feature-flags")
async def list_feature_flags():
    """获取所有 Feature Flag 状态"""
    return {"flags": load_flags(), "defaults": DEFAULT_FLAGS}

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
async def auth_me(request: Request):
    return {"username": getattr(request.state, "user", "anonymous"), "role": getattr(request.state, "role", "user")}

# ============ 统一前端入口 ============
from fastapi.responses import HTMLResponse, FileResponse

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    f = STATIC_DIR / "login.html"
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else "<h1>login.html not found</h1>")

@app.get("/", response_class=HTMLResponse)
async def index_page():
    f = STATIC_DIR / "index.html"
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else "<h1>index.html not found</h1>")

@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    f = STATIC_DIR / "index.html"
    return HTMLResponse(f.read_text(encoding="utf-8") if f.exists() else "<h1>index.html not found</h1>")

# 静态资源挂载
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 管理面板路由 — /, /admin, /api/health, /api/stats, /api/admin/*
# v1.41: 八卦体征端点
from src.api.v2_routes import router as v2_router
app.include_router(v2_router)
# admin_router registered earlier (before wiki catch-all routes)

# ============ D5: Prometheus Metrics ============
@app.get("/metrics")
async def metrics():
    """暴露 Prometheus 格式指标 — 浏览器直开 http://<host>:<port>/metrics"""
    from src.services.metrics import generate_metrics_text
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(generate_metrics_text(), media_type="text/plain; charset=utf-8")

@app.get("/api/admin/metrics-summary")
async def admin_metrics_summary():
    """管理面板：可观测性指标摘要（延迟 P50/P95/P99 + 错误率）"""
    from src.services.metrics import generate_health_summary
    return generate_health_summary()



# ============ 启动 ============

# v4.0: 代理路由 — 前端通过后端访问装载机
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
