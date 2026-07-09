"""
smart_router.py — 5 层阶梯路由框架（伏羲 v2.1 Phase 0）

路由层次：
  L1: Keyword Router（关键词路由，<5ms）
      预定义关键词字典 → 模板回复，正则匹配 + 哈希查找
  L2: Template Router（模板路由，<10ms）
      意图模板库 → 模板匹配 + 实体提取
  L3: Cache Router（缓存路由，<50ms）
      三层缓存：完全匹配(md5) / 语义相似(embedding cosine>0.92) / 意图路径匹配
      TTL：L1精确缓存 5min / L2语义缓存 10min
      上下文一致性检查
  L4: Small Model Router（Flash 模型路由，1-2s）
      DeepSeek V4 Flash 做意图分类，输出预锁定为 JSON
  L5: Full Model Router（全模型路由，2-5s）
      Mimo 全参数模型，最终兜底

升级判定逻辑：
  L1→L2：关键词不在预定义字典中
  L2→L3：无匹配模板 或 置信度 < 0.85
  L3→L4：缓存未命中 或 上下文变化 或 TTL 过期
  L4→L5：Flash 输出格式异常 或 置信度低(<0.7) 或 intent="reason"

不依赖 organs/ 或 Meridian，仅依赖 src/services/llm.py 的 _call_api。
"""


import asyncio
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ============================================================================
# 数据结构
# ============================================================================


@dataclass
class RoutingDecision:
    """每一层路由的返回结构"""

    level: int  # 1-5，命中层级
    result: Any  # 路由结果：模板回复 / 意图标签 / 缓存答案 / LLM 输出等
    confidence: float  # 0.0 - 1.0
    should_upgrade: bool  # 是否需要升级到下一层
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CacheEntry:
    """缓存条目"""

    key: str
    result: Any
    confidence: float
    created_at: float
    ttl: float
    context_hash: Optional[str] = None


# ============================================================================
# 文本预处理
# ============================================================================


def _normalize_text(text: str) -> str:
    """文本预处理：去首尾空格、统一全角半角、去多余空白"""
    text = text.strip()
    text = text.replace("\uff01", "!").replace("\uff1f", "?").replace("\uff0c", ",")
    text = text.replace("\u3002", ".").replace("\uff02", '"').replace("\uff07", "'")
    text = text.replace("\uff1a", ":").replace("\uff1b", ";")
    text = re.sub(r"\s+", " ", text)
    return text


# ============================================================================
# L1: Keyword Router（关键词路由，<5ms）
# ============================================================================

_KEYWORD_DICT: Dict[str, str] = {
    "你好": "你好！我是伏羲，有什么可以帮你的？",
    "您好": "您好！需要我做什么？",
    "hi": "Hi there! 有什么可以帮你的？",
    "hello": "Hello! How can I assist you today?",
    "嗨": "嗨！我在呢～",
    "早上好": "早上好！今天有什么计划？",
    "晚上好": "晚上好！还在工作吗？",
    "午安": "午安！休息一下再继续吧。",
    "在吗": "我在的，随时可以问我问题。",
    "在不在": "在呢，有什么想问的？",
    "再见": "再见！随时回来找我。",
    "拜拜": "拜拜～",
    "晚安": "晚安，做个好梦！",
    "bye": "Goodbye! Take care.",
    "拜": "拜拜，下次见！",
    "谢谢": "不客气！能帮到你就好。",
    "感谢": "不用谢，这是我该做的。",
    "thanks": "You're welcome!",
    "thank you": "You're welcome! Happy to help.",
    "多谢": "客气啦，随时找我。",
    "好的": "好的，我记下了。",
    "OK": "OK，收到。",
    "ok": "好的，明白了。",
    "嗯嗯": "嗯嗯，继续说吧。",
    "没问题": "那太好了，有什么后续？",
    "不对": "哦？哪里不对？我重新来。",
    "算了": "没关系，换个话题吧。",
    "你是谁": "我是伏羲，一个 AI 助手。可以帮你搜索、分析、写作、编程等。",
    "你叫什么": "我叫伏羲，源自中国古代神话中的创世神。",
    "你的名字": "我叫伏羲，是结合了多个大模型的智能助手。",
    "你能做什么": "我可以搜索信息、分析数据、写代码、翻译、生成文本、回答问题……试试看？",
    "你有什么功能": "搜索、写作、编程、翻译、数据分析、知识问答等等，你有什么需求？",
    "帮我": "好的，你想让我做什么？",
    "帮忙": "没问题，什么事？",
    "怎么办": "说说看具体情况，我帮你分析。",
    "救命": "别慌，说说什么问题？",
}

_KEYWORD_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"^(你好|您好|hi|hello|嗨)\s*[，,。.]?\s*$"), "greeting"),
    (re.compile(r"^(再见|拜拜|bye|晚安|拜)\s*[！!。.]?\s*$"), "farewell"),
    (re.compile(r"^(谢谢|感谢|thanks|thank\s*you|多谢)\s*[！!。.]?\s*$"), "thanks"),
    (re.compile(r"^(好的|OK|ok|嗯嗯|没问题|收到)\s*[！!。.]?\s*$"), "confirm"),
    (re.compile(r"^(你是谁|你叫什么|你的名字)"), "identity"),
    (re.compile(r"^(你能做什么|你有什么功能|你会什么)"), "capability"),
    (re.compile(r"^(帮我|帮忙|怎么办|救命)"), "help_request"),
    (re.compile(r"^(早上好|晚上好|午安)"), "time_greeting"),
]

