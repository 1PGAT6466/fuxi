"""
伏羲 Fuxi · 企业知识认知系统 v1.40
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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from src.config import HOST, PORT, VERSION, CORS_ORIGINS

# 静态资源目录指向 frontend/
STATIC_DIR = _project_root / "frontend"

# ============ 创建 FastAPI 应用 ============
from fastapi.staticfiles import StaticFiles
app = FastAPI(
    title="伏羲·内世界 — 企业知识认知系统",
    version="1.43",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ============ 伏羲 1.40 生命体启动 ============
_fuxi_instance = None  # module-level fallback

async def _start_fuxi():
    """启动伏羲生命体"""
    global _fuxi_instance
    try:
        from src.hypothalamus.fuxi import Fuxi
        _fuxi_instance = Fuxi()
        app.state.fuxi = _fuxi_instance
        app.state.meridian = _fuxi_instance.meridian
        app.state.fuxi_version = "1.43"
        app.state.fuxi_born_at = __import__('time').time()
        await _fuxi_instance.born()
        logging.getLogger("server").info("[Fuxi] 伏羲 1.42 生命体已苏醒")
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
from src.services.error_handler import setup_error_handlers
setup_error_handlers(app)
# ============ 中间件 ============
# ── API 认证中间件 ──
from src.api.auth import AuthMiddleware, InputLimitMiddleware
app.add_middleware(AuthMiddleware)
app.add_middleware(InputLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 内网环境全放开
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "x-admin-token"],
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

# ============ 注册路由 ============

# 搜索路由 — /api/search, /api/search-history, /api/images/*
from src.api.search import router as search_router
app.include_router(search_router)

# AI 对话路由 — /api/chat, /api/chat/agent
from src.api.chat import router as chat_router
app.include_router(chat_router)

# 文档管理路由 — /api/documents/*, /api/raw-store, /api/ingest-batch, /api/reindex, /api/reset
from src.api.documents import router as documents_router

# v10.1: MinerU + Unstructured dual engine
from src.services.mineru import apply_patches
apply_patches()
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

# 静态资源挂载
app.mount("/static/css", StaticFiles(directory=str(STATIC_DIR / "css")), name="static_css")
app.mount("/static/js", StaticFiles(directory=str(STATIC_DIR / "js")), name="static_js")
# 兼容旧路径
app.mount("/js", StaticFiles(directory=str(STATIC_DIR / "js")), name="static_js_legacy")
app.mount("/static/admin/js", StaticFiles(directory=str(STATIC_DIR / "admin" / "js")), name="static_admin_js")
app.mount("/static/admin", StaticFiles(directory=str(STATIC_DIR / "admin"), html=True), name="static_admin")

# 管理面板路由 — /, /admin, /api/health, /api/stats, /api/admin/*
# v1.41: 八卦体征端点
from src.api.v2_routes import router as v2_router
app.include_router(v2_router)
# admin_router registered earlier (before wiki catch-all routes)

# ============ D5: Prometheus Metrics ============
@app.get("/metrics")
async def metrics():
    """暴露 Prometheus 格式指标 — 浏览器直开 http://172.25.30.200:8080/metrics"""
    from src.services.metrics import generate_metrics_text
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(generate_metrics_text(), media_type="text/plain; charset=utf-8")

@app.get("/api/admin/metrics-summary")
async def admin_metrics_summary():
    """管理面板：可观测性指标摘要（延迟 P50/P95/P99 + 错误率）"""
    from src.services.metrics import generate_health_summary
    return generate_health_summary()



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
    )
