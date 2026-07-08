#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
base_gua.py — 八卦基类 · 伏羲 v2.1 重构

GuaBase 是所有八卦模块的抽象基类，提供：
  - 4 级健康梯度：FULL / DEGRADED / MINIMAL / OFF
  - 每个外部依赖独立的断路器（CircuitState）
  - 降级矩阵：condition_fn + FallbackAction
  - 定时恢复探活（_recovery_loop）
  - 统一的 execute(params) 接口
  - 健康上报方法 health_summary()

设计原则：
  - 无器官层(organs/)依赖
  - 接口极简，每个卦只暴露一个类
  - 完整 type hints 与 docstring
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

from src.bagua.intent_bus import (
    Trigrams,
    GuaHandler,
    Signal,
    IntentResult,
    IntentBus,
    DispatchStatus,
    get_intent_bus,
)

# 统一断路器：从 infra 导入，用于 GuaBase._circuits 和 IntentBus._get_circuit_breaker
from src.infra.circuit_breaker import (
    CircuitState,
    CircuitBreaker,
    DependencyStatus,
)

logger = logging.getLogger("bagua.base_gua")


# ============================================================================
# 枚举定义
# ============================================================================


class HealthLevel(Enum):
    """4 级健康梯度

    FULL:       全功能正常，所有依赖健康
    DEGRADED:   降级运行，部分依赖不可用但核心功能仍可工作
    MINIMAL:    最低限度运行，仅保留容错/兜底逻辑
    OFF:        完全关闭，不可用
    """

    FULL = "full"
    DEGRADED = "degraded"
    MINIMAL = "minimal"
    OFF = "off"


# ============================================================================
# 数据结构
# ============================================================================


@dataclass
class FallbackAction:
    """降级动作

    Attributes:
        name:         降级动作名称（用于日志/上报）
        handler:      降级执行函数，接收原 params 返回替代结果
        description:  可读描述
    """

    name: str
    handler: Callable[[Dict[str, Any]], Any]
    description: str = ""


@dataclass
class DegradationRule:
    """降级规则

    描述：当 condition_fn 返回 True 时触发降级，执行 fallback。

    Attributes:
        name:           规则名称
        condition_fn:   触发条件函数，返回 True 表示应降级
        fallback:       降级动作
        priority:       优先级（数值越小越优先匹配）
    """

    name: str
    condition_fn: Callable[[], bool]
    fallback: FallbackAction
    priority: int = 0


# ============================================================================
# GuaBase — 八卦基类
# ============================================================================


