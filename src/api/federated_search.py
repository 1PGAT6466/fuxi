"""
联邦搜索 API — 伏羲 v1.50
============================
提供跨多个搜索源的统一搜索功能。

端点：
  POST /api/search/federated — 联邦搜索
  GET  /api/search/sources   — 获取搜索源
"""

import asyncio
import logging
import time
from typing import List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel
from src.api.response import error, success

logger = logging.getLogger(__name__)

router = APIRouter(tags=["联邦搜索"])


# ============ 搜索源注册 ============

# 内置搜索源配置
_BUILTIN_SOURCES = [
    {
        "id": "local_kb",
        "name": "本地知识库",
        "description": "伏羲系统内置的向量知识库",
        "type": "vector",
        "enabled": True,
        "priority": 1,
    },
    {
        "id": "web_search",
        "name": "网络搜索",
        "description": "通过外部搜索引擎获取实时信息",
        "type": "external",
        "enabled": False,  # 需要配置 API Key
        "priority": 2,
    },
    {
        "id": "wiki",
        "name": "知识图谱",
        "description": "伏羲世界树知识图谱",
        "type": "graph",
        "enabled": True,
        "priority": 3,
    },
    {
        "id": "documents",
        "name": "文档检索",
        "description": "原始文档全文检索",
        "type": "fulltext",
        "enabled": True,
        "priority": 4,
    },
]


def _get_enabled_sources() -> list:
    """获取启用的搜索源"""
    # 后续可从数据库或配置文件读取动态搜索源
    return [s for s in _BUILTIN_SOURCES if s.get("enabled", False)]


# ============ Pydantic 模型 ============


class FederatedSearchBody(BaseModel):
    q: str
    sources: Optional[List[str]] = None  # 指定搜索源，None 表示所有启用的源
    top_k: int = 10
    timeout_sec: float = 10.0

    class Config:
        # 允许额外字段，避免 422 错误
        extra = "ignore"
        # 提供 JSON Schema 示例
        json_schema_extra = {
            "example": {"q": "搜索关键词", "sources": ["local_kb", "wiki"], "top_k": 10, "timeout_sec": 10.0}
        }


# ============ 搜索源实现 ============


async def _search_local_kb(query: str, top_k: int) -> dict:
    """搜索本地知识库"""
    try:
        from src.db.vector_store import search as vector_search

        results = await asyncio.to_thread(vector_search, query, top_k)
        return {
            "source": "local_kb",
            "results": results or [],
            "count": len(results) if results else 0,
        }
    except ImportError:
        return {"source": "local_kb", "results": [], "count": 0, "error": "向量库未初始化"}
    except Exception as e:
        logger.warning("local_kb 搜索失败: %s", e)
        return {"source": "local_kb", "results": [], "count": 0, "error": str(e)}


async def _search_wiki(query: str, top_k: int) -> dict:
    """搜索知识图谱"""
    try:
        from src.taiyin.mcp_tools import search_wiki

        results = await search_wiki(query, limit=top_k)
        return {
            "source": "wiki",
            "results": results if isinstance(results, list) else [],
            "count": len(results) if isinstance(results, list) else 0,
        }
    except ImportError:
        return {"source": "wiki", "results": [], "count": 0, "error": "知识图谱模块未加载"}
    except Exception as e:
        logger.warning("wiki 搜索失败: %s", e)
        return {"source": "wiki", "results": [], "count": 0, "error": str(e)}


async def _search_documents(query: str, top_k: int) -> dict:
    """搜索文档"""
    try:
        from src.db.data_store import search_chunks

        results = await asyncio.to_thread(search_chunks, query, top_k)
        return {
            "source": "documents",
            "results": results or [],
            "count": len(results) if results else 0,
        }
    except ImportError:
        return {"source": "documents", "results": [], "count": 0, "error": "文档存储未初始化"}
    except Exception as e:
        logger.warning("documents 搜索失败: %s", e)
        return {"source": "documents", "results": [], "count": 0, "error": str(e)}


async def _search_web(query: str, top_k: int) -> dict:
    """网络搜索（占位实现）"""
    # 后续集成外部搜索 API
    return {
        "source": "web_search",
        "results": [],
        "count": 0,
        "error": "网络搜索未配置",
    }


# 搜索源 → 实现函数映射
_SEARCH_IMPL = {
    "local_kb": _search_local_kb,
    "wiki": _search_wiki,
    "documents": _search_documents,
    "web_search": _search_web,
}


# ============ 端点 ============


@router.post("/api/search/federated")
async def federated_search(body: FederatedSearchBody, request: Request):
    """联邦搜索 — 同时查询多个搜索源并合并结果"""
    try:
        query = body.q.strip()
        if not query:
            return error("搜索关键词不能为空", status_code=400)

        # 确定要搜索的源
        if body.sources:
            # 用户指定的源
            search_sources = [s for s in _BUILTIN_SOURCES if s["id"] in body.sources and s["enabled"]]
        else:
            # 所有启用的源
            search_sources = _get_enabled_sources()

        if not search_sources:
            return error("没有可用的搜索源", status_code=400)

        # 并发搜索
        tasks = []
        source_ids = []
        for src in search_sources:
            impl = _SEARCH_IMPL.get(src["id"])
            if impl:
                tasks.append(impl(query, body.top_k))
                source_ids.append(src["id"])

        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed_ms = (time.time() - start_time) * 1000

        # 汇总结果
        all_results = []
        source_results = {}
        errors = []

        for i, result in enumerate(results):
            src_id = source_ids[i]
            if isinstance(result, Exception):
                errors.append({"source": src_id, "error": str(result)})
                source_results[src_id] = {"results": [], "count": 0, "error": str(result)}
            else:
                source_results[src_id] = result
                all_results.extend(result.get("results", []))

        # 按相关性排序（如果结果有 score 字段）
        all_results.sort(key=lambda r: r.get("score", 0), reverse=True)
        all_results = all_results[: body.top_k]

        return success(
            data={
                "query": query,
                "results": all_results,
                "total_count": len(all_results),
                "source_results": source_results,
                "errors": errors if errors else None,
                "elapsed_ms": round(elapsed_ms, 2),
                "sources_queried": source_ids,
            },
            message="联邦搜索完成",
        )
    except Exception as e:
        logger.exception("federated_search 失败: %s", e)
        return error("联邦搜索失败", status_code=500, detail=str(e))


@router.get("/api/search/sources")
async def list_sources(request: Request):
    """获取所有搜索源及其状态"""
    try:
        sources = []
        for src in _BUILTIN_SOURCES:
            sources.append(
                {
                    "id": src["id"],
                    "name": src["name"],
                    "description": src["description"],
                    "type": src["type"],
                    "enabled": src["enabled"],
                    "priority": src["priority"],
                }
            )

        return success(
            data={
                "sources": sources,
                "total": len(sources),
                "enabled_count": sum(1 for s in sources if s["enabled"]),
            },
            message="搜索源列表",
        )
    except Exception as e:
        logger.exception("list_sources 失败: %s", e)
        return error("获取搜索源列表失败", status_code=500, detail=str(e))
