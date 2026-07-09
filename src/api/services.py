"""
services.py — 伏羲 v2.1 /api/services 聚合端点

GET /api/services — 返回所有已注册服务的清单（JSON 数组），含健康检查。
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

from src.api.response import success, error
from src.api.auth import require_admin  # v1.50 R2: 内部端点需要认证

logger = logging.getLogger("api.services")

router = APIRouter(prefix="/api/services", tags=["services"])

# ── 服务 Manifest 信息 ──
# 这些信息从服务注册表中获取，此处是基础 manifest。
# 实际生产环境可动态从 data/services/ 目录读取 manifest.json。
_SERVICES_MANIFEST: List[dict] = [
    {
        "id": "search",
        "name": "知识检索 乾 ☰",
        "icon": "search",
        "category": "knowledge",
        "guaAffinity": "乾",
        "route": "/api/search",
        "apiBase": "/api/search",
        "endpoints": ["GET /api/search", "GET /api/search-history", "GET /api/images/search"],
        "status": "up",
        "description": "全文检索、图片搜索、搜索历史",
    },
    {
        "id": "chat",
        "name": "AI 对话 离 ☲",
        "icon": "chat",
        "category": "interaction",
        "guaAffinity": "离",
        "route": "/api/chat",
        "apiBase": "/api/chat",
        "endpoints": ["POST /api/chat", "POST /api/chat/agent"],
        "status": "up",
        "description": "AI 对话、Agent 工作台",
    },
    {
        "id": "documents",
        "name": "文档管理 坤 ☷",
        "icon": "document",
        "category": "knowledge",
        "guaAffinity": "坤",
        "route": "/api/documents",
        "apiBase": "/api/documents",
        "endpoints": [
            "POST /api/documents/upload", "GET /api/documents/list",
            "POST /api/documents/ingest", "POST /api/documents/reindex"
        ],
        "status": "up",
        "description": "文档上传、入库、重索引",
    },
    {
        "id": "wiki",
        "name": "知识 Wiki 震 ☳",
        "icon": "wiki",
        "category": "knowledge",
        "guaAffinity": "震",
        "route": "/api/wiki",
        "apiBase": "/api/wiki",
        "endpoints": ["GET /api/wiki", "POST /api/wiki", "GET /api/wiki/search"],
        "status": "up",
        "description": "Wiki 知识管理、搜索",
    },
    {
        "id": "graph",
        "name": "知识图谱 巽 ☴",
        "icon": "graph",
        "category": "knowledge",
        "guaAffinity": "巽",
        "route": "/api/graph",
        "apiBase": "/api/graph",
        "endpoints": ["GET /api/graph", "GET /api/graph/build", "GET /api/graph/nodes", "GET /api/graph/path"],
        "status": "up",
        "description": "知识图谱构建、节点查询、路径发现",
    },
    {
        "id": "admin",
        "name": "管理中心 坎 ☵",
        "icon": "admin",
        "category": "management",
        "guaAffinity": "坎",
        "route": "/api/admin",
        "apiBase": "/api/admin",
        "endpoints": ["GET /api/admin/stats", "POST /api/admin/audit-logs"],
        "status": "up",
        "description": "系统管理、审计日志、仪表板",
    },
    {
        "id": "ai-tools",
        "name": "AI 工具箱 兑 ☱",
        "icon": "tools",
        "category": "tools",
        "guaAffinity": "兑",
        "route": "/api/ai",
        "apiBase": "/api/ai",
        "endpoints": [
            "POST /api/ai/summarize", "POST /api/ai/translate",
            "POST /api/ai/keywords", "POST /api/ai/entities",
            "POST /api/ai/classify", "GET /api/ai/health"
        ],
        "status": "up",
        "description": "摘要、翻译、关键词、实体提取、分类",
    },
    {
        "id": "analytics",
        "name": "数据分析 艮 ☶",
        "icon": "chart",
        "category": "data",
        "guaAffinity": "艮",
        "route": "/api/analytics",
        "apiBase": "/api/analytics",
        "endpoints": [
            "GET /api/analytics/stats", "POST /api/analytics/trends",
            "GET /api/analytics/report", "POST /api/analytics/export",
            "GET /api/analytics/health"
        ],
        "status": "up",
        "description": "数据统计、趋势分析、报表导出",
    },
    {
        "id": "doc-tools",
        "name": "文档工具 艮 ☶",
        "icon": "file-tools",
        "category": "tools",
        "guaAffinity": "艮",
        "route": "/api/tools",
        "apiBase": "/api/tools",
        "endpoints": [
            "POST /api/tools/convert", "POST /api/tools/merge",
            "POST /api/tools/split", "POST /api/tools/compress",
            "GET /api/tools/health"
        ],
        "status": "up",
        "description": "文档转换、合并、拆分、压缩",
    },
    {
        "id": "dxf-viewer",
        "name": "DXF 看图 坤 ☷",
        "icon": "viewer",
        "category": "tools",
        "guaAffinity": "坤",
        "route": "/api/dxf",
        "apiBase": "/api/dxf",
        "endpoints": [
            "POST /api/dxf/upload", "GET /api/dxf/files",
            "GET /api/dxf/view/{hash}", "GET /api/dxf/download/{hash}",
            "GET /api/dxf/health"
        ],
        "status": "up",
        "description": "DXF/CAD 文件上传、查看、下载",
    },
    {
        "id": "evaluation",
        "name": "评测系统 离 ☲",
        "icon": "evaluation",
        "category": "management",
        "guaAffinity": "离",
        "route": "/api/eval",
        "apiBase": "/api/eval",
        "endpoints": [
            "POST /api/eval/run", "GET /api/eval/report",
            "GET /api/eval/history", "GET /api/evaluation/*"
        ],
        "status": "up",
        "description": "自动化评测、报告生成、历史查询",
    },
    {
        "id": "metrics",
        "name": "系统监控 离 ☲",
        "icon": "monitor",
        "category": "management",
        "guaAffinity": "离",
        "route": "/api/metrics",
        "apiBase": "/api/metrics",
        "endpoints": ["GET /api/metrics", "GET /metrics"],
        "status": "up",
        "description": "Prometheus 指标、系统健康状态",
    },
    {
        "id": "feature-flags",
        "name": "功能开关 坎 ☵",
        "icon": "toggle",
        "category": "management",
        "guaAffinity": "坎",
        "route": "/api/feature-flags",
        "apiBase": "/api/feature-flags",
        "endpoints": ["GET /api/feature-flags", "PUT /api/feature-flags/{name}"],
        "status": "up",
        "description": "功能开关管理，支持秒级回滚",
    },
    {
        "id": "symbols",
        "name": "四象状态 离 ☲",
        "icon": "symbols",
        "category": "platform",
        "guaAffinity": "离",
        "route": "/api/symbols",
        "apiBase": "/api/symbols",
        "endpoints": ["GET /api/symbols/status"],
        "status": "up",
        "description": "四象系统状态监控",
    },
    {
        "id": "growth",
        "name": "成长系统 乾 ☰",
        "icon": "growth",
        "category": "platform",
        "guaAffinity": "乾",
        "route": "/api/growth",
        "apiBase": "/api/growth",
        "endpoints": ["GET /api/growth/overview"],
        "status": "up",
        "description": "系统成长数据概览",
    },
    {
        "id": "mcp",
        "name": "MCP 协议 坤 ☷",
        "icon": "protocol",
        "category": "integration",
        "guaAffinity": "坤",
        "route": "/api/mcp",
        "apiBase": "/api/mcp",
        "endpoints": [
            "POST /api/mcp", "GET /api/mcp/tools",
            "POST /api/mcp/sag_search", "POST /api/mcp/sag_ingest",
            "POST /api/mcp/sag_explain", "GET /api/mcp/sag_status"
        ],
        "status": "up",
        "description": "MCP JSON-RPC 协议入口",
    },
]


@router.get("", dependencies=[Depends(require_admin)])
@router.get("/", dependencies=[Depends(require_admin)])
# FAKE-ASYNC: 同步函数标记 async 仅为接口统一
async def list_services(request: Request):
    """获取所有已注册服务的清单 — v1.50 R2: 需要管理员权限"""
    try:
        # 从 auto_discovery 模块获取动态发现的路由信息
        try:
            from src.api._auto_discovery import get_discovered_router_info
            discovered = get_discovered_router_info()
        except ImportError:
            discovered = []

        # 更新健康状态（简单 ping 自身）
        services = []
        for svc in _SERVICES_MANIFEST:
            svc_copy = dict(svc)
            # 尝试做健康检查 — 检查服务路由是否在发现列表中
            svc_copy["status"] = _check_service_health(svc, discovered)
            services.append(svc_copy)

        return success({
            "services": services,
            "total": len(services),
            "auto_discovered_routes": len(discovered),
        })
    except Exception as e:
        logger.error(f"[Services] 获取服务清单失败: {e}", exc_info=True)
        return error("获取服务清单失败", status_code=500, detail=str(e))


@router.get("/{service_id}", dependencies=[Depends(require_admin)])
async def get_service(service_id: str, request: Request):
    """获取单个服务的详细信息 — v1.50 R2: 需要管理员权限"""
    for svc in _SERVICES_MANIFEST:
        if svc["id"] == service_id:
            return success(svc)
    return error(f"服务未找到: {service_id}", status_code=404)


def _check_service_health(svc: dict, discovered: List[dict]) -> str:
    """检查服务健康状态

    通过自动发现列表验证服务路由是否已注册。
    若有对应路由注册则标记为 up，否则标记为 unknown。
    """
    route = svc.get("route", "")
    # 对于已发现的路由，检查是否有匹配的前缀
    for d in discovered:
        d_prefix = d.get("prefix", "")
        if route.startswith(d_prefix) or d_prefix.startswith(route):
            return "up"
    # 如果没有自动发现数据，标记为 unknown 而非盲目假设 up
    if not discovered:
        return "unknown"
    # 路由未在发现列表中注册
    return "degraded"
