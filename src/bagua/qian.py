#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qian.py — 乾卦 ☰ · 伏羲 v2.1 重构

乾卦是伏羲 RAG 系统的意识中枢（0 的居所），通过 IntentBus 调度
其他 7 个卦，实现完整的"意图循环"：

  用户提问 → 乾卦 think() → 意图决策 → IntentBus.dispatch() →
  目标卦执行 → 结果回馈 → 乾卦再决策 → … → DONE → 最终答案

乾卦提供：
  - 意图循环（Intent Loop）：逐轮 LLM 决策 + 意图派发
  - CycleGuard（循环守护）：同卦连续上限、总轮数限制、未检索禁 DONE
  - SafetyCruise（安全巡航）：CycleGuard 连续拦截后接管，按固定流水线执行
  - 三层降级：L1 重试（Mimo→DeepSeek→OpenAI 4o-mini）→ L2 ShaoyinBrain
    → L3 兜底直答
  - Session 隔离：每个 session_id 有独立的状态和 think() 调用

不依赖 organs/ 或 Meridian，仅依赖 src/services/llm.py 的 call_llm()
和 src/bagua/intent_bus.py 的 IntentBus。
"""


import asyncio
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.bagua.base_gua import (
    GuaBase,
    CircuitState,
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
)

# ---- 第九宫自进化桥接 ----
try:
    from src.evolution.feedback_loop import record_feedback as _evo_record_feedback
    _EVO_FEEDBACK_AVAILABLE = True
except ImportError:
    _EVO_FEEDBACK_AVAILABLE = False
try:
    from src.services.feedback_store import _learn_buffer
    _LEARN_BUFFER_AVAILABLE = True
except ImportError:
    _learn_buffer = None
    _LEARN_BUFFER_AVAILABLE = False

# ---- 4o-mini Fallback 配置（L1 三层重试） ----
_OPENAI_4O_MINI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
_OPENAI_4O_MINI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
_OPENAI_4O_MINI_TIMEOUT: int = int(os.getenv("OPENAI_TIMEOUT", "30"))

logger = logging.getLogger("bagua.qian")

# ============================================================================
# 数据目录常量 — 用于日志和缓存文件
# ============================================================================

_DATA_DIR: Path = Path(__file__).resolve().parent.parent.parent / "data"
_INTENT_LOG_PATH: Path = _DATA_DIR / "intent_decisions.jsonl"
_DEGRADATION_COUNTER_PATH: Path = _DATA_DIR / "degradation_counters.json"
_INTENT_CACHE_PATH: Path = _DATA_DIR / "intent_pattern_cache.json"

# ============================================================================
# 常量定义
# ============================================================================

# Session TTL（秒）— 超过此时间未活动的 session 将被自动清理
SESSION_TTL: float = 3600.0

# 可用卦及其能力描述
AVAILABLE_TRIGRAMS: Dict[str, Dict[str, str]] = {
    "SEARCH":   {"gua": "巽", "capability": "本地知识检索", "when": "问题需要查知识库"},
    "SEARCH_X": {"gua": "坎", "capability": "外部搜索+精炼",  "when": "需要实时/外部信息"},
    "REFINE":   {"gua": "坎", "capability": "精炼排序",       "when": "候选太多需去重择优"},
    "DECIDE":   {"gua": "乾", "capability": "决策判断",       "when": "需逻辑推理/综合"},
    "FUSION":   {"gua": "离", "capability": "融合照亮",       "when": "多源信息需融合"},
    "UPLOAD":   {"gua": "震", "capability": "消化启动",       "when": "知识需消化入库"},
    "GUARD":    {"gua": "艮", "capability": "安全检查",       "when": "输入输出需过滤"},
    "PRESENT":  {"gua": "兑", "capability": "输出答案",       "when": "信息足够，生成回答"},
    "DONE":     {"gua": "—",  "capability": "结束",           "when": "答案已完成"},
}

# 意图 → 目标卦映射（IntentBus 调度时使用）
# 对照 fuxi-v2.1-0-to-64-final.md 八卦职责表：
#   巽 ☴ = 检索（体内外搜索）、坎 ☵ = 精炼+外部搜索、离 ☲ = 决策/融合
#   震 ☳ = 消化管线、艮 ☶ = 守卫/安全、兑 ☱ = 界面+审计
INTENT_TO_TARGET_GUA: Dict[str, str] = {
    "SEARCH":   "巽",   # 巽—检索（体内外搜索）
    "SEARCH_X": "坎",   # 坎—精炼+外部搜索
    "REFINE":   "坎",   # 坎—精炼/排序/Rerank
    "DECIDE":   "乾",   # 乾—决断（自身内省）
    "FUSION":   "离",   # 离—决策/综合判断
    "UPLOAD":   "震",   # 震—消化管线
    "GUARD":    "艮",   # 艮—守卫/安全
    "PRESENT":  "兑",   # 兑—界面+审计
}

# 兜底固定流水线（ShaoyinBrain / SafetyCruise）
FIXED_PIPELINE: List[str] = ["SEARCH", "REFINE", "DECIDE", "PRESENT", "DONE"]

# ============================================================================
# 乾卦决策 Prompt
# ============================================================================

_QIAN_SYSTEM_PROMPT = """你是乾卦(0)，伏羲RAG系统的意识中枢。唯一职责：按规则决策下一步。

## 可用能力
| 意图 | 目标卦 | 能力 | 使用时机 |
|------|-------|------|---------|
| SEARCH | 巽 ☴ | 本地知识检索 | 问题需要查知识库 |
| SEARCH_X | 坎 ☵ | 外部搜索+精炼 | 需要实时/外部信息 |
| REFINE | 坎 ☵ | 精炼排序 | 候选太多需去重择优 |
| DECIDE | 乾 ☰ | 决策判断 | 需逻辑推理/综合 |
| FUSION | 离 ☲ | 融合照亮 | 多源信息需融合 |
| UPLOAD | 震 ☳ | 消化启动 | 知识需消化入库 |
| GUARD | 艮 ☶ | 安全检查 | 输入输出需过滤 |
| PRESENT | 兑 ☱ | 输出答案 | 信息足够，生成回答 |
| DONE | — | 结束 | 答案已完成 |

## 规则（严格遵守）
1. 首轮：从 SEARCH/SEARCH_X 中选
2. 同卦不连续调 >2 次
3. 未执行 SEARCH 前禁止 DONE
4. 最多 8 轮，第 7 轮收束
5. DONE 需 confidence ≥ 0.7
6. 若某卦断路器断开(OPEN)，避免调该卦对应的意图
7. 健康水平为 MINIMAL/OFF 的卦应视为不可用

## 输出（仅 JSON，无其他文字）
{"intent":"SEARCH|...","confidence":0.85,"reasoning":"简因≤20字"}

