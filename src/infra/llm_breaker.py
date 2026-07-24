"""
llm_breaker.py — LLM/Embedder/Reranker 断路器集成包装器 (v1.50 R4)
=================================================================

将 src/infra/circuit_breaker.py 的 CircuitBreaker 集成到
LLM、Embedder、Reranker 调用中，防止下游服务故障导致级联失败。

使用示例::

    from src.infra.llm_breaker import llm_protected_call

    # 在 llm.py 的 _call_api 中集成
    async def _call_api(...):
        return await llm_protected_call(
            actual_call_func,
            fallback_func=None,
            service_name="mimo_llm",
        )

CircuitBreaker 参数:
  - failure_threshold: 5 次连续失败后熔断
  - recovery_timeout:  30 秒后尝试恢复
  - half_open_max_calls: 3 次探测成功后完全恢复
"""

import asyncio
import logging
import time
from typing import Any, Callable, Optional, Dict
from src.infra.circuit_breaker import CircuitBreaker, get_circuit_breaker
from src.infra.health_check import (
    record_circuit_open, record_circuit_close,
    record_llm_call,
)

logger = logging.getLogger("infra.llm_breaker")

# 全局断路器实例
_breakers: Dict[str, CircuitBreaker] = {}


def _get_breaker(service_name: str) -> CircuitBreaker:
    """获取或创建指定服务的断路器"""
    if service_name not in _breakers:
        _breakers[service_name] = get_circuit_breaker(
            service_name,
            failure_threshold=5,
            recovery_timeout=30.0,
            half_open_max_calls=3,
        )
    return _breakers[service_name]


async def protected_call(
    call_func: Callable,
    service_name: str,
    fallback_func: Optional[Callable] = None,
    *args,
    **kwargs,
) -> Any:
    """在断路器保护下执行异步调用

    流程：
      1. 检查断路器状态 → 若 OPEN，直接调用 fallback 或抛异常
      2. 执行实际调用
      3. 成功 → 记录成功，返回结果
      4. 失败 → 记录失败，调用 fallback 或抛异常

    Args:
        call_func:     实际调用函数（异步）
        service_name:  服务名称（用于断路器标识）
        fallback_func: 降级函数（异步），失败时调用
        *args, **kwargs: 传递给 call_func

    Returns:
        调用结果（成功时）或 fallback 结果（降级时）

    Raises:
        RuntimeError: 断路器 OPEN 且无 fallback 时
        原始异常:    失败且无 fallback 时
    """
    breaker = _get_breaker(service_name)

    # 检查断路器
    if not breaker.can_execute():
        logger.warning(
            "[CircuitBreaker:%s] 断路器 OPEN，拒绝请求", service_name,
        )
        record_circuit_open(service_name)
        if fallback_func:
            logger.info("[CircuitBreaker:%s] 使用 fallback", service_name)
            return await fallback_func(*args, **kwargs)
        raise RuntimeError(
            f"服务 [{service_name}] 不可用（断路器断开），请稍后重试"
        )

    try:
        result = await call_func(*args, **kwargs)
        breaker.record_success()
        record_llm_call(success=True)
        if not breaker.is_healthy:
            record_circuit_close(service_name)
        return result
    except Exception as e:
        breaker.record_failure()
        record_llm_call(success=False)

        if breaker.state.value == "open":
            record_circuit_open(service_name)

        if fallback_func:
            logger.info(
                "[CircuitBreaker:%s] 调用失败，使用 fallback: %s",
                service_name, str(e)[:100],
            )
            try:
                return await fallback_func(*args, **kwargs)
            except Exception as fallback_e:
                logger.error(
                    "[CircuitBreaker:%s] fallback 也失败: %s",
                    service_name, str(fallback_e)[:100],
                )
                raise e  # 抛出原始异常

        raise


def protected_call_sync(
    call_func: Callable,
    service_name: str,
    fallback_func: Optional[Callable] = None,
    *args,
    **kwargs,
) -> Any:
    """同步版本的断路器保护调用

    用于不需要异步的环境（如数据库操作）。
    """
    breaker = _get_breaker(service_name)

    if not breaker.can_execute():
        logger.warning(
            "[CircuitBreaker:%s] 断路器 OPEN，拒绝请求", service_name,
        )
        record_circuit_open(service_name)
        if fallback_func:
            return fallback_func(*args, **kwargs)
        raise RuntimeError(
            f"服务 [{service_name}] 不可用（断路器断开）"
        )

    try:
        result = call_func(*args, **kwargs)
        breaker.record_success()
        if not breaker.is_healthy:
            record_circuit_close(service_name)
        return result
    except Exception as e:
        breaker.record_failure()
        if breaker.state.value == "open":
            record_circuit_open(service_name)

        if fallback_func:
            try:
                return fallback_func(*args, **kwargs)
            except Exception:
                raise e
        raise


def get_breaker_status(service_name: str = None) -> Dict:
    """获取断路器状态

    Args:
        service_name: 可选的服务名，不传则返回所有

    Returns:
        状态字典或列表
    """
    if service_name:
        breaker = _breakers.get(service_name)
        if breaker:
            s = breaker.status
            return {
                "name": s.name,
                "state": s.circuit_state.value,
                "failure_count": s.failure_count,
                "last_ok": s.last_ok,
                "degraded": s.degraded,
            }
        return {"error": "unknown_service"}

    return {
        name: {
            "state": b.state.value,
            "failure_count": b.status.failure_count,
            "degraded": b.status.degraded,
        }
        for name, b in _breakers.items()
    }


def reset_breaker(service_name: str = None) -> None:
    """重置断路器

    Args:
        service_name: 可选的服务名，不传则重置所有
    """
    if service_name:
        breaker = _breakers.get(service_name)
        if breaker:
            breaker.reset()
    else:
        for b in _breakers.values():
            b.reset()
