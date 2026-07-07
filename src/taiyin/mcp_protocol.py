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
    """注册默认工具"""
    from src.taiyin.mcp_tools import sag_search, sag_ingest, sag_explain, sag_status

    server.register_tool(
        name="sag_search",
        description="搜索伏羲知识库",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索查询"},
                "top_k": {"type": "integer", "description": "返回结果数量", "default": 10},
            },
            "required": ["query"],
        },
        handler=sag_search,
    )

    server.register_tool(
        name="sag_ingest",
        description="入库文档到伏羲知识库",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "文件路径"},
                "category": {"type": "string", "description": "分类", "default": ""},
            },
            "required": ["file_path"],
        },
        handler=sag_ingest,
    )

    server.register_tool(
        name="sag_explain",
        description="解释查询结果",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "查询"},
            },
            "required": ["query"],
        },
        handler=sag_explain,
    )

    server.register_tool(
        name="sag_status",
        description="获取系统状态",
        input_schema={"type": "object", "properties": {}},
        handler=sag_status,
    )


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
