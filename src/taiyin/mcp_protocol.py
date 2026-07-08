"""
mcp_protocol.py — MCP协议深度集成
支持MCP标准协议格式 + 工具发现 + 资源暴露
"""
import json
import logging
import time
from typing import Dict, List, Any, Callable
from dataclasses import dataclass, field

logger = logging.getLogger("taiyin.mcp_protocol")


@dataclass
class MCPTool:
    """MCP工具定义"""
    name: str
    description: str
    input_schema: Dict
    handler: Callable = None


@dataclass
class MCPResource:
    """MCP资源定义"""
    uri: str
    name: str
    description: str
    mime_type: str = "application/json"


class MCPServer:
    """MCP服务器 — 标准协议实现"""

    def __init__(self, server_name: str = "fuxi-knowledge", version: str = "1.0.0"):
        self.server_name = server_name
        self.version = version
        self.tools: Dict[str, MCPTool] = {}
        self.resources: Dict[str, MCPResource] = {}
        self._initialized = False

    def register_tool(self, name: str, description: str, input_schema: Dict, handler: Callable):
        """注册MCP工具"""
        self.tools[name] = MCPTool(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=handler,
        )
        logger.info(f"[MCP] 注册工具: {name}")

    def register_resource(self, uri: str, name: str, description: str, mime_type: str = "application/json"):
        """注册MCP资源"""
        self.resources[uri] = MCPResource(
            uri=uri,
            name=name,
            description=description,
            mime_type=mime_type,
        )
        logger.info(f"[MCP] 注册资源: {uri}")

    async def handle_request(self, request: Dict) -> Dict:
        """处理MCP请求"""
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")

        try:
            if method == "initialize":
                return self._handle_initialize(request_id, params)
            elif method == "tools/list":
                return self._handle_tools_list(request_id)
            elif method == "tools/call":
                return await self._handle_tools_call(request_id, params)
            elif method == "resources/list":
                return self._handle_resources_list(request_id)
            elif method == "resources/read":
                return await self._handle_resources_read(request_id, params)
            else:
                return self._error_response(request_id, -32601, f"Unknown method: {method}")
        except Exception as e:
            logger.error(f"[MCP] 请求处理失败: {e}")
            return self._error_response(request_id, -32603, str(e))

    def _handle_initialize(self, request_id: Any, params: Dict) -> Dict:
        """处理初始化请求"""
        self._initialized = True
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                },
                "serverInfo": {
                    "name": self.server_name,
                    "version": self.version,
                },
            },
        }

    def _handle_tools_list(self, request_id: Any) -> Dict:
        """处理工具列表请求"""
        tools = []
        for name, tool in self.tools.items():
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
            })

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": tools},
        }

    async def _handle_tools_call(self, request_id: Any, params: Dict) -> Dict:
        """处理工具调用请求"""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        tool = self.tools.get(tool_name)
        if not tool:
            return self._error_response(request_id, -32602, f"Unknown tool: {tool_name}")

        if not tool.handler:
            return self._error_response(request_id, -32603, f"Tool {tool_name} has no handler")

        try:
            result = await tool.handler(**arguments)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False, indent=2),
                        }
                    ],
                },
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error: {str(e)}",
                        }
                    ],
                    "isError": True,
                },
            }

    def _handle_resources_list(self, request_id: Any) -> Dict:
        """处理资源列表请求"""
        resources = []
        for uri, resource in self.resources.items():
            resources.append({
                "uri": resource.uri,
                "name": resource.name,
                "description": resource.description,
                "mimeType": resource.mime_type,
            })

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"resources": resources},
        }

    async def _handle_resources_read(self, request_id: Any, params: Dict) -> Dict:
        """处理资源读取请求"""
        uri = params.get("uri", "")

        resource = self.resources.get(uri)
        if not resource:
            return self._error_response(request_id, -32602, f"Unknown resource: {uri}")

        # 根据URI返回资源内容
        content = await self._read_resource(uri)

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": resource.mime_type,
                        "text": json.dumps(content, ensure_ascii=False, indent=2),
                    }
                ],
            },
        }

# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
    async def _read_resource(self, uri: str) -> Dict:
        """读取资源内容"""
        if uri == "fuxi://symbols/status":
            from src.taiyin.growth_api import get_symbols_status
            return get_symbols_status()
        elif uri == "fuxi://growth/overview":
            from src.taiyin.growth_api import get_growth_overview
            return get_growth_overview()
        elif uri == "fuxi://flags":
            from src.taiyin.flags import load_flags
            return {"flags": load_flags()}
        else:
            return {"error": f"Unknown resource: {uri}"}

    def _error_response(self, request_id: Any, code: int, message: str) -> Dict:
        """生成错误响应"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        }


# 全局MCP服务器实例
_mcp_server: MCPServer = None


def get_mcp_server() -> MCPServer:
    """获取全局MCP服务器实例"""
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = MCPServer()
        _register_default_tools(_mcp_server)
        _register_default_resources(_mcp_server)
    return _mcp_server


def _register_default_tools(server: MCPServer):
    """注册默认工具 — v1.50 Phase F: 24 工具 (原 4 + 新增 20)"""
    from src.taiyin.mcp_tools import (
        sag_search, sag_ingest, sag_explain, sag_status,
        kb_search, kb_list_documents, kb_get_document,
        graph_query, graph_stats,
        wiki_search, wiki_get,
        dream_cycle_run, dream_cycle_report,
        gap_analyze, entity_expand, cross_entity_synthesize,
        file_upload, file_list,
        chat_query, eval_run,
        notifications_list, feature_flags_list,
        health_check, audit_logs,
    )

    # ── 原有 4 个 ──
    _reg(server, "sag_search", "搜索伏羲知识库",
         {"query": "s|搜索查询", "top_k": "i|返回结果数量|10"},
         ["query"], sag_search)

    _reg(server, "sag_ingest", "入库文档到伏羲知识库",
         {"file_path": "s|文件路径", "category": "s|分类|"},
         ["file_path"], sag_ingest)

    _reg(server, "sag_explain", "解释查询结果",
         {"query": "s|查询"},
         ["query"], sag_explain)

    _reg(server, "sag_status", "获取系统状态", {}, [], sag_status)

    # ── 新增 20 个 ──
    _reg(server, "kb_search", "知识库语义搜索 — 向量相似度+全文搜索",
         {"query": "s|搜索查询", "top_k": "i|返回结果数量|5",
          "mode": "s|搜索模式(semantic/keyword/hybrid)|semantic"},
         ["query"], kb_search)

    _reg(server, "kb_list_documents", "列出知识库文档",
         {}, [], kb_list_documents)

    _reg(server, "kb_get_document", "获取单个文档内容",
         {"doc_id": "s|文档ID(file_hash)"},
         ["doc_id"], kb_get_document)

    _reg(server, "graph_query", "知识图谱查询",
         {"entity": "s|实体名称|", "source": "s|源实体过滤|",
          "target": "s|目标实体过滤|", "edge_type": "s|边类型|",
          "min_confidence": "n|最小置信度|0.0", "limit": "i|返回上限|100"},
         [], graph_query)

    _reg(server, "graph_stats", "图谱统计", {}, [], graph_stats)

    _reg(server, "wiki_search", "Wiki页面搜索",
         {"q": "s|搜索关键词|", "category": "s|分类过滤|",
          "limit": "i|返回上限|20"},
         [], wiki_search)

    _reg(server, "wiki_get", "获取Wiki页面",
         {"page_id": "s|Wiki页面ID"},
         ["page_id"], wiki_get)

    _reg(server, "dream_cycle_run", "触发夜间消化循环",
         {}, [], dream_cycle_run)

    _reg(server, "dream_cycle_report", "获取最新日报",
         {}, [], dream_cycle_report)

    _reg(server, "gap_analyze", "运行Gap Analysis — 分析知识库覆盖缺口",
         {"query": "s|分析主题|", "topic": "s|分析主题(备用)|"},
         [], gap_analyze)

    _reg(server, "entity_expand", "实体向量扩展",
         {"entity_name": "s|实体名称", "top_k": "i|返回扩展数|10"},
         ["entity_name"], entity_expand)

    _reg(server, "cross_entity_synthesize", "跨实体合成 — 查找实体间关联路径",
         {"entity_a": "s|实体A名称", "entity_b": "s|实体B名称"},
         ["entity_a", "entity_b"], cross_entity_synthesize)

    _reg(server, "file_upload", "文件上传 — 从本地路径入库",
         {"file_path": "s|本地文件路径", "category": "s|分类标签|"},
         ["file_path"], file_upload)

    _reg(server, "file_list", "文件列表",
         {"page": "i|页码|1", "page_size": "i|每页数量|50"},
         [], file_list)

    _reg(server, "chat_query", "对话查询（简单版）",
         {"query": "s|用户问题", "history": "a|对话历史|[]"},
         ["query"], chat_query)

    _reg(server, "eval_run", "运行评测",
         {"dataset": "s|评测数据集|", "test_name": "s|测试名称|"},
         [], eval_run)

    _reg(server, "notifications_list", "获取通知列表",
         {"page": "i|页码|1", "page_size": "i|每页数量|20",
          "unread_only": "b|只返回未读|false"},
         [], notifications_list)

    _reg(server, "feature_flags_list", "列出功能开关",
         {}, [], feature_flags_list)

    _reg(server, "health_check", "系统健康检查",
         {}, [], health_check)

    _reg(server, "audit_logs", "审计日志查询",
         {"user": "s|按用户过滤|", "action": "s|按操作类型过滤|",
          "days": "i|最近几天|1", "limit": "i|返回上限|100"},
         [], audit_logs)


def _reg(server, name: str, desc: str, params: dict, required: list, handler):
    """辅助：解析精简参数定义 → MCP input_schema {type:object, properties, required}

    params 格式: {"key": "type|desc|default"}
    type: s=string, i=integer, n=number, b=boolean, a=array
    """
    props = {}
    type_map = {"s": "string", "i": "integer", "n": "number", "b": "boolean", "a": "array"}
    for key, spec in params.items():
        parts = spec.split("|")
        t = parts[0] if parts else "s"
        desc_text = parts[1] if len(parts) > 1 else key
        default = parts[2] if len(parts) > 2 else None
        json_type = type_map.get(t, "string")
        prop = {"type": json_type, "description": desc_text}
        if default is not None:
            if t == "i":
                prop["default"] = int(default)
            elif t == "n":
                prop["default"] = float(default)
            elif t == "b":
                prop["default"] = default.lower() in ("true", "1")
            else:
                prop["default"] = default
        props[key] = prop

    schema = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    server.register_tool(name, desc, schema, handler)


def _register_default_resources(server: MCPServer):
    """注册默认资源"""
    server.register_resource(
        uri="fuxi://symbols/status",
        name="四象状态",
        description="四象模块的健康状态和指标",
    )

    server.register_resource(
        uri="fuxi://growth/overview",
        name="成长概览",
        description="成长引擎的指标和趋势",
    )

    server.register_resource(
        uri="fuxi://flags",
        name="Feature Flags",
        description="Feature Flag 状态",
    )
