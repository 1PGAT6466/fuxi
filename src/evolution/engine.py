"""
engine.py — 进化引擎核心（第九宫 · 中宫）

EvolutionEngine 是自进化闭环的核心调度引擎，协调四大组件：
  - FeedbackLoop:   反馈记录去重 + 批量学习触发
  - EvolutionLearner: 术语权重调整 + 个性化 boost
  - EvolutionEvolver: 实体发现 + 关系推理 + 图谱增量更新
  - EvolutionLifecycle: 知识生命周期事件记录 + 触发条件检查

提供统一调度接口，支持：
  - 全流程自动进化: run_evolution_cycle()
  - 分步执行:        run_step()
  - 定时巡检:        run_scheduled_check()
  - 健康监控:        health_summary()

设计决策：
  - 所有步骤均为异步，支持并行执行（feedback 独立，learn/evolve 可并发）
  - 三级降级：LLM 不可用 → 规则引擎 → 空操作
  - 统计数据自动聚合，支持监控仪表盘查询

Usage::

    from src.evolution.engine import EvolutionEngine

    engine = EvolutionEngine()

    # 执行完整进化循环
    result = await engine.run_evolution_cycle(
        feedback_batch=[{"query": "VLAN", "action": "like", "user_id": "u1"}],
        text="文档内容...",
    )

    # 查看健康状态
    health = engine.health_summary()

    # 定时巡检
    report = await engine.run_scheduled_check()
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.evolution.evolver import (
    EvolutionEvolver,
    discover_entities_from_text,
    evolve_knowledge_graph,
    get_knowledge_graph_nodes,
    get_knowledge_graph_stats,
)
from src.evolution.feedback_loop import (
    FeedbackLoop,
    get_feedback_loop_stats,
    record_feedback,
)
from src.evolution.learner import (
    EvolutionLearner,
    extract_new_terms,
    get_learner_stats,
    get_personalized_boost,
    learn_from_feedback,
)
from src.evolution.lifecycle import (
    EvolutionLifecycle,
    check_lifecycle_triggers,
    classify_lifecycle_confidence,
    get_lifecycle_candidates,
    record_lifecycle_event,
)

logger = logging.getLogger("evolution.engine")


# ============================================================================
# 数据类型
# ============================================================================


@dataclass
class EvolutionStepResult:
    """单步进化执行结果

    Attributes:
        step_name:      步骤名称
        success:        是否成功
        data:           步骤产出数据
        error:          错误信息（如果失败）
        duration_ms:    执行耗时（毫秒）
        skipped:        是否被跳过
        skip_reason:    跳过原因
    """

    step_name: str
    success: bool = True
    data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    duration_ms: float = 0.0
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class EvolutionCycleResult:
    """完整进化循环结果

    Attributes:
        ok:              整体是否成功
        steps:           各步骤结果列表
        total_duration_ms: 总耗时（毫秒）
        feedback_count:  处理的反馈数量
        entities_discovered: 发现的实体数量
        entities_added:  新增实体数量
        edges_added:     新增关系数量
        terms_updated:   更新的术语数量
        lifecycle_triggers: 生命周期触发事件数
        errors:          错误列表
        timestamp:       执行时间戳
    """

    ok: bool = True
    steps: List[EvolutionStepResult] = field(default_factory=list)
    total_duration_ms: float = 0.0
    feedback_count: int = 0
    entities_discovered: int = 0
    entities_added: int = 0
    edges_added: int = 0
    terms_updated: int = 0
    lifecycle_triggers: int = 0
    errors: List[str] = field(default_factory=list)
    timestamp: str = ""


# ============================================================================
# EvolutionEngine 类
# ============================================================================


class EvolutionEngine:
    """进化引擎 — 自进化闭环核心调度器

    协调四大进化组件完成完整的自进化管线：
      1. 反馈记录 (feedback)    — 记录用户交互反馈
      2. 离线学习 (learn)       — 从反馈中学习术语权重
      3. 知识进化 (evolve)      — 实体发现 + 图谱增量更新
      4. 生命周期 (lifecycle)   — 知识事件管理 + 触发检查

    支持三种运行模式：
      - 全流程: run_evolution_cycle()       — 一次性完整进化
      - 分步:   run_step(step_name, params) — 单独执行某一步
      - 定时:   run_scheduled_check()       — 由 cron 调度的巡检

    特性:
      - 异步并行: learn 和 evolve 可并发执行
      - 降级弹性: 单步失败不影响后续步骤
      - 可观测性: 每步均有耗时统计和错误记录
    """

    def __init__(self) -> None:
        # 延迟初始化组件
        self._feedback_loop: Optional[FeedbackLoop] = None
        self._learner: Optional[EvolutionLearner] = None
        self._evolver: Optional[EvolutionEvolver] = None
        self._lifecycle: Optional[EvolutionLifecycle] = None

        # 统计
        self._cycle_count: int = 0
        self._last_cycle_time: float = 0.0
        self._total_entities_evolved: int = 0
        self._total_feedback_processed: int = 0
        self._total_terms_learned: int = 0

        logger.info("[EvolutionEngine] 进化引擎初始化完成")

    # ========================================================================
    # 组件延迟初始化
    # ========================================================================

    def _get_feedback_loop(self) -> FeedbackLoop:
        if self._feedback_loop is None:
            self._feedback_loop = FeedbackLoop()
        return self._feedback_loop

    def _get_learner(self) -> EvolutionLearner:
        if self._learner is None:
            self._learner = EvolutionLearner()
        return self._learner

    def _get_evolver(self) -> EvolutionEvolver:
        if self._evolver is None:
            self._evolver = EvolutionEvolver()
        return self._evolver

    def _get_lifecycle(self) -> EvolutionLifecycle:
        if self._lifecycle is None:
            self._lifecycle = EvolutionLifecycle()
        return self._lifecycle

    # ========================================================================
    # 主入口：全流程进化
    # ========================================================================

    async def run_evolution_cycle(
        self,
        feedback_batch: Optional[List[Dict[str, Any]]] = None,
        text: str = "",
        file_name: str = "",
        user_id: str = "",
    ) -> EvolutionCycleResult:
        """执行完整的自进化循环

        管线流程：
          1. 反馈记录    — 批量记录用户反馈 (同步)
          2. 离线学习    — 从反馈中学习术语权重 (异步，可与 3 并行)
          3. 知识进化    — 实体发现 + 图谱更新 (异步，可与 2 并行)
          4. 生命周期    — 检查触发条件 + 事件记录 (异步)

        Args:
            feedback_batch: 反馈条目列表，每项含 query/action/user_id
            text:           待分析的文本（用于实体发现）
            file_name:      文本来源文件名
            user_id:        用户标识

        Returns:
            EvolutionCycleResult 完整结果对象
        """
        start_time = time.time()
        self._cycle_count += 1

        result = EvolutionCycleResult(
            steps=[],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        feedback_batch = feedback_batch or []

        # ----------------------------------------------------------------
        # Step 1: 反馈记录
        # ----------------------------------------------------------------
        step1 = await self._run_step_feedback(feedback_batch, user_id)
        result.steps.append(step1)
        if step1.success:
            result.feedback_count = step1.data.get("processed", 0)
            self._total_feedback_processed += result.feedback_count

        # ----------------------------------------------------------------
        # Step 2 & 3: 离线学习 + 知识进化（并行）
        # ----------------------------------------------------------------
        learn_task = None
        evolve_task = None

        # 如果有文本，启动实体发现
        if text.strip():
            evolve_task = asyncio.create_task(self._run_step_evolve(text, file_name))

        # 如果有反馈批次，启动学习
        if feedback_batch:
            learn_task = asyncio.create_task(self._run_step_learn(feedback_batch))

        # 等待并行任务完成
        if learn_task and evolve_task:
            step2, step3 = await asyncio.gather(learn_task, evolve_task)
        elif learn_task:
            step2 = await learn_task
            step3 = EvolutionStepResult(
                step_name="evolve",
                success=True,
                skipped=True,
                skip_reason="无待分析文本",
            )
        elif evolve_task:
            step2 = EvolutionStepResult(
                step_name="learn",
                success=True,
                skipped=True,
                skip_reason="无反馈批次",
            )
            step3 = await evolve_task
        else:
            step2 = EvolutionStepResult(
                step_name="learn",
                success=True,
                skipped=True,
                skip_reason="无待处理数据",
            )
            step3 = EvolutionStepResult(
                step_name="evolve",
                success=True,
                skipped=True,
                skip_reason="无待分析文本",
            )

        result.steps.extend([step2, step3])

        if step2.success:
            result.terms_updated = step2.data.get("terms_updated", 0)
            self._total_terms_learned += result.terms_updated
        if step3.success:
            result.entities_discovered = step3.data.get("entities_discovered", 0)
            result.entities_added = step3.data.get("entities_added", 0)
            result.edges_added = step3.data.get("edges_added", 0)
            self._total_entities_evolved += result.entities_added + result.edges_added

        # ----------------------------------------------------------------
        # Step 4: 生命周期检查
        # ----------------------------------------------------------------
        step4 = await self._run_step_lifecycle()
        result.steps.append(step4)
        if step4.success:
            result.lifecycle_triggers = step4.data.get("trigger_count", 0)

        # ----------------------------------------------------------------
        # 汇总
        # ----------------------------------------------------------------
        result.total_duration_ms = round((time.time() - start_time) * 1000, 1)
        self._last_cycle_time = time.time()

        # 收集错误
        for step in result.steps:
            if step.error:
                result.errors.append(f"[{step.step_name}] {step.error}")
            if not step.success:
                result.ok = False

        logger.info(
            "[EvolutionEngine] 进化循环完成: ok=%s duration=%.0fms " "feedback=%d entities=%d learn=%d triggers=%d",
            result.ok,
            result.total_duration_ms,
            result.feedback_count,
            result.entities_added,
            result.terms_updated,
            result.lifecycle_triggers,
        )

        return result

    # ========================================================================
    # 分步执行
    # ========================================================================

    async def run_step(
        self,
        step_name: str,
        params: Dict[str, Any],
    ) -> EvolutionStepResult:
        """单独执行一个进化步骤

        Args:
            step_name: 步骤名 "feedback" | "learn" | "evolve" | "lifecycle"
            params:    步骤参数

        Returns:
            EvolutionStepResult
        """
        step_map = {
            "feedback": self._run_step_feedback,
            "learn": self._run_step_learn,
            "evolve": self._run_step_evolve_text,
            "lifecycle": self._run_step_lifecycle,
        }

        if step_name not in step_map:
            return EvolutionStepResult(
                step_name=step_name,
                success=False,
                error=f"未知步骤: {step_name}，有效值: {list(step_map.keys())}",
            )

        handler = step_map[step_name]

        if step_name == "feedback":
            return await handler(params.get("feedback_batch", []), params.get("user_id", ""))
        elif step_name == "learn":
            return await handler(params.get("feedback_batch", []))
        elif step_name == "evolve":
            return await handler(params.get("text", ""), params.get("file_name", ""))
        elif step_name == "lifecycle":
            return await handler()
        else:
            return EvolutionStepResult(
                step_name=step_name,
                success=False,
                error="未处理的步骤",
            )

    async def _run_step_feedback(
        self,
        feedback_batch: List[Dict[str, Any]],
        user_id: str = "",
    ) -> EvolutionStepResult:
        """执行反馈记录步骤"""
        step_start = time.time()
        step = EvolutionStepResult(step_name="feedback")

        if not feedback_batch:
            step.skipped = True
            step.skip_reason = "无反馈数据"
            step.duration_ms = round((time.time() - step_start) * 1000, 1)
            return step

        try:
            feedback_loop = self._get_feedback_loop()
            processed = 0
            learn_triggered_count = 0

            for item in feedback_batch:
                fb_user_id = item.get("user_id", user_id)
                query = item.get("query", "")
                action = item.get("action", "click")
                results = item.get("results", None)
                metadata = item.get("metadata", None)

                if not query:
                    continue

                fb_result = await feedback_loop.record(
                    user_id=fb_user_id,
                    query=query,
                    action=action,
                    results=results,
                    metadata=metadata,
                )
                processed += 1
                if fb_result.get("learn_triggered"):
                    learn_triggered_count += 1

            step.success = True
            step.data = {
                "processed": processed,
                "learn_triggered": learn_triggered_count,
            }
            step.duration_ms = round((time.time() - step_start) * 1000, 1)

            logger.info(
                "[EvolutionEngine] 反馈记录完成: processed=%d learn_triggered=%d",
                processed,
                learn_triggered_count,
            )
        except Exception as exc:  # TODO: Narrow exception type
            step.success = False
            step.error = str(exc)
            step.duration_ms = round((time.time() - step_start) * 1000, 1)
            logger.error("[EvolutionEngine] 反馈记录失败: %s", exc, exc_info=True)

        return step

    async def _run_step_learn(
        self,
        feedback_batch: List[Dict[str, Any]],
    ) -> EvolutionStepResult:
        """执行离线学习步骤"""
        step_start = time.time()
        step = EvolutionStepResult(step_name="learn")

        if not feedback_batch:
            step.skipped = True
            step.skip_reason = "无反馈数据"
            step.duration_ms = round((time.time() - step_start) * 1000, 1)
            return step

        try:
            learner = self._get_learner()
            learn_result = await learner.learn_from_feedback(feedback_batch)
            step.success = learn_result.get("ok", True)
            step.data = {
                "processed": learn_result.get("processed", 0),
                "terms_updated": learn_result.get("terms_updated", 0),
            }
            step.duration_ms = round((time.time() - step_start) * 1000, 1)

            logger.info(
                "[EvolutionEngine] 学习完成: processed=%d terms=%d",
                step.data["processed"],
                step.data["terms_updated"],
            )
        except Exception as exc:  # TODO: Narrow exception type
            step.success = False
            step.error = str(exc)
            step.duration_ms = round((time.time() - step_start) * 1000, 1)
            logger.error("[EvolutionEngine] 学习失败: %s", exc, exc_info=True)

        return step

    async def _run_step_evolve(
        self,
        text: str,
        file_name: str = "",
    ) -> EvolutionStepResult:
        """执行知识进化步骤"""
        step_start = time.time()
        step = EvolutionStepResult(step_name="evolve")

        if not text.strip():
            step.skipped = True
            step.skip_reason = "无待分析文本"
            step.duration_ms = round((time.time() - step_start) * 1000, 1)
            return step

        try:
            evolver = self._get_evolver()

            # 从文本中发现实体
            entities = evolver.discover(text)
            entities_discovered = sum(len(v) for v in entities.values())

            if not entities:
                step.success = True
                step.data = {
                    "entities_discovered": 0,
                    "entities_added": 0,
                    "edges_added": 0,
                }
                step.duration_ms = round((time.time() - step_start) * 1000, 1)
                logger.info("[EvolutionEngine] 知识进化: 未发现新实体")
                return step

            # 增量更新知识图谱
            evolve_result = evolver.evolve(entities, file_name=file_name)

            step.success = True
            step.data = {
                "entities_discovered": entities_discovered,
                "entities_added": evolve_result.get("entities_added", 0),
                "edges_added": evolve_result.get("edges_added", 0),
            }
            step.duration_ms = round((time.time() - step_start) * 1000, 1)

            logger.info(
                "[EvolutionEngine] 知识进化完成: discovered=%d added=%d edges=%d",
                entities_discovered,
                step.data["entities_added"],
                step.data["edges_added"],
            )
        except Exception as exc:  # TODO: Narrow exception type
            step.success = False
            step.error = str(exc)
            step.duration_ms = round((time.time() - step_start) * 1000, 1)
            logger.error("[EvolutionEngine] 知识进化失败: %s", exc, exc_info=True)

        return step

    async def _run_step_evolve_text(
        self,
        text: str,
        file_name: str = "",
    ) -> EvolutionStepResult:
        """执行知识进化步骤（别名，与 run_step 接口兼容）"""
        return await self._run_step_evolve(text, file_name)

    async def _run_step_lifecycle(self) -> EvolutionStepResult:
        """执行生命周期检查步骤"""
        step_start = time.time()
        step = EvolutionStepResult(step_name="lifecycle")

        try:
            lifecycle = self._get_lifecycle()
            triggers = await lifecycle.check_triggers()

            candidates_total = 0
            for trigger in triggers:
                candidates = await lifecycle.get_candidates(trigger["event_type"])
                candidates_total += len(candidates)

            step.success = True
            step.data = {
                "trigger_count": len(triggers),
                "candidates_total": candidates_total,
                "triggers": triggers,
            }
            step.duration_ms = round((time.time() - step_start) * 1000, 1)

            logger.info(
                "[EvolutionEngine] 生命周期检查完成: triggers=%d candidates=%d",
                len(triggers),
                candidates_total,
            )
        except Exception as exc:  # TODO: Narrow exception type
            step.success = False
            step.error = str(exc)
            step.duration_ms = round((time.time() - step_start) * 1000, 1)
            logger.error(
                "[EvolutionEngine] 生命周期检查失败: %s",
                exc,
                exc_info=True,
            )

        return step

    # ========================================================================
    # 定时巡检
    # ========================================================================

    async def run_scheduled_check(self) -> Dict[str, Any]:
        """定时巡检入口 — 供 EasyClaw cron 调度

        执行轻量级巡检:
          1. 检查生命周期触发条件
          2. 如有触发 → 获取候选并尝试实体发现
          3. 返回巡检报告

        Returns:
            巡检报告 dict
        """
        logger.info("[EvolutionEngine] 定时巡检开始")
        start_time = time.time()

        report: Dict[str, Any] = {
            "ok": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "triggers_found": 0,
            "entities_discovered": 0,
            "evolution_performed": False,
            "errors": [],
            "duration_ms": 0.0,
        }

        try:
            # 检查生命周期触发条件
            lifecycle = self._get_lifecycle()
            triggers = await lifecycle.check_triggers()

            if not triggers:
                report["duration_ms"] = round((time.time() - start_time) * 1000, 1)
                logger.info("[EvolutionEngine] 定时巡检完成: 无触发条件")
                return report

            report["triggers_found"] = len(triggers)

            # 处理每个触发类型
            evolver = self._get_evolver()
            total_discovered = 0

            for trigger in triggers:
                try:
                    candidates = await lifecycle.get_candidates(trigger["event_type"])
                    if not candidates:
                        continue

                    # 将候选知识聚合为文本
                    combined_text = " ".join(c.get("query", "") or c.get("text", "") or "" for c in candidates[:50])

                    if not combined_text.strip():
                        continue

                    # 实体发现
                    entities = evolver.discover(combined_text)
                    if entities:
                        evolver.evolve(entities, file_name="scheduled_check")
                        discovered = sum(len(v) for v in entities.values())
                        total_discovered += discovered
                        report["evolution_performed"] = True

                except Exception as exc:  # TODO: Narrow exception type
                    report["errors"].append(f"[{trigger['event_type']}] {exc}")
                    logger.warning(
                        "[EvolutionEngine] 巡检步骤失败: %s — %s",
                        trigger["event_type"],
                        exc,
                    )

            report["entities_discovered"] = total_discovered
            report["duration_ms"] = round((time.time() - start_time) * 1000, 1)

            logger.info(
                "[EvolutionEngine] 定时巡检完成: triggers=%d discovered=%d",
                report["triggers_found"],
                total_discovered,
            )

        except Exception as exc:  # TODO: Narrow exception type
            report["ok"] = False
            report["errors"].append(str(exc))
            report["duration_ms"] = round((time.time() - start_time) * 1000, 1)
            logger.error("[EvolutionEngine] 定时巡检失败: %s", exc, exc_info=True)

        return report

    # ========================================================================
    # 健康状态
    # ========================================================================

    def health_summary(self) -> Dict[str, Any]:
        """生成进化引擎健康状态摘要

        Returns:
            健康状态字典，包含各组件状态和累计统计
        """
        try:
            feedback_stats = get_feedback_loop_stats()
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:  # TODO: Narrow exception type
            feedback_stats = {"error": "unavailable"}

        try:
            learner_stats = get_learner_stats()
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:  # TODO: Narrow exception type
            learner_stats = {"error": "unavailable"}

        try:
            graph_stats = get_knowledge_graph_stats()
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:  # TODO: Narrow exception type
            graph_stats = {"error": "unavailable"}

        return {
            "ok": True,
            "cycle_count": self._cycle_count,
            "last_cycle_sec": (round(time.time() - self._last_cycle_time, 1) if self._last_cycle_time > 0 else -1),
            "cumulative": {
                "total_feedback_processed": self._total_feedback_processed,
                "total_entities_evolved": self._total_entities_evolved,
                "total_terms_learned": self._total_terms_learned,
            },
            "components": {
                "feedback": feedback_stats,
                "learner": learner_stats,
                "graph": graph_stats,
            },
        }

    # ========================================================================
    # 统计重置
    # ========================================================================

    def reset_stats(self) -> None:
        """重置统计计数器"""
        self._cycle_count = 0
        self._last_cycle_time = 0.0
        self._total_entities_evolved = 0
        self._total_feedback_processed = 0
        self._total_terms_learned = 0
        logger.info("[EvolutionEngine] 统计已重置")


# ============================================================================
# 全局单例
# ============================================================================

_evolution_engine_instance: Optional[EvolutionEngine] = None


def get_evolution_engine() -> EvolutionEngine:
    """获取全局 EvolutionEngine 单例

    Returns:
        EvolutionEngine 单例
    """
    global _evolution_engine_instance
    if _evolution_engine_instance is None:
        _evolution_engine_instance = EvolutionEngine()
    return _evolution_engine_instance


# ============================================================================
# 便捷函数
# ============================================================================


async def run_evolution_cycle(
    feedback_batch: Optional[List[Dict[str, Any]]] = None,
    text: str = "",
    file_name: str = "",
    user_id: str = "",
) -> Dict[str, Any]:
    """便捷函数：执行完整进化循环

    Args:
        feedback_batch: 反馈条目列表
        text:           待分析文本
        file_name:      来源文件名
        user_id:        用户标识

    Returns:
        进化循环结果字典
    """
    engine = get_evolution_engine()
    result = await engine.run_evolution_cycle(
        feedback_batch=feedback_batch,
        text=text,
        file_name=file_name,
        user_id=user_id,
    )

    return {
        "ok": result.ok,
        "feedback_count": result.feedback_count,
        "entities_discovered": result.entities_discovered,
        "entities_added": result.entities_added,
        "edges_added": result.edges_added,
        "terms_updated": result.terms_updated,
        "lifecycle_triggers": result.lifecycle_triggers,
        "errors": result.errors,
        "duration_ms": result.total_duration_ms,
        "timestamp": result.timestamp,
    }


async def run_scheduled_evolution_check() -> Dict[str, Any]:
    """便捷函数：执行定时巡检

    Returns:
        巡检报告
    """
    engine = get_evolution_engine()
    return await engine.run_scheduled_check()


def get_evolution_health() -> Dict[str, Any]:
    """便捷函数：获取进化引擎健康状态

    Returns:
        健康状态摘要
    """
    engine = get_evolution_engine()
    return engine.health_summary()