_PATTERN_REPLY_MAP: Dict[str, str] = {
    "greeting": "你好！有什么可以帮你的？",
    "farewell": "再见！随时回来找我。",
    "thanks": "不客气！能帮到你就好。",
    "confirm": "好的，收到。",
    "identity": "我是伏羲，一个多模型融合的 AI 助手，可以搜索、分析、写作、编程……试试看？",
    "capability": "我能：搜索信息、分析数据、写代码、翻译、生文、问答、知识管理等等。你想试试哪个？",
    "help_request": "没问题，请说具体一点，我来帮你。",
    "time_greeting": "你好！现在正是好时光，有什么可以帮你的？",
}


async def _l1_keyword_route(user_input: str) -> RoutingDecision:
    """L1: 关键词路由 — 哈希查找 + 正则匹配"""
    normalized = _normalize_text(user_input)
    lower_input = normalized.lower()

    # Step 1: 哈希查找
    for key, reply in _KEYWORD_DICT.items():
        if lower_input == _normalize_text(key).lower():
            return RoutingDecision(
                level=1, result=reply, confidence=1.0,
                should_upgrade=False,
                metadata={"type": "keyword_exact", "key": key},
            )

    # Step 2: 正则匹配
    for pattern, tag in _KEYWORD_PATTERNS:
        if pattern.match(normalized):
            reply = _PATTERN_REPLY_MAP.get(tag, "")
            if reply:
                return RoutingDecision(
                    level=1, result=reply, confidence=0.95,
                    should_upgrade=False,
                    metadata={"type": "keyword_pattern", "tag": tag},
                )

    return RoutingDecision(
        level=1, result=None, confidence=0.0,
        should_upgrade=True, metadata={"type": "keyword_miss"},
    )


# ============================================================================
# L2: Template Router（模板路由，<10ms）
# ============================================================================

_TEMPLATE_LIBRARY: List[Tuple[re.Pattern, str, Dict[str, str], float]] = [
    (re.compile(r"搜(?:索|一下|一搜)?\s*(?:关于|有关)?(?P<topic>.+?)的(?P<aspect>.+)"), "search", {"topic": "搜索主题", "aspect": "搜索方面"}, 0.90),
    (re.compile(r"(?:帮我?|给我|帮忙|我想)?(?:查|找|搜)(?:一下|一查)?\s*(?P<query>.+)"), "search", {"query": "搜索查询"}, 0.88),
    (re.compile(r"(?P<topic>.+?)(?:是|的)(?:什么|咋样|怎么样|如何|怎么)"), "knowledge_qa", {"topic": "知识主题"}, 0.85),
    (re.compile(r"(?:把|将|帮我把|帮我)?(?P<text>.+?)翻译(?:成|为|到)?(?P<target_lang>.+)"), "translate", {"text": "待翻译文本", "target_lang": "目标语言"}, 0.92),
    (re.compile(r"(?P<text>.+?)(?:的)?英文(?:怎么[说写]|是啥|是?什么)"), "translate", {"text": "待翻译文本", "target_lang": "英文"}, 0.90),
    (re.compile(r"(?:帮我?|给我)?写(?:一[篇个]|一下)?(?P<content_type>.+?)(?:关于|主题[是为]|内容是?)?(?P<topic>.+)"), "writing", {"content_type": "内容类型", "topic": "写作主题"}, 0.88),
    (re.compile(r"(?:生成|创作|起草)(?:一[篇个]|一下)?(?P<content_type>.+?)(?:关于|主题[是为]|内容是?)?(?P<topic>.+)"), "writing", {"content_type": "内容类型", "topic": "写作主题"}, 0.88),
    (re.compile(r"(?:帮我?)?总结(?:一下|这段|这篇)?(?P<content>.+)"), "summarize", {"content": "待总结内容"}, 0.90),
    (re.compile(r"(?:帮我?)?概括(?:一下|这段|这篇)?(?P<content>.+)"), "summarize", {"content": "待概括内容"}, 0.89),
    (re.compile(r"(?:帮我?|请)?写(?:一[段个]|点)?(?P<lang>.+?)(?:代码|程序)(?:实现|完成)?(?P<task>.+)"), "code_gen", {"lang": "编程语言", "task": "编程任务"}, 0.88),
    (re.compile(r"(?:帮我?)?用(?P<lang>.+?)实现(?P<task>.+)"), "code_gen", {"lang": "编程语言", "task": "编程任务"}, 0.90),
    (re.compile(r"(?:这段|这个)?(?:代码|程序)(?:有?什么)?(?:问题|错误|bug|错|毛病)(?P<code>.+)"), "code_review", {"code": "待审查代码"}, 0.87),
    (re.compile(r"(?:帮我?)?分析(?:一下)?(?P<target>.+)"), "analysis", {"target": "分析目标"}, 0.87),
    (re.compile(r"(?P<target>.+?)的(?:优缺点|利弊|好坏)"), "analysis", {"target": "分析目标"}, 0.85),
    (re.compile(r"(?:解释|说明)(?:一下)?(?P<concept>.+)"), "explain", {"concept": "待解释概念"}, 0.89),
    (re.compile(r"(?:什么是|啥是|什么叫)(?P<concept>.+)"), "explain", {"concept": "待解释概念"}, 0.90),
    (re.compile(r"(?:推荐|建议)(?:一些?|几个?)?(?P<category>.+)"), "recommend", {"category": "推荐类别"}, 0.86),
    (re.compile(r"(?:有没有?|有什么)(?:好|适合|推荐)的(?P<category>.+)"), "recommend", {"category": "推荐类别"}, 0.85),
    (re.compile(r"(?P<a>.+?)和(?P<b>.+?)(?:的)?(?:区别|不同|哪个好|怎么选|对比|比较)"), "compare", {"a": "比较对象A", "b": "比较对象B"}, 0.88),
    (re.compile(r"(?:计算|算)(?:一下|一算)?(?P<expression>.+)"), "calculate", {"expression": "计算表达式"}, 0.90),
    (re.compile(r"(?P<expression>.+?)(?:等于|是多少|等于多少|得多少)"), "calculate", {"expression": "计算表达式"}, 0.85),
    (re.compile(r"(?:给我?|讲)(?:一个?|个?)(?:笑话|段子)"), "joke", {}, 0.95),
    (re.compile(r"(?:起|取|帮我想)(?:个?|一个?)(?:名字|名称)(?:给|为)?(?P<target>.+)"), "naming", {"target": "命名目标"}, 0.88),
]

