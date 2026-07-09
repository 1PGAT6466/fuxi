"""
伏羲 v1.50 — MCP 路由（从 server.py 拆分）
=======================================
MCP 协议入口、工具列表、工具调用端点。
"""
import logging
import traceback
import inspect

from fastapi import FastAPI, Request, Depends

from src.api.auth import require_admin
from src.api.response import success, error

logger = logging.getLogger("server")

# MCP 工具处理器注册表（启动时初始化）
_MCP_TOOLS_MODULE = None
MCP_TOOL_HANDLERS: dict = {}

_MCP_TOOL_PERMISSIONS = {
    "sag_search": "user", "sag_ingest": "admin", "sag_explain": "user",
    "sag_status": "user", "kb_search": "user", "kb_list_documents": "user",
    "kb_get_document": "user", "graph_query": "user", "graph_stats": "user",
    "wiki_search": "user", "wiki_get": "user", "dream_cycle_run": "admin",
    "dream_cycle_report": "user", "gap_analyze": "user", "entity_expand": "user",
    "cross_entity_synthesize": "user", "file_upload": "admin", "file_list": "user",
    "chat_query": "user", "eval_run": "admin", "notifications_list": "user",
    "feature_flags_list": "user", "health_check": "public", "audit_logs": "admin",
}


def _init_mcp_handlers():
    """初始化 MCP 工具处理器注册表"""
    global _MCP_TOOLS_MODULE, MCP_TOOL_HANDLERS
    try:
        _MCP_TOOLS_MODULE = __import__("src.taiyin.mcp_tools", fromlist=["*"])
    except ImportError as e:
        logger.warning(f"MCP 工具模块加载失败: {e}")
        _MCP_TOOLS_MODULE = None
        return

    _tool_map = {
        "sag_search": "sag_search", "sag_ingest": "sag_ingest",
        "sag_explain": "sag_explain", "sag_status": "sag_status",
        "kb_search": "kb_search", "kb_list_documents": "kb_list_documents",
        "kb_get_document": "kb_get_document", "graph_query": "graph_query",
        "graph_stats": "graph_stats", "wiki_search": "wiki_search",
        "wiki_get": "wiki_get", "dream_cycle_run": "dream_cycle_run",
        "dream_cycle_report": "dream_cycle_report", "gap_analyze": "gap_analyze",
        "entity_expand": "entity_expand",
        "cross_entity_synthesize": "cross_entity_synthesize",
        "file_upload": "file_upload", "file_list": "file_list",
        "chat_query": "chat_query", "eval_run": "eval_run",
        "notifications_list": "notifications_list",
        "feature_flags_list": "feature_flags_list",
        "health_check": "health_check", "audit_logs": "audit_logs",
    }

    for tool_name, attr_name in _tool_map.items():
        handler = getattr(_MCP_TOOLS_MODULE, attr_name, None)
        if handler is not None:
            MCP_TOOL_HANDLERS[tool_name] = handler
        else:
            logger.warning(f"MCP 工具 '{tool_name}' 在 mcp_tools 模块中未找到")

    logger.info(f"MCP 工具注册完成: {len(MCP_TOOL_HANDLERS)}/{len(_tool_map)} 个可用")


def _check_mcp_permission(tool_name: str, request: Request) -> bool:
    """检查 MCP 工具权限"""
    required = _MCP_TOOL_PERMISSIONS.get(tool_name, "user")
    if required == "public":
        return True

    current_user = getattr(request.state, "user", None)
    current_role = getattr(request.state, "role", "user")
    if not current_user or current_user == "anonymous":
        return False
    if required == "admin":
        return current_role == "admin"
    return True


def register_mcp_routes(app: FastAPI) -> None:
    """注册所有 MCP 路由到 FastAPI app"""
    _init_mcp_handlers()

    # 让全局别名可用
    import src.server as _server
    _server.MCP_TOOL_HANDLERS = MCP_TOOL_HANDLERS

    @app.post("/api/mcp")
    async def mcp_handler(request: Request):
        """MCP协议入口 — 标准JSON-RPC 2.0"""
        from src.taiyin.mcp_protocol import get_mcp_server
        body = await request.json()
        server = get_mcp_server()
        return await server.handle_request(body)

    @app.get("/api/mcp/tools", dependencies=[Depends(require_admin)])
    async def mcp_list_tools():
        """列出所有MCP工具 — 需要管理员权限"""
        from src.taiyin.mcp_protocol import get_mcp_server
        server = get_mcp_server()
        return success(
            data={"tools": [{"name": t.name, "description": t.description} for t in server.tools.values()]},
            message="MCP工具列表",
        )

    @app.post("/api/mcp/call")
    async def mcp_call(request: Request):
        """MCP 通用工具调用端点 — v1.50 Phase F"""
        body = await request.json()
        tool_name = body.get("tool", "")
        args = body.get("args", {})

        if not tool_name:
            return error("缺少 tool 参数", status_code=400,
                         detail=f"可用工具: {list(MCP_TOOL_HANDLERS.keys())}")

        if not _check_mcp_permission(tool_name, request):
            return error(f"无权调用工具: {tool_name}", status_code=403,
                         detail="权限不足")

        handler = MCP_TOOL_HANDLERS.get(tool_name)
        if handler is None:
            available = list(MCP_TOOL_HANDLERS.keys())
            if _MCP_TOOLS_MODULE is None:
                return error(f"未知工具: {tool_name}（MCP 工具模块未加载）",
                             status_code=404, detail=str(available))
            return error(f"未知工具: {tool_name}", status_code=404,
                         detail=str(available))

        try:
            result = handler(args)
            if inspect.isawaitable(result):
                result = await result
            return success(
                data={"tool": tool_name, "result": result},
                message=f"MCP工具 {tool_name} 执行成功",
            )
        except (RuntimeError, ValueError, TypeError, OSError) as e:
            logger.error(f"[MCP/call] {tool_name} 执行失败: {e}\n{traceback.format_exc()}")
            return error(f"MCP工具 {tool_name} 执行失败", status_code=500, detail=str(e))
