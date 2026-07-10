import asyncio
"""
伏羲 v1.44 — 路由注册
=====================
从 server.py 拆分: 自动路由发现、服务路由、MCP 路由、内联路由。
"""
import logging
from pathlib import Path

from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse, Response, PlainTextResponse

from src.config import LOADER_URL

logger = logging.getLogger("server")

STATIC_DIR = Path(__file__).parent.parent.parent / "frontend"
_is_production = __import__('os').environ.get("FUXI_ENV", "production").lower() == "production"


def register_all_routes(app: FastAPI) -> None:
    """注册所有路由到 FastAPI 应用"""

    _register_auto_discovered_routes(app)
    _register_service_routes(app)
    _register_mcp_routes(app)
    _register_inline_routes(app)
    _register_static_routes(app)

    logger.info("[Routes] 所有路由注册完成")


# ── 路由自动发现 ──

def _register_auto_discovered_routes(app: FastAPI) -> None:
    """自动发现 src/api/ 下的路由"""
    from src.api._auto_discovery import auto_discover_routers
    auto_discover_routers(app)

    # Auth routes（手动注册，特殊中间件依赖）
    from src.api.auth_routes import router as auth_router
    app.include_router(auth_router)


# ── 服务路由 ──

def _register_service_routes(app: FastAPI) -> None:
    """注册各服务路由（保留手动注册的路由）"""
    from src.api.services import router as services_router
    app.include_router(services_router)

    from src.api.unified_search import router as unified_search_router
    app.include_router(unified_search_router)

    from src.api.notifications import router as notifications_router
    app.include_router(notifications_router)

    from src.api.user_preferences import router as user_preferences_router
    app.include_router(user_preferences_router)

    from src.api.feature_flags_ws import router as ff_ws_router
    app.include_router(ff_ws_router)

    from src.api.evaluation import router as evaluation_router
    from src.api.evolution import router as evolution_router
    app.include_router(evaluation_router)
    app.include_router(evolution_router)

    from src.api.system_routes import router as system_router
    app.include_router(system_router)

    from src.api.path_aliases import router as path_alias_router
    app.include_router(path_alias_router)

    from src.api.synthesis import router as synthesis_router
    app.include_router(synthesis_router)

    from src.api.v2_routes import router as v2_router
    app.include_router(v2_router)

    from src.api.rag import router as rag_router
    app.include_router(rag_router)

    from src.api.kb import router as kb_router
    app.include_router(kb_router)

    from src.api.tenant_routes import router as tenant_router
    app.include_router(tenant_router)

    from src.api.files_view import router as files_view_router
    app.include_router(files_view_router)

    # Zombie services
    from src.services.ai_tools.routes import router as ai_tools_router
    app.include_router(ai_tools_router)

    from src.services.data_analytics.routes import router as analytics_router
    app.include_router(analytics_router, prefix="/api/analytics")

    from src.services.doc_tools.routes import router as doc_tools_router
    app.include_router(doc_tools_router)

    from src.services.dxf_viewer.api import router as dxf_viewer_router
    app.include_router(dxf_viewer_router)


# ── MCP 路由 ──

def _register_mcp_routes(app: FastAPI) -> None:
    """注册 MCP 路由"""
    from src.core.mcp_routes import register_mcp_routes
    register_mcp_routes(app)


# ── 内联路由 ──