_INTENT_DESCRIPTIONS: Dict[str, str] = {
    "search": "搜索信息",
    "knowledge_qa": "知识问答",
    "translate": "翻译",
    "writing": "写作生成",
    "summarize": "总结概括",
    "code_gen": "代码生成",
    "code_review": "代码审查",
    "analysis": "分析评估",
    "explain": "解释说明",
    "recommend": "推荐建议",
    "compare": "对比比较",
    "calculate": "计算求值",
    "joke": "讲笑话",
    "naming": "起名字",
}

_PLAN_INTENTS = {"search", "knowledge_qa", "code_gen", "code_review", "writing",
                 "analysis", "recommend", "compare", "naming"}
_REASON_INTENTS = {"explain", "calculate"}
_EXECUTE_INTENTS = {"translate", "summarize", "joke"}


async def _l2_template_route(user_input: str) -> RoutingDecision:
    """L2: 模板路由 — 模板匹配 + 实体提取"""
    normalized = _normalize_text(user_input)

    best_match: Optional[Tuple[str, Dict[str, str], float, str]] = None

    for pattern, intent, slots, base_confidence in _TEMPLATE_LIBRARY:
        m = pattern.search(normalized)
        if m:
            entities: Dict[str, str] = {}
            for slot_name in slots:
                value = m.groupdict().get(slot_name, "")
                if value:
                    entities[slot_name] = value.strip()

            fill_rate = len(entities) / max(len(slots), 1) if slots else 1.0
            confidence = base_confidence * (0.7 + 0.3 * fill_rate)

            if best_match is None or confidence > best_match[2]:
                best_match = (intent, entities, confidence, pattern.pattern)

    if best_match is None:
        return RoutingDecision(
            level=2, result=None, confidence=0.0,
            should_upgrade=True, metadata={"type": "template_miss"},
        )

    intent, entities, confidence, matched_pattern = best_match

    if confidence < 0.85:
        return RoutingDecision(
            level=2, result={"intent": intent, "entities": entities},
            confidence=confidence, should_upgrade=True,
            metadata={"type": "template_low_conf", "pattern": matched_pattern},
        )

    if intent in _PLAN_INTENTS:
        meta_type = "plan"
    elif intent in _REASON_INTENTS:
        meta_type = "reason"
    elif intent in _EXECUTE_INTENTS:
        meta_type = "execute"
    else:
        meta_type = "unknown"

    result = {
        "intent": intent,
        "intent_desc": _INTENT_DESCRIPTIONS.get(intent, intent),
        "meta_type": meta_type,
        "entities": entities,
    }

    return RoutingDecision(
        level=2, result=result, confidence=confidence,
        should_upgrade=False,
        metadata={"type": "template_match", "pattern": matched_pattern},
    )


# ============================================================================
# L3: Cache Router（缓存路由，<50ms）
# ============================================================================

_L1_CACHE: Dict[str, CacheEntry] = {}
_L2_CACHE: Dict[str, CacheEntry] = {}
_L3_CACHE: Dict[str, CacheEntry] = {}

# 保护三层缓存的异步锁（修复并发安全问题）
_cache_lock: asyncio.Lock = asyncio.Lock()

L1_CACHE_TTL = 300   # 5 分钟
L2_CACHE_TTL = 600   # 10 分钟
L3_CACHE_TTL = 1800  # 30 分钟

SEMANTIC_SIMILARITY_THRESHOLD = 0.92


