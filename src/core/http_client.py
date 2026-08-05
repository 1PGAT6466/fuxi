"""
Async HTTP client helper.
Replaces sync urllib.request.urlopen() in async functions.
Uses global aiohttp session with connection pool.

v1.50 安全修复: 集成内网 IP 过滤，防止出站请求泄露内网信息
"""

import logging

import aiohttp
from src.infra.internal_ip_filter import check_outbound_url

logger = logging.getLogger(__name__)

# Shared session (reused across requests) with connection pool
_session = None


async def get_session():
    global _session
    if _session is None or _session.closed:
        connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=20,
            ttl_dns_cache=300,
            enable_cleanup_closed=True,
        )
        _session = aiohttp.ClientSession(connector=connector)
    return _session


async def fetch(url: str, timeout: int = 15, headers: dict = None) -> bytes:
    """Fetch URL content as bytes. Replaces urllib.request.urlopen().read().

    v1.50: 出站前检查内网 IP 过滤
    """
    if not check_outbound_url(url):
        raise ValueError(f"出站请求被拒绝: URL 指向内网地址")
    session = await get_session()
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout), headers=headers) as resp:
        return await resp.read()


async def fetch_json(url: str, timeout: int = 15) -> dict:
    """Fetch URL and parse as JSON.

    v1.50: 出站前检查内网 IP 过滤
    """
    if not check_outbound_url(url):
        raise ValueError(f"出站请求被拒绝: URL 指向内网地址")
    session = await get_session()
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
        return await resp.json()


async def post(url: str, data: bytes = None, json_data: dict = None, timeout: int = 15, headers: dict = None) -> tuple:
    """POST request. Returns (status, body_bytes).

    v1.50: 出站前检查内网 IP 过滤
    """
    if not check_outbound_url(url):
        raise ValueError(f"出站请求被拒绝: URL 指向内网地址")
    session = await get_session()
    async with session.post(
        url, data=data, json=json_data, timeout=aiohttp.ClientTimeout(total=timeout), headers=headers
    ) as resp:
        body = await resp.read()
        return resp.status, body


async def close():
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None
