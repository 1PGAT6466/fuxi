"""
Async HTTP client helper.
Replaces sync urllib.request.urlopen() in async functions.
"""
import aiohttp
import logging

logger = logging.getLogger(__name__)

# Shared session (reused across requests)
_session = None
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

async def get_session():
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session

async def fetch(url: str, timeout: int = 15, headers: dict = None) -> bytes:
    """Fetch URL content as bytes. Replaces urllib.request.urlopen().read()."""
    session = await get_session()
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout), headers=headers) as resp:
        return await resp.read()

async def fetch_json(url: str, timeout: int = 15) -> dict:
    """Fetch URL and parse as JSON."""
    session = await get_session()
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
        return await resp.json()

async def post(url: str, data: bytes = None, json_data: dict = None, 
               timeout: int = 15, headers: dict = None) -> tuple:
    """POST request. Returns (status, body_bytes)."""
    session = await get_session()
    async with session.post(url, data=data, json=json_data, 
                           timeout=aiohttp.ClientTimeout(total=timeout),
                           headers=headers) as resp:
        body = await resp.read()
        return resp.status, body

async def close():
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None
