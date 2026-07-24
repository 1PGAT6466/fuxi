"""
intent_bus.py — 统一意图总线（服务层 P2 增强）

为伏羲 RAG 流程提供轻量级意图分类与路由能力，与 bagua/intent_bus.py
（八卦体系内部通信中枢）互补：

  - bagua/intent_bus.py：卦间信号调度（乾卦→任意卦），含超时/重试/断路器
  - services/intent_bus.py：RAG 意图分类与路由（SEARCH→DIGEST→REFINE→PRESENT→DONE）

乾卦意图循环：
  用户提问 → 意图分类(SEARCH/DIGEST/REFINE/PRESENT/DONE) →
  意图路由 → 对应处理器执行 → 结果回馈 → 下一轮意图决策 → … → DONE

能力：
  - 意图分类：SEARCH（检索）、DIGEST（消化）、REFINE（精炼）、PRESENT（输出）、DONE（结束）
  - 意图路由：根据意图类型分发到对应的 async handler
  - 意图历史：完整记录意图转换链路（trace_id + timestamp）
  - 意图循环守卫：同意图连续上限、总轮数限制、未检索禁 DONE
  - 预加载缓存：高频简单查询零延迟路由
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("services.intent_bus")

# ============================================================================
# 枚举 & 数据类
# ============================================================================


class RAGIntent(str, Enum):
    """RAG 意图类型 — 乾卦意图循环的五种标准意图"""
    SEARCH = "SEARCH"       # 检索：查知识库/向量/图谱
    DIGEST = "DIGEST"       # 消化：新知识入库/结构化
    REFINE = "REFINE"       # 精炼：结果去重/排序/融合
    PRESENT = "PRESENT"     # 输出：生成最终回答
    DONE = "DONE"           # 结束：答案已完成


@dataclass
class IntentDecision:
    """意图决策结果"""
    intent: RAGIntent
    confidence: float       # 0.0 - 1.0
    reasoning: str = ""
    target_handler: str = ""  # 目标处理器标识
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IntentRecord:
    """意图历史记录"""
    step: int
    intent: RAGIntent
    confidence: float
    reasoning: str
    timestamp: float = field(default_factory=time.time)
    latency_ms: float = 0.0
    result_summary: str = ""


# ============================================================================
# 预加载意图缓存 — 高频查询零延迟
# ============================================================================

_PRELOAD_INTENT_CACHE: Dict[str, str] = {
    # 问候/闲聊 → PRESENT（不检索）
    "你好": "PRESENT",
    "嗨": "PRESENT",
    "喂": "PRESENT",
    "hello": "PRESENT",
    "hi": "PRESENT",
    "早上好": "PRESENT",
    "晚上好": "PRESENT",
    "下午好": "PRESENT",
    "谢谢": "PRESENT",
    "感谢": "PRESENT",
    "thank": "PRESENT",
    "再见": "PRESENT",
    "拜拜": "PRESENT",
    "bye": "PRESENT",
    "好的": "PRESENT",
    "OK": "PRESENT",
    "ok": "PRESENT",
    "帮助": "PRESENT",
    "help": "PRESENT",
    "怎么用": "PRESENT",
    "如何使用": "PRESENT",
    # 搜索类 → SEARCH（前缀匹配）
    "搜*": "SEARCH",
    "查找*": "SEARCH",
    "搜索*": "SEARCH",
    "查一下*": "SEARCH",
    "查找": "SEARCH",
    # 上传/消化类 → DIGEST
    "上传*": "DIGEST",
    "消化*": "DIGEST",
    "导入*": "DIGEST",
    "学习*": "DIGEST",
}

# 意图配置：描述、可用处理器、健康指标
_INTENT_CONFIG: Dict[str, Dict[str, Any]] = {
    "SEARCH": {
        "description": "本地知识检索 + 外部搜索",
        "handlers": ["vector_search", "graph_search", "web_search"],
        "max_consecutive": 3,
        "requires_prior_search_for_done": True,
    },
    "DIGEST": {
        "description": "新知识消化入库",
        "handlers": ["pipeline_ingest", "kg_extract"],
        "max_consecutive": 2,
    },
    "REFINE": {
        "description": "结果精炼去重排序",
        "handlers": ["rerank", "fusion", "dedup"],
        "max_consecutive": 2,
    },
    "PRESENT": {
        "description": "生成最终回答",
        "handlers": ["llm_generate", "template_reply"],
        "max_consecutive": 1,
    },
    "DONE": {
        "description": "结束意图循环",
        "handlers": [],
        "max_consecutive": 1,
    },
}

# ============================================================================
# IntentBus 核心类
# ============================================================================


class IntentBus:
    """统一意图总线 — RAG 意图分类与路由中枢

    使用方式:
        bus = IntentBus()
        bus.register_handler(RAGIntent.SEARCH, my_search_handler)

        # 单步意图决策
        decision = await bus.classify_intent("什么是 VLAN")

        # 完整意图循环
        final_answer = await bus.run_intent_loop("什么是 VLAN", history=[])

    Lifecycle:
        - 创建后通过 register_handler() 注册处理器
        - 调用 classify_intent() 做意图分类
        - 调用 dispatch() 分发意图到处理器
        - 调用 run_intent_loop() 自动完成完整意图循环
    """

    # 循环约束
    MAX_TOTAL_ROUNDS: int = 8
    MAX_CONSECUTIVE_SAME_INTENT: int = 3
    DONE_MIN_CONFIDENCE: float = 0.7

    def __init__(self, session_id: str = "", data_dir: Optional[Path] = None):
        """
        Args:
            session_id: 会话标识，用于隔离不同会话的意图状态
            data_dir: 数据目录（持久化意图日志）
        """
        self.session_id = session_id or hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        self._handlers: Dict[RAGIntent, List[Callable]] = {}
        self._intent_history: List[IntentRecord] = []
        self._round_count: int = 0
        self._query: str = ""
        self._last_intent: Optional[RAGIntent] = None
        self._consecutive_count: int = 0
        self._searched: bool = False
        self._data_dir = data_dir

        # 缓存
        self._cache: Dict[str, IntentDecision] = {}
        self._cache_hits: int = 0
        self._cache_misses: int = 0

        logger.debug(f"[IntentBus] 初始化 session={self.session_id}")

    # ------------------------------------------------------------------
    # 处理器注册
    # ------------------------------------------------------------------

    def register_handler(self, intent: RAGIntent, handler: Callable) -> None:
        """注册意图处理器

        Args:
            intent: 意图类型
            handler: async callable，签名为 async def handler(query, context, decision) -> dict
        """
        if intent not in self._handlers:
            self._handlers[intent] = []
        self._handlers[intent].append(handler)
        logger.debug(f"[IntentBus] 注册处理器: {intent.value} -> {handler.__name__}")

    def unregister_handler(self, intent: RAGIntent, handler: Callable) -> None:
        """取消注册处理器"""
        if intent in self._handlers and handler in self._handlers[intent]:
            self._handlers[intent].remove(handler)

    # ------------------------------------------------------------------
    # 意图分类
    # ------------------------------------------------------------------

    async def classify_intent(
        self,
        query: str,
        history: Optional[List[Dict[str, Any]]] = None,
        use_llm: bool = True,
    ) -> IntentDecision:
        """分类用户查询意图

        分类优先级：
          1. 预加载缓存（精确/前缀匹配）— 零延迟
          2. MD5 语义缓存 — <1ms
          3. 正则规则匹配 — <5ms
          4. LLM 分类 — 1-3s（仅复杂查询）

        Args:
            query: 用户查询文本
            history: 对话历史
            use_llm: 是否启用 LLM 分类（默认 True）

        Returns:
            IntentDecision 对象
        """
        query = query.strip()
        if not query:
            return IntentDecision(intent=RAGIntent.PRESENT, confidence=1.0, reasoning="空查询")

        # L1: 预加载缓存匹配
        cached_intent = _match_preload_cache(query)
        if cached_intent:
            decision = IntentDecision(
                intent=RAGIntent(cached_intent),
                confidence=0.95,
                reasoning=f"预加载缓存命中: {cached_intent}",
            )
            return decision

        # L2: MD5 语义缓存
        cache_key = hashlib.md5(query.encode("utf-8")).hexdigest()
        if cache_key in self._cache:
            self._cache_hits += 1
            cached = self._cache[cache_key]
            logger.debug(f"[IntentBus] 缓存命中: {query[:30]}... -> {cached.intent.value}")
            return cached

        self._cache_misses += 1

        # L3: 正则规则分类
        rule_decision = _rule_based_classify(query, self._searched)
        if rule_decision and rule_decision.confidence >= 0.8:
            self._cache[cache_key] = rule_decision
            return rule_decision

        # L4: LLM 分类（仅复杂查询）
        if use_llm and len(query) > 10:
            try:
                llm_decision = await _llm_classify_intent(query, history, self._searched)
                if llm_decision:
                    self._cache[cache_key] = llm_decision
                    return llm_decision
            except Exception as e:
                logger.warning(f"[IntentBus] LLM 意图分类失败: {e}")

        # 默认：SEARCH
        default = IntentDecision(intent=RAGIntent.SEARCH, confidence=0.6, reasoning="默认检索")
        self._cache[cache_key] = default
        return default

    # ------------------------------------------------------------------
    # 意图路由与派发
    # ------------------------------------------------------------------

    async def dispatch(
        self,
        decision: IntentDecision,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """派发意图到对应的处理器执行

        Args:
            decision: 意图决策结果
            query: 原始查询
            context: 上下文数据（前序步骤的结果等）

        Returns:
            处理器返回的结果字典
        """
        intent = decision.intent
        handlers = self._handlers.get(intent, [])

        if not handlers:
            logger.warning(f"[IntentBus] {intent.value} 无注册处理器，跳过")
            return {"intent": intent.value, "result": None, "skipped": True}

        # 按注册顺序依次执行（支持链式处理）
        result = {}
        current_context = context or {}
        current_context["query"] = query
        current_context["decision"] = {"intent": decision.intent.value, "confidence": decision.confidence}

        for handler in handlers:
            try:
                handler_result = await handler(query, current_context, decision)
                if handler_result:
                    current_context.update(handler_result)
                    result = {**result, **handler_result}
            except Exception as e:
                logger.error(f"[IntentBus] 处理器 {handler.__name__} 执行失败: {e}", exc_info=True)
                result["_error"] = str(e)

        result["intent"] = intent.value
        return result

    # ------------------------------------------------------------------
    # 完整意图循环
    # ------------------------------------------------------------------

    async def run_intent_loop(
        self,
        query: str,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """执行完整的乾卦意图循环

        循环流程:
          while intent != DONE:
            1. classify_intent(query) -> 意图决策
            2. 循环守卫检查（同意图上限/总轮数/未检索禁DONE）
            3. dispatch(intent) -> 派发到处理器
            4. 记录意图历史
            5. 下一轮决策

        Args:
            query: 用户查询
            history: 对话历史

        Returns:
            包含 answer 和 intent_trace 的结果字典
        """
        self._reset_cycle(query)
        context: Dict[str, Any] = {"history": history or []}
        final_result: Dict[str, Any] = {}

        start_time = time.time()

        while self._round_count < self.MAX_TOTAL_ROUNDS:
            self._round_count += 1

            # Step 1: 意图分类
            decision = await self.classify_intent(query, history)

            # Step 2: 循环守卫检查
            guard_result = self._cycle_guard(decision)
            if guard_result:
                logger.info(f"[IntentBus] 循环守卫拦截: {guard_result}")
                decision = guard_result

            # Step 3: 记录意图历史
            t0 = time.time()
            record = IntentRecord(
                step=self._round_count,
                intent=decision.intent,
                confidence=decision.confidence,
                reasoning=decision.reasoning,
            )

            # Step 4: 派发执行
            if decision.intent == RAGIntent.DONE:
                record.latency_ms = (time.time() - t0) * 1000
                record.result_summary = "意图循环结束"
                self._intent_history.append(record)
                logger.info(f"[IntentBus] 意图循环完成: {len(self._intent_history)} 轮")
                break

            step_result = await self.dispatch(decision, query, context)

            record.latency_ms = (time.time() - t0) * 1000
            record.result_summary = str(step_result.get("summary", ""))[:100]
            self._intent_history.append(record)

            # Step 5: 更新上下文
            context.update(step_result)
            final_result = step_result

            # 跟踪 SEARCH 意图
            if decision.intent == RAGIntent.SEARCH:
                self._searched = True

            # 跟踪连续意图
            if self._last_intent == decision.intent:
                self._consecutive_count += 1
            else:
                self._consecutive_count = 1
            self._last_intent = decision.intent

        total_ms = (time.time() - start_time) * 1000

        # 构建返回结果
        return {
            "query": query,
            "session_id": self.session_id,
            "rounds": self._round_count,
            "intent_trace": [
                {
                    "step": r.step,
                    "intent": r.intent.value,
                    "confidence": r.confidence,
                    "reasoning": r.reasoning,
                    "latency_ms": round(r.latency_ms, 1),
                }
                for r in self._intent_history
            ],
            "result": final_result,
            "total_latency_ms": round(total_ms, 1),
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
        }

    # ------------------------------------------------------------------
    # 循环守卫
    # ------------------------------------------------------------------

    def _cycle_guard(self, decision: IntentDecision) -> Optional[IntentDecision]:
        """循环守卫：拦截不合理的意图决策

        规则：
          1. 未执行 SEARCH 前禁止 DONE
          2. 同意图连续次数超限
          3. 总轮数即将达到上限时强制收束
          4. DONE 置信度不够时降级

        Returns:
            修正后的决策，或 None（原决策通过）
        """
        # 规则 1: 未检索禁止 DONE
        if decision.intent == RAGIntent.DONE and not self._searched:
            logger.info("[IntentBus] 循环守卫: 未检索禁止DONE，强制SEARCH")
            return IntentDecision(
                intent=RAGIntent.SEARCH,
                confidence=0.5,
                reasoning="未检索，禁止DONE",
            )

        # 规则 2: 同意图连续超限
        max_consecutive = _INTENT_CONFIG.get(decision.intent.value, {}).get("max_consecutive", 3)
        if self._last_intent == decision.intent and self._consecutive_count >= max_consecutive:
            fallback = self._fallback_intent(decision.intent)
            logger.info(f"[IntentBus] 循环守卫: {decision.intent.value} 连续超限，降级到 {fallback.value}")
            return IntentDecision(
                intent=fallback,
                confidence=0.5,
                reasoning=f"{decision.intent.value} 连续超限({max_consecutive})",
            )

        # 规则 3: 第 7 轮强制收束
        if self._round_count >= self.MAX_TOTAL_ROUNDS - 1 and decision.intent not in (RAGIntent.PRESENT, RAGIntent.DONE):
            logger.info("[IntentBus] 循环守卫: 接近轮数上限，强制 PRESENT")
            return IntentDecision(intent=RAGIntent.PRESENT, confidence=0.6, reasoning="轮数收束")

        # 规则 4: DONE 置信度不足
        if decision.intent == RAGIntent.DONE and decision.confidence < self.DONE_MIN_CONFIDENCE:
            logger.info(f"[IntentBus] 循环守卫: DONE 置信度不足({decision.confidence})，降级")
            return IntentDecision(intent=RAGIntent.PRESENT, confidence=0.6, reasoning="DONE 置信度不足")

        return None

    def _fallback_intent(self, current: RAGIntent) -> RAGIntent:
        """获取当前意图的降级意图"""
        fallback_map = {
            RAGIntent.SEARCH: RAGIntent.REFINE,
            RAGIntent.DIGEST: RAGIntent.SEARCH,
            RAGIntent.REFINE: RAGIntent.PRESENT,
            RAGIntent.PRESENT: RAGIntent.DONE,
            RAGIntent.DONE: RAGIntent.DONE,
        }
        return fallback_map.get(current, RAGIntent.PRESENT)

    def _reset_cycle(self, query: str) -> None:
        """重置意图循环状态"""
        self._intent_history.clear()
        self._round_count = 0
        self._query = query
        self._last_intent = None
        self._consecutive_count = 0
        self._searched = False

    # ------------------------------------------------------------------
    # 属性 & 统计
    # ------------------------------------------------------------------

    @property
    def intent_trace(self) -> List[Dict[str, Any]]:
        """返回意图转换历史"""
        return [
            {
                "step": r.step,
                "intent": r.intent.value,
                "confidence": r.confidence,
                "reasoning": r.reasoning,
                "latency_ms": round(r.latency_ms, 1),
            }
            for r in self._intent_history
        ]

    @property
    def stats(self) -> Dict[str, Any]:
        """返回统计信息"""
        return {
            "session_id": self.session_id,
            "round_count": self._round_count,
            "intent_trace": self.intent_trace,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_size": len(self._cache),
        }

    def clear_cache(self) -> None:
        """清除缓存"""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0


# ============================================================================
# 辅助函数
# ============================================================================


def _match_preload_cache(query: str) -> Optional[str]:
    """匹配预加载意图缓存

    匹配规则：
      1. 精确匹配
      2. 前缀通配（"搜*" 匹配 "搜" 开头的 query）
      3. 子串包含（非通配模式，query 包含模式关键词）
    """
    # 精确匹配
    if query in _PRELOAD_INTENT_CACHE:
        return _PRELOAD_INTENT_CACHE[query]

    # 前缀通配
    for pattern, intent in _PRELOAD_INTENT_CACHE.items():
        if pattern.endswith("*") and query.startswith(pattern[:-1]):
            return intent

    # 子串包含（仅限短关键词，避免误匹配）
    for pattern, intent in _PRELOAD_INTENT_CACHE.items():
        if "*" not in pattern and len(pattern) >= 2 and pattern in query:
            # 只在 query 较短时做子串匹配
            if len(query) <= 20:
                return intent

    return None


def _rule_based_classify(query: str, has_searched: bool = False) -> Optional[IntentDecision]:
    """基于规则的正则快速分类

    分类规则优先级：
      1. 上传/导入类 → DIGEST
      2. 对比/分析类（有检索结果时） → REFINE
      3. 简单知识问答 → SEARCH
      4. 已检索且信息足够 → PRESENT
    """
    # 上传/消化类
    upload_patterns = [
        r"(上传|导入|消化|学习).*(文档|文件|知识|数据)",
        r"(帮我|请).*(上传|导入|消化)",
    ]
    for pat in upload_patterns:
        if re.search(pat, query):
            return IntentDecision(intent=RAGIntent.DIGEST, confidence=0.85, reasoning="上传/消化模式")

    # 精炼类（需要去重/排序）
    refine_patterns = [
        r"(对比|比较|区别|vs\.?|哪个更好|哪个更)",
        r"(汇总|总结|归纳).*结果",
        r"(排序|筛选|去重|精炼)",
    ]
    for pat in refine_patterns:
        if re.search(pat, query):
            return IntentDecision(intent=RAGIntent.REFINE, confidence=0.80, reasoning="精炼模式")

    # 已检索且是简单确认 → PRESENT
    if has_searched and len(query) <= 15:
        confirm_patterns = [r"^(对的|没错|是的|不对|不是|可以|行|好)", r"^(继续|再来|下一个|还有)"]
        for pat in confirm_patterns:
            if re.search(pat, query):
                return IntentDecision(intent=RAGIntent.PRESENT, confidence=0.85, reasoning="确认/继续模式")

    return None


async def _llm_classify_intent(
    query: str,
    history: Optional[List[Dict[str, Any]]] = None,
    has_searched: bool = False,
) -> Optional[IntentDecision]:
    """LLM 意图分类（复杂查询兜底）

    使用轻量 Prompt 让 LLM 输出 JSON 格式意图决策。
    """
    try:
        from src.services.llm import call_llm_fast

        searched_note = "true" if has_searched else "false"

        prompt = f"""你是意图分类器。分析用户查询，返回 JSON。

