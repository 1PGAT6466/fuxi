"""
circuit_breaker.py — 断路器
防止级联故障
"""
import time
import logging
from typing import Dict, Callable, Any
from enum import Enum

logger = logging.getLogger("infra.circuit_breaker")


class CircuitState(Enum):
    """断路器状态"""
    CLOSED = "closed"  # 正常
    OPEN = "open"  # 断开
    HALF_OPEN = "half_open"  # 半开


class CircuitBreaker:
    """断路器"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        """获取当前状态"""
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time > self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    def record_success(self):
        """记录成功"""
        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            if self._half_open_calls >= self.half_open_max_calls:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0

    def record_failure(self):
        """记录失败"""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN

    def can_execute(self) -> bool:
        """是否可以执行"""
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        elif state == CircuitState.HALF_OPEN:
            return self._half_open_calls < self.half_open_max_calls
        else:
            return False


# 全局断路器
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """获取断路器"""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(**kwargs)
    return _circuit_breakers[name]