{runtime_state}"""

# ============================================================================
# 意图预加载缓存 — 高频简单查询跳过 LLM
# ============================================================================

# 预加载意图规则：query_pattern → intent（通配符 * 支持前缀匹配）
_DEFAULT_INTENT_PRELOAD_CACHE: Dict[str, str] = {
    # 问候类
    "你好": "PRESENT",
    "嗨": "PRESENT",
    "喂": "PRESENT",
    "hello": "PRESENT",
    "hi": "PRESENT",
    "早上好": "PRESENT",
    "晚上好": "PRESENT",
    "下午好": "PRESENT",
    # 帮助类
    "帮助": "PRESENT",
    "help": "PRESENT",
    "怎么用": "PRESENT",
    "如何使用": "PRESENT",
    # 搜索类（前缀匹配）
    "搜*": "SEARCH",
    "查找*": "SEARCH",
    "搜索*": "SEARCH",
    "查一下*": "SEARCH",
    "查找": "SEARCH",
    # 感谢
    "谢谢": "PRESENT",
    "感谢": "PRESENT",
    "thank": "PRESENT",
    # 确认/否定
    "好的": "PRESENT",
    "OK": "PRESENT",
    "ok": "PRESENT",
    "不行": "PRESENT",
    "可以": "PRESENT",
    # 告别
    "再见": "PRESENT",
    "拜拜": "PRESENT",
    "bye": "PRESENT",
}


def _load_intent_preload_cache() -> Dict[str, str]:
    """从磁盘加载意图预加载缓存，合并默认规则

    磁盘文件优先，若不存在则返回默认缓存。
    """
    try:
        if _INTENT_CACHE_PATH.exists():
            with open(_INTENT_CACHE_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                merged = dict(_DEFAULT_INTENT_PRELOAD_CACHE)
                merged.update(loaded)
                logger.info("☰ [乾] 意图预加载缓存: 加载 %d 条规则 (磁盘 %d + 默认 %d)",
                             len(merged), len(loaded), len(_DEFAULT_INTENT_PRELOAD_CACHE))
                return merged
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        logger.warning("☰ [乾] 加载意图预加载缓存失败: %s", exc)
    return dict(_DEFAULT_INTENT_PRELOAD_CACHE)


def _save_intent_preload_cache(cache: Dict[str, str]) -> None:
    """将意图预加载缓存持久化到磁盘"""
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(_INTENT_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        logger.debug("☰ [乾] 意图预加载缓存已保存: %d 条规则", len(cache))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("☰ [乾] 保存意图预加载缓存失败: %s", exc)


def _match_intent_preload(query: str, cache: Dict[str, str]) -> Optional[str]:
    """查询预加载缓存，匹配意图

    匹配规则：
      1. 精确匹配（query 完全相同）
      2. 前缀通配匹配（模式 "搜*" 匹配 "搜" 开头的 query）
      3. 包含匹配（query 包含模式关键词，非通配模式）

    Args:
        query: 用户查询文本（已做 strip）
        cache: 预加载缓存字典

    Returns:
        匹配的意图，或 None（未命中）
    """
    if not query:
        return None

    # 精确匹配
    if query in cache:
        return cache[query]

    # 前缀通配匹配
    for pattern, intent in cache.items():
        if pattern.endswith("*") and query.startswith(pattern[:-1]):
            return intent

    # 包含匹配（短 query 且无通配符的模式）
    for pattern, intent in cache.items():
        if "*" not in pattern and len(pattern) <= len(query) and pattern in query:
            return intent

    return None


# ============================================================================
# DegradationCounter — 三层降级监控计数器
# ============================================================================


@dataclass
class DegradationCounter:
    """三层降级链监控计数器

    记录 L1/L2/L3 每层的触发次数和时间，支持小时级重置
    和 L2 触发频次超阈值告警。

    Attributes:
        l1_count:        L1 dispatch 失败次数
        l2_count:        L2 ShaoyinBrain 触发次数
        l3_count:        L3 兜底直答触发次数
        total_requests:  时间段内总请求数
        l1_timestamps:   L1 触发的时间戳列表
        l2_timestamps:   L2 触发的时间戳列表
        l3_timestamps:   L3 触发的时间戳列表
        hour_start:      当前统计周期开始时间
        last_reset:      上次重置时间
        last_alert_sent: 上次发送告警时间
    """
    l1_count: int = 0
    l2_count: int = 0
    l3_count: int = 0
    total_requests: int = 0
    l1_timestamps: List[float] = field(default_factory=list)
    l2_timestamps: List[float] = field(default_factory=list)
    l3_timestamps: List[float] = field(default_factory=list)
    hour_start: float = field(default_factory=time.time)
    last_reset: float = field(default_factory=time.time)
    last_alert_sent: float = 0.0

    def record_l1_failure(self) -> None:
        """记录一次 L1 dispatch 失败"""
        self.l1_count += 1
        self.l1_timestamps.append(time.time())
        self._trim_old_timestamps(self.l1_timestamps)

    def record_l2_trigger(self) -> None:
        """记录一次 L2 降级触发"""
        self.l2_count += 1
        self.l2_timestamps.append(time.time())
        self._trim_old_timestamps(self.l2_timestamps)

    def record_l3_trigger(self) -> None:
        """记录一次 L3 兜底触发"""
        self.l3_count += 1
        self.l3_timestamps.append(time.time())
        self._trim_old_timestamps(self.l3_timestamps)

    def record_request(self) -> None:
        """记录一次总请求"""
        self.total_requests += 1

    def get_l2_rate_percent(self) -> float:
        """计算当前小时 L2 触发占比（%）

        Returns:
            L2 触发次数占 L1 失败次数的百分比，若无 L1 失败则返回 0
        """
        if self.l1_count == 0:
            return 0.0
        return round((self.l2_count / self.l1_count) * 100, 2)

    def should_alert_l2(self, threshold_percent: float = 5.0) -> bool:
        """判断是否应发送 L2 超频告警

        当 L2 触发频次超过 threshold_percent%/hour 且距上次告警 > 10 分钟时
        触发告警。

        Args:
            threshold_percent: 触发阈值百分比（默认 5%）

        Returns:
            True 如果应发送告警
        """
        rate = self.get_l2_rate_percent()
        if rate < threshold_percent:
            return False
        now = time.time()
        # 避免频繁告警：至少间隔 10 分钟
        if now - self.last_alert_sent < 600:
            return False
        self.last_alert_sent = now
        return True

    def try_hourly_reset(self) -> bool:
        """尝试每小时重置计数器

        检查是否距离 hour_start 已过 1 小时，若是则重置并返回 True。
        重置前将旧数据写入磁盘备份。

        Returns:
            True 如果执行了重置
        """
        now = time.time()
        if now - self.hour_start >= 3600:
            # 备份旧数据
            self._backup_to_disk()
            # 重置
            self.l1_count = 0
            self.l2_count = 0
            self.l3_count = 0
            self.total_requests = 0
            self.l1_timestamps.clear()
            self.l2_timestamps.clear()
            self.l3_timestamps.clear()
            self.hour_start = now
            self.last_reset = now
            logger.info("☰ [乾] 降级计数器小时级重置")
            return True
        return False

    def _trim_old_timestamps(self, ts_list: List[float], window: float = 3600.0) -> None:
        """清理超过 window 秒的旧时间戳"""
        cutoff = time.time() - window
        while ts_list and ts_list[0] < cutoff:
            ts_list.pop(0)

    def _backup_to_disk(self) -> None:
        """将当前计数器快照写入磁盘备份"""
        try:
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            snapshot = {
                "hour_start": self.hour_start,
                "last_reset": self.last_reset,
                "l1_count": self.l1_count,
                "l2_count": self.l2_count,
                "l3_count": self.l3_count,
                "total_requests": self.total_requests,
                "l2_rate_percent": self.get_l2_rate_percent(),
                "written_at": time.time(),
            }
            with open(_DEGRADATION_COUNTER_PATH, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
        except (OSError, json.JSONDecodeError) as exc:
            logger.debug("☰ [乾] 降级计数器备份失败: %s", exc)

    def get_summary(self) -> Dict[str, Any]:
        """获取当前计数器摘要"""
        return {
            "l1_count": self.l1_count,
            "l2_count": self.l2_count,
            "l3_count": self.l3_count,
            "total_requests": self.total_requests,
            "l2_rate_percent": self.get_l2_rate_percent(),
            "hour_elapsed_sec": round(time.time() - self.hour_start, 1),
        }


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
          5. DONE 但 confidence < min

        Args:
            intent:     本轮意图
            confidence: 决策置信度
            state:      当前循环状态（会被修改以更新 consecutive_same 等）
            query:      用户查询（用于生成异常签名）

        Returns:
            (是否通过, 原因说明)。通过时 reason 为空字符串。
        """
        # 规则 0: 已知问题透传 — 同一模式已被 learn 识别，直接放行
        signature = self._make_anomaly_signature(intent, query, state)
        if signature in self._known_issues:
            logger.info(
                "☰ [乾] CycleGuard 已知问题透传: %s (signature=%s)",
                intent, signature[:60],
            )
            return True, ""

        # 规则 1: 超过 max_rounds
        if state.round_count >= self.max_rounds:
            self._record_anomaly(intent, query, state, reason=f"超过最大轮数 ({self.max_rounds})")
            return False, f"超过最大轮数限制 ({self.max_rounds})"

        # 规则 2: 连续同卦 > max_consecutive_same
        if intent == state.last_intent:
            state.consecutive_same += 1
        else:
            state.consecutive_same = 1
            state.last_intent = intent

        if state.consecutive_same > self.max_consecutive_same:
            self._record_anomaly(intent, query, state, reason=f"连续调用 {intent} 超过 {self.max_consecutive_same} 次")
            return False, f"连续调用 {intent} 超过 {self.max_consecutive_same} 次"

        # 规则 3: 每卦总调用上限
        per_trigram_count = state.per_trigram_count.get(intent, 0)
        max_for_this = self.max_per_trigram.get(intent, 999)
        if per_trigram_count >= max_for_this:
            self._record_anomaly(intent, query, state, reason=f"{intent} 调用次数已达上限 ({max_for_this})")
            return False, f"{intent} 调用次数已达上限 ({max_for_this})"

        # 规则 4: DONE 前未执行 SEARCH
        if intent == "DONE" and not state.has_searched:
            self._record_anomaly(intent, query, state, reason="未执行 SEARCH 前禁止 DONE")
            return False, "未执行 SEARCH 前禁止 DONE"

        # 规则 5: DONE 但 confidence < min
        if intent == "DONE" and confidence < self.min_confidence_for_done:
            self._record_anomaly(intent, query, state, reason=f"DONE 置信度 {confidence:.2f} < {self.min_confidence_for_done}")
            return False, f"DONE 置信度 {confidence:.2f} < {self.min_confidence_for_done}"

        return True, ""

    def force_fallback(self) -> str:
        """返回强制降级信号"""
        return "FALLBACK_FIXED_PIPELINE"

    def record_intent(self, intent: str, state: CycleGuardState) -> None:
        """记录本轮意图执行（通过预检查后调用）

        Args:
            intent: 本轮意图
            state:  循环状态
        """
        state.round_count += 1
        state.per_trigram_count[intent] = state.per_trigram_count.get(intent, 0) + 1
        if intent in ("SEARCH", "SEARCH_X"):
            state.has_searched = True

    # ========================================================================
    # 异常模式学习 — 记录拦截、识别已知问题、自动透传
    # ========================================================================

    @staticmethod
    def _make_anomaly_signature(intent: str, query: str, state: CycleGuardState) -> str:
        """生成异常模式签名

        签名格式：intent|round_count|consecutive_same|query_prefix
        用于跨 session 识别相同的拦截模式。

        Args:
            intent:  被拦截的意图
            query:   用户查询文本
            state:   当前循环状态

        Returns:
            签名字符串
        """
        q = (query or "").strip()[:40]
        return f"{intent}|R{state.round_count}|CS{state.consecutive_same}|q={q}"

    def _record_anomaly(
        self,
        intent: str,
        query: str,
        state: CycleGuardState,
        reason: str,
    ) -> None:
        """记录一次异常拦截到缓存（CycleGuard 模块级）

        同时检查是否应标记为"已知问题"：
        同一签名连续出现 >= KNOWN_ISSUE_THRESHOLD 次时自动标记。

        Args:
            intent:  被拦截的意图
            query:   用户查询
            state:   当前循环状态
            reason:  拦截原因
        """
        signature = self._make_anomaly_signature(intent, query, state)

        # 维护模块级异常缓存（FIFO + 去重）
        self._anomaly_cache.append(signature)
        if len(self._anomaly_cache) > self.MAX_ANOMALY_CACHE_SIZE:
            self._anomaly_cache = self._anomaly_cache[-self.MAX_ANOMALY_CACHE_SIZE:]

        # 也更新 session 级缓存
        state.anomaly_cache.append(signature)
        if len(state.anomaly_cache) > self.MAX_ANOMALY_CACHE_SIZE:
            state.anomaly_cache = state.anomaly_cache[-self.MAX_ANOMALY_CACHE_SIZE:]

        # 检查是否达到已知问题阈值
        self._check_known_issue(signature, state, intent, reason)

    def _check_known_issue(
        self,
        signature: str,
        state: CycleGuardState,
        intent: str,
        reason: str,
    ) -> None:
        """检查异常签名是否应标记为已知问题

        最近 N 次异常缓存中同一签名出现 >= KNOWN_ISSUE_THRESHOLD 次
        则自动标记为 known_issue，后续直接透传。

        Args:
            signature:  异常签名
            state:      当前循环状态
            intent:     被拦截的意图
            reason:     拦截原因
        """
        # 用 session 级缓存做快速统计
        recent = state.anomaly_cache[-self.KNOWN_ISSUE_THRESHOLD * 2:]
        count = sum(1 for s in recent if s == signature)
        if count >= self.KNOWN_ISSUE_THRESHOLD and signature not in self._known_issues:
            self._known_issues.add(signature)
            logger.warning(
                "☰ [乾] CycleGuard 自动标记已知问题: intent=%s reason='%s' signature=%s (连续 %d 次)",
                intent, reason, signature[:60], count,
            )

    def get_anomaly_stats(self) -> Dict[str, Any]:
        """获取异常模式统计

        Returns:
            {"cache_size": int, "known_issues_count": int, "known_issues": [str, ...]}
        """
        return {
            "cache_size": len(self._anomaly_cache),
            "known_issues_count": len(self._known_issues),
            "known_issues": list(self._known_issues)[-20:],  # 最近 20 个
        }

    def clear_anomaly_cache(self) -> None:
        """清理异常模式缓存"""
        self._anomaly_cache.clear()
        self._known_issues.clear()
        logger.info("☰ [乾] CycleGuard 异常缓存已清理")


# ============================================================================
# SafetyCruise — 安全巡航
# ============================================================================


class SafetyCruise:
    """安全巡航 — CycleGuard 连续拦截 >2 次后接管，按固定流水线执行

    Attributes:
        FIXED_SEQUENCE: 固定执行序列 [SEARCH, REFINE, DECIDE, PRESENT, DONE]
    """

    FIXED_SEQUENCE: List[str] = list(FIXED_PIPELINE)

    def __init__(self) -> None:
        self._sequence_index: int = 0
        self._active: bool = False

    @property
    def is_active(self) -> bool:
        """是否已激活（接管中）"""
        return self._active

    def activate(self) -> None:
        """激活 SafetyCruise — 开始固定流水线"""
        self._active = True
        self._sequence_index = 0
        logger.warning("[SafetyCruise] 接管启动，执行固定流水线 %s", self.FIXED_SEQUENCE)

    def deactivate(self) -> None:
        """停用 SafetyCruise"""
        self._active = False
        self._sequence_index = 0

    def reset(self) -> None:
        """重置状态（停用 + 索引归零）"""
        self._active = False
        self._sequence_index = 0

    def suggest(self, state: CycleGuardState) -> Optional[str]:
        """给 LLM 的建议（提示性，不强制接管）

        当 SafetyCruise 已激活但还没到序列终点时，
        给出收束建议。

        Args:
            state: 当前循环状态

        Returns:
            建议文本，或 None（暂无建议）
        """
        if not self._active:
            return None

        r = state.round_count + 1
        remaining = len(self.FIXED_SEQUENCE) - self._sequence_index
        if remaining > 0:
            return (
                f"SafetyCruise 建议：当前第 {r} 轮，"
                f"建议执行流水线步骤 {self._sequence_index+1}/{len(self.FIXED_SEQUENCE)}: "
                f"{self.FIXED_SEQUENCE[self._sequence_index]}"
            )
        return "当前已到最后一轮，请尽快输出 DONE。"

    def override(self, state: CycleGuardState) -> Optional[Dict[str, Any]]:
        """强制按固定序列返回下一步意图

        按 FIXED_SEQUENCE 顺序依次输出意图。
        序列执行完毕后输出 DONE 并自动停用。

        Args:
            state: 当前循环状态

        Returns:
            {"intent": "...", "confidence": 1.0, "reasoning": "..."} 或 None（未激活）
        """
        if not self._active:
            return None

        if self._sequence_index >= len(self.FIXED_SEQUENCE):
            self.deactivate()
            return {"intent": "DONE", "confidence": 1.0, "reasoning": "固定流水线完成"}

        intent = self.FIXED_SEQUENCE[self._sequence_index]
        self._sequence_index += 1

        return {
            "intent": intent,
            "confidence": 0.95,
            "reasoning": f"SafetyCruise step {self._sequence_index}/{len(self.FIXED_SEQUENCE)}",
        }


