"""
smart_self_rag.py — 智能 Self-RAG
两层控制：Flag + 条件触发，规则优先 LLM 兜底
"""
import re
import logging
from typing import Dict, List, Optional

logger = logging.getLogger("shaoyin.smart_self_rag")

# 数字查询模式
NUMERIC_PATTERNS = [
    r"拉伸强度", r"硬度", r"密度", r"熔点", r"温度",
    r"压力", r"电压", r"电流", r"频率", r"转速",
    r"多少", r"数值", r"参数", r"规格", r"指标",
    r"收缩率", r"热变形", r"冲击强度", r"弯曲强度",
]

# 触发条件
TRIGGER_CONDITIONS = {
    "must_trigger": [
        {"metric": "max_score", "operator": "<", "value": 0.5},
        {"metric": "score_variance", "operator": ">", "value": 0.3},
    ],
    "skip_conditions": [
        {"metric": "max_score", "operator": ">", "value": 0.8},
    ],
}


class ReflectionResult:
    """反思结果"""
    def __init__(self, action: str, confidence: float, reason: str = ""):
        self.action = action  # pass / crag_rewrite / retry
        self.confidence = confidence
        self.reason = reason


class SmartSelfRAG:
    """智能 Self-RAG — 规则优先，LLM 兜底"""

    def __init__(self):
        pass

    async def reflect_if_needed(self, query: str, results: List[Dict], context: Dict = None) -> ReflectionResult:
        """按需触发 Self-RAG"""
        if not results:
            return ReflectionResult(action="crag_rewrite", confidence=0.0, reason="no_results")

        # 检查是否可以跳过
        if self._should_skip(results):
            logger.info("[Self-RAG] 跳过反思（高置信度）")
            return ReflectionResult(action="pass", confidence=0.9, reason="high_confidence")

        # 检查是否必须触发
        if self._must_trigger(results):
            logger.info("[Self-RAG] 触发完整反思（低置信度）")
            return await self._full_reflect(query, results)

        # 轻量级反思
        logger.info("[Self-RAG] 轻量级反思")
        return self._light_reflect(query, results)

    def _should_skip(self, results: List[Dict]) -> bool:
        """是否应该跳过"""
        max_score = max([r.get("score", 0) for r in results], default=0)
        return max_score > 0.8

    def _must_trigger(self, results: List[Dict]) -> bool:
        """是否必须触发"""
        max_score = max([r.get("score", 0) for r in results], default=0)
        return max_score < 0.5

    def _light_reflect(self, query: str, results: List[Dict]) -> ReflectionResult:
        """轻量级反思 — 规则优先（< 0.1s）"""
        # 数字查询规则检查
        if self._is_numeric_query(query):
            return self._numeric_rule_check(query, results)

        # 关键词重叠检查
        return self._keyword_overlap_check(query, results)

    def _is_numeric_query(self, query: str) -> bool:
        """是否为数字查询"""
        for pattern in NUMERIC_PATTERNS:
            if re.search(pattern, query):
                return True
        return False

    def _numeric_rule_check(self, query: str, results: List[Dict]) -> ReflectionResult:
        """数字查询规则检查"""
        for result in results[:3]:
            text = result.get("text", "")
            has_numbers = bool(re.search(r'\d+\.?\d*', text))
            if has_numbers:
                return ReflectionResult(action="pass", confidence=0.8, reason="numeric_rule_pass")

        return ReflectionResult(action="crag_rewrite", confidence=0.3, reason="no_numeric_result")

    def _keyword_overlap_check(self, query: str, results: List[Dict]) -> ReflectionResult:
        """关键词重叠检查"""
        try:
            import jieba
            query_keywords = set(jieba.cut(query))
        except:
            query_keywords = set(query.split())

        if not results:
            return ReflectionResult(action="crag_rewrite", confidence=0.0, reason="no_results")

        top_result = results[0]
        text = top_result.get("text", "")
        try:
            result_keywords = set(jieba.cut(text))
        except:
            result_keywords = set(text.split())

        overlap = len(query_keywords & result_keywords) / len(query_keywords) if query_keywords else 0

        if overlap > 0.5:
            return ReflectionResult(action="pass", confidence=0.8, reason="keyword_overlap_high")
        elif overlap > 0.3:
            return ReflectionResult(action="pass", confidence=0.6, reason="keyword_overlap_medium")
        else:
            return ReflectionResult(action="crag_rewrite", confidence=0.3, reason="keyword_overlap_low")

    async def _full_reflect(self, query: str, results: List[Dict]) -> ReflectionResult:
        """完整反思（LLM）"""
        try:
            from src.infra.llm import call_ai
            context = "\n".join([r.get("text", "")[:200] for r in results[:3]])
            prompt = f"判断以下检索结果是否回答了问题。只回答 PASS 或 FAIL。\n问题：{query}\n结果：{context}"
            response = await call_ai(prompt)
            if response and "PASS" in response.upper():
                return ReflectionResult(action="pass", confidence=0.7, reason="llm_pass")
            return ReflectionResult(action="crag_rewrite", confidence=0.3, reason="llm_fail")
        except Exception as e:
            logger.warning(f"[Self-RAG] LLM反思失败: {e}")
            return ReflectionResult(action="pass", confidence=0.5, reason="llm_error_fallback")
