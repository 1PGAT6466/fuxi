"""
rate_limiter.py — 速率限制
令牌桶 + 滑动窗口
"""
import time
import logging
from typing import Dict
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
        self._last_access = time.time()  # 用于过期清理

    def acquire(self) -> bool:
        """获取许可"""
        now = time.time()
        self._last_access = now

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
        self._last_access = now
        while self._requests and self._requests[0] < now - self.window_seconds:
            self._requests.popleft()
        return max(0, self.max_requests - len(self._requests))

    @property
    def is_expired(self) -> bool:
        """判断限流器是否过期（超过 2 个窗口未访问）"""
        return time.time() - self._last_access > self.window_seconds * 2


# 全局限速器
_rate_limiters: Dict[str, SlidingWindowRateLimiter] = {}
_RATE_LIMITER_TTL = 300  # 5 分钟未访问则清理
_last_cleanup = time.time()


def _cleanup_expired_limiters():
    """清理过期的限流器实例，防止内存泄漏"""
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < _RATE_LIMITER_TTL:
        return
    _last_cleanup = now
    expired_keys = [k for k, v in _rate_limiters.items() if v.is_expired]
    for k in expired_keys:
        del _rate_limiters[k]
    if expired_keys:
        logger.debug("清理过期限流器 %d 个", len(expired_keys))


def get_rate_limiter(name: str, max_requests: int = 60, window_seconds: int = 60) -> SlidingWindowRateLimiter:
    """获取限速器"""
    _cleanup_expired_limiters()
    if name not in _rate_limiters:
        _rate_limiters[name] = SlidingWindowRateLimiter(max_requests, window_seconds)
    return _rate_limiters[name]


def get_global_rate_limiter(name: str, max_requests: int = 60, window_sec: int = 60) -> SlidingWindowRateLimiter:
    """获取全局限速器 — v1.50 R3 Blue 新增
    
    用于健康检查等公共端点的速率限制。
    基于客户端 IP 进行限流。
    
    Args:
        name: 限速器名称（如 "health_check"）
        max_requests: 窗口内最大请求数
        window_sec: 窗口秒数
    
    Returns:
        SlidingWindowRateLimiter 实例
    """
    return get_rate_limiter(name, max_requests, window_sec)