## 意图类型
- SEARCH: 需要检索知识库
- DIGEST: 需要消化/导入新知识
- REFINE: 需要对已有结果精炼/对比/排序
- PRESENT: 信息足够，直接生成回答
- DONE: 结束

## 上下文
已执行检索: {searched_note}

## 用户查询
{query}

## 输出（仅 JSON）
{{"intent":"SEARCH","confidence":0.85,"reasoning":"简因≤20字"}}"""

        result = await call_llm_fast(prompt, max_tokens=150)
        if not result:
            return None

        # 清理 JSON
        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[1].rsplit("```", 1)[0]

        data = json.loads(result)
        intent_str = data.get("intent", "SEARCH").upper()
        confidence = float(data.get("confidence", 0.7))
        reasoning = data.get("reasoning", "LLM分类")[:20]

        # 验证 intent 有效性
        valid_intents = {e.value for e in RAGIntent}
        if intent_str not in valid_intents:
            intent_str = "SEARCH"

        return IntentDecision(
            intent=RAGIntent(intent_str),
            confidence=min(max(confidence, 0.0), 1.0),
            reasoning=reasoning,
        )

    except Exception as e:
        logger.debug(f"[IntentBus] LLM 分类异常: {e}")
        return None


# ============================================================================
# 默认处理器工厂
# ============================================================================


async def default_search_handler(query: str, context: Dict[str, Any], decision: IntentDecision) -> Dict[str, Any]:
    """默认 SEARCH 处理器：调用混合检索"""
    try:
        from src.services.retrieval import hybrid_search
        results = await hybrid_search(query, top_k=10)
        summary = f"检索到 {len(results)} 条结果"
        for i, r in enumerate(results[:3]):
            summary += f"\n  [{i + 1}] {r.get('file_name', '')}: {r.get('text', '')[:80]}..."
        return {"results": results, "summary": summary, "count": len(results)}
    except Exception as e:
        return {"error": str(e), "summary": f"检索失败: {e}"}


async def default_refine_handler(query: str, context: Dict[str, Any], decision: IntentDecision) -> Dict[str, Any]:
    """默认 REFINE 处理器：调用重排序"""
    results = context.get("results", [])
    if not results:
        return {"summary": "无结果可精炼"}
    try:
        from src.services.retrieval import _rerank_layer
        reranked = await _rerank_layer(query, results, top_k=5)
        return {"results": reranked, "summary": f"精炼后 {len(reranked)} 条", "count": len(reranked)}
    except Exception as e:
        return {"results": results, "summary": f"精炼跳过: {e}", "count": len(results)}


async def default_present_handler(query: str, context: Dict[str, Any], decision: IntentDecision) -> Dict[str, Any]:
    """默认 PRESENT 处理器：生成最终回答"""
    results = context.get("results", [])
    try:
        from src.services.llm import call_llm
        ctx_text = "\n".join([r.get("text", "")[:300] for r in results[:5]])
        prompt = f"""基于以下参考资料回答用户问题。如资料不足，据实说明。

## 参考资料
{ctx_text if ctx_text else "（无参考资料）"}

## 用户问题
{query}

## 回答（简洁、准确）"""
        answer = await call_llm(prompt)
        return {"answer": answer, "summary": "回答已生成"}
    except Exception as e:
        return {"answer": f"抱歉，生成回答时出错: {e}", "summary": "生成失败"}


def create_default_intent_bus(session_id: str = "") -> IntentBus:
    """工厂函数：创建预配置的 IntentBus 实例

    自动注册默认处理器：
      SEARCH → hybrid_search
      REFINE → rerank
      PRESENT → LLM 生成
      DIGEST → 空操作（需外部注册）
    """
    bus = IntentBus(session_id=session_id)
    bus.register_handler(RAGIntent.SEARCH, default_search_handler)
    bus.register_handler(RAGIntent.REFINE, default_refine_handler)
    bus.register_handler(RAGIntent.PRESENT, default_present_handler)
    logger.info(f"[IntentBus] 创建默认实例 session={bus.session_id}")
    return bus
