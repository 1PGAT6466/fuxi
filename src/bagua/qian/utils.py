"""
qian/utils.py - 工具函数
========================

包含意图预加载缓存、降级计数器等工具函数。
"""

from dataclasses import dataclass, field
from pathlib import Path
from src.bagua._common import (
    hashlib, json, logging, os, re, time,
    Any, Dict, List, Optional, Tuple,
)

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