def _compute_md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _compute_ngram_similarity(text_a: str, text_b: str, n: int = 3) -> float:
    """基于字符 n-gram 的 Jaccard 相似度（轻量级语义近似）"""
    def get_ngrams(s: str, n: int) -> set:
        s = s.lower().strip()
        if len(s) < n:
            return {s}
        return {s[i:i + n] for i in range(len(s) - n + 1)}

    a_grams = get_ngrams(text_a, n)
    b_grams = get_ngrams(text_b, n)
    if not a_grams or not b_grams:
        return 0.0
    intersection = a_grams & b_grams
    union = a_grams | b_grams
    return len(intersection) / len(union) if union else 0.0


def _compute_context_hash(context: Optional[List[Dict[str, str]]]) -> str:
    """计算会话上下文的结构化哈希"""
    if not context:
        return "empty"
    recent = context[-3:]
    role_sequence = "|".join(msg.get("role", "?") for msg in recent)
    snippet = "|".join(msg.get("content", "")[:20] for msg in recent)
    raw = f"{role_sequence}|{snippet}"
    return _compute_md5(raw)


async def _l3_cache_route(
    user_input: str,
    l2_result: Optional[Dict[str, Any]] = None,
    context: Optional[List[Dict[str, str]]] = None,
) -> RoutingDecision:
    """L3: 缓存路由 — 三层缓存查找

    所有读写操作在 _cache_lock 保护下进行，确保并发安全。
    """
    normalized = _normalize_text(user_input)
    now = time.time()
    current_ctx_hash = _compute_context_hash(context)

    async with _cache_lock:
        # ---- Tier 1: 精确匹配（MD5） ----
        md5_key = _compute_md5(normalized)
        if md5_key in _L1_CACHE:
            entry = _L1_CACHE[md5_key]
            if now - entry.created_at < entry.ttl:
                return RoutingDecision(
                    level=3, result=entry.result, confidence=entry.confidence,
                    should_upgrade=False,
                    metadata={"type": "cache_exact", "cache_tier": "L1",
                              "age_s": round(now - entry.created_at, 1)},
                )
            else:
                del _L1_CACHE[md5_key]

        # ---- Tier 2: 语义相似（ngram Jaccard） ----
        best_sim = 0.0
        best_entry: Optional[CacheEntry] = None

        for cache_key, entry in list(_L2_CACHE.items()):
            if now - entry.created_at >= entry.ttl:
                del _L2_CACHE[cache_key]
                continue
            sim = _compute_ngram_similarity(normalized, cache_key)
            if sim > best_sim:
                best_sim = sim
                best_entry = entry

        if best_entry and best_sim >= SEMANTIC_SIMILARITY_THRESHOLD:
            # 上下文一致性检查
            if best_entry.context_hash and best_entry.context_hash != current_ctx_hash:
                return RoutingDecision(
                    level=3, result=None, confidence=0.0,
                    should_upgrade=True,
                    metadata={"type": "cache_context_mismatch", "cache_tier": "L2",
                              "sim_score": round(best_sim, 4)},
                )
            return RoutingDecision(
                level=3, result=best_entry.result,
                confidence=best_entry.confidence * best_sim,
                should_upgrade=False,
                metadata={"type": "cache_semantic", "cache_tier": "L2",
                          "sim_score": round(best_sim, 4),
                          "age_s": round(now - best_entry.created_at, 1)},
            )

        # ---- Tier 3: 意图路径匹配 ----
        if l2_result and "intent" in l2_result:
            intent_path = l2_result["intent"]
            entities = l2_result.get("entities", {})
            if entities:
                entity_path = "|".join(sorted(entities.keys()))
                intent_path = f"{intent_path}:{entity_path}"

            if intent_path in _L3_CACHE:
                entry = _L3_CACHE[intent_path]
                if now - entry.created_at < entry.ttl:
                    return RoutingDecision(
                        level=3, result=entry.result, confidence=entry.confidence,
                        should_upgrade=False,
                        metadata={"type": "cache_intent_path", "cache_tier": "L3",
                                  "intent_path": intent_path},
                    )
                else:
                    del _L3_CACHE[intent_path]

        return RoutingDecision(
            level=3, result=None, confidence=0.0,
            should_upgrade=True,
            metadata={"type": "cache_miss", "best_sim_score": round(best_sim, 4)},
        )


# ---- 缓存写入 ----

async def _write_exact_cache(user_input: str, result: Any, confidence: float = 0.98):
    async with _cache_lock:
        key = _compute_md5(_normalize_text(user_input))
        _L1_CACHE[key] = CacheEntry(
            key=key, result=result, confidence=confidence,
            created_at=time.time(), ttl=L1_CACHE_TTL,
        )


async def _write_semantic_cache(user_input: str, result: Any,
                                context: Optional[List[Dict[str, str]]] = None,
                                confidence: float = 0.92):
    async with _cache_lock:
        normalized = _normalize_text(user_input)
        _L2_CACHE[normalized] = CacheEntry(
            key=normalized, result=result, confidence=confidence,
            created_at=time.time(), ttl=L2_CACHE_TTL,
            context_hash=_compute_context_hash(context),
        )


async def _write_intent_path_cache(intent_path: str, result: Any, confidence: float = 0.90):
    async with _cache_lock:
        _L3_CACHE[intent_path] = CacheEntry(
            key=intent_path, result=result, confidence=confidence,
            created_at=time.time(), ttl=L3_CACHE_TTL,
        )


