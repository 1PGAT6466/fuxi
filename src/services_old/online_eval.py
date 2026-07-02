"""
online_eval.py — 在线评估 (v1.43)
从用户行为自动构建评测信号，写入审计日志
"""
import time, logging
from typing import Dict, Optional
from src.services.audit import log_audit

logger = logging.getLogger(__name__)


def record_search_quality(query: str, result_count: int, duration_ms: int, user_feedback: str = ""):
    """记录搜索质量信号"""
    quality = "good" if result_count > 0 else "empty"
    if duration_ms > 10000:
        quality = "slow"
    
    log_audit(
        action="search_quality",
        query=query,
        result_summary=f"results={result_count}, duration={duration_ms}ms",
        duration_ms=duration_ms,
        status=quality,
        metadata={"result_count": result_count, "user_feedback": user_feedback},
    )


def record_answer_quality(query: str, answer: str, judge_score: int, fact_check_score: float):
    """记录答案质量信号"""
    quality = "good" if judge_score >= 3 else "poor"
    
    log_audit(
        action="answer_quality",
        query=query,
        result_summary=f"judge={judge_score}, fact_check={fact_check_score}",
        status=quality,
        metadata={"judge_score": judge_score, "fact_check_score": fact_check_score},
    )


def record_feedback(user_id: str, query: str, action: str, answer_preview: str = ""):
    """记录用户反馈"""
    log_audit(
        action=f"feedback_{action}",
        query=query,
        user_id=user_id,
        result_summary=answer_preview[:200],
        status="feedback",
    )


def get_quality_trend(hours: int = 24) -> Dict:
    """获取质量趋势"""
    from src.services.audit import get_audit_stats
    stats = get_audit_stats(hours)
    
    search_stats = stats.get("search_quality", {"count": 0, "avg_ms": 0})
    answer_stats = stats.get("answer_quality", {"count": 0})
    feedback_stats = {k: v for k, v in stats.items() if k.startswith("feedback_")}
    
    return {
        "search": search_stats,
        "answer": answer_stats,
        "feedback": feedback_stats,
        "total_queries": sum(v.get("count", 0) for v in stats.values()),
    }
