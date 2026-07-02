"""
eval_automation.py — 评测管线自动化
定时评测 + 自动报告 + 退化检测
"""
import json
import logging
import time
import os
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("services.eval_automation")

EVAL_DIR = Path("data/evaluation")
REPORT_DIR = Path("data/evaluation/reports")


class EvalAutomation:
    """评测管线自动化"""

    def __init__(self):
        EVAL_DIR.mkdir(parents=True, exist_ok=True)
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        self._eval_history: List[Dict] = []

    async def run_daily_eval(self) -> Dict:
        """运行每日评测"""
        logger.info("[EvalAutomation] 开始每日评测")

        report = {
            "timestamp": time.time(),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "metrics": {},
            "issues": [],
            "recommendations": [],
        }

        # 1. 检索质量评测
        search_metrics = await self._eval_search_quality()
        report["metrics"]["search"] = search_metrics

        # 2. 答案质量评测
        answer_metrics = await self._eval_answer_quality()
        report["metrics"]["answer"] = answer_metrics

        # 3. 系统性能评测
        perf_metrics = await self._eval_performance()
        report["metrics"]["performance"] = perf_metrics

        # 4. 退化检测
        degradation = await self._check_degradation(report["metrics"])
        report["degradation"] = degradation

        # 5. 生成建议
        report["recommendations"] = self._generate_recommendations(report)

        # 6. 保存报告
        self._save_report(report)

        logger.info(f"[EvalAutomation] 每日评测完成: {len(report['issues'])} 个问题")
        return report

    async def _eval_search_quality(self) -> Dict:
        """评测检索质量"""
        try:
            from src.services.online_eval import get_online_evaluator
            evaluator = get_online_evaluator()
            stats = await evaluator.get_stats(hours=24)

            return {
                "total_queries": stats.get("total_queries", 0),
                "avg_latency_ms": stats.get("avg_latency_ms", 0),
                "avg_result_count": stats.get("avg_result_count", 0),
                "avg_max_score": stats.get("avg_max_score", 0),
                "feedback_count": stats.get("feedback_count", 0),
                "avg_rating": stats.get("avg_rating", 0),
            }
        except Exception as e:
            logger.warning(f"[EvalAutomation] 检索质量评测失败: {e}")
            return {}

    async def _eval_answer_quality(self) -> Dict:
        """评测答案质量"""
        try:
            from src.services.eval_pipeline import get_eval_pipeline
            pipeline = get_eval_pipeline()
            stats = await pipeline.get_eval_stats()

            return {
                "total_evals": stats.get("total_evals", 0),
                "metrics": stats.get("metrics", {}),
            }
        except Exception as e:
            logger.warning(f"[EvalAutomation] 答案质量评测失败: {e}")
            return {}

    async def _eval_performance(self) -> Dict:
        """评测系统性能"""
        try:
            from src.infra.meridian_monitor import get_monitor
            monitor = get_monitor()
            health = monitor.get_health_report()
            percentiles = monitor.get_latency_percentiles()

            return {
                "status": health.get("status", "unknown"),
                "error_rate": health.get("error_rate", 0),
                "success_rate": health.get("success_rate", 0),
                "latency_p50": percentiles.get("p50", 0),
                "latency_p95": percentiles.get("p95", 0),
                "latency_p99": percentiles.get("p99", 0),
            }
        except Exception as e:
            logger.warning(f"[EvalAutomation] 性能评测失败: {e}")
            return {}

    async def _check_degradation(self, metrics: Dict) -> Dict:
        """检查退化"""
        degradation = {
            "detected": False,
            "issues": [],
        }

        # 检查检索质量退化
        search = metrics.get("search", {})
        if search.get("avg_max_score", 1) < 0.3:
            degradation["detected"] = True
            degradation["issues"].append("检索平均最高分 < 0.3")

        if search.get("avg_latency_ms", 0) > 5000:
            degradation["detected"] = True
            degradation["issues"].append("检索平均延迟 > 5s")

        # 检查性能退化
        perf = metrics.get("performance", {})
        if perf.get("error_rate", 0) > 0.05:
            degradation["detected"] = True
            degradation["issues"].append("错误率 > 5%")

        if perf.get("latency_p95", 0) > 10000:
            degradation["detected"] = True
            degradation["issues"].append("P95延迟 > 10s")

        return degradation

    def _generate_recommendations(self, report: Dict) -> List[str]:
        """生成建议"""
        recommendations = []

        search = report["metrics"].get("search", {})
        if search.get("avg_max_score", 1) < 0.5:
            recommendations.append("检索质量较低，建议检查索引和查询扩展")

        perf = report["metrics"].get("performance", {})
        if perf.get("latency_p95", 0) > 5000:
            recommendations.append("P95延迟较高，建议启用缓存或优化检索流程")

        if report["degradation"].get("detected"):
            recommendations.append("检测到退化，建议检查最近的代码变更")

        return recommendations

    def _save_report(self, report: Dict):
        """保存评测报告"""
        try:
            date = report.get("date", datetime.now().strftime("%Y-%m-%d"))
            report_file = REPORT_DIR / f"eval_report_{date}.json"
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)

            # 同时追加到历史记录
            history_file = EVAL_DIR / "eval_history.jsonl"
            with open(history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "date": date,
                    "total_queries": report["metrics"].get("search", {}).get("total_queries", 0),
                    "avg_latency_ms": report["metrics"].get("search", {}).get("avg_latency_ms", 0),
                    "error_rate": report["metrics"].get("performance", {}).get("error_rate", 0),
                    "degradation_detected": report["degradation"].get("detected", False),
                }, ensure_ascii=False) + "\n")

            logger.info(f"[EvalAutomation] 报告已保存: {report_file}")
        except Exception as e:
            logger.warning(f"[EvalAutomation] 保存报告失败: {e}")

    async def get_eval_history(self, days: int = 7) -> List[Dict]:
        """获取评测历史"""
        history_file = EVAL_DIR / "eval_history.jsonl"
        if not history_file.exists():
            return []

        records = []
        cutoff = time.time() - days * 86400

        try:
            with open(history_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        # 简单的日期比较
                        records.append(record)
                    except:
                        pass
        except Exception:
            pass

        return records[-days:]

    async def get_latest_report(self) -> Optional[Dict]:
        """获取最新的评测报告"""
        date = datetime.now().strftime("%Y-%m-%d")
        report_file = REPORT_DIR / f"eval_report_{date}.json"

        if not report_file.exists():
            # 尝试获取昨天的
            yesterday = datetime.now().strftime("%Y-%m-%d")
            report_file = REPORT_DIR / f"eval_report_{yesterday}.json"

        if not report_file.exists():
            return None

        try:
            with open(report_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None


# 全局实例
_eval_automation: Optional[EvalAutomation] = None


def get_eval_automation() -> EvalAutomation:
    """获取全局评测自动化实例"""
    global _eval_automation
    if _eval_automation is None:
        _eval_automation = EvalAutomation()
    return _eval_automation
