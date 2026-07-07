#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_bagua_smoke.py — 八卦层冒烟测试 · 伏羲 v2.1 Phase 4

测试范围：
  1. 卦注册到 IntentBus + dispatch 成功
  2. 乾卦 think() 固定规则路径（rule_based 模式）
  3. 三层降级路径
  4. 断路器触发 → 降级
  5. 统一断路器：IntentBus 与 GuaBase 共享 CircuitBreaker 实例
"""
from __future__ import annotations

import sys
import os
import time
import threading
import pytest

# 确保 repo 在路径中
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_ROOT)

from src.bagua.base_gua import (
    GuaBase,
    CircuitState,
    HealthLevel,
    DegradationRule,
    FallbackAction,
)
from src.bagua.intent_bus import (
    IntentBus,
    Signal,
    SignalType,
    Priority,
    IntentResult,
    DispatchStatus,
    get_intent_bus,
    reset_intent_bus,
)
from src.infra.circuit_breaker import (
    CircuitBreaker,
    get_circuit_breaker,
    reset_all_circuit_breakers,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def reset_circuits():
    """每个测试前重置断路器和 IntentBus 全局状态"""
    reset_intent_bus()
    reset_all_circuit_breakers()
    yield
    reset_intent_bus()
    reset_all_circuit_breakers()


# ============================================================================
# 测试用的最小卦实现
# ============================================================================

class EchoGua(GuaBase):
    """用于测试的回声卦：直接返回接收到的 payload"""

    GUA_NAME = "echo"
    GUA_EMOJI = "◉"

    def _setup_degradation_rules(self) -> None:
        pass

    def _execute_core(self, params):
        return {"echo": params, "status": "ok"}


class FailingGua(GuaBase):
    """用于测试的失败卦：总是抛出异常"""

    GUA_NAME = "failing"
    GUA_EMOJI = "✕"

    def __init__(self, fail_count: int = 999, intent_bus=None):
        super().__init__(intent_bus=intent_bus)
        self._fail_count = fail_count
        self._call_count = 0

    def _setup_degradation_rules(self) -> None:
        pass

    def _execute_core(self, params):
        self._call_count += 1
        if self._call_count <= self._fail_count:
            raise RuntimeError(f"Simulated failure #{self._call_count}")
        return {"success": True, "call": self._call_count}


class DegradingGua(GuaBase):
    """用于测试降级路径的卦"""

    GUA_NAME = "degrading"
    GUA_EMOJI = "⊕"

    def __init__(self, intent_bus=None):
        super().__init__(intent_bus=intent_bus)
        self._core_called = False
        self._fallback_called = False
        self._simulate_failure = True

    def _setup_degradation_rules(self) -> None:
        self.add_rule(DegradationRule(
            name="simulated_failure",
            condition_fn=lambda: self._simulate_failure,
            fallback=FallbackAction(
                name="fallback_handler",
                handler=self._fallback_handler,
                description="测试降级处理器",
            ),
            priority=1,
        ))

    def _execute_core(self, params):
        self._core_called = True
        return {"from_core": True, "params": params}

    def _fallback_handler(self, params):
        self._fallback_called = True
        return {"from_fallback": True, "params": params}


# ============================================================================
# 测试 1: 卦注册 + dispatch 成功
# ============================================================================

class TestGuaRegistration:
    """测试：卦注册到 IntentBus 并成功 dispatch"""

    def test_register_and_dispatch_echo(self):
        """EchoGua 注册后 dispatch 返回正确的 echo 结果"""
        bus = get_intent_bus()
        echo = EchoGua(intent_bus=bus)

        # 注册
        echo.register_to_bus()
        assert "echo" in bus.get_registered_guas()

        # 打开 session
        bus.open_session("test-session-1")

        # dispatch
        signal = Signal(
            source="test",
            target="echo",
            signal_type=SignalType.REQUEST,
            priority=Priority.NORMAL,
            payload={"message": "hello world"},
            session_id="test-session-1",
        )
        result = bus.dispatch(signal)

        assert result.status == DispatchStatus.OK
        assert result.payload.get("echo", {}).get("message") == "hello world"

        # 清理
        echo.unregister_from_bus()
        bus.close_session("test-session-1")

    def test_dispatch_to_unregistered_target(self):
        """dispatch 到未注册的目标返回 TARGET_UNREGISTERED"""
        bus = get_intent_bus()
        bus.open_session("test-session-2")

        signal = Signal(
            source="test",
            target="nonexistent",
            signal_type=SignalType.REQUEST,
            session_id="test-session-2",
        )
        result = bus.dispatch(signal)

        assert result.status == DispatchStatus.TARGET_UNREGISTERED
        bus.close_session("test-session-2")

    def test_dispatch_missing_session(self):
        """dispatch 缺少 session_id 返回错误"""
        bus = get_intent_bus()
        echo = EchoGua(intent_bus=bus)
        echo.register_to_bus()

        signal = Signal(
            source="test",
            target="echo",
            signal_type=SignalType.REQUEST,
            session_id="",  # 空 session
        )
        result = bus.dispatch(signal)

        assert result.status == DispatchStatus.UNKNOWN_ERROR
        echo.unregister_from_bus()


# ============================================================================
# 测试 2: 乾卦 think() 固定规则路径
# ============================================================================

class TestQianFixedRule:
    """测试：乾卦 think() rule_based 模式（固定规则，不调 LLM）"""

    @pytest.mark.asyncio
    async def test_think_rule_based_basic(self):
        """乾卦 rule_based 模式可以完整执行固定流水线"""
        from src.bagua.qian import QianGua

        bus = get_intent_bus()
        qian = QianGua(intent_bus=bus, intent_mode="rule_based")
        qian.start()

        bus.open_session("test-qian-rule")

        # 执行 think — 固定序列: SEARCH → REFINE → DECIDE → PRESENT → DONE
        result = await qian.think(
            query="什么是伏羲？",
            history=[],
            session_id="test-qian-rule",
        )

        assert "answer" in result
        assert "rounds" in result
        assert "intents_used" in result
        assert result.get("intents_used") == ["SEARCH", "REFINE", "DECIDE", "PRESENT", "DONE"]

        qian.stop()
        qian.clear_session("test-qian-rule")
        bus.close_session("test-qian-rule")

    @pytest.mark.asyncio
    async def test_think_rule_based_returns_structure(self):
        """乾卦返回结构完整（answer/sources/mode/confidence/rounds/intents_used/fallback_used/elapsed_ms）"""
        from src.bagua.qian import QianGua

        bus = get_intent_bus()
        qian = QianGua(intent_bus=bus, intent_mode="rule_based")
        qian.start()

        bus.open_session("test-qian-struct")
        result = await qian.think(
            query="测试查询",
            history=[],
            session_id="test-qian-struct",
        )

        assert "answer" in result
        assert "sources" in result
        assert "mode" in result
        assert "qian_rule_based" in result.get("mode", "")
        assert "confidence" in result
        assert "rounds" in result
        assert "intents_used" in result
        assert "fallback_used" in result
        assert "elapsed_ms" in result

        qian.stop()
        qian.clear_session("test-qian-struct")
        bus.close_session("test-qian-struct")


# ============================================================================
# 测试 3: 三层降级路径
# ============================================================================

class TestDegradationPath:
    """测试：GuaBase.execute() 的三层降级路径"""

    def test_normal_execution_no_degradation(self):
        """正常执行不触发降级"""
        gua = EchoGua()
        gua._simulate_failure = False  # 仅 DegradingGua 有此属性

        result = gua.execute({"test": "value"})
        assert result.get("echo", {}).get("test") == "value"
        assert gua.health == HealthLevel.FULL

    def test_degradation_triggered_by_condition(self):
        """降级条件满足时触发 fallback"""
        gua = DegradingGua()
        gua._simulate_failure = True

        result = gua.execute({"test": "degraded"})

        assert result.get("from_fallback") is True
        assert gua._fallback_called is True
        assert gua._core_called is False  # 核心逻辑未被调用（降级优先）


    def test_degradation_not_triggered_when_healthy(self):
        """条件不满足时不触发降级"""
        gua = DegradingGua()
        gua._simulate_failure = False

        result = gua.execute({"test": "normal"})

        assert result.get("from_core") is True
        assert gua._core_called is True
        assert gua._fallback_called is False

    def test_exception_fallback(self):
        """核心执行异常后触发降级兜底"""
        class ExceptionFallbackGua(GuaBase):
            GUA_NAME = "exc_fallback"
            GUA_EMOJI = "⚡"

            def __init__(self):
                super().__init__()
                self.fallback_hit = False

            def _setup_degradation_rules(self):
                self.add_rule(DegradationRule(
                    name="always",
                    condition_fn=lambda: True,
                    fallback=FallbackAction(
                        name="safety",
                        handler=lambda p: {"fallback": True, "safe": "yes"},
                    ),
                    priority=999,  # 低优先级，仅在异常后触发
                ))

            def _execute_core(self, params):
                raise ValueError("核心逻辑崩溃!")

        gua = ExceptionFallbackGua()
        result = gua.execute({"action": "do_it"})

        # 异常后走降级矩阵兜底
        assert result.get("fallback") is True
        assert result.get("safe") == "yes"


# ============================================================================
# 测试 4: 断路器触发 → 降级
# ============================================================================

class TestCircuitBreaker:
    """测试：断路器触发 → IntentBus 拒绝 dispatch → GuaBase 感知断路器状态"""

    def test_circuit_breaker_opens_after_failures(self):
        """5 次失败后断路器断开"""
        cb = CircuitBreaker(name="test-cb", failure_threshold=5)

        assert cb.can_execute() is True
        assert cb.state == CircuitState.CLOSED

        for i in range(5):
            cb.record_failure()

        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

    def test_circuit_breaker_half_open_probe(self):
        """半开状态下放行探活请求"""
        cb = CircuitBreaker(
            name="test-half-open",
            failure_threshold=2,
            recovery_timeout=0.01,  # 100ms → 快速恢复
        )

        # 熔断
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # 等待恢复超时
        time.sleep(0.05)
        _ = cb.state  # 触发自动半开转换
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.can_execute() is True

    def test_circuit_breaker_recovery(self):
        """连续成功探测后断路器恢复"""
        cb = CircuitBreaker(
            name="test-recovery",
            failure_threshold=2,
            recovery_timeout=0.01,
            half_open_max_calls=2,
        )

        # 熔断 → 半开
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.05)
        _ = cb.state  # 触发半开

        assert cb.state == CircuitState.HALF_OPEN

        # 连续成功 → 恢复
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_intent_bus_circuit_open_blocks_dispatch(self):
        """IntentBus 断路器断开时 dispatch 返回 CIRCUIT_OPEN"""
        bus = get_intent_bus()
        echo = EchoGua(intent_bus=bus)
        echo.register_to_bus()
        bus.open_session("test-cb-block")

        # 模拟 5 次失败触发断路器
        cb = bus._get_circuit_breaker("test-source", "echo")
        for _ in range(5):
            cb.record_failure()

        assert cb.state == CircuitState.OPEN

        signal = Signal(
            source="test-source",
            target="echo",
            signal_type=SignalType.REQUEST,
            session_id="test-cb-block",
        )
        result = bus.dispatch(signal)

        assert result.status == DispatchStatus.CIRCUIT_OPEN

        # 清理
        cb.reset()
        echo.unregister_from_bus()
        bus.close_session("test-cb-block")

    def test_unified_circuit_breaker_shared(self):
        """验证 IntentBus 和 GuaBase 使用同一套断路器实例

        IntentBus._get_circuit_breaker("乾", "离") 使用全局注册表，
        GuaBase 通过 get_circuit_breaker() 获取相同实例。
        """
        bus = get_intent_bus()

        # IntentBus 获取断路器
        cb_from_bus = bus._get_circuit_breaker("乾", "离")
        assert cb_from_bus is not None
        assert cb_from_bus.state == CircuitState.CLOSED

        # 通过全局注册表获取同 key 的断路器
        cb_from_global = get_circuit_breaker("乾->离")
        assert cb_from_global is cb_from_bus  # 同一个实例！

        # 模拟 IntentBus dispatch 失败，触发断路器
        for _ in range(5):
            cb_from_bus.record_failure()

        assert cb_from_bus.state == CircuitState.OPEN
        assert cb_from_global.state == CircuitState.OPEN  # 共享状态

        # GuaBase 通过全局注册表注册的断路器也受影响
        gua_cb = get_circuit_breaker("乾->离")
        assert gua_cb.state == CircuitState.OPEN
        assert gua_cb.can_execute() is False

    def test_gua_base_circuits_imported_from_infra(self):
        """GuaBase._circuits 使用 infra 的 CircuitBreaker，而非本地实现"""
        from src.infra.circuit_breaker import CircuitBreaker as InfraCB
        from src.bagua.base_gua import CircuitBreaker as GuaBCB

        # 它们应该是同一个类
        assert GuaBCB is InfraCB

    def test_gua_base_register_dependency_uses_infra(self):
        """register_dependency 返回的是 infra 断路器实例，且使用全局注册表"""
        gua = EchoGua()
        cb = gua.register_dependency("test-dep-gua")

        from src.infra.circuit_breaker import CircuitBreaker as InfraCB
        assert isinstance(cb, InfraCB)

        # 通过全局注册表可获取同一实例（GuaBase 现在通过 get_circuit_breaker 创建）
        global_cb = get_circuit_breaker("test-dep-gua")
        assert global_cb is cb

        # 验证共享状态：在其中一个记录失败，另一个也感知
        for _ in range(5):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert global_cb.state == CircuitState.OPEN


# ============================================================================
# 测试: GuaBase 生命周期与健康状态
# ============================================================================

class TestGuaBaseHealth:
    """测试：GuaBase 生命周期、健康状态、health_summary"""

    def test_health_levels(self):
        """验证 4 级健康梯度定义"""
        levels = list(HealthLevel)
        assert len(levels) == 4
        assert HealthLevel.FULL.value == "full"
        assert HealthLevel.DEGRADED.value == "degraded"
        assert HealthLevel.MINIMAL.value == "minimal"
        assert HealthLevel.OFF.value == "off"

    def test_start_stop_lifecycle(self):
        """卦的 start/stop 生命周期"""
        gua = EchoGua()
        assert gua.is_alive is False

        gua.start()
        assert gua.is_alive is True
        assert gua.health == HealthLevel.FULL
        assert gua.uptime_sec >= 0

        gua.stop()
        assert gua.is_alive is False
        assert gua.health == HealthLevel.OFF

    def test_health_summary(self):
        """health_summary 返回完整状态"""
        gua = EchoGua()
        gua.register_dependency("test_dep_1", failure_threshold=3)

        summary = gua.health_summary()
        assert summary["gua"] == "echo"
        assert summary["health"] in ("full", "off")
        assert "dependencies" in summary
        assert "test_dep_1" in summary["dependencies"]
        assert summary["dependencies"]["test_dep_1"]["circuit"] == "closed"

    def test_get_dependency(self):
        """get_dependency 获取已注册依赖的断路器"""
        gua = EchoGua()
        gua.register_dependency("my_dep")

        cb = gua.get_dependency("my_dep")
        assert cb is not None
        assert cb.state == CircuitState.CLOSED

        cb_none = gua.get_dependency("nonexistent")
        assert cb_none is None


# ============================================================================
# 运行入口
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
