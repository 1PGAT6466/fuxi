"""
大脑 v1.50 — 伏羲唯一的意识

精修内容：
1. Instinct: 关键词 → 多意图联合识别 + 消歧规则
2. 思考记忆: 最近 N 轮对话自动融入当前思考
3. 降级链: 验证 deepseek → ollama → 模板的完整路径
4. 自我纠错: 低置信度触发重新组装
"""

import asyncio
import logging
import time
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.hypothalamus.meridian import Meridian, Signal, SignalPriority

logger = logging.getLogger("brain")

# ========== 伏羲人格 ==========
# FUXI_PERSONA: 从 config.PROMPTS 读取（版本化管理）
from src.config import PROMPTS
FUXI_PERSONA = PROMPTS.get("fuxi_persona", "你是伏羲，企业知识认知中枢。")


# ========== Instinct（本能）v1.42 ==========

# 多意图关键词表：一个查询可以同时命中多个意图
_INTENT_PATTERNS: Dict[str, List[str]] = {
    "compare": [
        r"和.*比较", r"和.*区别", r"和.*哪个好", r"对比", r"vs\.?", r"差异",
        r"哪个更", r"优缺点", r"优劣", r"选哪个", r"更适合", r"比起",
        r"相对于", r"与.*相比", r"选用.*还是",
    ],
    "numeric_lookup": [
        r"参数", r"温度", r"熔点", r"密度", r"收缩率", r"强度", r"硬度",
        r"拉伸", r"弯曲", r"冲击强度", r"模量", r"热变形", r"熔点",
        r"多少度", r"多少mpa", r"多少gpa", r"比重", r"粘度",
        r"规格", r"尺寸公差", r"粗糙度", r"间隙",
    ],
    "table_query": [
        r"bom", r"清单", r"采购", r"型号表", r"物料表", r"选型表",
        r"规格表", r"有哪些.*型号", r"表格",
    ],
    "definition": [
        r"是什么", r"定义", r"什么叫", r"什么是", r"含义",
        r"全称", r"缩写", r"简称", r"解释",
    ],
    "how_to": [
        r"怎么", r"如何", r"步骤", r"流程", r"方法", r"操作",
        r"配置", r"设置", r"安装", r"部署", r"调试",
    ],
    "material_selector": [
        r"选材", r"哪种材料", r"用什么材料", r"材料选择",
        r"替代.*材料", r"替代品", r"可以代替",
    ],
}

_INTENT_ORDER = ["compare", "numeric_lookup", "material_selector", "table_query", "definition", "how_to"]


class Instinct:
    """伏羲的本能——零延迟意图识别
    
    v1.42: 从单一意图 → 多意图联合识别
    查询"PA66和POM哪个更适合做齿轮" → [compare, material_selector, numeric_lookup]
    """
    
    @staticmethod
    def classify_intent(query: str, context: List[str] = None) -> Dict[str, Any]:
        """多意图分类——返回所有命中的意图及其置信度"""
        query = query.strip().lower()
        intents = {}
        primary = "general_search"
        primary_score = 0
        
        for intent in _INTENT_ORDER:
            patterns = _INTENT_PATTERNS.get(intent, [])
            matches = 0
            for pat in patterns:
                if re.search(pat, query):
                    matches += 1
            if matches > 0:
                score = min(matches / max(len(patterns) * 0.2, 1), 1.0)
                intents[intent] = round(score, 2)
                if score > primary_score:
                    primary = intent
                    primary_score = score
        
        # 上下文消歧：如果上文在讨论材料，当前问"参数"不加 material_lookup 就失忆了
        if context:
            ctx_text = " ".join(context).lower()
            if "材料" in ctx_text or "材料" in query or "pa" in query or "pom" in query or "pc" in query:
                if "material_selector" not in intents and any(kw in query for kw in ["材料", "选", "替代"]):
                    intents["material_selector"] = 0.5
            if "对比" in ctx_text or "比较" in ctx_text:
                if "compare" not in intents:
                    intents["compare"] = 0.4
        
        # 材料名检测：含材料名时自动标记 material_selector
        material_pattern = r"(pa\d{1,2}|pom|pc|abs|pps|pbt|pei|peek|ptfe|pmma|lcp)"
        if re.search(material_pattern, query):
            if "material_selector" not in intents:
                intents["material_selector"] = 0.5
            # 只有材料名没有意图词 → 默认 definition + numeric_lookup
            if len(intents) <= 1 and primary == "general_search":
                intents["definition"] = 0.5
                intents["numeric_lookup"] = 0.3
        
        return {
            "intent": primary,
            "intents": intents,
            "count": len(intents),
        }
    
    @staticmethod
    def needs_table_search(intent: Dict) -> bool:
        return "table_query" in intent.get("intents", {})
    
    @staticmethod
    def needs_graph_reasoning(intent: Dict) -> bool:
        return "compare" in intent.get("intents", {}) or intent.get("intent") == "compare"
    
    @staticmethod
    def needs_external_search(intent: Dict, internal_hits: int) -> bool:
        """体内命中不足 + 需要事实性答案 → 触发外探"""
        if internal_hits >= 3:
            return False
        high_need = {"numeric_lookup", "definition", "material_selector"}
        return bool(set(intent.get("intents", {}).keys()) & high_need)
    
    @staticmethod
    def estimate_complexity(query: str, intent: Dict) -> int:
        """评估查询复杂度 (1-5)"""
        score = 1
        
        # 多意图 → 更复杂
        count = intent.get("count", 1)
        if count >= 3:
            score += 2
        elif count >= 2:
            score += 1
        
        # 比较类需要综合分析 → 高复杂度
        if intent.get("intent") == "compare" or "compare" in intent.get("intents", {}):
            score += 1
        
        # 长查询 → 更复杂
        if len(query) > 30:
            score += 1
        if len(query) > 80:
            score += 1
        
        return min(score, 5)


