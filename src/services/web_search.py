"""
伏羲 v1.50 — Tavily 联网搜索服务
=================================
接入 Tavily API，为伏羲提供实时联网搜索能力。
Tavily API Key 未配置时静默降级，返回空结果。
"""
import logging
from typing import Any, Dict, List, Optional

import httpx

from src.config import TAVILY_API_KEY, TAVILY_MAX_RESULTS, TAVILY_TIMEOUT

logger = logging.getLogger(__name__)

TAVILY_API_URL = "https://api.tavily.com/search"


def is_available() -> bool:
    """检查 Tavily 服务是否可用（API Key 已配置）"""
    return bool(TAVILY_API_KEY)


async def search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    include_answer: bool = True,
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    调用 Tavily API 执行联网搜索。

    Args:
        query: 搜索查询
        max_results: 最大结果数（默认 5）
        search_depth: 搜索深度 "basic" 或 "advanced"
        include_answer: 是否包含 AI 生成的摘要答案
        include_domains: 限定搜索的域名列表
        exclude_domains: 排除的域名列表

    Returns:
        {
            "success": bool,
            "answer": str | None,       # AI 摘要答案
            "results": [                # 搜索结果列表
                {
                    "title": str,
                    "url": str,
                    "content": str,
                    "score": float,
                }
            ],
            "query": str,
            "error": str | None,
        }
    """
    if not TAVILY_API_KEY:
        return {
            "success": False,
            "answer": None,
            "results": [],
            "query": query,
            "error": "Tavily API Key 未配置，联网搜索不可用",
        }

    payload: Dict[str, Any] = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "max_results": min(max_results, TAVILY_MAX_RESULTS),
        "search_depth": search_depth,
        "include_answer": include_answer,
    }
    if include_domains:
        payload["include_domains"] = include_domains
    if exclude_domains:
        payload["exclude_domains"] = exclude_domains

    try:
        async with httpx.AsyncClient(timeout=TAVILY_TIMEOUT) as client:
            resp = await client.post(TAVILY_API_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "score": item.get("score", 0.0),
            })

        return {
            "success": True,
            "answer": data.get("answer"),
            "results": results,
            "query": query,
            "error": None,
        }

    except httpx.TimeoutException:
        logger.warning(f"[Tavily] 搜索超时: {query}")
        return {
            "success": False,
            "answer": None,
            "results": [],
            "query": query,
            "error": "搜索请求超时",
        }
    except httpx.HTTPStatusError as e:
        logger.warning(f"[Tavily] HTTP 错误 {e.response.status_code}: {e}")
        return {
            "success": False,
            "answer": None,
            "results": [],
            "query": query,
            "error": f"搜索服务返回错误: {e.response.status_code}",
        }
    except Exception as e:
        logger.error(f"[Tavily] 搜索异常: {e}", exc_info=True)
        return {
            "success": False,
            "answer": None,
            "results": [],
            "query": query,
            "error": f"搜索异常: {str(e)}",
        }