async def clear_cache():
    """清空所有缓存"""
    async with _cache_lock:
        _L1_CACHE.clear()
        _L2_CACHE.clear()
        _L3_CACHE.clear()
    logger.info("All router caches cleared")


def clear_cache_sync():
    """同步清空所有缓存（用于同步代码路径）"""
    _L1_CACHE.clear()
    _L2_CACHE.clear()
    _L3_CACHE.clear()
    logger.info("All router caches cleared (sync)")


async def get_cache_stats() -> Dict[str, int]:
    """获取缓存统计"""
    async with _cache_lock:
        return {
            "l1_exact": len(_L1_CACHE),
            "l2_semantic": len(_L2_CACHE),
            "l3_intent_path": len(_L3_CACHE),
        }


# ============================================================================
# L4: Small Model Router（Flash 模型路由，1-2s）
# ============================================================================

_FLASH_INTENT_CLASSIFY_PROMPT = """你是一个意图分类器。分析用户输入，输出严格 JSON 格式。

## 意图类别
- search: 搜索信息、查找资料
- knowledge_qa: 知识问答、解释概念
- translate: 翻译文本
- writing: 写作生成（文章、邮件、报告等）
- summarize: 总结概括文本
- code_gen: 生成代码
- code_review: 审查/修复代码
- analysis: 分析评估
- explain: 解释说明
- recommend: 推荐建议
- compare: 对比比较
- calculate: 计算求值
- chat: 闲聊/问候
- reason: 复杂推理（数学、逻辑、多步推理）
- plan: 规划安排
- creative: 创意生成
- other: 其他

## 输出格式（必须严格 JSON，不要其他文字）
{{"intent": "<意图类别>", "confidence": <0.0-1.0>, "entities": {{<key>: "<value>"}}, "meta_type": "<plan|reason|execute|chat>"}}

meta_type 规则：
- plan: 需要多步执行的任务 (search, knowledge_qa, code_gen, code_review, writing, analysis, recommend, compare)
- reason: 需要逻辑推理的任务 (explain, calculate, reason)
- execute: 直接转换为操作的任务 (translate, summarize, creative)
- chat: 纯对话

## 用户输入
{user_input}

## 你的 JSON 输出（仅输出 JSON）："""


async def _l4_small_model_route(
    user_input: str,
    l2_result: Optional[Dict[str, Any]] = None,
) -> RoutingDecision:
    """L4: 小模型路由 — DeepSeek V4 Flash 做意图分类"""
    normalized = _normalize_text(user_input)

    hint = ""
    if l2_result and l2_result.get("intent"):
        hint = f"\n\n提示：用户输入可能属于 {l2_result['intent']} 类别（来自模板匹配）。"

    prompt = _FLASH_INTENT_CLASSIFY_PROMPT.format(user_input=normalized[:2000])
    if hint:
        prompt += hint

    try:
        from src.services.llm import _call_api
        from src.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_TIMEOUT

        if not DEEPSEEK_API_KEY:
            return RoutingDecision(
                level=4, result=None, confidence=0.0,
                should_upgrade=True, metadata={"type": "flash_no_key"},
            )

        flash_model = "deepseek-v4-flash"

        raw_output = await _call_api(
            base_url=DEEPSEEK_BASE_URL,
            api_key=DEEPSEEK_API_KEY,
            model=flash_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.1,
            timeout=max(DEEPSEEK_TIMEOUT, 10),
        )

        if not raw_output:
            return RoutingDecision(
                level=4, result=None, confidence=0.0,
                should_upgrade=True, metadata={"type": "flash_empty"},
            )

        raw_output = raw_output.strip()
        raw_output = re.sub(r"^```(?:json)?\s*", "", raw_output)
        raw_output = re.sub(r"\s*```$", "", raw_output)

        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[^{}]*"intent"[^{}]*\}', raw_output)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    return RoutingDecision(
                        level=4, result=None, confidence=0.0,
                        should_upgrade=True,
                        metadata={"type": "flash_parse_error",
                                  "raw": raw_output[:200]},
                    )
            else:
                return RoutingDecision(
                    level=4, result=None, confidence=0.0,
                    should_upgrade=True,
                    metadata={"type": "flash_no_json",
                              "raw": raw_output[:200]},
                )

        intent = parsed.get("intent", "other")
        confidence = float(parsed.get("confidence", 0.5))
        entities = parsed.get("entities", {})
        meta_type = parsed.get("meta_type", "chat")

        if confidence < 0.7:
            return RoutingDecision(
                level=4, result=parsed, confidence=confidence,
                should_upgrade=True,
                metadata={"type": "flash_low_conf"},
            )

        if intent == "reason":
            return RoutingDecision(
                level=4, result=parsed, confidence=confidence,
                should_upgrade=True,
                metadata={"type": "flash_reason_intent"},
            )

        result = {
            "intent": intent,
            "intent_desc": _INTENT_DESCRIPTIONS.get(intent, intent),
            "meta_type": meta_type,
            "confidence": confidence,
            "entities": entities,
            "source": "flash",
        }

        return RoutingDecision(
            level=4, result=result, confidence=confidence,
            should_upgrade=False,
            metadata={"type": "flash_classified", "model": flash_model},
        )

    except Exception as e:  # TODO: Narrow exception type
        return RoutingDecision(
            level=4, result=None, confidence=0.0,
            should_upgrade=True,
            metadata={"type": "flash_exception", "error": str(e)},
        )


