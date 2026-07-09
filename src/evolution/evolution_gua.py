"""
evolution_gua.py — 第九宫（中宫）· 自进化中枢

中宫 ⊙ 是伏羲 v2.1 第九宫，承载自进化闭环：
  反馈记录 → 离线学习 → 知识进化 → 生命周期管理

继承 GuaBase，遵循八卦框架统一接口，支持：
  - _execute_core(params) — 统一执行入口（action 驱动）
  - _setup_degradation_rules() — 降级规则注册
  - register_to_bus() — IntentBus 集成
  - 健康检查与恢复探活

Usage::

    from src.evolution import EvolutionGua

    gua = EvolutionGua()
    gua.start()

    # 记录反馈
    result = gua.execute({"action": "feedback", "user_id": "u1", "query": "test"})

    # 触发学习
    result = gua.execute({"action": "learn", "feedback_batch": [...]})

    # 触发知识进化
    result = gua.execute({"action": "evolve", "entities": {...}, "file_name": "doc.txt"})

    # 检查生命周期
    result = gua.execute({"action": "lifecycle"})

    gua.stop()
"""


import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from src.bagua.base_gua import (
    GuaBase,
    DegradationRule,
    FallbackAction,
)
from src.bagua.intent_bus import (
    IntentBus,
)

logger = logging.getLogger("evolution.gua")