class GuaBase(ABC, GuaHandler):
    """八卦基类 — 所有八卦模块的抽象父类

    继承自 ABC（抽象基类）和 GuaHandler（IntentBus 卦处理器接口），
    确保每一个卦都可以注册到 IntentBus 并通过 handle_signal() 接收调度。

    每个卦（乾、坤、震、巽、坎、离、艮、兑）继承此类，
    重写 _setup_degradation_rules() 和 _execute_core() 实现具体逻辑。

    Usage::

        class QianGua(GuaBase):
            def _setup_degradation_rules(self) -> None:
                self.add_rule(...)

            def _execute_core(self, params: Dict[str, Any]) -> Any:
                # 核心业务逻辑
                ...

        gua = QianGua()
        gua.start()
        result = gua.execute({"query": "test"})
        logger.info(gua.health_summary())
        gua.stop()
    """

    # ========================================================================
    # 类级别常量（子类可覆盖）
    # ========================================================================

    GUA_NAME: str = "base"
    GUA_EMOJI: str = "◉"
    GUA_DESCRIPTION: str = "八卦基类"

    # 恢复探活间隔（秒），子类可按需调整
    RECOVERY_LOOP_INTERVAL: float = 15.0

    # 八卦枚举映射：子类 GUA_NAME → Trigrams 枚举
    _TRIGRAM_MAP: Dict[str, Trigrams] = {
        "乾": Trigrams.QIAN,              # qian.py
        "kun": Trigrams.KUN,              # kun.py
        "zhen": Trigrams.ZHEN,            # zhen.py
        "xun": Trigrams.XUN,              # xun.py
        "kan": Trigrams.KAN,              # kan.py
        "li": Trigrams.LI,                # li.py
        "gen": Trigrams.GEN,              # gen.py
        "dui": Trigrams.DUI,              # dui.py
        "中宫": Trigrams.ZHONG_GONG,       # evolution/evolution_gua.py — 第九宫
    }

    def __init__(self, intent_bus: Optional[IntentBus] = None) -> None:
        # -- 初始化 GuaHandler 父类 --
        trigram = self._TRIGRAM_MAP.get(self.GUA_NAME, Trigrams.QIAN)
        GuaHandler.__init__(self, name=self.GUA_NAME, trigram=trigram)

        self._born_at: float = time.time()
        self._alive: bool = False

        # -- trigram 属性（对齐 IntentBus.register_gua 的 GuaHandler 接口）--
        self.trigram: Trigrams = trigram

        # -- IntentBus 引用（用于 register_to_bus()）--
        self._intent_bus: IntentBus = intent_bus or get_intent_bus()

        # -- 健康状态 --
        self._health: HealthLevel = HealthLevel.FULL

        # -- 断路器注册表 {dependency_name: CircuitBreaker} --
        self._circuits: Dict[str, CircuitBreaker] = {}

        # -- 降级矩阵 [(priority, DegradationRule), ...] --
        self._degradation_rules: List[Tuple[int, DegradationRule]] = []

        # -- 恢复探活任务 --
        self._recovery_task: Optional[asyncio.Task[None]] = None

        # 子类初始化钩子
        self._setup_dependencies()
        self._setup_degradation_rules()

    # ========================================================================
    # 子类必须重写的方法
    # ========================================================================

    @abstractmethod
    def _setup_degradation_rules(self) -> None:
        """子类：在此定义降级规则

        调用 self.add_rule(...) 逐条注册。
        """
        ...

    @abstractmethod
    def _execute_core(self, params: Dict[str, Any]) -> Any:
        """子类：核心业务逻辑

        Args:
            params: 调用参数（各卦自定义）

        Returns:
            业务结果（类型由各卦定义）

        Raises:
            可抛任意异常，由 execute() 外层统一处理降级。
        """
        ...

    # ========================================================================
    # 依赖注册（子类可选覆盖）
    # ========================================================================

    def _setup_dependencies(self) -> None:
        """子类可覆盖：注册外部依赖及其断路器参数

        示例::

            self.register_dependency("llm", failure_threshold=3)
            self.register_dependency("vectordb", failure_threshold=5)
        """
        pass

    # ========================================================================
    # 公共 API
    # ========================================================================

    def register_dependency(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ) -> CircuitBreaker:
        """注册一个外部依赖并创建其专属断路器

        使用全局断路器注册表（src.infra.circuit_breaker.get_circuit_breaker），
        确保 IntentBus dispatch 失败会影响 GuaBase 的子卦断路器状态。

        Args:
            name:                 依赖名称
            failure_threshold:    失败阈值
            recovery_timeout:     恢复超时秒数
            half_open_max_calls:  半开探测请求数

        Returns:
            CircuitBreaker 实例（来自全局注册表）
        """
        if name in self._circuits:
            logger.debug("依赖 [%s] 已注册，跳过", name)
            return self._circuits[name]

        # 使用全局注册表，与 IntentBus 共享断路器实例
        from src.infra.circuit_breaker import get_circuit_breaker as get_cb
        cb = get_cb(
            name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_max_calls=half_open_max_calls,
        )
        self._circuits[name] = cb
        logger.info(
            "[%s] 注册依赖 %s (breaker_threshold=%d, timeout=%.1fs)",
            self.GUA_NAME, name, failure_threshold, recovery_timeout,
        )
        return cb

    def add_rule(self, rule: DegradationRule) -> None:
        """注册一条降级规则

        规则按 priority 排序，数值越小越优先匹配。
        """
        self._degradation_rules.append((rule.priority, rule))
        self._degradation_rules.sort(key=lambda x: x[0])
        logger.debug(
            "[%s] 注册降级规则: %s (priority=%d)",
            self.GUA_NAME, rule.name, rule.priority,
        )

    def execute(self, params: Dict[str, Any]) -> Any:
        """统一的执行入口

        流程：
          1. 走降级矩阵，按 priority 依次匹配 condition_fn
          2. 命中降级规则 → 执行 FallbackAction
          3. 无降级命中 → 执行 _execute_core()
          4. 核心逻辑异常时 → 再次遍历降级矩阵兜底

        Args:
            params: 调用参数

        Returns:
            执行结果（或降级结果）

        Raises:
            RuntimeError: 当健康状态为 OFF 且无可用降级时
        """
        if self._health == HealthLevel.OFF:
            # 完全关闭时也尝试走降级矩阵兜底
            for _, rule in self._degradation_rules:
                if rule.condition_fn():
                    logger.warning(
                        "[%s] OFF 状态下命中降级规则: %s",
                        self.GUA_NAME, rule.name,
                    )
                    return rule.fallback.handler(params)
            raise RuntimeError(
                f"[{self.GUA_NAME}] 健康状态为 OFF，且无可用降级规则"
            )

        # 常规降级检查
        for _, rule in self._degradation_rules:
            if rule.condition_fn():
                self._health = HealthLevel.DEGRADED
                logger.warning(
                    "[%s] 触发降级规则: %s → %s",
                    self.GUA_NAME, rule.name, rule.fallback.name,
                )
                return rule.fallback.handler(params)

        # 正常执行
        try:
            result = self._execute_core(params)
            # 成功 → 更新健康状态
            if self._health != HealthLevel.FULL:
                self._health = HealthLevel.FULL
                logger.info("[%s] 健康状态恢复 → FULL", self.GUA_NAME)
            return result
        except Exception as exc:
            logger.error(
                "[%s] 核心执行异常: %s", self.GUA_NAME, exc, exc_info=True
            )
            # 异常后再次走降级矩阵
            for _, rule in self._degradation_rules:
                if rule.condition_fn():
                    self._health = HealthLevel.MINIMAL
                    logger.warning(
                        "[%s] 异常后命中降级规则: %s",
                        self.GUA_NAME, rule.name,
                    )
                    return rule.fallback.handler(params)
            raise

    # ========================================================================
    # IntentBus 集成（GuaHandler 接口实现）
    # ========================================================================

    def handle_signal(self, signal: Signal) -> IntentResult:
        """处理 IntentBus 派发的信号

        实现 GuaHandler 接口。默认行为：调用 self.execute(signal.payload)
        并将结果封装为 IntentResult。

        各卦可重写此方法以实现自定义的信号处理逻辑。

        Args:
            signal: IntentBus 派发的 Signal 对象

        Returns:
            IntentResult 包含执行结果
        """
        start = time.time()
        try:
            result = self.execute(signal.payload)
            return IntentResult(
                status=DispatchStatus.OK,
                payload={"result": result} if not isinstance(result, dict) else result,
                latency_ms=(time.time() - start) * 1000,
            )
        except Exception as exc:
            logger.error(
                "[%s] handle_signal 异常: %s", self.GUA_NAME, exc, exc_info=True
            )
            return IntentResult(
                status=DispatchStatus.UNKNOWN_ERROR,
                error_message=str(exc),
                latency_ms=(time.time() - start) * 1000,
            )

    def register_to_bus(self, name: Optional[str] = None) -> None:
        """将本卦注册到 IntentBus

        注册后，IntentBus.dispatch() 可以将信号路由到本卦的 handle_signal()。

        典型用法：在子类的 start() 方法中调用。

        Args:
            name: 注册名称，默认使用 self.GUA_NAME。
                  注意：乾卦的 GUA_NAME="乾" 对应 IntentBus 的 "乾"，
                  其他卦使用英文名（如 "kun"）与对应的 Trigrams 枚举一致。
        """
        register_name = name or self.GUA_NAME
        try:
            self._intent_bus.register_gua(register_name, self)
            logger.info(
                "[%s] 已注册到 IntentBus (name=%s, trigram=%s)",
                self.GUA_NAME, register_name, self.trigram.value,
            )
        except Exception as exc:
            logger.error(
                "[%s] 注册到 IntentBus 失败: %s", self.GUA_NAME, exc
            )
            raise

    def unregister_from_bus(self, name: Optional[str] = None) -> bool:
        """从 IntentBus 反注册本卦

        Args:
            name: 注册名称，默认使用 self.GUA_NAME

        Returns:
            True 表示成功反注册
        """
        register_name = name or self.GUA_NAME
        return self._intent_bus.unregister_gua(register_name)

    def health_check(self) -> Dict[str, Any]:
        """健康检查 — 返回标准化健康状态

        所有卦统一调用此方法用于运行时健康检查。
        协议：
          - healthy:    全功能正常，所有依赖健康
          - degraded:   降级运行（部分依赖不可用但核心功能可用）
          - unavailable: 卦未启动 / 完全不可用

        Returns:
            {
                "name": "qian",
                "emoji": "☰",
                "status": "healthy" | "degraded" | "unavailable",
                "health_level": "full" | "degraded" | "minimal" | "off",
                "uptime_sec": 3600.0,
                "is_alive": true,
                "dependencies": {
                    "llm": {"circuit": "closed", "degraded": false},
                    ...
                }
            }
        """
        if not self._alive:
            return {
                "name": self.GUA_NAME,
                "emoji": self.GUA_EMOJI,
                "status": "unavailable",
                "health_level": self._health.value,
                "uptime_sec": round(time.time() - self._born_at, 1),
                "is_alive": False,
                "dependencies": {},
            }

        # 确定状态
        if self._health == HealthLevel.FULL:
            status = "healthy"
        elif self._health == HealthLevel.DEGRADED:
            status = "degraded"
        else:
            status = "unavailable"

        deps: Dict[str, Dict[str, Any]] = {}
        for name, cb in self._circuits.items():
            s = cb.status
            deps[name] = {
                "circuit": s.circuit_state.value,
                "degraded": s.degraded,
            }

        return {
            "name": self.GUA_NAME,
            "emoji": self.GUA_EMOJI,
            "status": status,
            "health_level": self._health.value,
            "uptime_sec": round(time.time() - self._born_at, 1),
            "is_alive": True,
            "dependencies": deps,
        }

    def health_summary(self) -> Dict[str, Any]:
        """生成健康状态摘要

        Returns:
            包含 gua 级别状态和各依赖断路器状态的字典::

                {
                    "gua": "qian",
                    "emoji": "☰",
                    "health": "full",
                    "uptime_sec": 3600.0,
                    "dependencies": {
                        "llm": {"circuit": "closed", "failures": 0, "degraded": false},
                        ...
                    }
                }
        """
        deps: Dict[str, Dict[str, Any]] = {}
        for name, cb in self._circuits.items():
            s = cb.status
            deps[name] = {
                "circuit": s.circuit_state.value,
                "failures": s.failure_count,
                "last_ok_sec": s.last_ok,
                "degraded": s.degraded,
            }

        return {
            "gua": self.GUA_NAME,
            "emoji": self.GUA_EMOJI,
            "health": self._health.value,
            "uptime_sec": round(time.time() - self._born_at, 1),
            "dependencies": deps,
        }

    def get_dependency(self, name: str) -> Optional[CircuitBreaker]:
        """获取指定依赖的断路器

        Args:
            name: 依赖名

        Returns:
            CircuitBreaker 或 None
        """
        return self._circuits.get(name)

    # ========================================================================
    # 生命周期
    # ========================================================================

    def start(self) -> None:
        """启动卦模块：开始恢复探活循环 + 注册到 IntentBus"""
        if self._alive:
            logger.warning("[%s] 已启动，跳过", self.GUA_NAME)
            return

        self._alive = True
        self._health = HealthLevel.FULL
        logger.info(
            "%s [%s] 启动 — %s",
            self.GUA_EMOJI, self.GUA_NAME, self.GUA_DESCRIPTION,
        )

        # 注册到 IntentBus（确保 dispatch() 能找到本卦）
        try:
            self.register_to_bus()
        except Exception as exc:
            logger.error("[%s] IntentBus 注册失败: %s", self.GUA_NAME, exc)

        # 启动异步探活循环
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self._recovery_task = asyncio.ensure_future(self._recovery_loop())
            else:
                self._recovery_task = loop.create_task(self._recovery_loop())
        except RuntimeError:
            # 无事件循环时（测试/同步环境），延迟启动
            logger.debug("[%s] 无事件循环，探活延迟启动", self.GUA_NAME)

    def stop(self) -> None:
        """停止卦模块：取消探活任务，标记为 OFF"""
        if not self._alive:
            return

        self._alive = False
        self._health = HealthLevel.OFF

        # 从 IntentBus 反注册
        try:
            self.unregister_from_bus()
        except Exception as exc:
            logger.debug("[%s] IntentBus 反注册异常: %s", self.GUA_NAME, exc)

        if self._recovery_task is not None:
            self._recovery_task.cancel()
            self._recovery_task = None

        logger.info(
            "%s [%s] 已停止 — uptime=%.0fs",
            self.GUA_EMOJI, self.GUA_NAME,
            time.time() - self._born_at,
        )

    # ========================================================================
    # 定时恢复探活
    # ========================================================================

    async def _recovery_loop(self) -> None:
        """定时探测所有断路器的恢复情况

        对 HALF_OPEN / OPEN 状态的断路器执行探测，
        成功后自动恢复。
        子类可覆盖 _probe_dependency() 实现自定义探测逻辑。
        """
        logger.debug("[%s] 恢复探活循环启动 (interval=%.1fs)", self.GUA_NAME, self.RECOVERY_LOOP_INTERVAL)

        while self._alive:
            try:
                await self._probe_all_dependencies()
            except asyncio.CancelledError:
                logger.debug("[%s] 探活循环已取消", self.GUA_NAME)
                break
            except Exception as exc:
                logger.error("[%s] 探活异常: %s", self.GUA_NAME, exc, exc_info=True)

            await asyncio.sleep(self.RECOVERY_LOOP_INTERVAL)

    async def _probe_all_dependencies(self) -> None:
        """批量探测所有依赖"""
        for name, cb in self._circuits.items():
            if cb.state in (CircuitState.OPEN, CircuitState.HALF_OPEN):
                try:
                    ok = await self._probe_dependency(name)
                    if ok:
                        cb.record_success()
                    else:
                        cb.record_failure()
                except Exception:
                    cb.record_failure()
                    logger.debug("[%s] 依赖 [%s] 探活失败", self.GUA_NAME, name)

    async def _probe_dependency(self, dependency_name: str) -> bool:
        """子类可覆盖：自定义依赖探测逻辑

        默认返回 True（无操作），子类应实现真正的健康检查。

        Args:
            dependency_name: 依赖名

        Returns:
            True 表示依赖可用
        """
        return True

    # ========================================================================
    # 辅助方法
    # ========================================================================

    @property
    def health(self) -> HealthLevel:
        """当前健康等级"""
        return self._health

    @property
    def is_alive(self) -> bool:
        """是否运行中"""
        return self._alive

    @property
    def uptime_sec(self) -> float:
        """运行时长（秒）"""
        return time.time() - self._born_at
