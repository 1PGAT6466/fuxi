"""
timeout.py — 超时处理
异步超时 + 降级
"""
import asyncio
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger("infra.timeout")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行


async def with_timeout(
    coro,
    timeout_seconds: float,
    fallback: Any = None,
    timeout_message: str = "操作超时",
) -> Any:
    """带超时的异步执行"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning(f"[Timeout] {timeout_message} ({timeout_seconds}s)")
        return fallback
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行


async def with_timeout_and_retry(
    coro_func: Callable,
    timeout_seconds: float,
    max_retries: int = 2,
    fallback: Any = None,
) -> Any:
    """带超时和重试的异步执行"""
    for attempt in range(max_retries + 1):
        try:
            return await asyncio.wait_for(coro_func(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            if attempt < max_retries:
                logger.warning(f"[Timeout] 尝试 {attempt + 1}/{max_retries} 超时, 重试...")
            else:
                logger.error(f"[Timeout] 所有 {max_retries} 次重试超时")
                return fallback
        except Exception as e:
            logger.error(f"[Timeout] 执行失败: {e}")
            if attempt == max_retries:
                return fallback

    return fallback
