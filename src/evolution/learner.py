"""
learner.py — 离线学习封装层（第九宫 · 中宫）

封装 src/services/learner.py 的术语权重调整、个性化 boost、
高频术语提取等功能，在第九宫（EvolutionGua）框架内统一调用。

不复制代码，全部 import 自 services/learner。
"""

import logging
from typing import Dict, List

# ---- 从 services 导入原有实现 ----
from src.services.learner import (
    update_term_weight,
    log_feedback as _learner_log_feedback,
    extract_new_terms,
    get_personalized_boost,
    get_feedback_stats as _learner_get_stats,
)

logger = logging.getLogger("evolution.learner")


class EvolutionLearner:
    """演化学习器 — 第九宫的离线学习组件

    封装 services/learner 的底层实现，提供一致的演化层接口。

    主要功能：
      - learn_from_feedback(): 从批量反馈学习，调整术语权重
      - extract_terms():      从文本提取高频专业术语
      - personalize():        基于用户历史返回个性化 boost
      - stats():              获取学习统计
    """

    def __init__(self):
        self._initialized = True
        logger.info("[EvolutionLearner] 初始化完成")

    async def learn_from_feedback(self, feedback_batch: List[Dict]) -> Dict:
        """从批量反馈中学习

        对每条反馈调整术语权重：👍/like/copy/click → +0.1，👎/dislike → -0.05

        Args:
            feedback_batch: 反馈条目列表，每项含:
                - query:  查询文本
                - action: like/dislike/correct/copy/click

        Returns:
            {"ok": bool, "processed": int, "terms_updated": int}
        """
        terms_updated = 0
        processed = 0

        for item in feedback_batch:
            query = item.get("query", "")
            action = item.get("action", "")
            processed += 1

            if action in ("like", "copy", "click"):
                for term in query.split():
                    if len(term) >= 2:
                        update_term_weight(term, positive=True)
                        terms_updated += 1
            elif action == "dislike":
                for term in query.split():
                    if len(term) >= 2:
                        update_term_weight(term, positive=False)
                        terms_updated += 1
            elif action == "correct":
                # 更正反馈也记录
                correction = item.get("correction", "")
                if correction:
                    _learner_log_feedback(
                        query=query,
                        file_hash=item.get("file_hash", ""),
                        chunk_index=item.get("chunk_index", 0),
                        action="correct",
                        correction=correction,
                    )

        logger.info(
            "[EvolutionLearner] 学习完成: processed=%d terms_updated=%d",
            processed, terms_updated,
        )
        return {"ok": True, "processed": processed, "terms_updated": terms_updated}

    def extract_terms(self, text: str, min_freq: int = 3) -> List[str]:
        """从文本中提取高频专业术语

        Args:
            text:     待分析的文本
            min_freq: 最小词频阈值（默认 3）

        Returns:
            术语列表（最多 50 条）
        """
        return extract_new_terms(text, min_freq=min_freq)

    def personalize(self, query: str) -> Dict[str, float]:
        """基于用户反馈历史返回个性化术语 boost

        Args:
            query: 查询文本

        Returns:
            {term: boost_value, ...} 例如 {"OpenAI": 0.4}
        """
        return get_personalized_boost(query)

    def stats(self, days: int = 7) -> Dict:
        """获取近 N 天反馈学习统计

        Args:
            days: 统计天数（默认 7）

        Returns:
            {"total": int, "likes": int, "dislikes": int, "corrections": int}
        """
        return _learner_get_stats(days=days)


# ---- 便捷函数 ----

async def learn_from_feedback(feedback_batch: List[Dict]) -> Dict:
    """便捷函数：从批量反馈中学习

    等价于 EvolutionLearner().learn_from_feedback(feedback_batch)

    Args:
        feedback_batch: 反馈条目列表

    Returns:
        {"ok": bool, "processed": int, "terms_updated": int}
    """
    learner = EvolutionLearner()
    return await learner.learn_from_feedback(feedback_batch)


def get_learner_stats(days: int = 7) -> Dict:
    """便捷函数：获取学习者统计"""
    learner = EvolutionLearner()
    return learner.stats(days=days)