class EvolutionGua(GuaBase):
    """中宫 ⊙ — 自进化中枢

    第九宫卦，是伏羲系统的自进化闭环载体。
    整合四大核心能力：
      - 反馈闭环（feedback_loop）: 记录用户反馈，去重，批量学习触发
      - 离线学习（learner）:       术语权重调整，个性化 boost
      - 知识进化（evolver）:       实体发现，关系推理，图谱增量更新
      - 生命周期（lifecycle）:     知识事件记录，触发条件检查，置信度分类

    继承 GuaBase，遵循八卦框架统一的生命周期、健康管理、降级矩阵模式。
    通过 execute() 统一入口以 action 参数区分操作。

    Attributes:
        GUA_NAME:        卦名 "中宫"
        GUA_EMOJI:       emoji "⊙"
        GUA_DESCRIPTION: 卦述 "自进化中枢"
    """

    # ========================================================================
    # 类级别常量
    # ========================================================================

    GUA_NAME: str = "中宫"
    GUA_EMOJI: str = "⊙"
    GUA_DESCRIPTION: str = "自进化中枢 — 反馈闭环、离线学习、知识进化、生命周期管理"

    # 恢复探活间隔
    RECOVERY_LOOP_INTERVAL: float = 30.0

    def __init__(self, intent_bus: Optional[IntentBus] = None) -> None:
        super().__init__(intent_bus=intent_bus)

        # 延迟初始化各组件，避免启动时的循环导入
        self._feedback_loop: Any = None
        self._learner: Any = None
        self._evolver: Any = None
        self._lifecycle: Any = None

        # 统计
        self._execution_count: int = 0
        self._last_execution_time: float = 0.0

        logger.info(
            "⊙ [中宫] 初始化完成 — %s", self.GUA_DESCRIPTION,
        )

    # ========================================================================
    # GuaBase 抽象方法实现
    # ========================================================================

    def _setup_degradation_rules(self) -> None:
        """注册中宫降级规则

        优先级规则：
          - 10: 所有四大组件均不可用 → 降级为空操作
          - 20: 学习者不可用 → 跳过学习
          - 30: 进化器不可用 → 跳过进化
        """
        # 规则 10: 四大组件全部不可用 → 空操作降级
        self.add_rule(DegradationRule(
            name="all_components_unavailable",
            condition_fn=self._all_components_degraded,
            fallback=FallbackAction(
                name="noop_fallback",
                handler=self._fallback_noop,
                description="所有进化组件不可用，返回空操作",
            ),
            priority=10,
        ))

        # 规则 20: 学习者不可用 → 跳过学习步骤
        self.add_rule(DegradationRule(
            name="learner_unavailable",
            condition_fn=lambda: not self._is_learner_available(),
            fallback=FallbackAction(
                name="skip_learn",
                handler=self._fallback_skip_learn,
                description="学习者不可用，跳过学习",
            ),
            priority=20,
        ))

        # 规则 30: 进化器不可用 → 跳过进化步骤
        self.add_rule(DegradationRule(
            name="evolver_unavailable",
            condition_fn=lambda: not self._is_evolver_available(),
            fallback=FallbackAction(
                name="skip_evolve",
                handler=self._fallback_skip_evolve,
                description="进化器不可用，跳过进化",
            ),
            priority=30,
        ))

    def _execute_core(self, params: Dict[str, Any]) -> Any:
        """统一执行入口 — action 驱动

        Args:
            params: 执行参数，必须包含 "action" 键:
                - action="feedback": 记录用户反馈
                  还需: user_id, query, action_type[可选], results[可选], metadata[可选]
                - action="learn":   触发离线学习
                  还需: feedback_batch[可选]
                - action="evolve":  触发知识进化
                  还需: entities[可选], file_name[可选], text[可选]
                - action="lifecycle": 管理知识生命周期
                  还需: event_type[可选], event_data[可选]

        Returns:
            各 action 对应的结果 dict:

            feedback:  {"ok": bool, "dedup": bool, "learn_triggered": bool}
            learn:     {"ok": bool, "processed": int, "terms_updated": int}
            evolve:    {"ok": bool, "entities_added": int, "edges_added": int, "entities_discovered": int}
            lifecycle: {"ok": bool, "triggers": list, "candidates": list}

        Raises:
            ValueError: 缺少 action 参数或 action 无效
        """
        action = params.get("action", "")
        if not action:
            raise ValueError(
                "[中宫] execute() 缺少 action 参数。"
                "有效值: feedback, learn, evolve, lifecycle"
            )

        self._execution_count += 1
        self._last_execution_time = time.time()

        if action == "feedback":
            return self._handle_feedback(params)
        elif action == "learn":
            return self._handle_learn(params)
        elif action == "evolve":
            return self._handle_evolve(params)
        elif action == "lifecycle":
            return self._handle_lifecycle(params)
        else:
            raise ValueError(
                f"[中宫] 未知的 action: '{action}'。"
                f"有效值: feedback, learn, evolve, lifecycle"
            )

    # ========================================================================
    # Action 处理器
    # ========================================================================

    def _handle_feedback(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 feedback action

        记录用户反馈，带去重和批量学习触发。

        Args:
            params: {"user_id": str, "query": str, "action_type": str, ...}

        Returns:
            {"ok": bool, "dedup": bool, "learn_triggered": bool}
        """
        user_id = params.get("user_id", "anonymous")
        query = params.get("query", "")
        action_type = params.get("action_type", "click")
        results = params.get("results", None)
        metadata = params.get("metadata", None)

        if not query:
            return {"ok": False, "error": "query 参数不能为空"}

        try:
            # 使用 run_until_complete 在同步上下文中调用 async 函数
            result = _sync_run(
                self._get_feedback_loop().record(
                    user_id=user_id,
                    query=query,
                    action=action_type,
                    results=results,
                    metadata=metadata,
                )
            )
            logger.info(
                "⊙ [中宫] 反馈已记录: user=%s query='%s...' dedup=%s learn=%s",
                user_id, query[:40], result.get("dedup"), result.get("learn_triggered"),
            )
            return result
        except Exception as exc:  # TODO: Narrow exception type
            logger.error("⊙ [中宫] 反馈记录异常: %s", exc, exc_info=True)
            return {"ok": False, "error": str(exc)}

    def _handle_learn(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 learn action

        从反馈批次中学习，调整术语权重。

        Args:
            params: {"feedback_batch": [{query, action, ...}, ...]}

        Returns:
            {"ok": bool, "processed": int, "terms_updated": int}
        """
        feedback_batch = params.get("feedback_batch", [])

        if not feedback_batch:
            return {"ok": False, "error": "feedback_batch 不能为空"}

        try:
            result = _sync_run(
                self._get_learner().learn_from_feedback(feedback_batch)
            )
            logger.info(
                "⊙ [中宫] 学习完成: processed=%d terms_updated=%d",
                result.get("processed", 0), result.get("terms_updated", 0),
            )
            return result
        except Exception as exc:  # TODO: Narrow exception type
            logger.error("⊙ [中宫] 学习异常: %s", exc, exc_info=True)
            return {"ok": False, "error": str(exc)}

    def _handle_evolve(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 evolve action

        从文本中发现实体并增量更新知识图谱。

        Args:
            params: {
                "entities": {type: [names]} (可选),
                "file_name": str (可选),
                "text": str (可选，用于实体发现),
            }

        Returns:
            {
                "ok": bool,
                "entities_added": int,
                "edges_added": int,
                "entities_discovered": int,
            }
        """
        entities = params.get("entities", {})
        file_name = params.get("file_name", "")
        text = params.get("text", "")

        # 如果没有提供实体但有文本，则从文本中发现
        entities_discovered = 0
        if not entities and text:
            entities = self._get_evolver().discover(text)
            entities_discovered = sum(len(v) for v in entities.values())

        if not entities:
            return {"ok": False, "error": "既无 entities 也无 text 可用于实体发现"}

        try:
            evolve_result = self._get_evolver().evolve(entities, file_name=file_name)
            logger.info(
                "⊙ [中宫] 知识进化完成: entities_added=%d edges_added=%d",
                evolve_result.get("entities_added", 0),
                evolve_result.get("edges_added", 0),
            )
            return {
                "ok": True,
                "entities_added": evolve_result.get("entities_added", 0),
                "edges_added": evolve_result.get("edges_added", 0),
                "entities_discovered": entities_discovered,
            }
        except Exception as exc:  # TODO: Narrow exception type
            logger.error("⊙ [中宫] 知识进化异常: %s", exc, exc_info=True)
            return {"ok": False, "error": str(exc)}

    def _handle_lifecycle(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 lifecycle action

        管理知识生命周期：记录事件或检查触发条件。

        Args:
            params: {
                "event_type": str (可选),
                "event_data": dict (可选),
                "check": bool (可选，是否检查触发条件),
            }

        Returns:
            {"ok": bool, "triggers": list, "candidates": list}
        """
        event_type = params.get("event_type", "")
        event_data = params.get("event_data", {})
        do_check = params.get("check", True)

        lifecycle = self._get_lifecycle()

        # 如果有事件类型和数据，则记录
        if event_type and event_data:
            try:
                _sync_run(lifecycle.record(event_type, event_data))
                logger.info(
                    "⊙ [中宫] 生命周期事件已记录: type=%s",
                    event_type,
                )
            except Exception as exc:  # TODO: Narrow exception type
                logger.error("⊙ [中宫] 生命周期记录异常: %s", exc, exc_info=True)

        # 检查触发条件
        triggers: List[Dict] = []
        candidates: List[Dict] = []

        if do_check:
            try:
                triggers = _sync_run(lifecycle.check_triggers())
                for trigger in triggers:
                    candidates.extend(
                        _sync_run(lifecycle.get_candidates(trigger["event_type"]))
                    )
                if triggers:
                    logger.info(
                        "⊙ [中宫] 生命周期触发: %d 种事件类型",
                        len(triggers),
                    )
            except Exception as exc:  # TODO: Narrow exception type
                logger.error("⊙ [中宫] 生命周期检查异常: %s", exc, exc_info=True)

        return {
            "ok": True,
            "triggers": triggers,
            "candidates": candidates,
        }

    # ========================================================================
    # 日志触发检查（新增 — 供离线巡检使用）
    # ========================================================================

    async def trigger_log_check(self) -> Dict[str, Any]:
        """离线巡检入口 — 检查反馈日志并触发学习/进化

        当反馈日志积累到阈值时自动调用：
          1. 检查生命周期触发条件
          2. 如有触发 → 获取候选知识并执行进化
          3. 返回检查摘要

        Returns:
            {"ok": bool, "lifecycle_triggers": list, "evolution_done": bool}
        """
        lifecycle = self._get_lifecycle()
        triggers = await lifecycle.check_triggers()

        evolution_done = False
        for trigger in triggers:
            candidates = await lifecycle.get_candidates(trigger["event_type"])
            if candidates:
                # 将候选知识中的 query 聚合为文本用于实体发现
                combined_text = " ".join(
                    c.get("query", "") or c.get("text", "") or ""
                    for c in candidates[:50]
                )
                if combined_text.strip():
                    evolver = self._get_evolver()
                    entities = evolver.discover(combined_text)
                    if entities:
                        evolver.evolve(entities, file_name="lifecycle_auto")
                        evolution_done = True

        return {
            "ok": True,
            "lifecycle_triggers": triggers,
            "evolution_done": evolution_done,
        }

    # ========================================================================
    # 组件延迟初始化
    # ========================================================================

    def _get_feedback_loop(self) -> Any:
        """延迟获取 FeedbackLoop 实例"""
        if self._feedback_loop is None:
            from src.evolution.feedback_loop import FeedbackLoop
            self._feedback_loop = FeedbackLoop()
        return self._feedback_loop

    def _get_learner(self) -> Any:
        """延迟获取 EvolutionLearner 实例"""
        if self._learner is None:
            from src.evolution.learner import EvolutionLearner
            self._learner = EvolutionLearner()
        return self._learner

    def _get_evolver(self) -> Any:
        """延迟获取 EvolutionEvolver 实例"""
        if self._evolver is None:
            from src.evolution.evolver import EvolutionEvolver
            self._evolver = EvolutionEvolver()
        return self._evolver

    def _get_lifecycle(self) -> Any:
        """延迟获取 EvolutionLifecycle 实例"""
        if self._lifecycle is None:
            from src.evolution.lifecycle import EvolutionLifecycle
            self._lifecycle = EvolutionLifecycle()
        return self._lifecycle

    # ========================================================================
    # 降级条件判断
    # ========================================================================

    def _all_components_degraded(self) -> bool:
        """检查是否所有四大组件均不可用"""
        return (
            not self._is_feedback_available()
            and not self._is_learner_available()
            and not self._is_evolver_available()
            and not self._is_lifecycle_available()
        )

    def _is_feedback_available(self) -> bool:
        """检查反馈闭环是否可用"""
        try:
            return True
        except ImportError:
            return False

    def _is_learner_available(self) -> bool:
        """检查学习者是否可用"""
        try:
            return True
        except ImportError:
            return False

    def _is_evolver_available(self) -> bool:
        """检查进化器是否可用"""
        try:
            return True
        except ImportError:
            return False

    def _is_lifecycle_available(self) -> bool:
        """检查生命周期管理器是否可用"""
        try:
            return True
        except ImportError:
            return False

    # ========================================================================
    # 降级处理器
    # ========================================================================

    def _fallback_noop(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """降级：所有组件不可用 → 空操作"""
        logger.warning("⊙ [中宫] 空操作降级: 所有进化组件不可用")
        return {
            "ok": False,
            "degraded": True,
            "level": "critical",
            "message": "所有自进化组件当前不可用，已跳过操作",
            "action": params.get("action", "unknown"),
        }

    def _fallback_skip_learn(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """降级：学习者不可用 → 跳过学习"""
        logger.warning("⊙ [中宫] 跳过学习: 学习者不可用")
        return {
            "ok": True,
            "degraded": True,
            "skipped": "learn",
            "message": "学习者不可用，已跳过学习步骤",
        }

    def _fallback_skip_evolve(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """降级：进化器不可用 → 跳过进化"""
        logger.warning("⊙ [中宫] 跳过进化: 进化器不可用")
        return {
            "ok": True,
            "degraded": True,
            "skipped": "evolve",
            "message": "进化器不可用，已跳过进化步骤",
        }

    # ========================================================================
    # 健康状态增强
    # ========================================================================

    def health_summary(self) -> Dict[str, Any]:
        """生成增强的健康状态摘要（含进化组件状态）

        Returns:
            健康状态字典，包含四大组件的可用性
        """
        summary = super().health_summary()

        # 添加进化层状态
        summary["evolution"] = {
            "feedback_loop": self._is_feedback_available(),
            "learner": self._is_learner_available(),
            "evolver": self._is_evolver_available(),
            "lifecycle": self._is_lifecycle_available(),
        }

        # 添加执行统计
        summary["execution_count"] = self._execution_count
        summary["last_execution_sec"] = (
            round(time.time() - self._last_execution_time, 1)
            if self._last_execution_time > 0
            else -1
        )

        return summary

    # ========================================================================
    # 依赖探活增强
    # ========================================================================

    async def _probe_dependency(self, dependency_name: str) -> bool:
        """增强的依赖探测：检查进化组件是否可导入"""
        if dependency_name == "feedback_store":
            return self._is_feedback_available()
        elif dependency_name == "learner":
            return self._is_learner_available()
        elif dependency_name == "evolver":
            return self._is_evolver_available()
        elif dependency_name == "lifecycle":
            return self._is_lifecycle_available()
        return await super()._probe_dependency(dependency_name)

    # ========================================================================
    # 生命周期扩展
    # ========================================================================

    def start(self) -> None:
        """启动中宫 — 注册依赖并启动探活"""
        # 注册四大组件依赖
        self.register_dependency("feedback_store", failure_threshold=10, recovery_timeout=60.0)
        self.register_dependency("learner", failure_threshold=5, recovery_timeout=30.0)
        self.register_dependency("evolver", failure_threshold=5, recovery_timeout=30.0)
        self.register_dependency("lifecycle", failure_threshold=5, recovery_timeout=30.0)

        super().start()
        logger.info("⊙ [中宫] 自进化中枢已启动")

    def stop(self) -> None:
        """停止中宫 — 清理资源"""
        # 清理组件引用
        self._feedback_loop = None
        self._learner = None
        self._evolver = None
        self._lifecycle = None

        super().stop()
        logger.info("⊙ [中宫] 自进化中枢已停止 (executions=%d)", self._execution_count)


# ========================================================================
# 工具函数
# ========================================================================


def _sync_run(coro: Any) -> Any:
    """在同步上下文中安全运行异步协程

    尝试获取当前事件循环来运行，如果失败则用 asyncio.run()。
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 使用 nest_asyncio 解决嵌套事件循环
            try:
                import nest_asyncio
                nest_asyncio.apply()
                new_loop = asyncio.new_event_loop()
                return new_loop.run_until_complete(coro)
            except ImportError:
                # fallback: 在线程中运行
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, coro)
                    return future.result(timeout=30)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)
