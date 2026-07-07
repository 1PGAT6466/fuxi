"""
utility_layer.py — 肾工具层

职责：辅助函数（计算/格式化/判断）
"""

import logging
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger("kidney.utility")


class KidneyUtilityLayer:
    """肾工具层——辅助函数"""

    # ── 计算函数 ──

    @staticmethod
    def calculate_quality_score(chunk: Dict) -> float:
        """计算数据块质量分数（0.0-1.0）
        
        评分维度：
        1. 访问频率（0-0.3分）
        2. 新鲜度（0-0.1分）
        3. 完整性（0-0.4分）
        """
        score = 0.5

        # 1. 访问频率
        access_count = chunk.get("access_count", 0)
        if access_count > 10:
            score += 0.3
        elif access_count > 3:
            score += 0.15
        elif access_count == 0:
            score -= 0.3

        # 2. 新鲜度
        created_at = chunk.get("created_at", "")
        if created_at:
            try:
                created = datetime.fromisoformat(created_at.replace("Z", ""))
                days_old = (datetime.now() - created).days
                if days_old < 30:
                    score += 0.1
                elif days_old > 180:
                    score -= 0.1
            except (ValueError, TypeError) as e:
                logger.warning(f"[Kidney] 解析 created_at 失败 '{created_at}': {e}")

        # 3. 完整性
        if not chunk.get("text", "").strip():
            score -= 0.4

        return max(min(score, 1.0), 0.0)

    @staticmethod
    def calculate_deficiency(count: int, average: float) -> float:
        """计算薄弱程度（0.0-1.0）"""
        if average <= 0:
            return 1.0
        return round(1 - count / average, 2)

    # ── 判断函数 ──

    @staticmethod
    def is_stale(last_access: float, stale_days: int) -> bool:
        """判断是否过期"""
        import time
        if not last_access:
            return True
        days_stale = (time.time() - last_access) / 86400
        return days_stale > stale_days

    @staticmethod
    def is_essence(score: float, threshold: float = 0.5) -> bool:
        """判断是否为精华"""
        return score >= threshold

    @staticmethod
    def is_deficient(count: int, average: float, threshold: float = 0.3) -> bool:
        """判断是否薄弱"""
        return count < average * threshold

    # ── 格式化函数 ──

    @staticmethod
    def format_filter_result(total: int, essence: int, waste: int) -> Dict:
        """格式化过滤结果"""
        return {
            "total_chunks": total,
            "essence": essence,
            "waste": waste,
            "essence_ratio": round(essence / max(total, 1), 2),
        }

    @staticmethod
    def format_purge_result(purged: int, total_purged: int) -> Dict:
        """格式化清理结果"""
        return {
            "purged": purged,
            "total_purged": total_purged,
        }

    @staticmethod
    def format_deficiency_result(weak_areas: List[Dict], category_distribution: Dict) -> Dict:
        """格式化薄弱检测结果"""
        return {
            "weak_areas": weak_areas,
            "category_distribution": category_distribution,
        }

    @staticmethod
    def format_stats(filter_count: int, purged_total: int, essence_total: int,
                     running: bool, stale_days: int, alive: bool) -> Dict:
        """格式化统计信息"""
        return {
            "filter_count": filter_count,
            "purged_total": purged_total,
            "essence_total": essence_total,
            "running": running,
            "stale_days_threshold": stale_days,
            "alive": alive,
        }
