import asyncio

"""
伏羲 v1.44 — 路由注册
=====================
从 server.py 拆分: 自动路由发现、服务路由、MCP 路由、内联路由。
"""
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from src.config import LOADER_URL

logger = logging.getLogger("server")

STATIC_DIR = Path(__file__).parent.parent.parent / "frontend" / "vue3-migration" / "dist"
_is_production = __import__("os").environ.get("FUXI_ENV", "production").lower() == "production"


def register_all_routes(app: FastAPI) -> None:
    """注册所有路由到 FastAPI 应用"""

    _register_auto_discovered_routes(app)
    _register_service_routes(app)
    _register_mcp_routes(app)
    _register_static_routes(app)  # 静态资源必须在 inline 路由之前注册
    _register_inline_routes(app)

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

    from src.api.favorites import router as favorites_router

    app.include_router(favorites_router)

    from src.api.history import router as history_router

    app.include_router(history_router)

    from src.api.feedback import router as feedback_router

    app.include_router(feedback_router)

    from src.api.tasks import router as tasks_router

    app.include_router(tasks_router)

    from src.api.feature_flags_ws import router as ff_ws_router

    app.include_router(ff_ws_router)

    from src.api.evaluation import router as evaluation_router
    from src.api.evolution import router as evolution_router

    app.include_router(evaluation_router)
    app.include_router(evolution_router)

    from src.api.workflows import router as workflows_router

    app.include_router(workflows_router)

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

    # 新增的 API 路由
    from src.api.dashboard_new import router as dashboard_new_router

    app.include_router(dashboard_new_router)

    from src.api.auth_new import router as auth_new_router

    app.include_router(auth_new_router)

    from src.api.user_new import router as user_new_router

    app.include_router(user_new_router)

    from src.api.notifications_new import router as notifications_new_router

    app.include_router(notifications_new_router)

    from src.api.history_new import router as history_new_router

    app.include_router(history_new_router)

    from src.api.favorites_new import router as favorites_new_router

    app.include_router(favorites_new_router)

    from src.api.clipboard_new import router as clipboard_new_router

    app.include_router(clipboard_new_router)

    from src.api.search_new import router as search_new_router

    app.include_router(search_new_router)

    from src.api.ops_new import router as ops_new_router

    app.include_router(ops_new_router)

    from src.api.evaluation_new import router as evaluation_new_router

    app.include_router(evaluation_new_router)

    from src.api.feature_flags_new import router as feature_flags_new_router

    app.include_router(feature_flags_new_router)

    from src.api.layouts_new import router as layouts_new_router

    app.include_router(layouts_new_router)

    from src.api.tenant_routes import router as tenant_router

    app.include_router(tenant_router)

    from src.api.files_view import router as files_view_router

    app.include_router(files_view_router)

    # v1.50 P1 修复: 统一文件管理 API
    from src.api.files_unified import router as files_unified_router

    app.include_router(files_unified_router)

    # v1.44: API 密钥管理
    from src.api.api_keys import router as api_keys_router

    app.include_router(api_keys_router)

    # v1.44: Webhook 管理
    from src.api.webhooks import router as webhooks_router

    app.include_router(webhooks_router)

    # 插件管理路由
    from src.api.plugin_manager_routes import router as plugin_manager_router

    app.include_router(plugin_manager_router)

    # 插件系统 Phase 1 路由
    from src.api.plugin_phase1_routes import router as plugin_phase1_router

    app.include_router(plugin_phase1_router)

    # 插件系统 Phase 2 路由
    from src.api.plugin_phase2_routes import router as plugin_phase2_router

    app.include_router(plugin_phase2_router)

    # 插件系统 Phase 3 路由
    from src.api.plugin_phase3_routes import router as plugin_phase3_router

    app.include_router(plugin_phase3_router)

    # 统一功能模块管理
    from src.api.modules import router as modules_router

    app.include_router(modules_router)

    # 监控中心
    from src.api.monitoring import router as monitoring_router

    app.include_router(monitoring_router)

    # 自运转中心
    from src.api.scheduler import router as scheduler_router

    app.include_router(scheduler_router)

    # 报告中心
    from src.api.reports import router as reports_router

    app.include_router(reports_router)

    # 配置中心
    from src.api.config_api import router as config_router

    app.include_router(config_router)

    # 四象状态
    from src.api.symbols import router as symbols_router

    app.include_router(symbols_router)

    # Zombie services
    from src.services.ai_tools.routes import router as ai_tools_router

    app.include_router(ai_tools_router)

    from src.services.data_analytics.routes import router as analytics_router

    app.include_router(analytics_router, prefix="/api/analytics")

    from src.services.doc_tools.routes import router as doc_tools_router

    app.include_router(doc_tools_router)

    from src.services.dxf_viewer.api import router as dxf_viewer_router

    app.include_router(dxf_viewer_router)

    # 服务市场
    from src.api.market import router as market_router

    app.include_router(market_router)

    # v1.50: AI 智能处理 API
    from src.api.ai_routes import router as ai_router

    app.include_router(ai_router)

    # v1.50: 开发者门户
    from src.api.developer_portal import router as developer_portal_router

    app.include_router(developer_portal_router)

    # 运维监控 API
    from src.api.ops_routes import router as ops_router

    app.include_router(ops_router)

    # Phase 3: 报告管理 API
    from src.api.report_routes import router as report_router

    app.include_router(report_router)


