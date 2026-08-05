"""
rate_limiter.py — 令牌桶限流器
===============================
用于控制 API 请求速率，防止系统过载。

令牌桶算法：
- 桶中有固定数量的令牌
- 每个请求消耗一个令牌
- 令牌以固定速率补充
- 桶空时拒绝请求
"""
import asyncio
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TokenBucket:
    """令牌桶限流器
    
    Args:
        rate: 令牌补充速率（个/秒）
        capacity: 桶容量（最大令牌数）
    """
    
    def __init__(self, rate: float = 10.0, capacity: int = 50):
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_time = time.monotonic()
        self._lock = asyncio.Lock()
        
        # 统计信息
        self._total_requests = 0
        self._rejected_requests = 0
    
    async def acquire(self, timeout: float = 30.0) -> bool:
        """获取一个令牌
        
        Args:
            timeout: 等待超时时间（秒）
            
        Returns:
            True: 成功获取令牌
            False: 超时或被拒绝
        """
        async with self._lock:
            self._total_requests += 1
            
            # 补充令牌
            now = time.monotonic()
            elapsed = now - self.last_time
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_time = now
            
            # 检查是否有足够的令牌
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            
            # 计算需要等待的时间
            wait_time = (1.0 - self.tokens) / self.rate
            
            if wait_time > timeout:
                self._rejected_requests += 1
                logger.warning(
                    f"[RateLimiter] 请求被拒绝，需要等待 {wait_time:.1f}s > 超时 {timeout}s"
                )
                return False
        
        # 等待令牌补充
        await asyncio.sleep(wait_time)
        
        # 重新尝试获取令牌
        async with self._lock:
            self._total_requests += 1
            now = time.monotonic()
            elapsed = now - self.last_time
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_time = now
            
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            
            self._rejected_requests += 1
            return False
    
    def get_stats(self) -> dict:
        """获取限流器统计信息"""
        return {
            "rate": self.rate,
            "capacity": self.capacity,
            "current_tokens": round(self.tokens, 2),
            "total_requests": self._total_requests,
            "rejected_requests": self._rejected_requests,
            "rejection_rate": round(
                self._rejected_requests / max(self._total_requests, 1) * 100, 2
            ),
        }


class RequestQueue:
    """请求队列
    
    用于平滑处理峰值请求，当系统过载时将请求放入队列等待处理。
    
    Args:
        max_size: 队列最大长度
        timeout: 队列等待超时时间（秒）
    """
    
    def __init__(self, max_size: int = 50, timeout: float = 30.0):
        self.max_size = max_size
        self.timeout = timeout
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._total_requests = 0
        self._queued_requests = 0
        self._timeout_requests = 0
    
    async def put(self, item: any) -> bool:
        """将请求放入队列
        
        Args:
            item: 请求数据
            
        Returns:
            True: 成功放入队列
            False: 队列已满或超时
        """
        self._total_requests += 1
        
        try:
            # 非阻塞尝试
            self._queue.put_nowait(item)
            self._queued_requests += 1
            return True
        except asyncio.QueueFull:
            # 队列已满，等待
            try:
                await asyncio.wait_for(
                    self._queue.put(item),
                    timeout=self.timeout
                )
                self._queued_requests += 1
                return True
            except asyncio.TimeoutError:
                self._timeout_requests += 1
                logger.warning(f"[RequestQueue] 队列已满，请求超时")
                return False
    
    async def get(self) -> Optional[any]:
        """从队列获取请求
        
        Returns:
            请求数据，或 None（队列为空）
        """
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None
    
    def get_stats(self) -> dict:
        """获取队列统计信息"""
        return {
            "max_size": self.max_size,
            "current_size": self._queue.qsize(),
            "total_requests": self._total_requests,
            "queued_requests": self._queued_requests,
            "timeout_requests": self._timeout_requests,
            "queue_usage": round(
                self._queue.qsize() / max(self.max_size, 1) * 100, 2
            ),
        }


# 全局限流器实例
_rate_limiter: Optional[TokenBucket] = None
_request_queue: Optional[RequestQueue] = None


def get_rate_limiter() -> TokenBucket:
    """获取全局限流器实例"""
    global _rate_limiter
    if _rate_limiter is None:
        import os
        rate = float(os.getenv("RATE_LIMITER_RATE", "10"))
        capacity = int(os.getenv("RATE_LIMITER_CAPACITY", "50"))
        _rate_limiter = TokenBucket(rate=rate, capacity=capacity)
    return _rate_limiter


def get_request_queue() -> RequestQueue:
    """获取全局请求队列实例"""
    global _request_queue
    if _request_queue is None:
        import os
        max_size = int(os.getenv("REQUEST_QUEUE_MAX_SIZE", "50"))
        timeout = float(os.getenv("REQUEST_QUEUE_TIMEOUT", "30"))
        _request_queue = RequestQueue(max_size=max_size, timeout=timeout)
    return _request_queue
