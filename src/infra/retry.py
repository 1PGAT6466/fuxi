"""
retry.py — 重试机制
指数退避 + 条件重试 + jitter（防雷鸣羊群效应）
"""
import asyncio
import logging
import random
from typing import Callable, Any, Optional

logger = logging.getLogger("infra.retry")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行


async def retry_async(
    func: Callable,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None,
) -> Any:
    """异步重试装饰器"""
    last_exception = None
    current_delay = delay

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                # v1.50 R4: 添加 jitter 防止雷鸣羊群效应
                jittered = current_delay * (0.5 + random.random())
                logger.warning(f"[Retry] 尝试 {attempt + 1}/{max_retries} 失败: {e}, 等待 {jittered:.1f}s")
                if on_retry:
                    on_retry(attempt, e)
                await asyncio.sleep(jittered)
                current_delay *= backoff
            else:
                logger.error(f"[Retry] 所有 {max_retries} 次重试失败: {e}")

    raise last_exception


def retry_sync(
    func: Callable,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Any:
    """同步重试装饰器"""
    import time
    last_exception = None
    current_delay = delay

    for attempt in range(max_retries + 1):
        try:
            return func()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                # v1.50 R4: 添加 jitter 防止雷鸣羊群效应
                jittered = current_delay * (0.5 + random.random())
                logger.warning(f"[Retry] 尝试 {attempt + 1}/{max_retries} 失败: {e}, 等待 {jittered:.1f}s")
                time.sleep(jittered)
                current_delay *= backoff
            else:
                logger.error(f"[Retry] 所有 {max_retries} 次重试失败: {e}")

    raise last_exception
