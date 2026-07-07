"""
circuit_breaker.py — 断路器
防止级联故障

提供统一的 CircuitBreaker 实现，供 IntentBus 和 GuaBase 共享使用。
IntentBus._get_circuit_breaker() 和 GuaBase._circuits 使用同一套断路器实例。
"""
import time
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Any
from enum import Enum

logger = logging.getLogger("infra.circuit_breaker")


class CircuitState(Enum):
    """断路器状态"""
    CLOSED = "closed"  # 正常
    OPEN = "open"  # 断开
    HALF_OPEN = "half_open"  # 半开


@dataclass
class DependencyStatus:
    """单个依赖的状态快照

    Attributes:
        name:          依赖名
        circuit_state: 断路器当前状态
        failure_count: 最近窗口内失败次数
        last_ok:       最后一次成功时间戳（0 表示从未成功）
        degraded:      是否触发降级
    """

    name: str
    circuit_state: CircuitState
    failure_count: int = 0
    last_ok: float = 0.0
    degraded: bool = False


class CircuitBreaker:
    """断路器

    每个外部依赖一个独立断路器，互不影响。
    支持定时修复探活（allow_probe）。

    Usage::

        cb = CircuitBreaker(name="llm", failure_threshold=5)
        if cb.can_execute():
            try:
                result = do_something()
                cb.record_success()
            except Exception:
                cb.record_failure()
                raise

    IntentBus 使用::

        cb = bus._get_circuit_breaker("乾", "离")
        # cb 是 CircuitBreaker 实例，GuaBase 也可通过同名 key 共享

    GuaBase 使用::

        cb = self.register_dependency("llm")
        assert isinstance(cb, CircuitBreaker)
    """

    def __init__(
        self,
        name: str = "",
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        """
        Args:
            name:                断路器名称（对应依赖名）。对于 IntentBus，可为空字符串。
            failure_threshold:   失败阈值，连续达到后熔断
            recovery_timeout:    熔断后等待恢复的秒数
            half_open_max_calls: 半开状态下允许的最大探测请求数
        """
        self.name: str = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0
        self._last_success_time: float = 0.0
        self._half_open_calls: int = 0

    # ----- properties -----

    @property
    def state(self) -> CircuitState:
        """获取当前状态（含自动半开转换）"""
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time > self.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
                self._half_open_calls = 0
        return self._state

    @property
    def is_healthy(self) -> bool:
        """当前是否可正常服务（非 OPEN）"""
        return self.state != CircuitState.OPEN

    @property
    def status(self) -> DependencyStatus:
        """生成当前状态快照"""
        return DependencyStatus(
            name=self.name,
            circuit_state=self.state,
            failure_count=self._failure_count,
            last_ok=self._last_success_time,
            degraded=self.state == CircuitState.OPEN,
        )

    @property
    def circuit_state(self) -> CircuitState:
        """别名：获取断路器状态（兼容旧接口）"""
        return self.state

    # ----- 状态变更 -----

    def record_success(self) -> None:
        """记录一次成功调用"""
        self._last_success_time = time.time()
        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            if self._half_open_calls >= self.half_open_max_calls:
                # 连续成功达到阈值 → 恢复
                self._transition_to(CircuitState.CLOSED)
                self._failure_count = 0
                logger.info(
                    "Circuit [%s] 已恢复 → CLOSED (连续 %d 次探测成功)",
                    self.name, self._half_open_calls,
                )
        elif self._state == CircuitState.CLOSED:
            # 成功后重置失败计数（连续失败才熔断）
            self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self) -> None:
        """记录一次失败调用"""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
            logger.warning(
                "Circuit [%s] 半开探测失败 → OPEN", self.name,
            )
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                self._transition_to(CircuitState.OPEN)
                logger.warning(
                    "Circuit [%s] 熔断触发 → OPEN (连续失败 %d 次)",
                    self.name, self._failure_count,
                )

    def can_execute(self) -> bool:
        """是否可以放行请求"""
        s = self.state
        if s == CircuitState.CLOSED:
            return True
        if s == CircuitState.HALF_OPEN:
            return self._half_open_calls < self.half_open_max_calls
        return False

    def reset(self) -> None:
        """强制重置断路器"""
        self._transition_to(CircuitState.CLOSED)
        self._failure_count = 0
        self._half_open_calls = 0
        logger.info("Circuit [%s] 已强制重置 → CLOSED", self.name)

    # ----- internal -----

    def _transition_to(self, target: CircuitState) -> None:
        old = self._state
        self._state = target
        if old != target:
            logger.debug("Circuit [%s] %s → %s", self.name, old.value, target.value)


# 全局断路器注册表
# key 格式：对于 IntentBus 为 (source, target) tuple；
# 对于 GuaBase 为 dependency_name 字符串。
# 两者共享同一注册表，确保 IntentBus dispatch 失败会影响 GuaBase 断路器状态。
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """获取或创建断路器

    Args:
        name: 断路器名称（唯一标识）
        **kwargs: 传递给 CircuitBreaker 构造函数的额外参数

    Returns:
        CircuitBreaker 实例
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name=name, **kwargs)
    return _circuit_breakers[name]


def reset_all_circuit_breakers() -> None:
    """重置所有断路器（主要用于测试）"""
    _circuit_breakers.clear()
    logger.debug("所有断路器已重置")
