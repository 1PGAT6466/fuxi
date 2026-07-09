"""
composer.py — 少阴·LLM合成器
三级降级：MiMo→DeepSeek→模板
"""
import logging
from typing import Dict, List

logger = logging.getLogger("shaoyin.composer")


class AnswerComposer:
    """答案合成器"""

    async def compose(self, query: str, results: List[Dict],
                       history: List[Dict] = None) -> Dict:
        """合成答案"""
        if not results:
            return {
                "answer": "知识库中未找到相关信息",
                "confidence": 0.0,
                "sources": [],
            }

        context = self._build_context(results)

        try:
            from src.infra.llm import call_llm_by_task
            answer = await call_llm_by_task(
                task="synthesis",
                prompt=f"基于以下资料回答问题。\n\n资料：{context}\n\n问题：{query}\n\n回答：",
            )
            confidence = self._estimate_confidence(answer, results)
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[Composer] LLM合成失败: {e}")
            answer = self._template_compose(query, results)
            confidence = 0.3

        return {
            "answer": answer,
            "confidence": confidence,
            "sources": [{"file_name": r.get("file_name", ""), "score": r.get("score", 0)} for r in results[:5]],
        }

    def _build_context(self, results: List[Dict]) -> str:
        contexts = []
        for i, r in enumerate(results[:5]):
            text = r.get("text", "")[:500]
            source = r.get("file_name", "未知")
            contexts.append(f"[{i+1}] 来源: {source}\n{text}")
        return "\n\n".join(contexts)

    def _template_compose(self, query: str, results: List[Dict]) -> str:
        answer = f"关于「{query}」，以下是相关信息：\n\n"
        for i, r in enumerate(results[:3]):
            text = r.get("text", "")[:200]
            source = r.get("file_name", "未知")
            answer += f"{i+1}. {text}（来源: {source}）\n"
        return answer

    def _estimate_confidence(self, answer: str, results: List[Dict]) -> float:
        if not answer or len(answer) < 20:
            return 0.2
        max_score = max([r.get("score", 0) for r in results], default=0)
        return min(0.9, max_score + 0.2)
