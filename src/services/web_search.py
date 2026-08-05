"""
联网搜索模块 — Tavily 集成（安全版）
包含：SSRF防护、URL白名单、结果净化、注入检测
"""
import os
import re
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 安全配置
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
MAX_QUERY_LENGTH = 500
MAX_RESULTS = 10
ALLOWED_SCHEMES = {"https"}
BLOCKED_DOMAINS = {"localhost", "127.0.0.1", "0.0.0.0", "10.", "172.16.", "192.168."}

@dataclass
class SearchResult:
    title: str
    content: str
    url: str
    score: float
    source_type: str = "tavily"

def _sanitize_query(query: str) -> str:
    """清理搜索查询，防止注入"""
    query = query.strip()[:MAX_QUERY_LENGTH]
    # 移除潜在的指令覆盖模式
    query = re.sub(r'(?:忽略|无视|跳过|重写|覆盖).*(?:指令|规则|限制)', '', query)
    return query

def _is_safe_url(url: str) -> bool:
    """URL安全检查，防止SSRF"""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        # 只允许HTTPS
        if parsed.scheme not in ALLOWED_SCHEMES:
            return False
        hostname = parsed.hostname or ""
        # 阻止内网地址
        for blocked in BLOCKED_DOMAINS:
            if hostname.startswith(blocked) or hostname == blocked:
                return False
        return True
    except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
        return False

def _sanitize_content(content: str) -> str:
    """净化搜索结果内容，防止注入"""
    if not content:
        return ""
    # 移除潜在的prompt注入
    content = re.sub(r'(?:忽略|无视|跳过|重写|覆盖).*(?:指令|规则|限制)', '', content)
    # 移除控制字符
    content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', content)
    # 限制长度
    return content[:5000]

async def web_search(query: str, max_results: int = MAX_RESULTS) -> List[SearchResult]:
    """安全的联网搜索"""
    if not TAVILY_API_KEY:
        logger.warning("[WebSearch] TAVILY_API_KEY 未配置，搜索降级")
        return []
    
    query = _sanitize_query(query)
    if not query:
        return []
    
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": query,
                    "max_results": max_results,
                    "include_answer": False,
                },
            )
            if response.status_code != 200:
                logger.error(f"[WebSearch] Tavily API 错误: {response.status_code}")
                return []
            
            data = response.json()
            results = []
            for item in data.get("results", []):
                url = item.get("url", "")
                # URL安全检查
                if not _is_safe_url(url):
                    logger.warning(f"[WebSearch] 阻止不安全URL: {url}")
                    continue
                results.append(SearchResult(
                    title=_sanitize_content(item.get("title", "")),
                    content=_sanitize_content(item.get("content", "")),
                    url=url,
                    score=item.get("score", 0.0),
                ))
            return results
    except Exception as e:
        logger.error(f"[WebSearch] 搜索失败: {e}")
        return []
