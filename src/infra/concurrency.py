"""
concurrency.py — 并发控制
少阳Semaphore(3) / 太阳Semaphore(10) / 太阴RateLimiting
"""
import asyncio
import logging
import time
from typing import Dict, Optional

logger = logging.getLogger("infra.concurrency")


class RateLimiter:
    """速率限制器"""

    def __init__(self, max_requests: int = 60, period_seconds: int = 60):
        self.max_requests = max_requests
        self.period_seconds = period_seconds
        self._requests: list = []
        self._lock = asyncio.Lock()
        # v1.50 R4: 同步锁，用于保护 get_remaining() 的 read/cull 操作
        import threading
        self._sync_lock = threading.Lock()
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

    async def acquire(self) -> bool:
        """获取许可 — v1.50 R4: 双重锁保护"""
        async with self._lock:
            with self._sync_lock:
                now = time.time()
                # 清理过期请求
                self._requests = [t for t in self._requests if t > now - self.period_seconds]

                if len(self._requests) >= self.max_requests:
                    return False

                self._requests.append(now)
                return True

    def get_remaining(self) -> int:
        """获取剩余许可数 — v1.50 R4: threading.Lock 保护"""
        with self._sync_lock:
            now = time.time()
            self._requests = [t for t in self._requests if t > now - self.period_seconds]
            return max(0, self.max_requests - len(self._requests))


class ConcurrencyManager:
    """并发管理器"""

    def __init__(self):
        self._semaphores: Dict[str, asyncio.Semaphore] = {
            "shaoyang": asyncio.Semaphore(3),
            "taiyang": asyncio.Semaphore(10),
            "shaoyin": asyncio.Semaphore(20),
            "taiyin": asyncio.Semaphore(50),
        }
        self._rate_limiters: Dict[str, RateLimiter] = {
            "global": RateLimiter(60, 60),
            "chat": RateLimiter(10, 60),
            "upload": RateLimiter(3, 60),
        }

    async def acquire_symbol(self, symbol_id: str):
        """获取象的信号量"""
        semaphore = self._semaphores.get(symbol_id)
        if semaphore:
            return await semaphore.acquire()
        return True

    def release_symbol(self, symbol_id: str):
        """释放象的信号量"""
        semaphore = self._semaphores.get(symbol_id)
        if semaphore:
            semaphore.release()

    async def check_rate_limit(self, endpoint: str = "global") -> bool:
        """检查速率限制"""
        limiter = self._rate_limiters.get(endpoint)
        if limiter:
            return await limiter.acquire()
        return True

    def get_status(self) -> Dict:
        """获取并发状态"""
        status = {}
        for symbol_id, semaphore in self._semaphores.items():
            status[symbol_id] = {
                "available": semaphore._value,
                "locked": semaphore.locked(),
            }
        return status


# 全局实例
_concurrency: Optional[ConcurrencyManager] = None


def get_concurrency_manager() -> ConcurrencyManager:
    """获取全局并发管理器"""
    global _concurrency
    if _concurrency is None:
        _concurrency = ConcurrencyManager()
    return _concurrency