# ============================================================================
# ParallelPipeline — 流水线并行化
# ============================================================================


class ParallelPipeline:
    """流水线并行化 — 并发执行多个独立卦的任务

    当安全巡航/固定流水线中有多个无数据依赖的步骤时，
    可以将它们并行派发以降低端到端延迟。

    并行组定义：
      - Group A (检索): SEARCH + SEARCH_X → 无依赖，可并行
      - Group B (后处理): REFINE + GUARD → 依赖于 A 的结果
      - Group C (终局): DECIDE + PRESENT → 依赖于 B 的结果

    使用方式：
        pipeline = ParallelPipeline(qian_gua, intent_bus, session)
        results = await pipeline.execute_parallel_group(
            intents=["SEARCH", "SEARCH_X"],
            query="..."
        )
    """

    # 可并行的意图组
    PARALLEL_GROUPS: Dict[str, List[str]] = {
        "retrieval": ["SEARCH", "SEARCH_X"],   # 检索组：本地 + 外部同时进行
        "process": ["REFINE", "GUARD"],          # 后处理组：精炼 + 安全审查
    }

    def __init__(
        self,
        qian_gua: Any,
        intent_bus: IntentBus,
        session: "QianSession",
    ) -> None:
        self._qian = qian_gua
        self._intent_bus = intent_bus
        self._session = session

    async def execute_parallel_group(
        self,
        intents: List[str],
        query: str,
    ) -> Dict[str, Dict[str, Any]]:
        """并行派发一组意图，返回每个意图的结果

        Args:
            intents: 要并发执行的意图列表
            query:   原始查询

        Returns:
            {intent: {"status": "ok"|"error", "data": ..., "error": ...}}
        """
        if not intents:
            return {}

        tasks = []
        intent_map: Dict[int, str] = {}

        for i, intent in enumerate(intents):
            target_gua = INTENT_TO_TARGET_GUA.get(intent)
            if not target_gua:
                continue
            intent_map[i] = intent
            tasks.append(
                self._dispatch_one(intent, target_gua, query)
            )

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        results: Dict[str, Dict[str, Any]] = {}
        for i, r in enumerate(results_list):
            intent = intent_map.get(i, f"unknown_{i}")
            if isinstance(r, Exception):
                results[intent] = {"status": "error", "error": str(r), "data": ""}
                logger.warning(
                    "☰ [乾] 并行派发 %s 异常: %s", intent, r
                )
            else:
                results[intent] = r

        return results

    async def _dispatch_one(
        self,
        intent: str,
        target_gua: str,
        query: str,
    ) -> Dict[str, Any]:
        """派发单个意图（内部由 execute_with_degradation 调用）"""
        signal = Signal(
            source="乾",
            target=target_gua,
            signal_type=SignalType.REQUEST,
            priority=Priority.HIGH,
            payload={"intent": intent, "query": query},
            session_id=self._session.session_id,
            ttl=30.0,
        )
        result = self._intent_bus.dispatch(signal)
        if result.status == DispatchStatus.OK and result.payload:
            return {"status": "ok", "data": result.payload.get("result", str(result.payload))}
        return {"status": "error", "error": result.error_message, "data": ""}

    @classmethod
    def get_parallel_schedule(cls, remaining_intents: List[str]) -> List[List[str]]:
        """给定剩余的意图列表，返回建议的并行执行计划

        Returns:
            [[batch1], [batch2], ...] 每个 batch 内的意图可以并行
        """
        schedule: List[List[str]] = []
        for group_name, group_intents in cls.PARALLEL_GROUPS.items():
            batch = [i for i in remaining_intents if i in group_intents]
            if batch:
                schedule.append(batch)
        # 剩余不在并行组中的意图各自单独执行
        remaining = [i for i in remaining_intents
                     if not any(i in g for g in cls.PARALLEL_GROUPS.values())]
        for intent in remaining:
            schedule.append([intent])
        return schedule


# ============================================================================
# QianSession — 会话级状态
# ============================================================================


@dataclass
class QianSession:
    """乾卦单个会话的独立状态

    每个 session_id 拥有独立的 QianSession 实例，包含循环状态、
    安全巡航状态、累积上下文等。确保并发会话之间完全隔离。

    Attributes:
        session_id:           会话标识
        query:                用户原始提问
        history:              对话历史
        cycle_state:          循环守护状态
        safety_cruise:        安全巡航实例
        accumulated_context:  累积上下文（各卦返回结果）
        final_answer:         最终答案
        created_at:           会话创建时间
        last_activity:        最后活动时间
    """

    session_id: str
    query: str
    history: List[Dict[str, str]] = field(default_factory=list)

    # 循环与安全
    cycle_state: CycleGuardState = field(default_factory=CycleGuardState)
    safety_cruise: SafetyCruise = field(default_factory=SafetyCruise)

    # 上下文累积
    accumulated_context: List[Dict[str, Any]] = field(default_factory=list)
    final_answer: Optional[str] = None

    # 时间戳
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    def add_context(self, source: str, content: Any) -> None:
        """向累积上下文添加一条信息

        Args:
            source:  信息来源（如 "SEARCH(离卦)"）
            content: 内容（字符串或可序列化对象）
        """
        self.accumulated_context.append({
            "source": source,
            "content": str(content),
            "timestamp": time.time(),
        })
        self.last_activity = time.time()

    def get_context_for_decide(self) -> str:
        """生成注入下一轮 LLM 决策的上下文摘要

        取最近 5 条累积上下文，截断过长内容。

        Returns:
            格式化的上下文字符串
        """
        if not self.accumulated_context:
            return "（尚无上下文信息）"

        lines: List[str] = []
        recent = self.accumulated_context[-5:]
        for i, item in enumerate(recent, 1):
            content = str(item["content"])
            if len(content) > 300:
                content = content[:300] + "..."
            lines.append(f"[{i}] {item['source']}: {content}")
        return "\n".join(lines)


# ============================================================================
# QianGua — 乾卦主类
# ============================================================================


