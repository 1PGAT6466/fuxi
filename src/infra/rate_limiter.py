"""
rate_limiter.py — 速率限制
令牌桶 + 滑动窗口
"""
import time
import logging
from typing import Dict, Optional
from collections import deque

logger = logging.getLogger("infra.rate_limiter")


class TokenBucketRateLimiter:
    """令牌桶速率限制器"""

    def __init__(self, rate: float, capacity: int):
        self.rate = rate  # 每秒生成的令牌数
        self.capacity = capacity  # 桶容量
        self._tokens = capacity
        self._last_refill = time.time()
        self._lock = None

    def _refill(self):
        """补充令牌"""
        now = time.time()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last_refill = now

    def acquire(self, tokens: int = 1) -> bool:
        """获取令牌"""
        import threading
        if self._lock is None:
            self._lock = threading.Lock()

        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False


class SlidingWindowRateLimiter:
    """滑动窗口速率限制器"""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests = deque()

    def acquire(self) -> bool:
        """获取许可"""
        now = time.time()

        # 清理过期请求
        while self._requests and self._requests[0] < now - self.window_seconds:
            self._requests.popleft()

        if len(self._requests) < self.max_requests:
            self._requests.append(now)
            return True

        return False

    def get_remaining(self) -> int:
        """获取剩余许可数"""
        now = time.time()
        while self._requests and self._requests[0] < now - self.window_seconds:
            self._requests.popleft()
        return max(0, self.max_requests - len(self._requests))


# 全局限速器
_rate_limiters: Dict[str, SlidingWindowRateLimiter] = {}


def get_rate_limiter(name: str, max_requests: int = 60, window_seconds: int = 60) -> SlidingWindowRateLimiter:
    """获取限速器"""
    if name not in _rate_limiters:
        _rate_limiters[name] = SlidingWindowRateLimiter(max_requests, window_seconds)
    return _rate_limiters[name]