# ============================================================================
# L5: Full Model Router（全模型路由，2-5s）
# ============================================================================

_FULL_MODEL_ROUTE_PROMPT = """你是一个智能路由分析器。分析以下用户输入，提供完整的意图理解和执行计划。

## 用户输入
{user_input}

## 前几层分析提示
意图提示: {intent_hint}
实体提示: {entities_hint}

## 输出格式（严格 JSON）
{{
  "intent": "<意图类别>",
  "intent_desc": "<人类可读描述>",
  "meta_type": "<plan|reason|execute|chat>",
  "confidence": <0.0-1.0>,
  "entities": {{<key>: "<value>"}},
  "reasoning": "<简短推理过程>",
  "route_decision": "<direct_answer|search|generate|multi_step>"
}}

请仅输出 JSON："""


async def _l5_full_model_route(
    user_input: str,
    l2_result: Optional[Dict[str, Any]] = None,
    l4_result: Optional[Dict[str, Any]] = None,
) -> RoutingDecision:
    """L5: 全模型路由 — 使用 Mimo 全参数模型做最终兜底"""
    normalized = _normalize_text(user_input)

    intent_hint = "未知"
    entities_hint = "无"
    if l4_result and l4_result.get("intent"):
        intent_hint = l4_result["intent"]
        entities_hint = json.dumps(l4_result.get("entities", {}), ensure_ascii=False)
    elif l2_result and l2_result.get("intent"):
        intent_hint = l2_result["intent"]
        entities_hint = json.dumps(l2_result.get("entities", {}), ensure_ascii=False)

    prompt = _FULL_MODEL_ROUTE_PROMPT.format(
        user_input=normalized[:3000],
        intent_hint=intent_hint,
        entities_hint=entities_hint,
    )

    try:
        from src.services.llm import call_llm

        raw_output = await call_llm(
            prompt=prompt,
            max_tokens=500,
            temperature=0.2,
        )

        if not raw_output:
            logger.warning("L5 full model returned empty, using fallback")
            return RoutingDecision(
                level=5,
                result={
                    "intent": "other", "intent_desc": "其他",
                    "meta_type": "chat", "confidence": 0.3,
                    "entities": {}, "reasoning": "全模型兜底（API 返回空）",
                    "route_decision": "direct_answer",
                },
                confidence=0.3,
                should_upgrade=False,
                metadata={"type": "full_model_fallback_empty"},
            )

        raw_output = raw_output.strip()
        raw_output = re.sub(r"^```(?:json)?\s*", "", raw_output)
        raw_output = re.sub(r"\s*```$", "", raw_output)

        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[^{}]*"intent"[^{}]*\}', raw_output)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    parsed = {"intent": "other", "meta_type": "chat",
                              "confidence": 0.3, "entities": {},
                              "route_decision": "direct_answer"}
            else:
                parsed = {"intent": "other", "meta_type": "chat",
                          "confidence": 0.3, "entities": {},
                          "route_decision": "direct_answer"}

        intent = parsed.get("intent", "other")
        confidence = float(parsed.get("confidence", 0.5))
        entities = parsed.get("entities", {})

        result = {
            "intent": intent,
            "intent_desc": parsed.get("intent_desc",
                                       _INTENT_DESCRIPTIONS.get(intent, intent)),
            "meta_type": parsed.get("meta_type", "chat"),
            "confidence": confidence,
            "entities": entities,
            "reasoning": parsed.get("reasoning", ""),
            "route_decision": parsed.get("route_decision", "direct_answer"),
            "source": "full_model",
        }

        return RoutingDecision(
            level=5, result=result, confidence=confidence,
            should_upgrade=False,
            metadata={"type": "full_model_routed"},
        )

    except Exception as e:  # TODO: Narrow exception type
        logger.error(f"L5 full model route exception: {e}")
        return RoutingDecision(
            level=5,
            result={
                "intent": "other", "intent_desc": "其他",
                "meta_type": "chat", "confidence": 0.1,
                "entities": {},
                "reasoning": f"全模型异常兜底: {e}",
                "route_decision": "direct_answer",
            },
            confidence=0.1,
            should_upgrade=False,
            metadata={"type": "full_model_exception", "error": str(e)},
        )


# ============================================================================
# 主编排器：route()
# ============================================================================


