"""
qian/cycle_guard.py - CycleGuard（循环守护）
============================================

防止意图循环失控，拦截规则：
- 超过 max_rounds → 强制终止
- 连续同卦 > max_consecutive_same → 拦截
- DONE 前未执行 SEARCH → 拦截
- DONE 但 confidence < min_confidence_for_done → 拦截
- 单卦总调用超过上限 → 拦截
"""

from dataclasses import dataclass, field
from src.bagua._common import (
    hashlib, json, logging, os, re, time,
    Any, Dict, List, Optional, Tuple,
)

logger = logging.getLogger("bagua.qian")

# ============================================================================
# CycleGuard — 循环守护
# ============================================================================


@dataclass
class CycleGuardState:
    """CycleGuard 内部状态

    Attributes:
        round_count:                已执行轮数
        last_intent:                上一轮的意图
        consecutive_same:           连续相同意图计数
        per_trigram_count:          每个意图的累计调用次数
        has_searched:               是否已经执行过 SEARCH/SEARCH_X
        guard_intervention_count:   CycleGuard 连续拦截次数
        anomaly_cache:              异常模式缓存（最近 100 次被拦截的意图组合）
        known_issues:               已知问题签名集合（同一模式连续拦截 >=3 次后标记）
    """
    round_count: int = 0
    last_intent: Optional[str] = None
    consecutive_same: int = 0
    per_trigram_count: Dict[str, int] = field(default_factory=dict)
    has_searched: bool = False
    guard_intervention_count: int = 0
    anomaly_cache: List[str] = field(default_factory=list)       # 最近 100 次被拦截的意图组合
    known_issues: set = field(default_factory=set)               # 已知问题签名集合


