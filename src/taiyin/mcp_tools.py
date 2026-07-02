"""
mcp_tools.py — MCP 暴露工具
供外部 Agent 调用的 4 个工具
"""
import logging
from typing import Dict, List

logger = logging.getLogger("taiyin.mcp_tools")


async def sag_search(query: str, top_k: int = 10) -> Dict:
    """MCP 工具：搜索知识库"""
    from src.taiyang.retrieval import hybrid_search
    try:
        results = await hybrid_search(query, top_k=top_k)
        return {
            "results": results,
            "count": len(results),
            "query": query,
        }
    except Exception as e:
        logger.error(f"[MCP] sag_search 失败: {e}")
        return {"error": str(e), "results": []}


async def sag_ingest(file_path: str, category: str = "") -> Dict:
    """MCP 工具：入库文档"""
    from src.shaoyang.pipeline import ShaoyangPipeline
    try:
        pipeline = ShaoyangPipeline(None)
        result = await pipeline.digest(file_path, category=category)
        return {
            "chunks": result.get("chunks", 0),
            "events": result.get("events", 0),
            "entities": result.get("entities", 0),
            "file_path": file_path,
        }
    except Exception as e:
        logger.error(f"[MCP] sag_ingest 失败: {e}")
        return {"error": str(e)}


async def sag_explain(query: str) -> Dict:
    """MCP 工具：解释查询结果"""
    from src.shaoyin.brain import ShaoyinBrain
    try:
        brain = ShaoyinBrain(None)
        result = await brain.think(query)
        return {
            "answer": result.get("answer", ""),
            "confidence": result.get("confidence", 0),
            "sources": result.get("sources", []),
        }
    except Exception as e:
        logger.error(f"[MCP] sag_explain 失败: {e}")
        return {"error": str(e)}


async def sag_status() -> Dict:
    """MCP 工具：获取系统状态"""
    from src.infra.meridian_monitor import get_monitor
    try:
        monitor = get_monitor()
        return monitor.get_health_report()
    except Exception as e:
        logger.error(f"[MCP] sag_status 失败: {e}")
        return {"error": str(e)}


# MCP 工具定义
MCP_TOOLS = [
    {
        "name": "sag_search",
        "description": "搜索伏羲知识库",
        "parameters": {
            "query": {"type": "string", "description": "搜索查询"},
            "top_k": {"type": "integer", "description": "返回结果数量", "default": 10},
        },
    },
    {
        "name": "sag_ingest",
        "description": "入库文档到伏羲知识库",
        "parameters": {
            "file_path": {"type": "string", "description": "文件路径"},
            "category": {"type": "string", "description": "分类", "default": ""},
        },
    },
    {
        "name": "sag_explain",
        "description": "解释查询结果",
        "parameters": {
            "query": {"type": "string", "description": "查询"},
        },
    },
    {
        "name": "sag_status",
        "description": "获取系统状态",
        "parameters": {},
    },
]