async def route(
    user_input: str,
    context: Optional[List[Dict[str, str]]] = None,
) -> RoutingDecision:
    """
    5 层阶梯路由主编排

    参数：
        user_input: 用户输入文本
        context: 对话上下文 [{"role": "user"/"assistant", "content": "..."}]

    返回：
        RoutingDecision，包含命中层级、结果、置信度、should_upgrade 标记
    """
    if not user_input or not user_input.strip():
        return RoutingDecision(
            level=1, result="你好？有什么我可以帮忙的吗？", confidence=1.0,
            should_upgrade=False, metadata={"type": "empty_input"},
        )

    logger.info(f"Routing: '{user_input[:80]}...'")
    start_time = time.time()

    # ---- L1: Keyword ----
    l1 = await _l1_keyword_route(user_input)
    if not l1.should_upgrade:
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"L1 hit in {elapsed:.1f}ms: {l1.metadata.get('type')}")
        l1.metadata["elapsed_ms"] = round(elapsed, 1)
        await _trigger_shadow_if_enabled(user_input, context, l1)
        return l1

    # ---- L2: Template ----
    l2 = await _l2_template_route(user_input)
    if not l2.should_upgrade:
        # 将 L2 结果写入缓存
        if l2.confidence >= 0.88:
            await _write_semantic_cache(user_input, l2.result, context, l2.confidence)
            intent_path = l2.result.get("intent", "")
            if intent_path:
                await _write_intent_path_cache(intent_path, l2.result, l2.confidence)
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"L2 hit in {elapsed:.1f}ms: intent={l2.result.get('intent')}")
        l2.metadata["elapsed_ms"] = round(elapsed, 1)
        await _trigger_shadow_if_enabled(user_input, context, l2)
        return l2

    # ---- L3: Cache ----
    l3 = await _l3_cache_route(
        user_input,
        l2_result=l2.result if isinstance(l2.result, dict) else None,
        context=context,
    )
    if not l3.should_upgrade:
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"L3 hit in {elapsed:.1f}ms: {l3.metadata.get('type')}")
        l3.metadata["elapsed_ms"] = round(elapsed, 1)
        await _trigger_shadow_if_enabled(user_input, context, l3)
        return l3

    # ---- L4: Flash ----
    l4 = await _l4_small_model_route(
        user_input,
        l2_result=l2.result if isinstance(l2.result, dict) else None,
    )
    if not l4.should_upgrade:
        # 将 Flash 结果写入逐层缓存
        if l4.confidence >= 0.8:
            await _write_exact_cache(user_input, l4.result, l4.confidence)
            await _write_semantic_cache(user_input, l4.result, context, l4.confidence)
            intent_path = l4.result.get("intent", "")
            if intent_path:
                await _write_intent_path_cache(intent_path, l4.result, l4.confidence)
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"L4 hit in {elapsed:.1f}ms: intent={l4.result.get('intent')}")
        l4.metadata["elapsed_ms"] = round(elapsed, 1)
        await _trigger_shadow_if_enabled(user_input, context, l4)
        return l4

    # ---- L5: Full Model (final fallback) ----
    l5 = await _l5_full_model_route(
        user_input,
        l2_result=l2.result if isinstance(l2.result, dict) else None,
        l4_result=l4.result if isinstance(l4.result, dict) else None,
    )
    # L5 总是 should_upgrade=False（最终兜底）
    if l5.confidence >= 0.7:
        await _write_exact_cache(user_input, l5.result, l5.confidence)
        await _write_semantic_cache(user_input, l5.result, context, l5.confidence)
        intent_path = l5.result.get("intent", "")
        if intent_path:
            await _write_intent_path_cache(intent_path, l5.result, l5.confidence)
    elapsed = (time.time() - start_time) * 1000
    logger.info(f"L5 final in {elapsed:.1f}ms: intent={l5.result.get('intent')}")
    l5.metadata["elapsed_ms"] = round(elapsed, 1)
    await _trigger_shadow_if_enabled(user_input, context, l5)
    return l5


# ============================================================================
# 统一桥接：route_to_qian_intent()
# ============================================================================

# smart_router 意图 → qian 意图映射表
_INTENT_TO_QIAN_INTENT: Dict[str, str] = {
    "search": "SEARCH",
    "knowledge_qa": "SEARCH",
    "translate": "DECIDE",
    "writing": "PRESENT",
    "summarize": "PRESENT",
    "code_gen": "DECIDE",
    "code_review": "DECIDE",
    "analysis": "DECIDE",
    "explain": "DECIDE",
    "recommend": "DECIDE",
    "compare": "DECIDE",
    "calculate": "DECIDE",
    "joke": "PRESENT",
    "naming": "DECIDE",
    "chat": "PRESENT",
    "reason": "DECIDE",
    "plan": "DECIDE",
    "creative": "PRESENT",
    "other": "PRESENT",
}