# ── MCP 路由 ──


def _register_mcp_routes(app: FastAPI) -> None:
    """注册 MCP 路由"""
    from src.core.mcp_routes import register_mcp_routes

    register_mcp_routes(app)


# ── 内联路由 ──


def _register_inline_routes(app: FastAPI) -> None:
    """注册内联路由（metrics、认证、评测、四象状态、feature flags、前端页面、代理路由）"""

    from src.api.auth import require_admin

    # ── 健康检查（直接注册到 app，优先级高于 SPA catch-all）──
    from src.api.health import health_check as _health_check
    from src.api.response import error, success

    @app.get("/health")
    @app.head("/health")
    async def health_endpoint():
        return await _health_check()

    # ── 服务器信息（IP 发现，用于其他电脑自动找到伏羲）──
    @app.get("/api/server-info")
    async def server_info_endpoint():
        import socket

        hostname = socket.gethostname()
        ips = []
        try:
            for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
                ip = info[4][0]
                if ip not in ips and not ip.startswith("127."):
                    ips.append(ip)
        except (socket.gaierror, OSError):
            pass
        real_ips = [ip for ip in ips if not ip.startswith(("169.254.", "192.168.56.", "192.168.80."))]
        primary_ip = real_ips[0] if real_ips else (ips[0] if ips else "unknown")
        return {
            "hostname": hostname,
            "primary_ip": primary_ip,
            "all_ips": ips,
            "port": 8080,
            "access_url": f"http://{primary_ip}:8080",
            "local_url": "http://localhost:8080",
        }

    # ── Prometheus Metrics ──
    from src.services.metrics import (
        generate_health_summary,
        generate_metrics_text,
        get_metrics_response,
        update_store_stats,
    )

    @app.get("/api/metrics", dependencies=[Depends(require_admin)])
    async def prometheus_metrics():
        try:
            from src.db.data_store import load_chunks
            from src.db.vector_store import count_chunks

            chunks = await asyncio.to_thread(load_chunks)
            update_store_stats(sqlite_count=len(chunks) if chunks else 0, vector_count=count_chunks())
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
        return success(
            data={
                "username": getattr(request.state, "user", "anonymous"),
                "role": getattr(request.state, "role", "user"),
            },
            message="认证信息",
        )

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

    # ── 四象状态 ──
    from src.taiyin.growth_api import get_symbols_status

    @app.get("/api/symbols/status")
    async def symbols_status():
        return success(data=get_symbols_status(), message="四象状态")

    # ── 成长概览已移至 src/api/growth.py ──

    # ── Feature Flags ──
    from src.services.feature_flags import DEFAULT_FLAGS, load_flags, set_flag

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
        # Vue SPA: 所有路由都返回 index.html，由前端路由处理
        f = STATIC_DIR / "index.html"
        if f.exists():
            content = await asyncio.to_thread(f.read_text, encoding="utf-8")
            return HTMLResponse(
                content,
                headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"},
            )
        return HTMLResponse("<h1>index.html not found</h1>")

    @app.get("/", response_class=HTMLResponse)
    async def index_page():
        # Vue SPA: 返回 index.html
        f = STATIC_DIR / "index.html"
        if f.exists():
            content = await asyncio.to_thread(f.read_text, encoding="utf-8")
            return HTMLResponse(
                content,
                headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"},
            )
        return HTMLResponse("<h1>index.html not found</h1>")

    # Vue SPA catch-all: 所有非 API、非静态文件的路径都返回 index.html
    @app.get("/{path:path}", response_class=HTMLResponse)
    async def spa_catch_all(path: str):
        # 跳过 API 路由和静态文件
        if path.startswith("api/") or path.startswith("static/") or path.startswith("assets/"):
            return HTMLResponse("<h1>Not Found</h1>", status_code=404)
        # 跳过已知的非 SPA 路由（从 _KNOWN_ROUTES 中移除 admin，因为下面有单独的 admin_page 路由）
        _KNOWN_ROUTES = {"health", "login", "metrics", "favicon.ico", "robots.txt"}
        if path in _KNOWN_ROUTES:
            return HTMLResponse("<h1>Not Found</h1>", status_code=404)
        # 跳过文件扩展名（静态资源）
        if "." in path.split("/")[-1]:
            return HTMLResponse("<h1>Not Found</h1>", status_code=404)
        f = STATIC_DIR / "index.html"
        if f.exists():
            content = await asyncio.to_thread(f.read_text, encoding="utf-8")
            return HTMLResponse(
                content,
                headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"},
            )
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
            return HTMLResponse(
                content,
                headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"},
            )
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
                headers={"Content-Type": request.headers.get("Content-Type", "multipart/form-data")},
            ) as resp:
                return await resp.json()
        except (OSError, RuntimeError, ValueError) as e:
            return error(f"代理加载器上传失败: {str(e)}", status_code=502, detail=str(e))


