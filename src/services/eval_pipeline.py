"""
eval_pipeline.py — 评测管线集成
Recall@K / MRR / LLM-as-Judge
"""
import json
import logging
import time
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger("services.eval_pipeline")

from src.config import DATA_DIR as CONFIG_DATA_DIR
EVAL_DIR = Path(CONFIG_DATA_DIR) / "evaluation"


class EvalPipeline:
    """评测管线"""

    def __init__(self):
        EVAL_DIR.mkdir(parents=True, exist_ok=True)

# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
    async def evaluate_search(self, query: str, results: List[Dict],
                               expected: List[str] = None) -> Dict:
        """评估检索质量"""
        eval_result = {
            "query": query,
            "timestamp": time.time(),
            "result_count": len(results),
            "metrics": {},
        }

        if expected:
            # 计算 Recall@K
            for k in [1, 3, 5, 10]:
                recall = self._calculate_recall_at_k(results, expected, k)
                eval_result["metrics"][f"recall_at_{k}"] = recall

            # 计算 MRR
            mrr = self._calculate_mrr(results, expected)
            eval_result["metrics"]["mrr"] = mrr
        else:
            # 无标注数据时，记录基本指标
            eval_result["metrics"]["result_count"] = len(results)
            eval_result["metrics"]["max_score"] = max([r.get("score", 0) for r in results], default=0)
            eval_result["metrics"]["avg_score"] = sum([r.get("score", 0) for r in results]) / max(len(results), 1)

        # 保存评测结果
        self._save_eval_result(eval_result)

        return eval_result

# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
    async def evaluate_answer(self, query: str, answer: str,
                               sources: List[Dict] = None) -> Dict:
        """评估答案质量"""
        eval_result = {
            "query": query,
            "answer": answer[:200],
            "timestamp": time.time(),
            "metrics": {},
        }

        # 基本指标
        eval_result["metrics"]["answer_length"] = len(answer)
        eval_result["metrics"]["has_sources"] = len(sources) > 0 if sources else False
        eval_result["metrics"]["source_count"] = len(sources) if sources else 0

        # 保存评测结果
        self._save_eval_result(eval_result)

        return eval_result

    def _calculate_recall_at_k(self, results: List[Dict],
                                expected: List[str], k: int) -> float:
        """计算 Recall@K"""
        if not expected:
            return 0.0

        top_k = results[:k]
        top_k_ids = set([r.get("chunk_id", "") for r in top_k])
        expected_set = set(expected)

        hits = len(top_k_ids & expected_set)
        return hits / len(expected_set)

    def _calculate_mrr(self, results: List[Dict], expected: List[str]) -> float:
        """计算 MRR (Mean Reciprocal Rank)"""
        if not expected:
            return 0.0

        expected_set = set(expected)

        for i, r in enumerate(results):
            if r.get("chunk_id", "") in expected_set:
                return 1.0 / (i + 1)

        return 0.0

    def _save_eval_result(self, result: Dict):
        """保存评测结果"""
        try:
            eval_file = EVAL_DIR / "eval_results.jsonl"
            with open(eval_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[Eval] 保存评测结果失败: {e}")

# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
    async def get_eval_stats(self) -> Dict:
        """获取评测统计"""
        eval_file = EVAL_DIR / "eval_results.jsonl"

        if not eval_file.exists():
            return {"total_evals": 0, "metrics": {}}

        results = []
        try:
            with open(eval_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        results.append(json.loads(line.strip()))
                    except Exception as e:  # TODO: Narrow exception type
                        logger.warning("JSON解析评测结果失败: %s", e, exc_info=True)
        except Exception as e:  # TODO: Narrow exception type
            logger.warning("读取评测结果文件失败: %s", e, exc_info=True)

        if not results:
            return {"total_evals": 0, "metrics": {}}

        # 汇总指标
        all_metrics = {}
        for r in results:
            for k, v in r.get("metrics", {}).items():
                if isinstance(v, (int, float)):
                    if k not in all_metrics:
                        all_metrics[k] = []
                    all_metrics[k].append(v)

        avg_metrics = {}
        for k, values in all_metrics.items():
            avg_metrics[k] = sum(values) / len(values)

        return {
            "total_evals": len(results),
            "metrics": avg_metrics,
        }


# 全局实例
_eval_pipeline: Optional[EvalPipeline] = None


def get_eval_pipeline() -> EvalPipeline:
    """获取全局评测管线实例"""
    global _eval_pipeline
    if _eval_pipeline is None:
        _eval_pipeline = EvalPipeline()
    return _eval_pipeline