async def route_to_qian_intent(
    user_input: str,
    context: Optional[List[Dict[str, str]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    统一桥接：smart_router 结果 → qian 八卦意图

    当 smart_router L1-L5 高置信度命中时，直接映射为 qian 意图，
    跳过乾卦 LLM 决策，降低延迟和成本。

    Args:
        user_input: 用户输入
        context: 对话上下文

    Returns:
        {
            "intent": "SEARCH|DECIDE|PRESENT|...",
            "confidence": float,
            "reasoning": str,
            "source": "smart_router_bridge",
            "router_level": int,
        }
        或 None（未命中 / 置信度不足，应走 qian 完整循环）
    """
    decision = await route(user_input, context)

    # 仅高置信度结果才桥接
    if decision.should_upgrade or decision.confidence < 0.85:
        return None

    # 从 result 中提取意图
    intent = None
    if isinstance(decision.result, dict):
        intent = decision.result.get("intent", "")
    elif isinstance(decision.result, str):
        # L1 关键词直接回复 → 走 PRESENT
        intent = "chat"

    if not intent:
        return None

    qian_intent = _INTENT_TO_QIAN_INTENT.get(intent, "PRESENT")

    return {
        "intent": qian_intent,
        "confidence": decision.confidence,
        "reasoning": f"smart_router L{decision.level} 桥接: {intent}→{qian_intent}",
        "source": "smart_router_bridge",
        "router_level": decision.level,
        "original_intent": intent,
    }


# ============================================================================
# 同步包装器：方便同步代码调用
# ============================================================================


def route_sync(
    user_input: str,
    context: Optional[List[Dict[str, str]]] = None,
) -> RoutingDecision:
    """同步包装器，内部运行 asyncio event loop"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
        return loop.run_until_complete(route(user_input, context))
    except RuntimeError:
        return asyncio.run(route(user_input, context))


# ============================================================================
# 影子模式触发器
# ============================================================================

async def _trigger_shadow_if_enabled(
    user_input: str,
    context: Optional[List[Dict[str, str]]],
    production_result: RoutingDecision,
) -> None:
    """如果影子模式已启用，异步触发影子评估（不阻塞主流程）"""
    try:
        from src.config import SHADOW_ENABLED, SHADOW_MODEL, SHADOW_SAMPLE_RATE
        import random

        if not SHADOW_ENABLED:
            return

        # 采样率控制
        if SHADOW_SAMPLE_RATE < 1.0 and random.random() > SHADOW_SAMPLE_RATE:
            return

        # 异步触发，不等待结果
        asyncio.create_task(
            shadow_route(
                user_input=user_input,
                model_name=SHADOW_MODEL,
                context=context,
                production_result=production_result,
            )
        )
    except Exception as exc:
        logger.debug("[Shadow] 触发影子模式异常: %s", exc)


# ============================================================================
# 影子模式：异步对比实验模型，不阻塞生产流量
# ============================================================================

_shadow_results: List[Dict[str, Any]] = []
_shadow_max_results: int = 200


async def shadow_route(
    user_input: str,
    model_name: str,
    context: Optional[List[Dict[str, str]]] = None,
    production_result: Optional[RoutingDecision] = None,
) -> None:
    """影子模式 — 用实验模型异步评估同一请求，不阻塞主流程

    将生产模型的路由结果与实验模型（如 gemini-flash）的结果
    进行后台对比，写入影子日志供 A/B 分析。

    Args:
        user_input:        用户输入
        model_name:        实验模型名（如 "gemini-flash", "qwen-turbo"）
        context:           对话上下文
        production_result: 生产模型的路由决策（可选，用于对比）
    """
    try:
        from src.services.llm import _call_api
        from src.config import MIMO_API_KEY, MIMO_BASE_URL

        if not MIMO_API_KEY:
            return

        prompt = (f'分析以下用户输入，输出 JSON:\n'
                  f'{{"intent": "<类别>", "confidence": <0.0-1.0>, "meta_type": "<chat|plan|reason|execute>"}}\n'
                  f'\n用户输入: {user_input[:2000]}')

        raw = await _call_api(
            base_url=MIMO_BASE_URL,
            api_key=MIMO_API_KEY,
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.1,
            timeout=10,
        )

        if not raw:
            return

        import json as _json
        try:
            clean = raw.strip()
            clean = re.sub(r'^```(?:json)?\s*', '', clean)
            clean = re.sub(r'\s*```$', '', clean)
            parsed = _json.loads(clean)
        except _json.JSONDecodeError:
            return

        shadow_entry = {
            "timestamp": time.time(),
            "model": model_name,
            "intent": parsed.get("intent", "unknown"),
            "confidence": parsed.get("confidence", 0),
            "production_intent": (
                production_result.result.get("intent", "")
                if production_result and isinstance(production_result.result, dict)
                else None
            ),
            "production_confidence": (
                production_result.confidence if production_result else None
            ),
        }

        global _shadow_results
        _shadow_results.append(shadow_entry)
        if len(_shadow_results) > _shadow_max_results:
            _shadow_results = _shadow_results[-_shadow_max_results:]

        logger.debug(
            "[Shadow] model=%s intent=%s conf=%.2f | prod=%s",
            model_name,
            shadow_entry["intent"],
            shadow_entry["confidence"],
            shadow_entry["production_intent"] or "N/A",
        )

    except Exception as exc:  # TODO: Narrow exception type
        logger.debug("[Shadow] 影子评估异常: %s", exc)


def get_shadow_stats() -> Dict[str, Any]:
    """获取影子模式统计

    Returns:
        {
            "total_evaluations": int,
            "by_model": {model: count},
            "agreement_rate": float,
            "recent": [...]
        }
    """
    if not _shadow_results:
        return {"total_evaluations": 0, "by_model": {}, "agreement_rate": 1.0, "recent": []}

    by_model: Dict[str, int] = {}
    agreements = 0
    for entry in _shadow_results:
        model = entry.get("model", "unknown")
        by_model[model] = by_model.get(model, 0) + 1
        if entry.get("production_intent") == entry.get("intent"):
            agreements += 1

    return {
        "total_evaluations": len(_shadow_results),
        "by_model": by_model,
        "agreement_rate": round(agreements / len(_shadow_results), 4),
        "recent": _shadow_results[-10:],
    }


def clear_shadow_results() -> None:
    """清空影子结果缓存"""
    global _shadow_results
    _shadow_results = []
    logger.info("影子结果缓存已清空")