def _register_inline_routes(app: FastAPI) -> None:
    """注册内联路由（metrics、认证、评测、四象状态、feature flags、前端页面、代理路由）"""

    from src.api.auth import require_admin
    from src.api.response import success, error

    # ── Prometheus Metrics ──
    from src.services.metrics import get_metrics_response, update_store_stats, generate_metrics_text, generate_health_summary

    @app.get("/api/metrics", dependencies=[Depends(require_admin)])
    async def prometheus_metrics():
        try:
            from src.db.data_store import load_chunks
            from src.db.vector_store import count_chunks
            chunks = await asyncio.to_thread(load_chunks)
            update_store_stats(
                sqlite_count=len(chunks) if chunks else 0,
                vector_count=count_chunks()
            )
        except (ImportError, AttributeError, OSError) as e:
            logger.warning("Prometheus指标更新失败: %s", e, exc_info=True)
        return Response(content=get_metrics_response(), media_type="text/plain")

    @app.get("/metrics", dependencies=[Depends(require_admin)])
    async def metrics():
        return PlainTextResponse(generate_metrics_text(), media_type="text/plain; charset=utf-8")

    @app.get("/api/admin/metrics-summary", dependencies=[Depends(require_admin)])
    async def admin_metrics_summary():
        return generate_health_summary()

    # ── 认证 ──
    @app.get("/api/auth/me")
    async def auth_me(request: Request):
        return success(data={
            "username": getattr(request.state, "user", "anonymous"),
            "role": getattr(request.state, "role", "user"),
        }, message="认证信息")

    # ── 评测自动化 ──
    from src.services.eval_automation import get_eval_automation

    @app.post("/api/eval/run", dependencies=[Depends(require_admin)])
    async def eval_run():
        automation = get_eval_automation()
        return await automation.run_daily_eval()

    @app.get("/api/eval/report")
    async def eval_report():
        automation = get_eval_automation()
        report = await automation.get_latest_report()
        return success(data=report, message="最新评测报告") if report else success(data=None, message="暂无评测报告")

    @app.get("/api/eval/history")
    async def eval_history():
        automation = get_eval_automation()
        return success(data={"history": await automation.get_eval_history()}, message="评测历史")

    # ── 四象状态 + 成长 ──
    from src.taiyin.growth_api import get_growth_overview, get_symbols_status

    @app.get("/api/symbols/status")
    async def symbols_status():
        return success(data=get_symbols_status(), message="四象状态")

    @app.get("/api/growth/overview")
    async def growth_overview():
        return success(data=get_growth_overview(), message="成长概览")

    # ── Feature Flags ──
    from src.services.feature_flags import load_flags, set_flag, DEFAULT_FLAGS

    @app.get("/api/feature-flags", dependencies=[Depends(require_admin)])
    async def list_feature_flags():
        return success(data={"flags": load_flags(), "defaults": DEFAULT_FLAGS})

    @app.get("/api/feature-flags/{name}", dependencies=[Depends(require_admin)])
    async def get_feature_flag(name: str):
        from fastapi import HTTPException
        flags = load_flags()
        if name not in DEFAULT_FLAGS:
            raise HTTPException(404, f"未知 flag: {name}")
        return success(data={"flag": name, "value": flags.get(name, False), "default": DEFAULT_FLAGS.get(name, False)})

    @app.put("/api/feature-flags/{name}", dependencies=[Depends(require_admin)])
    async def update_feature_flag(name: str, request: Request):
        from fastapi import HTTPException
        body = await request.json()
        value = body.get("value", False)
        if name not in DEFAULT_FLAGS:
            raise HTTPException(404, f"未知 flag: {name}")
        set_flag(name, value)
        return success(data={"flag": name, "value": value}, message=f"Feature Flag {name} 已更新")

    # ── 前端入口页 ──
    @app.get("/login", response_class=HTMLResponse)
    async def login_page():
        f = STATIC_DIR / "login.html"
        if f.exists():
            content = await asyncio.to_thread(f.read_text, encoding="utf-8")
            return HTMLResponse(content)
        return HTMLResponse("<h1>login.html not found</h1>")

    @app.get("/", response_class=HTMLResponse)
    async def index_page():
        f = STATIC_DIR / "index.html"
        if f.exists():
            content = await asyncio.to_thread(f.read_text, encoding="utf-8")
            return HTMLResponse(content)
        return HTMLResponse("<h1>index.html not found</h1>")

    @app.get("/admin", response_class=HTMLResponse)
    async def admin_page(request: Request):
        from starlette.responses import RedirectResponse
        user = getattr(request.state, "user", None)
        if not user or user == "anonymous":
            return RedirectResponse(url="/login", status_code=302)
        f = STATIC_DIR / "index.html"
        if f.exists():
            content = await asyncio.to_thread(f.read_text, encoding="utf-8")
            return HTMLResponse(content)
        return HTMLResponse("<h1>index.html not found</h1>")

    # ── 代理路由 ──
    @app.get("/api/proxy/loader/files")
    async def proxy_loader_files():
        from src.core.http_client import get_session
        try:
            session = await get_session()
            async with session.get(f"{LOADER_URL}/api/files", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return await resp.json()
        except (OSError, RuntimeError, ValueError) as e:
            return error(f"代理加载器请求失败: {str(e)}", status_code=502, detail=str(e))

    @app.post("/api/proxy/loader/upload")
    async def proxy_loader_upload(request: Request):
        from src.core.http_client import get_session
        body = await request.body()
        try:
            session = await get_session()
            async with session.post(
                f"{LOADER_URL}/api/upload",
                data=body,
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"Content-Type": request.headers.get("Content-Type", "multipart/form-data")}
            ) as resp:
                return await resp.json()
        except (OSError, RuntimeError, ValueError) as e:
            return error(f"代理加载器上传失败: {str(e)}", status_code=502, detail=str(e))


# ── 静态资源 ──

def _register_static_routes(app: FastAPI) -> None:
    """注册静态资源挂载"""
    from fastapi.staticfiles import StaticFiles
    from starlette.staticfiles import StaticFiles as _StaticFiles

    _static_dist = STATIC_DIR / "dist"
    if _static_dist.exists():
        app.mount("/static", StaticFiles(directory=str(_static_dist)), name="static")
        logger.info(f"静态资源挂载: {_static_dist}")
    else:
        class _SafeStaticFiles(_StaticFiles):
            _BLOCKED_EXTS = {".vue", ".ts", ".tsx", ".jsx", ".json", ".lock", ".md"}
            _BLOCKED_NAMES = {"package.json", "package-lock.json", "vite.config.js", "vite.config.ts", "yarn.lock", "pnpm-lock.yaml"}
            def lookup_path(self, path: str):
                ext = Path(path).suffix.lower()
                if ext in self._BLOCKED_EXTS:
                    return None
                name = Path(path).name
                if name in self._BLOCKED_NAMES:
                    return None
                return super().lookup_path(path)
        app.mount("/static", _SafeStaticFiles(directory=str(STATIC_DIR)), name="static")
        logger.info(f"静态资源挂载（安全模式）: {STATIC_DIR}")