class CycleGuard:
    """循环守护器 — 防止意图循环失控

    拦截规则：
      - 超过 max_rounds → 强制终止
      - 连续同卦 > max_consecutive_same → 拦截
      - DONE 前未执行 SEARCH → 拦截
      - DONE 但 confidence < min_confidence_for_done → 拦截
      - 单卦总调用超过上限 → 拦截

    Attributes:
        max_rounds:              最大循环轮数（默认 8）
        max_consecutive_same:    同卦连续上限（默认 2）
        max_per_trigram:         每卦总调用上限
        min_confidence_for_done: DONE 最低置信度（默认 0.7）
        AnomalyCacheSize:          异常模式缓存最大容量（默认 100）
        KnownIssueThreshold:      同一模式连续拦截 N 次后标记为已知问题（默认 3）
    """

    # 缓存容量
    MAX_ANOMALY_CACHE_SIZE: int = 100
    # 已知问题阈值
    KNOWN_ISSUE_THRESHOLD: int = 3

    def __init__(
        self,
        max_rounds: int = 8,
        max_consecutive_same: int = 2,
        max_per_trigram: Optional[Dict[str, int]] = None,
        min_confidence_for_done: float = 0.7,
    ) -> None:
        self.max_rounds = max_rounds
        self.max_consecutive_same = max_consecutive_same
        self.max_per_trigram: Dict[str, int] = max_per_trigram or {
            "SEARCH": 3,
            "SEARCH_X": 2,
            "REFINE": 3,
            "DECIDE": 2,
            "GUARD": 2,
            "PRESENT": 2,
            "DONE": 1,
        }
        self.min_confidence_for_done = min_confidence_for_done
        # 异常模式缓存（模块级共享，用于跨 session 学习）
        self._anomaly_cache: List[str] = []
        self._known_issues: set = set()

    def pre_check(
        self,
        intent: str,
        confidence: float,
        state: CycleGuardState,
        query: str = "",
    ) -> Tuple[bool, str]:
        """执行预检查，返回 (通过, 原因)

        规则顺序：
          0. 已知问题透传：如果此意图组合已在 known_issues 中，直接通过
          1. 超过 max_rounds
          2. 连续同卦 > max_consecutive_same
          3. 每卦总调用上限
          4. DONE 前未执行 SEARCH
          5. DONE 但 confidence < min_confidence_for_done
          6. 异常模式检测
        """
        # 规则 0: 已知问题透传
        signature = self._make_anomaly_signature(intent, state.last_intent, state.consecutive_same)
        if signature in self._known_issues:
            logger.debug("☰ [乾] CycleGuard 已知问题透传: %s", signature)
            return True, "known_issue"

        # 规则 1: 超过 max_rounds
        if state.round_count >= self.max_rounds:
            reason = f"超过最大轮数 ({self.max_rounds})"
            self._record_anomaly(signature, reason)
            return False, reason

        # 规则 2: 连续同卦 > max_consecutive_same
        if intent == state.last_intent and state.consecutive_same >= self.max_consecutive_same:
            reason = f"连续同卦 {intent} 超过 {self.max_consecutive_same} 次"
            self._record_anomaly(signature, reason)
            return False, reason

        # 规则 3: 每卦总调用上限
        current_count = state.per_trigram_count.get(intent, 0)
        max_count = self.max_per_trigram.get(intent, 0)
        if max_count > 0 and current_count >= max_count:
            reason = f"卦 {intent} 总调用超过上限 ({max_count})"
            self._record_anomaly(signature, reason)
            return False, reason

        # 规则 4: DONE 前未执行 SEARCH
        if intent == "DONE" and not state.has_searched:
            reason = "DONE 前未执行 SEARCH"
            self._record_anomaly(signature, reason)
            return False, reason

        # 规则 5: DONE 但 confidence < min_confidence_for_done
        if intent == "DONE" and confidence < self.min_confidence_for_done:
            reason = f"DONE 置信度不足 ({confidence:.2f} < {self.min_confidence_for_done})"
            self._record_anomaly(signature, reason)
            return False, reason

        # 规则 6: 异常模式检测
        if self._check_known_issue(signature):
            reason = f"异常模式: {signature}"
            self._record_anomaly(signature, reason)
            return False, reason

        return True, "ok"

    def record_intent(self, intent: str, state: CycleGuardState) -> None:
        """记录意图，更新状态"""
        state.round_count += 1
        if intent == state.last_intent:
            state.consecutive_same += 1
        else:
            state.consecutive_same = 1
            state.last_intent = intent
        state.per_trigram_count[intent] = state.per_trigram_count.get(intent, 0) + 1
        if intent in ("SEARCH", "SEARCH_X"):
            state.has_searched = True

    def _make_anomaly_signature(self, intent: str, last_intent: Optional[str], consecutive_same: int) -> str:
        """生成异常模式签名"""
        return f"{last_intent or 'None'}→{intent}×{consecutive_same}"

    def _record_anomaly(self, signature: str, reason: str) -> None:
        """记录异常模式"""
        self._anomaly_cache.append(signature)
        if len(self._anomaly_cache) > self.MAX_ANOMALY_CACHE_SIZE:
            self._anomaly_cache.pop(0)

        # 检查是否达到已知问题阈值
        count = self._anomaly_cache.count(signature)
        if count >= self.KNOWN_ISSUE_THRESHOLD:
            self._known_issues.add(signature)
            logger.warning("☰ [乾] CycleGuard 标记已知问题: %s (连续 %d 次)", signature, count)

    def _check_known_issue(self, signature: str) -> bool:
        """检查是否为已知问题"""
        return signature in self._known_issues

    def get_anomaly_stats(self) -> Dict[str, Any]:
        """获取异常统计"""
        return {
            "anomaly_cache_size": len(self._anomaly_cache),
            "known_issues_count": len(self._known_issues),
            "known_issues": list(self._known_issues),
        }

    def clear_anomaly_cache(self) -> None:
        """清空异常缓存"""
        self._anomaly_cache.clear()
        self._known_issues.clear()
        logger.info("☰ [乾] CycleGuard 异常缓存已清空")