# ========== Thought（思维）==========

@dataclass
class Thought:
    """一次完整的思考"""
    query: str
    intent: Dict = field(default_factory=dict)
    results: Dict = field(default_factory=dict)
    answer: str = ""
    confidence: float = 0.0
    duration_ms: float = 0.0
    retries: int = 0  # v1.42: 自我纠错重试次数


# ========== Brain（大脑）v1.42 ==========

class Brain:
    """伏羲的大脑——唯一意识中心
    
    v1.42 精修:
    - 多意图本能
    - 思考记忆（上下文链）
    - 三级降级链 (deepseek → ollama → 模板)
    - 低置信度自我纠错
    """
    
    AGGREGATE_PROMPT = """{persona}

用户问题：{query}

知识库检索结果：
{context}

请根据以上检索结果回答用户问题。如果检索结果不足以回答问题，请诚实说明，不要编造。
来源引用格式：[来源: 文件名]
"""
    
    RETRY_PROMPT = """你之前的回答置信度过低（{score}）。

用户问题是：{query}

请仔细重新审视所有知识库结果，找出最相关的信息重新组织回答。
如果确实没有足够的相关信息，请明确说"知识库中未找到与此问题直接相关的信息"。
"""
    
    FALLBACK_TEMPLATE = """抱歉，我当前无法进行深度思考。

关于「{query}」，知识库中有以下相关内容：

{summary}

如需详细分析，请稍后再试，或联系管理员检查 LLM 服务状态。
"""
    
    def __init__(self, meridian: Meridian, llm_call=None, ollama_call=None):
        self.meridian = meridian
        self.instinct = Instinct()
        self.llm_call = llm_call or self._default_llm
        self.ollama_call = ollama_call  # Ollama 降级入口
        self._recent_thoughts: List[Thought] = []
        self._conversation_context: List[str] = []  # v1.42: 对话记忆
        self._conversation_history: List[Dict] = []  # v1.43: 完整对话历史(query+answer+intent)
        self._stats = {"thoughts": 0, "complex_success": 0, "retries": 0, "fallbacks": 0}
        
        self.meridian.register_organ("brain", "乾·大脑", "🧠", "伏羲唯一意识中心——多意图本能+三级降级+记忆")
        self.meridian.subscribe("brain", "heartbeat", self._handle_heartbeat)
        self.meridian.subscribe("brain", "query", self._handle_query)
    
    async def _handle_heartbeat(self, signal: Signal) -> None:
        self.meridian.heartbeat("brain")
    
    async def _handle_query(self, signal: Signal) -> None:
        query = signal.payload.get("query", "")
        enable_external = signal.payload.get("enable_external", False)
        result = await self.think(query, enable_external=enable_external)
        self.meridian.reply(signal, result)
    
    # ========== 主入口 ==========
    
    async def think(self, query: str, enable_external: bool = False) -> Dict:
        """大脑的一次完整思考
        
        Phase 1: 本能判断（多意图+上下文记忆）
        Phase 2: 体内检索（经络四肢）
        Phase 3: 外探（条件触发）
        Phase 4: LLM 合成（三级降级）
        Phase 5: 自我评估 → 低分纠错
        """
        t0 = time.time()
        self._stats["thoughts"] += 1
        thought = Thought(query=query)
        
        # Phase 1: 本能
        intent = self.instinct.classify_intent(query, self._conversation_context)
        complexity = self.instinct.estimate_complexity(query, intent)
        thought.intent = intent
        
        # Phase 2: 体内检索
        internal_results = await self._search_internal(query, intent)
        thought.results["internal"] = internal_results
        
        # Phase 3: 外探
        external_results = None
        internal_hits = len(internal_results.get("chunks", []))
        if enable_external and self.instinct.needs_external_search(intent, internal_hits):
            external_results = await self._search_external(query)
            thought.results["external"] = external_results
        
        # Phase 4: LLM 合成
        if complexity >= 3:
            answer = await self._compose_with_llm(query, thought.results)
        else:
            answer = self._compose_direct(query, thought.results)
        thought.answer = answer
        
        # Phase 5: 自我评估 + 纠错
        confidence = self._self_assess(answer, thought.results, intent)
        thought.confidence = confidence
        
        # v1.42: 低置信度自我纠错
        if confidence < 0.5 and thought.retries < 2:
            thought.retries += 1
            self._stats["retries"] += 1
            logger.info(f"[Brain] Low confidence ({confidence}), retrying...")
            retry_answer = await self._retry_compose(query, thought.results, confidence)
            retry_score = self._self_assess(retry_answer, thought.results, intent)
            if retry_score > confidence:
                thought.answer = retry_answer
                thought.confidence = retry_score
                logger.info(f"[Brain] Retry improved confidence: {confidence} → {retry_score}")
        
        thought.duration_ms = round((time.time() - t0) * 1000, 1)
        
        # 记忆
        self._recent_thoughts.append(thought)
        if len(self._recent_thoughts) > 50:
            self._recent_thoughts = self._recent_thoughts[-50:]
        # 上下文记忆（最近 10 轮，保留 query+answer）
        self._conversation_history.append({
            "query": query,
            "answer": (thought.answer or "")[:200],
            "intent": intent.get("intent", "general_search"),
        })
        if len(self._conversation_history) > 10:
            self._conversation_history = self._conversation_history[-10:]
        # 兼容旧接口：同步到 _conversation_context
        self._conversation_context = [
            f"Q: {t['query']} A: {t['answer'][:80]}" for t in self._conversation_history
        ]
        
        return {
            "answer": thought.answer,
            "confidence": thought.confidence,
            "intent": intent["intent"],
            "intents": intent.get("intents", {}),
            "complexity": complexity,
            "duration_ms": thought.duration_ms,
            "from_external": external_results is not None,
            "retries": thought.retries,
            "sources": self._extract_sources(thought.results),
        }
    
    # ========== 检索 ==========
    
    async def _search_internal(self, query: str, intent: Dict) -> Dict:
        """经络四肢检索，经络不通时降级直调"""
        t0 = time.time()
        
        result = await self.meridian.send_and_wait(
            Signal(source="brain", target="limbs", signal_type="search",
                   payload={"query": query, "top_k": self._top_k_for_intent(intent)},
                   priority=SignalPriority.HIGH),
            timeout=10.0,
        )
        
        if result is None:
            logger.warning("[Brain] Meridian search failed, direct fallback")
            result = await self._direct_search(query)
        
        logger.info(f"[Brain] Internal search: {len(result.get('chunks', []))} chunks in {time.time()-t0:.1f}s")
        return result or {"chunks": []}
    
    async def _search_external(self, query: str) -> Dict:
        """经络头发外探"""
        result = await self.meridian.send_and_wait(
            Signal(source="brain", target="skin", signal_type="search_external",
                   payload={"query": query, "top_k": 5},
                   priority=SignalPriority.NORMAL),
            timeout=15.0,
        )
        if result is None:
            logger.warning("[Brain] Hair agent unavailable, direct web search")
            result = await self._direct_external_search(query)
        return result or {"results": []}
    
    # ========== LLM 合成（三级降级）==========
    
    async def _compose_with_llm(self, query: str, results: Dict) -> str:
        """三级降级: deepseek → ollama → 模板拼接"""
        context = self._build_context(results)
        prompt = self.AGGREGATE_PROMPT.format(persona=FUXI_PERSONA, query=query, context=context or "无相关信息")
        
        # Level 1: DeepSeek (主 LLM)
        try:
            return await self.llm_call(prompt)
        except Exception as e:
            logger.warning(f"[Brain] Primary LLM failed: {e}, trying Ollama fallback")
        
        # Level 2: Ollama 本地降级
        if self.ollama_call:
            try:
                return await self.ollama_call(prompt)
            except Exception as e:
                logger.warning(f"[Brain] Ollama fallback failed: {e}")
        
        # Level 3: 模板拼接兜底
        self._stats["fallbacks"] += 1
        return self._compose_direct(query, results)
    
    async def _retry_compose(self, query: str, results: Dict, prev_score: float) -> str:
        """自我纠错：重新组织提示词"""
        prompt = self.RETRY_PROMPT.format(score=prev_score, query=query)
        raw_context = self._build_context(results, max_chunks=8)
        prompt += "\n\n检索结果：\n" + raw_context
        
        try:
            return await self.llm_call(prompt)
        except Exception:
            return self._compose_direct(query, results)
    
    def _compose_direct(self, query: str, results: Dict) -> str:
        """兜底：直接拼接"""
        chunks = results.get("internal", {}).get("chunks", [])
        if not chunks:
            ext = results.get("external", {}).get("results", [])
            if ext:
                return f"关于「{query}」，通过外部网络找到以下信息：\n\n" + \
                       "\n".join(f"- {r.get('text', '')[:200]}" for r in ext[:3])
            return f"关于「{query}」，体内知识和外部网络均未找到相关信息。"
        
        return "\n".join(f"**{c.get('file_name', '来源')}**: {c.get('text', '')[:300]}"
                        for c in chunks[:3])
    
    # ========== 自我评估 v1.42 ==========
    
    def _self_assess(self, answer: str, results: Dict, intent: Dict = None) -> float:
        """评估答案质量"""
        if not answer or len(answer.strip()) < 10:
            return 0.1
        
        score = 0.5  # 基础分
        
        # 长度
        if len(answer) > 100:
            score += 0.1
        if len(answer) > 300:
            score += 0.05
        
        # 来源
        chunks = results.get("internal", {}).get("chunks", [])
        ext = results.get("external", {}).get("results", [])
        total = len(chunks) + len(ext)
        if total >= 3:
            score += 0.15
        if total >= 5:
            score += 0.05
        
        # 幻觉检测：如果答案里有"知识库中未找到"说明诚实，给信任分
        if "未找到" in answer or "暂无" in answer:
            if total == 0:
                score += 0.2  # 诚实+无源 → 高分（诚实）
            else:
                score -= 0.1  # 有源却说没找到 → 矛盾
        
        # 引用检测
        if "[来源:" in answer or "来源：" in answer or "reference" in answer.lower():
            score += 0.1
        
        return min(score, 1.0)
    
    # ========== 辅助 ==========
    
    def _top_k_for_intent(self, intent: Dict) -> int:
        if intent.get("intent") == "compare":
            return 15
        if intent.get("count", 1) >= 2:
            return 12
        return 10
    
    def _build_context(self, results: Dict, max_chunks: int = 5) -> str:
        parts = []
        for chunk in results.get("internal", {}).get("chunks", [])[:max_chunks]:
            parts.append(f"[{chunk.get('file_name', '来源')}] {chunk.get('text', '')[:600]}")
        for ext in results.get("external", {}).get("results", [])[:3]:
            parts.append(f"[网络] {ext.get('text', '')[:400]}")
        return "\n\n---\n\n".join(parts)
    
    def _extract_sources(self, results: Dict) -> List[Dict]:
        sources = []
        for chunk in results.get("internal", {}).get("chunks", [])[:5]:
            sources.append({"file": chunk.get("file_name", ""), "type": "internal", "score": chunk.get("score", 0)})
        for ext in results.get("external", {}).get("results", [])[:3]:
            sources.append({"file": ext.get("source_url", ext.get("title", "网络")), "type": "external", "score": ext.get("score", 0)})
        return sources
    
    # ========== 降级直调 ==========
    
    async def _direct_search(self, query: str) -> Dict:
        try:
            from src.services.retrieval import hybrid_search
            from src.db.data_store import load_chunks
            chunks = load_chunks()
            results = await hybrid_search(query, chunks, top_k=10)
            return {"chunks": results}
        except Exception as e:
            logger.error(f"[Brain] Direct search failed: {e}")
            return {"chunks": []}
    
    async def _direct_external_search(self, query: str) -> Dict:
        try:
            from src.services.parsers import brave_search
            results = await brave_search(query, count=5)
            return {"results": results}
        except Exception:
            return {"results": []}
    
    async def _default_llm(self, prompt: str) -> str:
        try:
            from src.services.llm import call_ai
            return await call_ai(prompt)
        except Exception:
            return ""
    

    async def start_pulsing(self) -> None:
        """脑波循环 — v1.42 P0修复"""
        if getattr(self, '_pulse_running', False):
            return
        self._pulse_running = True
        self._pulse_task = asyncio.create_task(self._pulse_loop())
    
    async def _pulse_loop(self) -> None:
        """持续发送大脑心跳信号"""
        while self._pulse_running:
            try:
                self.meridian.heartbeat("brain")
                await asyncio.sleep(15)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Brain] Pulse error: {e}")
                await asyncio.sleep(5)

    def stats(self) -> Dict:
        return {
            **self._stats,
            "recent_thoughts": len(self._recent_thoughts),
            "context_depth": len(self._conversation_context),
            "alive": True,
        }
