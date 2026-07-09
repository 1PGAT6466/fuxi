"""
crag_corrector.py — CRAG 纠正器
检索质量评估 + 纠正重试
"""
import logging
from typing import Dict, List

logger = logging.getLogger("shaoyin.crag_corrector")


class RetrievalEvaluator:
    """检索质量评估"""

    def evaluate(self, query: str, results: List[Dict]) -> str:
        """
        评估检索质量
        返回: GOOD / NEED_REWRITE / OFF_TOPIC
        """
        if not results:
            return "NEED_REWRITE"

        max_score = max([r.get("score", 0) for r in results], default=0)

        # 检查最高分
        if max_score < 0.3:
            return "NEED_REWRITE"

        # 检查相关性
        try:
            import jieba
            query_keywords = set(jieba.cut(query))
        except Exception as e:  # TODO: Narrow exception type
            logger.warning("jieba分词失败(查询): %s", e, exc_info=True)
            query_keywords = set(query.split())

        for r in results[:3]:
            text = r.get("text", "")
            try:
                result_keywords = set(jieba.cut(text))
            except Exception as e:  # TODO: Narrow exception type
                logger.warning("jieba分词失败(结果): %s", e, exc_info=True)
                result_keywords = set(text.split())

            overlap = len(query_keywords & result_keywords) / len(query_keywords) if query_keywords else 0
            if overlap > 0.3:
                return "GOOD"

        return "OFF_TOPIC"


class CRAGCorrector:
    """CRAG 纠正器"""

    def __init__(self):
        self.evaluator = RetrievalEvaluator()

    async def correct_and_retry(self, query: str, results: List[Dict], top_k: int = 15) -> List[Dict]:
        """评估 + 纠正重试"""
        # 1. 评估检索质量
        quality = self.evaluator.evaluate(query, results)

        if quality == "GOOD":
            logger.info("[CRAG] 检索质量 GOOD, 无需纠正")
            return results

        if quality == "OFF_TOPIC":
            logger.info("[CRAG] 检索结果 OFF_TOPIC, 返回空")
            return []

        # 2. NEED_REWRITE: 重写查询并重试
        logger.info("[CRAG] 检索质量 NEED_REWRITE, 重写查询")
        rewritten = self._rewrite_query(query)
        new_results = await self._search(rewritten, top_k)

        if new_results:
            logger.info(f"[CRAG] 重写后检索到 {len(new_results)} 条结果")
            return new_results

        logger.info("[CRAG] 重写后仍无结果")
        return []

    def _rewrite_query(self, query: str) -> str:
        """重写查询（简化版）"""
        rewritten = query
        for word in ["什么是", "怎么", "如何", "为什么", "请"]:
            rewritten = rewritten.replace(word, "")
        return rewritten.strip()

    async def _search(self, query: str, top_k: int) -> List[Dict]:
        """执行检索"""
        try:
            from src.taiyang.retrieval import hybrid_search
            return await hybrid_search(query, top_k=top_k)
        except Exception as e:  # TODO: Narrow exception type
            logger.error(f"[CRAG] 检索失败: {e}")
            return []
