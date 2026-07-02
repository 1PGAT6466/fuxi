"""
online_eval.py — 在线评测
实时监控检索质量
"""
import json
import logging
import time
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger("services.online_eval")

ONLINE_EVAL_DIR = Path("data/online_eval")


class OnlineEvaluator:
    """在线评测器"""

    def __init__(self):
        ONLINE_EVAL_DIR.mkdir(parents=True, exist_ok=True)
        self._metrics_buffer: List[Dict] = []
        self._flush_interval = 100  # 每100条刷新一次

    async def record_search_metric(self, query: str, results: List[Dict],
                                     latency_ms: float, trace_id: str = ""):
        """记录检索指标"""
        metric = {
            "timestamp": time.time(),
            "type": "search",
            "query": query[:100],
            "result_count": len(results),
            "max_score": max([r.get("score", 0) for r in results], default=0),
            "avg_score": sum([r.get("score", 0) for r in results]) / max(len(results), 1),
            "latency_ms": latency_ms,
            "trace_id": trace_id,
        }

        self._metrics_buffer.append(metric)

        if len(self._metrics_buffer) >= self._flush_interval:
            await self._flush_metrics()

    async def record_feedback(self, query: str, result_id: str,
                                feedback: str, rating: int = 0):
        """记录用户反馈"""
        metric = {
            "timestamp": time.time(),
            "type": "feedback",
            "query": query[:100],
            "result_id": result_id,
            "feedback": feedback,
            "rating": rating,
        }

        self._metrics_buffer.append(metric)

        if len(self._metrics_buffer) >= self._flush_interval:
            await self._flush_metrics()

    async def _flush_metrics(self):
        """刷新指标到文件"""
        if not self._metrics_buffer:
            return

        try:
            metrics_file = ONLINE_EVAL_DIR / "metrics.jsonl"
            with open(metrics_file, "a", encoding="utf-8") as f:
                for metric in self._metrics_buffer:
                    f.write(json.dumps(metric, ensure_ascii=False) + "\n")

            self._metrics_buffer.clear()
        except Exception as e:
            logger.warning(f"[OnlineEval] 刷新指标失败: {e}")

    async def get_stats(self, hours: int = 24) -> Dict:
        """获取统计信息"""
        metrics_file = ONLINE_EVAL_DIR / "metrics.jsonl"

        if not metrics_file.exists():
            return {"total_queries": 0, "avg_latency_ms": 0}

        metrics = []
        cutoff = time.time() - hours * 3600

        try:
            with open(metrics_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        metric = json.loads(line.strip())
                        if metric.get("timestamp", 0) > cutoff:
                            metrics.append(metric)
                    except:
                        pass
        except Exception:
            pass

        if not metrics:
            return {"total_queries": 0, "avg_latency_ms": 0}

        search_metrics = [m for m in metrics if m.get("type") == "search"]
        feedback_metrics = [m for m in metrics if m.get("type") == "feedback"]

        stats = {
            "total_queries": len(search_metrics),
            "avg_latency_ms": sum([m.get("latency_ms", 0) for m in search_metrics]) / max(len(search_metrics), 1),
            "avg_result_count": sum([m.get("result_count", 0) for m in search_metrics]) / max(len(search_metrics), 1),
            "avg_max_score": sum([m.get("max_score", 0) for m in search_metrics]) / max(len(search_metrics), 1),
            "feedback_count": len(feedback_metrics),
            "avg_rating": sum([m.get("rating", 0) for m in feedback_metrics]) / max(len(feedback_metrics), 1),
        }

        return stats

    async def get_slow_queries(self, threshold_ms: float = 3000,
                                 limit: int = 10) -> List[Dict]:
        """获取慢查询"""
        metrics_file = ONLINE_EVAL_DIR / "metrics.jsonl"

        if not metrics_file.exists():
            return []

        slow_queries = []
        try:
            with open(metrics_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        metric = json.loads(line.strip())
                        if (metric.get("type") == "search" and
                            metric.get("latency_ms", 0) > threshold_ms):
                            slow_queries.append(metric)
                    except:
                        pass
        except Exception:
            pass

        # 按延迟排序
        slow_queries.sort(key=lambda x: x.get("latency_ms", 0), reverse=True)

        return slow_queries[:limit]


# 全局实例
_online_eval: Optional[OnlineEvaluator] = None


def get_online_evaluator() -> OnlineEvaluator:
    """获取全局在线评测器实例"""
    global _online_eval
    if _online_eval is None:
        _online_eval = OnlineEvaluator()
    return _online_eval
