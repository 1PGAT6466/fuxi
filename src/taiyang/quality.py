"""
quality.py — 太阳·检索质量评估
异常检测 + 免疫记忆
"""
import logging
from typing import Dict, List

logger = logging.getLogger("taiyang.quality")


class QualityChecker:
    """检索质量检查器"""

    def check(self, results: List[Dict], query: str) -> Dict:
        """检查检索质量"""
        issues = []

        if not results:
            issues.append("检索结果为空")

        max_score = max([r.get("score", 0) for r in results], default=0)
        if max_score < 0.3:
            issues.append(f"最高分过低: {max_score:.2f}")

        avg_score = sum([r.get("score", 0) for r in results]) / max(len(results), 1)
        if avg_score < 0.2:
            issues.append(f"平均分过低: {avg_score:.2f}")

        return {
            "quality": "good" if not issues else "degraded",
            "issues": issues,
            "max_score": max_score,
            "avg_score": avg_score,
            "result_count": len(results),
        }