# ── 静态资源 ──


def _register_static_routes(app: FastAPI) -> None:
    """注册静态资源挂载（Cache-Control + 预压缩）"""
    from fastapi.staticfiles import StaticFiles
    from starlette.staticfiles import StaticFiles as _StaticFiles

    if STATIC_DIR.exists():

        class _CachedStaticFiles(_StaticFiles):
            _BLOCKED_EXTS = {".vue", ".ts", ".tsx", ".jsx", ".json", ".lock", ".md"}
            _BLOCKED_NAMES = {
                "package.json",
                "package-lock.json",
                "vite.config.js",
                "vite.config.ts",
                "yarn.lock",
                "pnpm-lock.yaml",
            }

            def lookup_path(self, path: str):
                ext = Path(path).suffix.lower()
                if ext in self._BLOCKED_EXTS:
                    return None
                name = Path(path).name
                if name in self._BLOCKED_NAMES:
                    return None
                return super().lookup_path(path)

            async def get_response(self, path: str, scope):
                """重写响应，添加 Cache-Control 和预压缩支持"""
                accept = dict(scope.get("headers", [])).get(b"accept-encoding", b"").decode()

                # 尝试返回预压缩文件
                import os

                full = os.path.join(self.directory, path)
                if "br" in accept and os.path.isfile(full + ".br") and os.path.getsize(full + ".br") > 1024:
                    from starlette.responses import Response

                    data = open(full + ".br", "rb").read()
                    resp = Response(data, media_type=self._get_mime(path))
                    resp.headers["Content-Encoding"] = "br"
                    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
                    resp.headers["Vary"] = "Accept-Encoding"
                    return resp
                if "gzip" in accept and os.path.isfile(full + ".gz") and os.path.getsize(full + ".gz") > 1024:
                    from starlette.responses import Response

                    data = open(full + ".gz", "rb").read()
                    resp = Response(data, media_type=self._get_mime(path))
                    resp.headers["Content-Encoding"] = "gzip"
                    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
                    resp.headers["Vary"] = "Accept-Encoding"
                    return resp

                resp = await super().get_response(path, scope)
                if resp.status_code == 200:
                    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
                    resp.headers["Vary"] = "Accept-Encoding"
                return resp

            def _get_mime(self, path: str) -> str:
                ext = Path(path).suffix.lower()
                return {
                    ".js": "application/javascript",
                    ".css": "text/css",
                    ".svg": "image/svg+xml",
                    ".png": "image/png",
                }.get(ext, "application/octet-stream")

        app.mount("/assets", _CachedStaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")
        app.mount("/static", _CachedStaticFiles(directory=str(STATIC_DIR)), name="static")
        logger.info(f"静态资源挂载: {STATIC_DIR}")
    else:
        logger.warning(f"静态资源目录不存在: {STATIC_DIR}")
