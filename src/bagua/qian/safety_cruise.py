"""
qian/safety_cruise.py - SafetyCruise（安全巡航）
================================================

CycleGuard 连续拦截后接管，按固定流水线执行。
"""

from dataclasses import dataclass, field
from src.bagua._common import (
    hashlib, json, logging, os, re, time,
    Any, Dict, List, Optional, Tuple,
)

logger = logging.getLogger("bagua.qian")

# ============================================================================
# SafetyCruise — 安全巡航
# ============================================================================


@dataclass
class SafetyCruiseState:
    """SafetyCruise 内部状态

    Attributes:
        active:                是否激活
        pipeline_index:        当前流水线索引
        pipeline:              固定流水线
        start_time:            开始时间
        intervention_count:    干预次数
    """
    active: bool = False
    pipeline_index: int = 0
    pipeline: List[str] = field(default_factory=list)
    start_time: float = 0.0
    intervention_count: int = 0


class SafetyCruise:
    """安全巡航器 — CycleGuard 连续拦截后接管，按固定流水线执行

    当 CycleGuard 连续拦截超过阈值时，SafetyCruise 接管意图循环，
    按固定流水线执行，确保系统不会陷入无限循环。

    Attributes:
        pipeline:              固定流水线（默认 ["SEARCH", "REFINE", "DECIDE", "PRESENT", "DONE"]）
        max_intervention:      最大干预次数（默认 3）
    """

    def __init__(
        self,
        pipeline: Optional[List[str]] = None,
        max_intervention: int = 3,
    ) -> None:
        self.pipeline = pipeline or ["SEARCH", "REFINE", "DECIDE", "PRESENT", "DONE"]
        self.max_intervention = max_intervention

    def is_active(self, state: SafetyCruiseState) -> bool:
        """判断是否激活"""
        return state.active

    def activate(self, state: SafetyCruiseState) -> None:
        """激活安全巡航"""
        state.active = True
        state.pipeline_index = 0
        state.pipeline = self.pipeline.copy()
        state.start_time = time.time()
        state.intervention_count += 1
        logger.warning("☰ [乾] SafetyCruise 激活，按固定流水线执行")

    def deactivate(self, state: SafetyCruiseState) -> None:
        """停用安全巡航"""
        state.active = False
        state.pipeline_index = 0
        state.pipeline = []
        logger.info("☰ [乾] SafetyCruise 停用")

    def reset(self, state: SafetyCruiseState) -> None:
        """重置安全巡航"""
        state.active = False
        state.pipeline_index = 0
        state.pipeline = []
        state.start_time = 0.0
        state.intervention_count = 0
        logger.info("☰ [乾] SafetyCruise 重置")

    def suggest(self, state: SafetyCruiseState) -> Optional[str]:
        """建议下一个意图"""
        if not state.active:
            return None

        if state.pipeline_index >= len(state.pipeline):
            self.deactivate(state)
            return None

        intent = state.pipeline[state.pipeline_index]
        state.pipeline_index += 1
        logger.debug("☰ [乾] SafetyCruise 建议意图: %s (索引 %d)", intent, state.pipeline_index - 1)
        return intent

    def override(self, state: SafetyCruiseState, intent: str) -> bool:
        """覆盖当前意图"""
        if not state.active:
            return False

        if intent not in self.pipeline:
            logger.warning("☰ [乾] SafetyCruise 意图 %s 不在固定流水线中", intent)
            return False

        # 更新流水线索引
        state.pipeline_index = self.pipeline.index(intent) + 1
        logger.debug("☰ [乾] SafetyCruise 覆盖意图: %s (索引 %d)", intent, state.pipeline_index - 1)
        return True