class QianGua(GuaBase):
    """乾卦 ☰ — 伏羲 RAG 系统的意识中枢

    乾卦是 0 的居所，系统运行时的唯一意识中枢。
    通过 IntentBus 调度其他 7 个卦执行意图，在意图循环中完成
    从用户提问到最终答案的全过程。

    核心流程::

        用户提问
          │
          ▼
        think(query, history, session_id)
          │
          ▼
        ┌───────────── 意图循环 ─────────────┐
        │                                     │
        │  _decide() ──► 返回意图              │
        │     │                               │
        │     ├─ CycleGuard.pre_check()        │
        │     │   └─ 不通过 → SafetyCruise?    │
        │     │                               │
        │     ├─ intent == DONE?               │
        │     │   └─ 是 → _generate_final()    │
        │     │                               │
        │     ├─ intent != DONE               │
        │     │   └─ _execute_with_degradation │
        │     │       └─ dispatch_to_target_gua│
        │     │       └─ 结果注入 context       │
        │     │       └─ 回到 _decide()         │
        │     │                               │
        │     └─ 强制终止 → 降级回答             │
        └─────────────────────────────────────┘
          │
          ▼
        {"answer": "...", "rounds": N, ...}

    Usage::

        gua = QianGua(intent_bus=intent_bus)
        gua.start()

        result = await gua.think(
            query="OpenAI 的最新动态是什么？",
            history=[],
            session_id="session-123",
        )
        logger.info(f"Qian answer generated, length={len(result.get('answer', ''))}")

        gua.stop()

    Attributes:
        GUA_NAME:                   卦名 "乾"
        GUA_EMOJI:                  emoji "☰"
        GUA_DESCRIPTION:            卦述
        MAX_ROUNDS:                 最大循环轮数（默认 8）
        MAX_CONSECUTIVE_SAME:       同卦连续上限（默认 2）
        MIN_CONFIDENCE_FOR_DONE:    DONE 最低置信度（默认 0.7）
    """

    GUA_NAME: str = "乾"
    GUA_EMOJI: str = "☰"
    GUA_DESCRIPTION: str = "意识中枢 — 意图决策、调度协调、最终答案生成"

    # 配置
    MAX_ROUNDS: int = 8
    MAX_CONSECUTIVE_SAME: int = 2
    MIN_CONFIDENCE_FOR_DONE: float = 0.7

    # Level 0 固定规则序列（不调 LLM）
    FIXED_RULE_SEQUENCE: List[str] = ["SEARCH", "REFINE", "DECIDE", "PRESENT", "DONE"]

    # 健康检查常量（继承自 HeartAgent）
    BEAT_INTERVAL: float = 10.0

    def __init__(
        self,
        intent_bus: Optional[IntentBus] = None,
        intent_mode: str = "rule_based",
    ) -> None:
        """初始化乾卦

        Args:
            intent_bus: IntentBus 实例。如果为 None，使用全局单例 get_intent_bus()。
            intent_mode: 意图决策模式（来自 FUXI_INTENT_MODE 环境变量）。
                - "rule_based"（默认）：基于固定规则决策，不调 LLM（安全起步）
                - "shadow"：LLM 产生意图 → 记录到日志 → 实际执行用固定规则
                - "low_risk"：低风险场景调 LLM，其他用规则
                - "medium_risk"：大部分场景调 LLM，高风险仍用规则
                - "full_llm"：全部调 LLM 决策
        """
        super().__init__(intent_bus=intent_bus)
        # self._intent_bus 已在 GuaBase.__init__ 中设置
        self._intent_mode: str = intent_mode  # "rule_based" | "shadow" | "low_risk" | "medium_risk" | "full_llm"

        # 并发控制：限制同时进行的 think() 调用数
        self._think_semaphore: asyncio.Semaphore = asyncio.Semaphore(int(
            os.getenv("QIAN_MAX_CONCURRENT_THINK", "10")
        ))

        # 会话存储：session_id → QianSession
        self._sessions: Dict[str, QianSession] = {}

        # CycleGuard
        self._cycle_guard = CycleGuard(
            max_rounds=self.MAX_ROUNDS,
            max_consecutive_same=self.MAX_CONSECUTIVE_SAME,
            min_confidence_for_done=self.MIN_CONFIDENCE_FOR_DONE,
        )

        # ---- 新增：意图预加载缓存 ----
        self._intent_preload_cache: Dict[str, str] = _load_intent_preload_cache()

        # ---- 新增：降级监控计数器 ----
        self._degradation_counter: DegradationCounter = DegradationCounter()

        # ---- 新增：意图决策日志引擎版本 ----
        self._engine_version: str = "qian-v2.2-preload"

        # 健康检查状态（迁移自心/HeartAgent）
        self._beat_count: int = 0
        self._last_health: Dict[str, Any] = {}
        self._anomalies: List[Dict[str, Any]] = []
        self._health_running: bool = False
        self._health_task: Optional[asyncio.Task[None]] = None

    # ========================================================================
    # GuaBase 抽象方法实现
    # ========================================================================

    def _setup_degradation_rules(self) -> None:
        """注册乾卦降级规则"""
        # 规则 10: LLM 不可用时降级为固定流水线
        self.add_rule(DegradationRule(
            name="llm_unavailable",
            condition_fn=lambda: not self._is_llm_available(),
            fallback=FallbackAction(
                name="fixed_pipeline_fallback",
                handler=self._fallback_fixed_pipeline_sync,
                description="LLM 不可用时使用固定流水线",
            ),
            priority=10,
        ))

        # 规则 20: 会话过多→简化模式
        self.add_rule(DegradationRule(
            name="session_overload",
            condition_fn=lambda: len(self._sessions) > 500,
            fallback=FallbackAction(
                name="simplified_mode",
                handler=self._fallback_simplified_mode_sync,
                description="会话超载时使用简化模式",
            ),
            priority=20,
        ))

    def _execute_core(self, params: Dict[str, Any]) -> Any:
        """核心执行 — think() 的同步包装

        当通过 GuaBase.execute() 同步调用时，内部包装 think()。

        Args:
            params: {"query": "...", "history": [...], "session_id": "..."}

        Returns:
            think() 的结果 dict
        """
        query = params.get("query", "")
        history = params.get("history", [])
        session_id = params.get("session_id", "default")

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
            result = loop.run_until_complete(self.think(query, history, session_id))
        except RuntimeError:
            result = asyncio.run(self.think(query, history, session_id))

        return result

    # ========================================================================
    # 公共 API
    # ========================================================================

    async def think(
        self,
        query: str,
        history: Optional[List[Dict[str, str]]] = None,
        session_id: str = "default",
    ) -> Dict[str, Any]:
        """乾卦意识中枢 — 意图循环主入口

        对单次用户提问执行完整的意图循环：
        反复 LLM 决策 → IntentBus 派发 → 收集反馈 → 再决策，
        直到 DONE 或达到最大轮数。

        Args:
            query:      用户提问文本
            history:    对话历史 [{"role": "user"/"assistant", "content": "..."}]
            session_id: 会话标识。同一 session_id 的后续调用共享状态。

        Returns:
            {
                "answer": str,           # 最终答案文本
                "sources": [str, ...],    # 数据来源列表
                "mode": str,              # 执行模式 "qian" + intent_mode
                "confidence": float,      # 结果置信度
                "rounds": int,            # 执行轮数
                "intents_used": [str, ...],  # 使用的意图序列
                "fallback_used": bool,    # 是否使用了降级
                "elapsed_ms": float,      # 总耗时（毫秒）
            }
        """
        start_time = time.time()
        history = history or []

        # ---- 并发槽位控制：获取 Semaphore 确保不超过并发上限 ----
        acquired = False
        wait_start = time.time()
        try:
            sem_acquire_future = asyncio.ensure_future(
                self._think_semaphore.acquire()
            )
            # 最多等待 30s 获取槽位
            await asyncio.wait_for(sem_acquire_future, timeout=30.0)
            acquired = True
            wait_ms = (time.time() - wait_start) * 1000
            if wait_ms > 100:
                logger.debug(
                    "☰ [乾] Semaphore 等待 %.0fms (当前槽位: %d/%d)",
                    wait_ms,
                    self._think_semaphore._value,
                    int(os.getenv("QIAN_MAX_CONCURRENT_THINK", "10")),
                )
        except asyncio.TimeoutError:
            logger.warning(
                "☰ [乾] Semaphore 超时 (30s)，降级为同步处理",
            )
            acquired = False
        except (asyncio.TimeoutError, RuntimeError) as exc:
            logger.warning("☰ [乾] Semaphore 获取异常: %s", exc)
            acquired = False

        # ---- 每次 think() 前清理过期 session ----
        self._cleanup_expired_sessions()

        # 创建或获取会话（session-scoped）
        if session_id not in self._sessions:
            self._sessions[session_id] = QianSession(
                session_id=session_id,
                query=query,
                history=history,
            )
        session = self._sessions[session_id]

        # 确保 IntentBus 会话已打开
        self._intent_bus.open_session(session_id)

        intents_used: List[str] = []
        fallback_used = False
        final_answer = ""

        logger.info(
            "☰ [乾] Session=%s 开始意图循环 query='%s...'",
            session_id, query[:60],
        )

        try:
            # ---- 降级计数器：小时级重置 ----
            self._degradation_counter.try_hourly_reset()

            # ---- 降级计数器：记录总请求 ----
            self._degradation_counter.record_request()

            # ---- 上下文感知：读取坤卦对话历史最近 3 轮 ----
            kun_history_summary = await self._fetch_kun_history(session_id)
            if kun_history_summary:
                logger.debug("☰ [乾] 坤卦历史上下文: %d chars", len(kun_history_summary))

            # ================================================================
            # 主循环：逐轮决策 → 派发 → 收集
            # ================================================================
            while session.cycle_state.round_count < self.MAX_ROUNDS:
                # ---- SafetyCruise 接管检查 ----
                sc_override = session.safety_cruise.override(session.cycle_state)
                if sc_override is not None:
                    decision = sc_override
                    logger.info(
                        "☰ [乾] R%d SafetyCruise 接管: intent=%s",
                        session.cycle_state.round_count + 1,
                        decision["intent"],
                    )
                else:
                    # ---- 正常 LLM 决策（带入坤卦历史上下文）----
                    suggestion = session.safety_cruise.suggest(session.cycle_state)
                    decision = await self._decide(
                        query=query,
                        history=history,
                        context=session.get_context_for_decide(),
                        round_num=session.cycle_state.round_count + 1,
                        suggestion=suggestion,
                        session=session,
                        kun_history_summary=kun_history_summary,
                    )

                intent = decision.get("intent", "DONE")
                confidence = float(decision.get("confidence", 0.5))
                reasoning = str(decision.get("reasoning", ""))[:40]

                logger.info(
                    "☰ [乾] R%d 决策: intent=%s conf=%.2f reason='%s'",
                    session.cycle_state.round_count + 1,
                    intent, confidence, reasoning,
                )

                # ---- CycleGuard 预检查 ----
                passed, block_reason = self._cycle_guard.pre_check(
                    intent, confidence, session.cycle_state, query=query,
                )
                if not passed:
                    logger.warning(
                        "☰ [乾] R%d CycleGuard 拦截: %s",
                        session.cycle_state.round_count + 1, block_reason,
                    )
                    session.cycle_state.guard_intervention_count += 1

                    # 连续拦截 >2 次 → SafetyCruise 接管
                    if session.cycle_state.guard_intervention_count > 2:
                        if not session.safety_cruise.is_active:
                            session.safety_cruise.activate()
                            logger.warning("☰ [乾] SafetyCruise 激活")
                        continue

                    # 接近最大轮数时的最后一次尝试 → 强制降级
                    if session.cycle_state.round_count >= self.MAX_ROUNDS - 1:
                        fallback_used = True
                        final_answer = self._build_fallback_answer(session)
                        break
                    continue

                # 通过预检查 → 正式记录
                self._cycle_guard.record_intent(intent, session.cycle_state)
                intents_used.append(intent)

                # ---- 第九宫反馈桥接：记录每一步执行到 feedback_loop ----
                await self._evo_record_step(
                    session_id=session_id,
                    query=query,
                    intent=intent,
                    confidence=confidence,
                    round_num=session.cycle_state.round_count,
                )

                # ---- 检查 DONE ----
                if intent == "DONE":
                    final_answer = await self._generate_final_answer(session)
                    break

                # ---- 派发意图到目标卦 ----
                if intent in INTENT_TO_TARGET_GUA:
                    dispatch_result = await self._execute_with_degradation(
                        intent=intent,
                        session=session,
                        query=query,
                    )
                    if dispatch_result.get("status") == "ok":
                        session.add_context(
                            source=f"{intent}({INTENT_TO_TARGET_GUA[intent]}卦)",
                            content=dispatch_result.get("data", ""),
                        )
                    else:
                        session.add_context(
                            source=f"{intent}({INTENT_TO_TARGET_GUA[intent]}卦)",
                            content=f"[执行异常] {dispatch_result.get('error', '未知')}",
                        )
                else:
                    logger.warning("☰ [乾] 未知意图: %s", intent)
                    session.add_context(
                        source="未知意图",
                        content=f"系统无法处理意图 '{intent}'",
                    )

            # 超过最大轮数仍未拿到答案
            if not final_answer and session.cycle_state.round_count >= self.MAX_ROUNDS:
                fallback_used = True
                final_answer = self._build_fallback_answer(session)
                logger.warning("☰ [乾] 达到最大轮数 %d，强制终止", self.MAX_ROUNDS)

        except (ImportError, ModuleNotFoundError, ValueError, TypeError, KeyError) as exc:
            logger.error("☰ [乾] 意图循环异常: %s", exc, exc_info=True)
            fallback_used = True
            final_answer = f"抱歉，处理您的请求时出错了。请稍后重试。"

        finally:
            # 释放并发槽位
            if acquired:
                self._think_semaphore.release()

        elapsed_ms = (time.time() - start_time) * 1000

        # 计算置信度
        confidence = self._compute_confidence(
            intents_used=intents_used,
            fallback_used=fallback_used,
            session=session,
        )

        # 收集信息来源
        sources = self._collect_sources(session)

        return {
            "answer": final_answer,
            "sources": sources,
            "mode": f"qian_{self._intent_mode}",
            "confidence": confidence,
            "rounds": len(intents_used),
            "intents_used": intents_used,
            "fallback_used": fallback_used,
            "elapsed_ms": round(elapsed_ms, 1),
        }

    def clear_session(self, session_id: str) -> None:
        """清理指定会话

        Args:
            session_id: 会话标识
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.debug("☰ [乾] Session %s 已清理", session_id)
        self._intent_bus.close_session(session_id)

    def clear_all_sessions(self) -> None:
        """清理所有会话"""
        for sid in list(self._sessions.keys()):
            self.clear_session(sid)

    def _cleanup_expired_sessions(self) -> None:
        """清理过期 session

        移除超过 SESSION_TTL 秒未活动的 session。
        在每次 think() 调用开头执行，防止 _sessions 字典无限增长。
        """
        now = time.time()
        expired_ids = [
            sid for sid, session in self._sessions.items()
            if now - session.last_activity > SESSION_TTL
        ]
        for sid in expired_ids:
            self.clear_session(sid)
        if expired_ids:
            logger.debug(
                "☰ [乾] TTL 清理: 移除 %d 个过期 session",
                len(expired_ids),
            )

    # ========================================================================
    # 第九宫自进化桥接方法 — 反馈记录 + 定期学习
    # ========================================================================

    async def _evo_record_step(
        self,
        session_id: str,
        query: str,
        intent: str,
        confidence: float,
        round_num: int,
    ) -> None:
        """将乾卦每一步执行结果反馈给第九宫的 feedback_loop

        每当乾卦通过 CycleGuard 后记录一条 feedback：
          - action 映射：SEARCH/SEARCH_X/REFINE/DECIDE/FUSION → "click"
          - DONE 单独记录为 "copy"（表示用户最终获得了答案）
          - metadata 中包含 round_num、intent、confidence 等信息供 learner 分析

        同时，每次记录后检查是否需要触发定期学习（默认每小时）。

        Args:
            session_id: 会话 ID
            query:      用户原始查询
            intent:     当前意图
            confidence: LLM 决策置信度
            round_num:  当前轮数
        """
        if not _EVO_FEEDBACK_AVAILABLE:
            return

        action = "copy" if intent == "DONE" else "click"

        try:
            await _evo_record_feedback(
                user_id=session_id,
                query=query,
                action=action,
                metadata={
                    "step": intent,
                    "round": round_num,
                    "qian_confidence": confidence,
                    "source": "qian_think_loop",
                },
            )
        except (ImportError, ModuleNotFoundError, ValueError, TypeError) as exc:
            logger.debug("☰ [乾] 反馈桥接记录异常（非致命）: %s", exc)

        # 每次记录后检查是否需要触发定期学习
        await self._evo_maybe_learn(session_id)

    async def _evo_maybe_learn(self, session_id: str) -> None:
        """定期从 feedback 中学习新规则（默认每小时触发一次）

        检查 learner 是否可用，并基于反馈日志中最近的数据触发学习。
        使用 _evo_last_learn_time 控制频率，避免过于频繁。
        """
        if not _LEARN_BUFFER_AVAILABLE or _learn_buffer is None:
            return

        now = time.time()
        if not hasattr(self, "_evo_last_learn_time"):
            self._evo_last_learn_time: float = 0.0

        # 每小时最多学习一次
        LEARN_INTERVAL = 3600.0
        if now - self._evo_last_learn_time < LEARN_INTERVAL:
            return

        self._evo_last_learn_time = now

        try:
            if len(_learn_buffer) > 0:
                from src.evolution.learner import EvolutionLearner
                learner = EvolutionLearner()
                buffer_copy = list(_learn_buffer)
                _learn_buffer.clear()
                result = await learner.learn_from_feedback(buffer_copy)
                logger.info(
                    "☰ [乾] 定期学习触发: processed=%d terms_updated=%d",
                    result.get("processed", 0),
                    result.get("terms_updated", 0),
                )

                # 学习完成后触发 evolver 调参
                await self._evo_maybe_evolve()

        except (ImportError, ModuleNotFoundError, ValueError) as exc:
            logger.debug("☰ [乾] 定期学习检查异常（非致命）: %s", exc)

    async def _evo_maybe_evolve(self) -> None:
        """根据 learner 输出自动调参（知识图谱增量更新）

        当 learner 更新了术语权重后，检查是否需要触发知识图谱进化。
        从反馈日志中提取新实体并更新知识图谱。
        """
        try:
            from src.services.learner import load_term_weights
            from src.evolution.evolver import EvolutionEvolver
            weights = load_term_weights()

            # 如果有显著变化的术语（权重 > 0.5），视作新发现实体
            new_terms = {
                k: v for k, v in weights.items()
                if abs(v) > 0.5
            }

            if new_terms:
                evolver = EvolutionEvolver()
                # 将高频术语作为实体候选推送给 evolver
                entities = {"term": list(new_terms.keys())}
                result = evolver.evolve(entities, file_name="auto_tune_from_learner")
                if result.get("entities_added", 0) > 0:
                    logger.info(
                        "☰ [乾] 自动调参完成: entities_added=%d",
                        result.get("entities_added", 0),
                    )
        except (ImportError, ModuleNotFoundError, ValueError, KeyError) as exc:
            logger.debug("☰ [乾] 自动调参异常（非致命）: %s", exc)

    # ========================================================================
    # 辅助方法 — 置信度计算 & 来源收集
    # ========================================================================

    def _compute_confidence(
        self,
        intents_used: List[str],
        fallback_used: bool,
        session: QianSession,
    ) -> float:
        """计算本轮思考的置信度

        基于以下因素加权计算：
          - 是否使用降级（严重扣分）
          - 意图执行轮数（轮数越少越自信）
          - 是否有检索结果（有无上下文）
          - 最终答案是否非空

        Args:
            intents_used:  已使用的意图序列
            fallback_used: 是否触发降级
            session:       当前会话

        Returns:
            置信度 [0.0, 1.0]
        """
        if fallback_used:
            return 0.3

        score = 0.5  # 基础分

        # 有检索 → 加分
        if any(i in ("SEARCH", "SEARCH_X") for i in intents_used):
            score += 0.15

        # 有精炼决策 → 加分
        if any(i in ("REFINE", "DECIDE") for i in intents_used):
            score += 0.10

        # 轮数惩罚（轮数越多扣分越多）
        rounds = len(intents_used)
        if rounds <= 3:
            score += 0.10
        elif rounds <= 5:
            score += 0.05
        else:
            score -= 0.05 * (rounds - 5)

        # 有最终答案 → 加分
        if session.final_answer and len(session.final_answer) > 20:
            score += 0.10

        # 有上下文 → 加分
        if session.accumulated_context:
            score += 0.05

        return min(max(round(score, 2), 0.0), 1.0)

    @staticmethod
    def _collect_sources(session: QianSession) -> List[str]:
        """从会话累积上下文中提取来源列表

        去重并过滤掉异常来源（如 '[执行异常]'），返回干净来源列表。

        Args:
            session: 当前会话

        Returns:
            来源字符串列表，如 ["SEARCH(离卦)", "REFINE(巽卦)"]
        """
        seen: set = set()
        sources: list = []
        for item in session.accumulated_context:
            source = item.get("source", "")
            if source and source not in seen and "[执行异常]" not in source:
                seen.add(source)
                sources.append(source)
        return sources

    # ========================================================================
    # 内部方法 — LLM 决策
    # ========================================================================

    async def _decide(
        self,
        query: str,
        history: List[Dict[str, str]],
        context: str,
        round_num: int,
        suggestion: Optional[str] = None,
        session: Optional[QianSession] = None,
        kun_history_summary: str = "",
    ) -> Dict[str, Any]:
        """意图决策（支持 5 阶段 intent_mode + 预加载缓存 + 上下文感知）

        intent_mode 决定是否调用 LLM：
          - "rule_based"（默认）：走固定规则，不调 LLM（安全起步）
          - "shadow"：LLM 产生意图 → 记录差异日志 → 实际执行固定规则
          - "low_risk"：低风险场景调 LLM，其他用规则
          - "medium_risk"：大部分调 LLM，高风险仍用规则
          - "full_llm"：全部调 LLM 决策

        Args:
            query:                用户原始提问
            history:              对话历史
            context:              累积上下文（之前各卦返回的结果汇总）
            round_num:            当前轮数（1-based）
            suggestion:           SafetyCruise 建议文本（可选）
            session:              当前 QianSession（用于注入运行时状态）
            kun_history_summary:  坤卦对话历史摘要（上下文感知）

        Returns:
            {"intent": "SEARCH|...|DONE", "confidence": 0.85, "reasoning": "..."}
        """
        # ---- intent_mode 分支 ----
        if self._intent_mode == "rule_based":
            return self._decide_fixed_rule(round_num, context, suggestion)

        if self._intent_mode == "shadow":
            # 影子模式：LLM 产生意图 → 记录日志 → 实际执行固定规则
            rule_decision = self._decide_fixed_rule(round_num, context, suggestion)
            # 异步记录 LLM 决策（不阻塞）
            asyncio.ensure_future(
                self._shadow_compare(
                    query=query,
                    history=history,
                    context=context,
                    round_num=round_num,
                    suggestion=suggestion,
                    session=session,
                    kun_history_summary=kun_history_summary,
                    rule_decision=rule_decision,
                )
            )
            return rule_decision

        # ---- low_risk / medium_risk / full_llm: LLM 驱动路径 ----
        # ---- 首轮意图预加载缓存检查（仅 R1 检测，减少 LLM 调用）----
        if round_num == 1:
            preload_intent = _match_intent_preload(query.strip(), self._intent_preload_cache)
            if preload_intent and preload_intent in AVAILABLE_TRIGRAMS:
                logger.info(
                    "☰ [乾] 意图预加载命中: query='%s...' → intent=%s",
                    query.strip()[:30], preload_intent,
                )
                # 记录决策日志
                self._log_intent_decision(
                    session_id=session.session_id if session else "unknown",
                    query=query,
                    intent=preload_intent,
                    confidence=0.98,
                    reasoning="预加载缓存命中",
                )
                return {
                    "intent": preload_intent,
                    "confidence": 0.98,
                    "reasoning": "预加载缓存命中",
                }

        # ---- LLM 驱动路径 ----
        # 构建运行时状态摘要（注入到系统 Prompt）
        runtime_state = self._build_runtime_state(round_num, session)
        filled_prompt = _QIAN_SYSTEM_PROMPT.replace(
            "{runtime_state}", runtime_state
        )

        # 构建 user message
        parts: List[str] = [f"## 用户原始提问\n{query}\n"]

        # ---- 上下文感知：注入坤卦对话历史摘要 ----
        if kun_history_summary and round_num == 1:
            parts.append(f"## 对话历史上下文\n{kun_history_summary}\n")
            parts.append(
                "## 上下文感知指引\n"
                "- 若历史上下文中出现与当前提问紧密相关的对话，则这很可能是追问，"
                "请优先沿用与历史相同的检索策略（SEARCH → ...）\n"
                "- 若历史上下文与当前提问无明显关联，则这是新话题，"
                "请按常规首轮决策方式处理\n"
            )

        if context and context != "（尚无上下文信息）":
            parts.append(f"## 已获取的信息\n{context}\n")

        parts.append(f"## 当前状态\n第 {round_num}/{self.MAX_ROUNDS} 轮\n")

        if suggestion:
            parts.append(f"## 提示\n{suggestion}\n")

        parts.append("请输出下一步决策（仅 JSON）：")
        user_message = "\n".join(parts)

        try:
            raw = await self._call_llm_with_retry(
                system_prompt=filled_prompt,
                user_message=user_message,
                max_tokens=200,
                temperature=0.1,
                task_type="planning",
                session_id=session.session_id if session else "default",
            )

            if not raw:
                logger.warning("☰ [乾] LLM 返回空，使用决策兜底")
                return self._decide_fallback(round_num)

            parsed = self._parse_decide_output(raw, round_num)

            # ---- 决策日志记录 ----
            self._log_intent_decision(
                session_id=session.session_id if session else "unknown",
                query=query,
                intent=parsed.get("intent", "UNKNOWN"),
                confidence=float(parsed.get("confidence", 0.5)),
                reasoning=str(parsed.get("reasoning", ""))[:100],
            )

            return parsed

        except (ImportError, ModuleNotFoundError, json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.error("☰ [乾] LLM 调用异常: %s", exc)
            return self._decide_fallback(round_num)

    # ========================================================================
    # 内部方法 — 运行时状态摘要
    # ========================================================================

    def _build_runtime_state(
        self,
        round_num: int,
        session: Optional[QianSession] = None,
    ) -> str:
        """构建运行时状态摘要，注入到系统 Prompt

        包括：
          - 当前轮数 / 最大轮数
          - 各卦的 health_level 与断路器状态
          - 已拦截次数
          - 系统建议

        Args:
            round_num: 当前轮数
            session:   当前会话（用于获取拦截次数等）

        Returns:
            Markdown 格式的运行时状态字符串
        """
        lines: List[str] = []
        lines.append("\n## 当前系统状态")
        lines.append(f"- 轮次: {round_num}/{self.MAX_ROUNDS}")

        # 各卦的健康与断路器状态
        lines.append("- 可用卦状态:")

        # 意图→卦名→中文描述的查询表
        intent_to_pairs: List[Tuple[str, str, str]] = [
            ("SEARCH",   "巽", "搜索"),
            ("SEARCH_X", "坎", "外部搜索"),
            ("REFINE",   "坎", "精炼"),
            ("DECIDE",   "乾", "决策"),
            ("FUSION",   "离", "融合"),
            ("UPLOAD",   "震", "消化启动"),
            ("GUARD",    "艮", "安全"),
            ("PRESENT",  "兑", "输出"),
        ]

        for intent, gua_name, gua_label in intent_to_pairs:
            health_str = self._get_gua_health_summary(gua_name)
            circuit_status = self._get_gua_circuit_status(intent)
            cb_tag = "OPEN(断路)" if circuit_status == "open" else "CLOSED"
            lines.append(
                f"  - {gua_name}({gua_label}/{intent}): {health_str}, 断路器: {cb_tag}"
            )

        # 已拦截次数
        if session is not None:
            guard_count = session.cycle_state.guard_intervention_count
            lines.append(f"- 已拦截次数: {guard_count}")
            if guard_count > 0:
                lines.append(
                    f"- 系统建议: CycleGuard 已拦截 {guard_count} 次，"
                    f"请避免重复同样错误"
                )

        return "\n".join(lines)

    def _get_gua_health_summary(self, gua_name: str) -> str:
        """获取某个卦的健康摘要字符串

        Args:
            gua_name: 卦名（中文）

        Returns:
            "FULL" | "DEGRADED" | "MINIMAL" | "OFF" | "UNKNOWN"
        """
        try:
            registered = self._intent_bus.get_registered_guas() if self._intent_bus else []
            if gua_name in registered:
                return "FULL"
            return "UNREGISTERED"
        except (ImportError, ModuleNotFoundError, ValueError, KeyError, AttributeError):
            return "UNKNOWN"

    def _get_gua_circuit_status(self, intent: str) -> str:
        """获取某个意图对应目标卦的断路器状态

        Args:
            intent: 意图名称

        Returns:
            "open" | "closed" | "unknown"
        """
        target_gua = INTENT_TO_TARGET_GUA.get(intent)
        if not target_gua:
            return "unknown"
        try:
            dep = self.get_dependency(target_gua)
            if dep is not None:
                return "open" if dep.circuit_state == CircuitState.OPEN else "closed"
            return "closed"  # 未注册断路器即视为正常
        except (ImportError, ModuleNotFoundError, ValueError, KeyError, AttributeError):
            return "unknown"

    # ========================================================================
    # 内部方法 — Level 0 固定规则决策（不调 LLM）
    # ========================================================================

    def _decide_fixed_rule(
        self,
        round_num: int,
        context: str = "",
        suggestion: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Level 0 固定规则决策 — 完全基于规则，不调 LLM

        按 FIXED_RULE_SEQUENCE 顺序依次输出意图，
        序列执行完毕后输出 DONE。

        FIXED_RULE_SEQUENCE = ["SEARCH", "REFINE", "DECIDE", "PRESENT", "DONE"]

        对每个步骤：
          - SEARCH:     confidence=0.95, reasoning="固定规则-检索知识库"
          - REFINE:     confidence=0.92, reasoning="固定规则-精炼排序"
          - DECIDE:     confidence=0.90, reasoning="固定规则-综合判断"
          - PRESENT:    confidence=0.88, reasoning="固定规则-输出答案"
          - DONE:       confidence=0.95, reasoning="固定规则-流程结束"

        Args:
            round_num:  当前轮数（1-based）
            context:    累积上下文（参考用）
            suggestion: SafetyCruise 建议（参考用）

        Returns:
            {"intent": "...", "confidence": ..., "reasoning": "..."}
        """
        # 将轮数映射到固定序列索引（0-based）
        seq_index = round_num - 1
        seq_len = len(self.FIXED_RULE_SEQUENCE)

        # 如果轮数超过序列长度 → DONE
        if seq_index >= seq_len:
            return {
                "intent": "DONE",
                "confidence": 1.0,
                "reasoning": "固定规则-全部步骤完成",
            }

        intent = self.FIXED_RULE_SEQUENCE[seq_index]

        # 每个意图的描述与置信度
        step_map: Dict[str, Tuple[float, str]] = {
            "SEARCH":  (0.95, "固定规则-检索知识库"),
            "REFINE":  (0.92, "固定规则-精炼排序"),
            "DECIDE":  (0.90, "固定规则-综合判断"),
            "PRESENT": (0.88, "固定规则-输出答案"),
            "DONE":    (0.95, "固定规则-流程结束"),
        }

        confidence, reasoning = step_map.get(
            intent, (0.85, f"固定规则-{intent}")
        )

        logger.info(
            "☰ [乾] _decide_fixed_rule R%d: intent=%s conf=%.2f",
            round_num, intent, confidence,
        )

        return {
            "intent": intent,
            "confidence": confidence,
            "reasoning": reasoning,
        }

    def _parse_decide_output(self, raw: str, round_num: int) -> Dict[str, Any]:
        """解析 LLM 决策输出为标准化 dict

        Args:
            raw:       LLM 原始输出
            round_num: 当前轮数

        Returns:
            {"intent": "...", "confidence": ..., "reasoning": "..."}
        """
        # 清理 markdown 代码块
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            # 尝试提取 JSON 子串
            json_match = re.search(r'\{[^{}]*"intent"[^{}]*\}', cleaned)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    return self._decide_fallback(round_num)
            else:
                return self._decide_fallback(round_num)

        intent = parsed.get("intent", "DONE")
        confidence = float(parsed.get("confidence", 0.5))
        reasoning = str(parsed.get("reasoning", ""))[:40]

        # 验证意图有效性
        if intent not in AVAILABLE_TRIGRAMS:
            logger.warning("☰ [乾] 无效意图 '%s'，使用兜底", intent)
            return self._decide_fallback(round_num)

        return {
            "intent": intent,
            "confidence": min(max(confidence, 0.0), 1.0),
            "reasoning": reasoning,
        }

    def _decide_fallback(self, round_num: int) -> Dict[str, Any]:
        """决策兜底逻辑 — 根据当前轮数返回合理默认意图

        Args:
            round_num: 当前轮数（1-based）

        Returns:
            兜底意图 dict
        """
        if round_num == 1:
            return {"intent": "SEARCH", "confidence": 0.6, "reasoning": "首轮兜底检索"}
        elif round_num >= self.MAX_ROUNDS - 1:
            return {"intent": "DONE", "confidence": 0.7, "reasoning": "最终轮兜底结束"}
        else:
            return {"intent": "PRESENT", "confidence": 0.5, "reasoning": "兜底尝试输出"}

    # ========================================================================
    # 内部方法 — 影子模式对比
    # ========================================================================

    async def _shadow_compare(
        self,
        query: str,
        history: List[Dict[str, str]],
        context: str,
        round_num: int,
        suggestion: Optional[str],
        session: Optional[QianSession],
        kun_history_summary: str,
        rule_decision: Dict[str, Any],
    ) -> None:
        """影子模式：LLM 产生意图 → 记录差异 → 实际执行用固定规则

        日志记录 LLM 决策 vs 固定规则差异到 data/shadow_decisions.jsonl。
        这是渐进释放策略的核心：先看 LLM 想做什么，再逐步放权。

        Args:
            query:                用户提问
            history:              对话历史
            context:              累积上下文
            round_num:            当前轮数
            suggestion:           SafetyCruise 建议
            session:              当前会话
            kun_history_summary:  坤卦历史
            rule_decision:        固定规则决策结果
        """
        try:
            # 走 LLM 决策路径（不阻塞主流程）
            runtime_state = self._build_runtime_state(round_num, session)
            filled_prompt = _QIAN_SYSTEM_PROMPT.replace(
                "{runtime_state}", runtime_state
            )

            parts: List[str] = [f"## 用户原始提问\n{query}\n"]
            if context and context != "（尚无上下文信息）":
                parts.append(f"## 已获取的信息\n{context}\n")
            parts.append(f"## 当前状态\n第 {round_num}/{self.MAX_ROUNDS} 轮\n")
            if suggestion:
                parts.append(f"## 提示\n{suggestion}\n")
            parts.append("请输出下一步决策（仅 JSON）：")
            user_message = "\n".join(parts)

            llm_raw = await self._call_llm_with_retry(
                system_prompt=filled_prompt,
                user_message=user_message,
                max_tokens=200,
                temperature=0.1,
                task_type="planning",
                session_id=session.session_id if session else "shadow",
            )

            llm_decision = self._parse_decide_output(llm_raw or "", round_num)

            # 对比 LLM vs 规则
            matched = llm_decision.get("intent") == rule_decision.get("intent")

            # 写入影子决策日志
            shadow_log = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
                "session_id": session.session_id if session else "unknown",
                "query_preview": query[:100],
                "round": round_num,
                "rule_intent": rule_decision.get("intent"),
                "rule_confidence": rule_decision.get("confidence"),
                "llm_intent": llm_decision.get("intent"),
                "llm_confidence": llm_decision.get("confidence"),
                "llm_reasoning": llm_decision.get("reasoning", "")[:200],
                "matched": matched,
                "engine_version": self._engine_version,
            }

            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            shadow_path = _DATA_DIR / "shadow_decisions.jsonl"
            def _write_shadow():
                with open(shadow_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(shadow_log, ensure_ascii=False) + "\n")
            await asyncio.to_thread(_write_shadow)

            logger.info(
                "☰ [乾][影子] R%d LLM→%s vs 规则→%s (match=%s)",
                round_num,
                llm_decision.get("intent"),
                rule_decision.get("intent"),
                matched,
            )

        except (ImportError, ModuleNotFoundError, json.JSONDecodeError, ValueError) as exc:
            logger.debug("☰ [乾] 影子对比异常（非致命）: %s", exc)

    # ========================================================================
    # 内部方法 — 三层降级执行
    # ========================================================================

    async def _execute_with_degradation(
        self,
        intent: str,
        session: QianSession,
        query: str,
    ) -> Dict[str, Any]:
        """三层降级执行意图

        L1: 正常 IntentBus.dispatch()（带重试 + 指数退避）
        L2: ShaoyinBrain 固定流水线（直接 LLM 回答）
        L3: 兜底直答（纯文本降级响应）

        Args:
            intent:  目标意图名称
            session: 当前会话
            query:   用户提问

        Returns:
            {"status": "ok"|"error", "data": ..., "error": "...", "degraded": bool}
        """
        target_gua = INTENT_TO_TARGET_GUA.get(intent)
        if not target_gua:
            return {"status": "error", "error": f"意图 {intent} 无对应目标卦", "data": "", "degraded": False}

        # ---- L1: 正常 dispatch（带重试+指数退避） ----
        result = await self._dispatch_with_retry(
            intent=intent,
            target_gua=target_gua,
            session_id=session.session_id,
            query=query,
        )
        if result.status == DispatchStatus.OK and result.payload:
            return {
                "status": "ok",
                "data": result.payload.get("result", str(result.payload)),
                "degraded": False,
            }

        # ---- L1 失败记录 ----
        self._degradation_counter.record_l1_failure()
        logger.warning("☰ [乾] L1 dispatch 失败 (%s), 进入 L2 降级", result.status.value)

        # ---- L2: ShaoyinBrain 固定流水线 ----
        self._degradation_counter.record_l2_trigger()
        l2_result = await self._shaoyin_brain_fallback(intent, query)
        if l2_result:
            # ---- L2 超频告警 - 通知艮卦 ----
            await self._check_and_alert_degradation_l2()
            return {"status": "ok", "data": l2_result, "degraded": True}

        logger.warning("☰ [乾] L2 ShaoyinBrain 失败, 进入 L3 兜底")

        # ---- L3: 兜底直拼（检索结果拼接 prompt，不调 LLM） ----
        self._degradation_counter.record_l3_trigger()
        l3_data = await self._l3_no_llm_fallback(intent, session, query)
        return {
            "status": "ok",
            "data": l3_data,
            "degraded": True,
            "level": 3,
        }

    async def _dispatch_with_retry(
        self,
        intent: str,
        target_gua: str,
        session_id: str,
        query: str,
    ) -> IntentResult:
        """L1 调度：带重试 + 指数退避的 dispatch

        尝试 3 次，延时分别 1s / 2s / 4s。

        当 SEARCH→巽时，payload 中包含 operation="search"、query、top_k，
        确保巽卦的 _execute_core 能路由到本地 ChromaDB 检索路径。

        Args:
            intent:      意图名称
            target_gua:  目标卦名
            session_id:  会话 ID
            query:       原始查询

        Returns:
            IntentResult
        """
        last_result: Optional[IntentResult] = None
        retry_delays = [1.0, 2.0, 4.0]

        for attempt in range(3):
            # 构建 payload：SEARCH→巽 需要 operation="search" + query + top_k
            payload: Dict[str, Any] = {
                "intent": intent,
                "query": query,
                "attempt": attempt + 1,
            }
            if intent == "SEARCH" and target_gua == "巽":
                payload["operation"] = "search"
                payload["top_k"] = 5

            signal = Signal(
                source="乾",
                target=target_gua,
                signal_type=SignalType.REQUEST,
                priority=Priority.HIGH,
                payload=payload,
                session_id=session_id,
                ttl=30.0,
            )

            last_result = self._intent_bus.dispatch(signal)

            if last_result.status == DispatchStatus.OK:
                return last_result

            if last_result.status == DispatchStatus.CIRCUIT_OPEN:
                logger.warning(
                    "☰ [乾] 断路器断开 %s→%s，跳过重试",
                    "乾", target_gua,
                )
                break

            if attempt < 2:
                delay = retry_delays[attempt]
                logger.info(
                    "☰ [乾] dispatch 重试 %d/2 (delay=%.1fs): %s→%s",
                    attempt + 1, delay, "乾", target_gua,
                )
                await asyncio.sleep(delay)

        return last_result or IntentResult(
            status=DispatchStatus.UNKNOWN_ERROR,
            error_message="所有重试耗尽",
        )

    async def _shaoyin_brain_fallback(
        self, intent: str, query: str
    ) -> Optional[str]:
        """L2: ShaoyinBrain — 简化流水线回答

        当 IntentBus dispatch 失败时，直接用 LLM 回答作为降级方案。
        不使用复杂决策，简化为：问题 → LLM 直接回答。

        Args:
            intent: 原始意图
            query:  用户提问

        Returns:
            回答文本或 None
        """
        try:
            prompt = f"""基于以下信息，用简洁中文直接回答用户问题。

## 用户问题
{query}

## 要求
- 直接回答，不要反问
- 如果不确定，诚实说明
- 回答字数控制在 200 字以内"""

            answer = await self._call_llm_with_retry(
                system_prompt="你是一个企业知识助手，用简洁中文直接回答问题。",
                user_message=prompt,
                max_tokens=300,
                temperature=0.3,
                task_type="synthesis",
                session_id="l2_fallback",
            )
            return answer if answer else None

        except (ImportError, ModuleNotFoundError, ValueError, KeyError) as exc:
            logger.error("☰ [乾] ShaoyinBrain 降级异常: %s", exc)
            return None

    async def _l3_no_llm_fallback(
        self, intent: str, session: QianSession, query: str
    ) -> str:
        """L3 兜底直拼: 检索结果拼接 prompt，完全不调 LLM

        当 L1 全部模型失败 + L2 固定流水线也失败时，
        直接将已有的检索上下文拼接成结构化回复，
        不再调用任何 LLM 端点。

        这是最后的降级安全网，保证用户始终能得到有内容的回复。

        Args:
            intent:  原始意图
            session: 当前会话
            query:   用户提问

        Returns:
            拼接后的回答文本
        """
        if session.accumulated_context:
            # 有检索结果 → 直接拼接
            context_items = session.accumulated_context[-5:]
            parts = [f"关于「{query[:80]}」的检索结果：\n"]
            for i, item in enumerate(context_items, 1):
                source = item.get("source", "未知来源")
                content = str(item.get("content", ""))[:300]
                parts.append(f"[{i}] {source}: {content}")
            parts.append(
                "\n（注: 此回答由系统在降级模式下自动拼接，未经过 LLM 处理，建议稍后重试。）"
            )
            return "\n".join(parts)
        else:
            # 无检索结果 → 返回引导性提示
            return (
                f"关于「{query[:80]}」，系统当前无法获取相关信息。\n"
                "可能原因：\n"
                "- 知识库中暂无相关文档\n"
                "- 当前服务处于降级模式\n\n"
                "建议：\n"
                "1. 尝试换一种方式提问\n"
                "2. 确认知识库已上传相关文档\n"
                "3. 稍后重试"
            )

    # ========================================================================
    # 内部方法 — 最终答案生成
    # ========================================================================

    async def _generate_final_answer(self, session: QianSession) -> str:
        """DONE 时生成最终答案

        将累积上下文 + 对话历史合并，调用 LLM 生成最终回答。
        实现"调用离卦（decide）生成最终答案"的要求。

        Args:
            session: 当前会话

        Returns:
            最终答案文本
        """
        context_text = session.get_context_for_decide()

        prompt_parts: List[str] = [
            f"## 用户原始提问\n{session.query}\n",
        ]
        if context_text and context_text != "（尚无上下文信息）":
            prompt_parts.append(f"## 已获取的信息\n{context_text}\n")
        prompt_parts.append(
            "## 任务\n基于以上信息，用专业、准确的中文生成最终回答。"
            "请综合所有来源信息，给出完整答案。如果信息不足，诚实说明。"
        )
        user_message = "\n".join(prompt_parts)

        try:
            answer = await self._call_llm_with_retry(
                system_prompt=(
                    "你是伏羲，企业知识认知中枢。"
                    "专业、精准、有来源。不确定时诚实说明。"
                ),
                user_message=user_message,
                max_tokens=1024,
                temperature=0.3,
                task_type="synthesis",
                session_id=session.session_id,
            )
            if answer:
                session.final_answer = answer
                return answer
        except (ImportError, ModuleNotFoundError, ValueError, KeyError) as exc:
            logger.error("☰ [乾] 生成最终答案异常: %s", exc)

        # 兜底
        fallback = self._build_fallback_answer(session)
        session.final_answer = fallback
        return fallback

    def _build_fallback_answer(self, session: QianSession) -> str:
        """构建兜底答案

        当所有路径失败或超过最大轮数时，基于已有信息生成简化的文字回复。

        Args:
            session: 当前会话

        Returns:
            兜底答案文本
        """
        if session.accumulated_context:
            last_info = str(session.accumulated_context[-1]["content"])[:500]
            return (
                f"以下是根据已有信息整理的回答：\n\n"
                f"{last_info}\n\n"
                f"（注：此回答基于部分检索结果，可能不完整。）"
            )
        return (
            f"关于「{session.query[:100]}」，"
            f"暂时无法获取足够的信息来回答。请尝试换一种方式提问。"
        )

    # ========================================================================
    # 内部方法 — 上下文感知（坤卦对话历史）
    # ========================================================================

    async def _fetch_kun_history(self, session_id: str) -> str:
        """从坤卦读取最近 3 轮对话历史，生成上下文摘要

        通过 IntentBus dispatch 调用坤卦的 recall_conversation，
        取最近 6 条记录（每轮 user+assistant 为 2 条即 3 轮），
        生成压缩摘要注入到乾卦决策 Prompt。

        Args:
            session_id: 会话标识

        Returns:
            对话历史摘要文本，或空字符串（坤卦不可用时）
        """
        try:
            signal = Signal(
                source="乾",
                target="坤",
                signal_type=SignalType.REQUEST,
                priority=Priority.NORMAL,
                payload={
                    "action": "recall_conversation",
                    "session_id": session_id,
                    "n": 6,
                },
                session_id=session_id,
                ttl=5.0,
            )
            result = self._intent_bus.dispatch(signal)
            if result.status != DispatchStatus.OK or not result.payload:
                return ""

            data = result.payload.get("result", result.payload)
            if isinstance(data, dict):
                history_list = data.get("history", [])
            elif isinstance(data, list):
                history_list = data
            else:
                return ""

            if not history_list:
                return ""

            lines: List[str] = ["最近对话记录："]
            for i, msg in enumerate(history_list[-6:], 1):
                role = msg.get("role", "unknown") if isinstance(msg, dict) else "unknown"
                content = str(msg.get("content", "")) if isinstance(msg, dict) else str(msg)
                if len(content) > 100:
                    content = content[:100] + "..."
                lines.append(f"  [{role}]: {content}")

            summary = "\n".join(lines)
            logger.debug("☰ [乾] 坤卦历史摘要: %d 条记录, %d chars",
                         len(history_list), len(summary))
            return summary

        except (ImportError, ModuleNotFoundError, ValueError, KeyError) as exc:
            logger.debug("☰ [乾] 读取坤卦历史失败: %s", exc)
            return ""

    # ========================================================================
    # 内部方法 — 意图决策日志（结构化 JSONL）
    # ========================================================================

    def _log_intent_decision(
        self,
        session_id: str,
        query: str,
        intent: str,
        confidence: float,
        reasoning: str,
    ) -> None:
        """记录一条结构化的意图决策到 JSONL 文件

        每条记录字段：
          timestamp:      ISO 8601 时间戳
          session_id:     会话 ID
          query_hash:     query 的 MD5 哈希
          query_preview:  query 的前 100 字符
          intent:         决策意图
          confidence:     决策置信度
          reasoning:      决策理由
          engine_version: 引擎版本号
          model_mode:     intent_mode 模式
        """
        try:
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            record = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
                "session_id": session_id,
                "query_hash": hashlib.md5(query.encode("utf-8")).hexdigest(),
                "query_preview": query[:100],
                "intent": intent,
                "confidence": confidence,
                "reasoning": reasoning[:200],
                "engine_version": self._engine_version,
                "model_mode": self._intent_mode,
            }
            with open(_INTENT_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            logger.debug("☰ [乾] 意图决策已记录: intent=%s conf=%.2f", intent, confidence)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("☰ [乾] 记录意图决策日志失败: %s", exc)

    # ========================================================================
    # 内部方法 — 降级告警（通知艮卦）
    # ========================================================================

    async def _check_and_alert_degradation_l2(self) -> None:
        """检查 L2 降级触发率，若超阈值则向艮卦发送告警信号

        告警阈值：L2 触发频次超过 5%/hour。
        通过 IntentBus 向艮卦发送 ERROR 信号。
        """
        if not self._degradation_counter.should_alert_l2(threshold_percent=5.0):
            return

        summary = self._degradation_counter.get_summary()
        alert_msg = (
            f"[乾卦降级告警] L2 触发率超过阈值: "
            f"{summary['l2_rate_percent']}% ({summary['l2_count']}/{summary['l1_count']}), "
            f"总请求 {summary['total_requests']}"
        )
        logger.warning("☰ [乾] %s", alert_msg)

        try:
            alert = Signal(
                source="乾",
                target="艮",
                signal_type=SignalType.ERROR,
                priority=Priority.HIGH,
                payload={
                    "alert_type": "degradation_l2_high_rate",
                    "message": alert_msg,
                    "summary": summary,
                },
                ttl=30.0,
            )
            self._intent_bus.dispatch(alert)
            logger.info("☰ [乾] L2 降级告警已发送至艮卦")
        except (ImportError, ModuleNotFoundError, ValueError, KeyError) as exc:
            logger.debug("☰ [乾] 发送 L2 降级告警至艮卦失败: %s", exc)

    # ========================================================================
    # 内部方法 — LLM 调用封装
    # ========================================================================

    async def dispatch_llm(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 200,
        temperature: float = 0.1,
        task_type: str = "default",
        session_id: str = "default",
        tools: Optional[list] = None,
        tool_choice: Optional[str] = None,
    ) -> Optional[str]:
        """乾卦统一 LLM 调度器 — 所有八卦 LLM 调用的唯一入口（v1.50）

        这是乾卦作为「意识中枢」的核心职能之一：统一调度所有 LLM 请求，
        包括智能模型选择、成本预算熔断、三层降级链。

        三层降级链（L1→L2→L3）:
          L1 模型重试: Mimo-pro → DeepSeek-pro → 4o-mini
          L2 固定流程: 退回硬编码 8 步规则管道
          L3 兜底直拼: 检索结果拼接 prompt 不调 LLM

        模型选择智能化:
          - JSON 提取/分类/整理 → 非 pro 版（mimo-v2.5 / mimo-v2.5-turbo）
          - 推理/综合/决策 → pro 版（mimo-v2.5-pro）
          - 轻量任务（fast_*）→ turbo（mimo-v2.5-turbo）

        Args:
            system_prompt: 系统提示
            user_message:  用户消息
            max_tokens:    最大输出 token 数
            temperature:   温度参数
            task_type:     任务类型（影响模型选择），可选值：
                             "default", "extraction", "classification", "parsing",
                             "validation", "distillation", "synthesis", "reflection",
                             "reasoning", "planning", "fast_classify", "fast_extract"
            session_id:    会话 ID（用于 TokenBudget 跟踪）
            tools:         Function calling tools 定义
            tool_choice:   工具选择策略

        Returns:
            LLM 输出文本或 None
        """
        # ---- L1 智能模型选择 ----
        model_sequence = self._select_model_chain(task_type)

        # ---- TokenBudget 检查 ----
        try:
            from src.services.llm import get_session_budget, TokenBudgetExceeded
            budget = await get_session_budget(session_id)
            warn_msg = budget.warn_if_near_limit()
            if warn_msg:
                logger.warning("☰ [乾] %s", warn_msg)
            if budget.is_tripped:
                logger.error(
                    "☰ [乾] Session=%s 预算已熔断 ¥%.4f/¥%.2f, "
                    "强制走 L2 固定流程",
                    session_id, budget.consumed_cny, budget.budget_cny,
                )
                return None  # 返回 None 触发上层 L2 降级
        except ImportError:
            budget = None

        # ---- L1: 逐模型尝试（Mimo → DeepSeek → 4o-mini） ----
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        from src.services.llm import _call_api
        from src.config import (
            MIMO_API_KEY, MIMO_BASE_URL, MIMO_TIMEOUT,
            DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_TIMEOUT,
        )

        last_error = None
        for model_name in model_sequence:
            logger.info(
                "☰ [乾] dispatch_llm L1 尝试模型=%s task=%s session=%s",
                model_name, task_type, session_id,
            )

            try:
                # 确定使用哪个 API 端点
                if model_name.startswith("mimo"):
                    if not MIMO_API_KEY:
                        logger.debug("☰ [乾] Mimo API Key 未配置，跳过 %s", model_name)
                        continue
                    result = await _call_api(
                        base_url=MIMO_BASE_URL,
                        api_key=MIMO_API_KEY,
                        model=model_name,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        timeout=MIMO_TIMEOUT,
                        tools=tools,
                        tool_choice=tool_choice,
                    )
                elif model_name.startswith("deepseek"):
                    if not DEEPSEEK_API_KEY:
                        logger.debug("☰ [乾] DeepSeek API Key 未配置，跳过 %s", model_name)
                        continue
                    result = await _call_api(
                        base_url=DEEPSEEK_BASE_URL,
                        api_key=DEEPSEEK_API_KEY,
                        model=model_name,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        timeout=DEEPSEEK_TIMEOUT,
                        tools=tools,
                        tool_choice=tool_choice,
                    )
                elif model_name == "4o-mini":
                    if not _OPENAI_4O_MINI_API_KEY:
                        logger.debug("☰ [乾] 4o-mini API Key 未配置，跳过")
                        continue
                    result = await _call_api(
                        base_url=_OPENAI_4O_MINI_BASE_URL,
                        api_key=_OPENAI_4O_MINI_API_KEY,
                        model="gpt-4o-mini",
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        timeout=_OPENAI_4O_MINI_TIMEOUT,
                        tools=tools,
                        tool_choice=tool_choice,
                    )
                else:
                    continue

                if result:
                    # 成功 → 更新预算
                    if budget is not None:
                        try:
                            budget.consume(
                                model=model_name,
                                input_chars=len(system_prompt) + len(user_message),
                                output_chars=len(result),
                            )
                        except TokenBudgetExceeded:
                            logger.warning(
                                "☰ [乾] dispatch_llm 后检查: Session=%s 预算已熔断",
                                session_id,
                            )
                            # 仍然返回结果，但下次调用会提前拦截
                    logger.info(
                        "☰ [乾] dispatch_llm OK model=%s output=%d chars",
                        model_name, len(result),
                    )
                    return result

            except (ImportError, ModuleNotFoundError, ValueError, KeyError, OSError) as exc:
                last_error = exc
                logger.warning(
                    "☰ [乾] dispatch_llm 模型 %s 异常: %s",
                    model_name, exc,
                )
                continue

        if last_error:
            logger.error("☰ [乾] dispatch_llm L1 全部模型失败: %s", last_error)
        else:
            logger.error("☰ [乾] dispatch_llm L1 全部模型不可用")

        # ---- L2: ShaoyinBrain 固定流水线（由上层调用者负责，这里返回 None） ----
        return None

    @staticmethod
    def _select_model_chain(task_type: str) -> list:
        """根据 task_type 返回模型尝试序列

        智能选择逻辑：
          - JSON 提取/分类/解析 → 非 pro 版（mimo-v2.5 / mimo-v2.5-turbo）
          - 推理/综合/决策/反思 → pro 版（mimo-v2.5-pro）
          - 所有降级链路: → deepseek-v4-pro → 4o-mini

        Args:
            task_type: 任务类型

        Returns:
            模型名列表，按优先级降序
        """
        # JSON 输出类 → 非 pro 版
        json_tasks = {"extraction", "classification", "parsing", "validation",
                       "distillation"}
        # 推理类 → pro 版
        reason_tasks = {"synthesis", "reflection", "reasoning", "planning"}
        # 轻量类 → turbo
        fast_tasks = {"fast_classify", "fast_extract"}

        if task_type in json_tasks:
            # JSON 提取：不需要昂贵的 reasoning，非 pro 版即可
            return ["mimo-v2.5", "deepseek-v4-pro", "4o-mini"]
        elif task_type in reason_tasks:
            # 推理：需要 pro 版 reasoning 能力
            return ["mimo-v2.5-pro", "deepseek-v4-pro", "4o-mini"]
        elif task_type in fast_tasks:
            # 轻量：直接 turbo
            return ["mimo-v2.5-turbo", "deepseek-v4-flash", "4o-mini"]
        else:
            # 默认
            return ["mimo-v2.5-pro", "mimo-v2.5", "deepseek-v4-pro", "4o-mini"]

    async def _call_llm_with_retry(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 200,
        temperature: float = 0.1,
        task_type: str = "default",
        session_id: str = "default",
    ) -> Optional[str]:
        """向后兼容的 LLM 调用封装 — 内部委托给 dispatch_llm()

        此方法保留原有接口，内部转发到统一的 dispatch_llm()，
        确保所有现有调用方无需改动代码。

        Args:
            system_prompt: 系统提示
            user_message:  用户消息
            max_tokens:    最大 token 数
            temperature:   温度参数
            task_type:     任务类型
            session_id:    会话 ID

        Returns:
            LLM 输出文本或 None
        """
        return await self.dispatch_llm(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=max_tokens,
            temperature=temperature,
            task_type=task_type,
            session_id=session_id,
        )

    def _is_llm_available(self) -> bool:
        """检查 LLM 服务是否可用

        用于降级规则的条件判断。

        Returns:
            True 如果有可用的 LLM API Key
        """
        try:
            from src.config import MIMO_API_KEY, DEEPSEEK_API_KEY
            return bool(MIMO_API_KEY or DEEPSEEK_API_KEY)
        except ImportError:
            return True  # 导入失败时不触发降级

    # ========================================================================
    # 降级处理器（同步，用于 GuaBase.execute()）
    # ========================================================================

    def _fallback_fixed_pipeline_sync(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """固定流水线降级处理器（同步）

        当 LLM 不可用时，返回固定流水线的简化结果。
        """
        query = params.get("query", "")
        return {
            "answer": (
                f"[降级模式] 关于「{query[:80]}」，"
                f"系统当前以固定流水线模式运行，"
                f"建议稍后重试或联系管理员。"
            ),
            "rounds": 0,
            "intents_used": ["FIXED_PIPELINE_FALLBACK"],
            "fallback_used": True,
            "elapsed_ms": 0.0,
        }

    def _fallback_simplified_mode_sync(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """简化模式降级处理器（同步）

        当会话数过多时使用简化回答。
        """
        query = params.get("query", "")
        return {
            "answer": f"[高负载模式] 收到问题「{query[:80]}」，请稍后重新提交。",
            "rounds": 0,
            "intents_used": ["SIMPLIFIED_MODE"],
            "fallback_used": True,
            "elapsed_ms": 0.0,
        }


    # ========================================================================
    # 健康检查系统（迁移自心/HeartAgent）
    # ========================================================================

    def check_health(self) -> Dict[str, Any]:
        """执行一轮全系统健康检查

        检查所有已注册卦（通过 IntentBus）的健康状态，
        以及核心服务状态。等同于原 HeartAgent._beat() 的功能。

        Returns:
            {
                "organs": {guaname: {"name": ..., "alive": bool, ...}},
                "services": {"vector_store": str, "llm": str},
                "anomalies": [str, ...],
                "timestamp": float,
                "beat_number": int,
            }
        """
        health: Dict[str, Any] = {
            "timestamp": time.time(),
            "beat_number": self._beat_count + 1,
            "organs": {},
            "services": {},
            "anomalies": [],
        }

        # 1. 检查所有已注册卦的健康状态
        try:
            registered_guas = self._intent_bus.get_registered_guas()
            for trigram_name in registered_guas:
                # 用 dispatch 的 TargetUnregistered 状态判断存活
                is_alive = trigram_name in registered_guas
                health["organs"][trigram_name] = {
                    "name": trigram_name,
                    "alive": is_alive,
                    "last_heartbeat_ago": 0.0,
                }
                if not is_alive:
                    health["anomalies"].append(
                        f"卦 {trigram_name} 无响应"
                    )
        except (ImportError, ModuleNotFoundError, ValueError, KeyError) as exc:
            logger.debug("☰ [乾] 卦健康检查异常: %s", exc)

        # 也检查自身
        health["organs"][self.GUA_NAME] = {
            "name": self.GUA_NAME,
            "alive": self._alive,
            "last_heartbeat_ago": 0.0,
        }

        # 2. 检查核心服务
        health["services"]["vector_store"] = self._check_vector_store()
        health["services"]["llm"] = self._check_llm_service()

        # 3. 处理异常
        if health["anomalies"]:
            self._heal(health["anomalies"])

        self._beat_count += 1
        self._last_health = health

        logger.info(
            "☰ [乾] 健康检查 #%d: %d 卦, %d 异常",
            self._beat_count,
            len(health["organs"]),
            len(health["anomalies"]),
        )
        return health

    def get_stats(self) -> Dict[str, Any]:
        """获取心跳统计信息

        Returns:
            {
                "beat_count": int,
                "anomalies_24h": int,
                "last_beat_ago": float,
                "running": bool,
                "alive": bool,
            }
        """
        last_beat_ago: float = 0.0
        last_ts = self._last_health.get("timestamp", 0.0)
        if last_ts > 0:
            last_beat_ago = round(time.time() - last_ts, 1)

        anomalies_24h = len([
            a for a in self._anomalies
            if time.time() - a.get("time", 0) < 86400
        ])

        return {
            "beat_count": self._beat_count,
            "anomalies_24h": anomalies_24h,
            "last_beat_ago": last_beat_ago,
            "running": self._health_running,
            "alive": self._alive,
        }

    def start_beating(self) -> None:
        """启动定时健康检查心跳

        等同于 HeartAgent.start_beating()，启动一个异步循环
        定时执行 check_health()。
        """
        if self._health_running:
            return
        self._health_running = True
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self._health_task = asyncio.ensure_future(self._beat_loop())
            else:
                self._health_task = loop.create_task(self._beat_loop())
        except RuntimeError:
            logger.debug("☰ [乾] 无事件循环，健康心跳延迟启动")
        logger.info("☰ [乾] 健康心跳已启动 (interval=%.1fs)", self.BEAT_INTERVAL)

    async def stop_beating(self) -> None:
        """停止定时健康检查心跳"""
        self._health_running = False
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.debug("☰ [乾] 健康心跳停止异常: %s", exc)
            self._health_task = None
        logger.info("☰ [乾] 健康心跳已停止")

    # ========================================================================
    # 内部方法 — 健康检查
    # ========================================================================

    async def _beat_loop(self) -> None:
        """定时心跳循环"""
        while self._health_running:
            try:
                await asyncio.sleep(self.BEAT_INTERVAL)
                self.check_health()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(
                    "☰ [乾] 心跳异常: %s", exc, exc_info=True
                )

    def _heal(self, anomalies: List[str]) -> None:
        """发现异常后发送告警信号

        迁移自 HeartAgent._heal()。
        将异常信息广播给关注异常的其他卦（如兑卦/PRESENT）。

        Args:
            anomalies: 异常描述列表
        """
        for anomaly in anomalies:
            if "LLM" in anomaly or "向量" in anomaly or "vector" in anomaly:
                logger.warning(
                    "☰ [乾] 异常告警: %s — 通知兑卦(输出层)", anomaly
                )
                try:
                    alert = Signal(
                        source="乾",
                        target="兑",
                        signal_type=SignalType.ERROR,
                        priority=Priority.HIGH,
                        payload={"message": anomaly},
                        ttl=30.0,
                    )
                    self._intent_bus.dispatch(alert)
                except (ImportError, ModuleNotFoundError, ValueError, KeyError) as exc:
                    logger.debug("☰ [乾] 告警派发异常: %s", exc)

            self._anomalies.append({
                "time": time.time(),
                "message": anomaly,
            })

    def _check_vector_store(self) -> str:
        """检查向量存储服务状态

        Returns:
            "ok" | "degraded" | "unknown"
        """
        try:
            from src.db.vector_store import VectorStore
            vs = VectorStore()
            return "ok" if vs else "ok"
        except (ImportError, ModuleNotFoundError, ValueError, KeyError) as exc:
            logger.debug("☰ [乾] 向量存储检查: %s", exc)
            return "degraded"

    def _check_llm_service(self) -> str:
        """检查 LLM 服务状态

        Returns:
            "ok" | "degraded" | "unknown"
        """
        try:
            import os
            api_key = os.getenv("DEEPSEEK_API_KEY", "")
            if api_key:
                return "ok"
            return "degraded"
        except (ImportError, ModuleNotFoundError, KeyError):
            return "unknown"


# ============================================================================
# 模块导出
# ============================================================================

__all__ = [
    "QianGua",
    "CycleGuard",
    "CycleGuardState",
    "SafetyCruise",
    "ParallelPipeline",
    "QianSession",
    "DegradationCounter",
    "AVAILABLE_TRIGRAMS",
    "INTENT_TO_TARGET_GUA",
    "FIXED_PIPELINE",
    "SESSION_TTL",
    "_match_intent_preload",
    "_load_intent_preload_cache",
    "_save_intent_preload_cache",
]