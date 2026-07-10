"""
seed_score_ab.py — seed_score A/B 测试框架
权重来源：SAG论文 arxiv 2606.15971
"""
import os
import json
import time
import hashlib
import logging
from typing import Dict, List
import asyncio

logger = logging.getLogger("taiyang.seed_score_ab")

TEST_DIR = "data/ab_tests"


class SeedScoreABTest:
    """seed_score A/B 测试"""

    TEST_CONFIG = {
        "test_name": "seed_score_weight_optimization",
        "traffic_split": 0.5,
        "variants": {
            "control": {
                "name": "SAG论文权重",
                "vector_weight": 0.85,
                "entity_weight": 0.15,
                "dual_channel_weight": 0.05,
            },
            "treatment": {
                "name": "中文优化权重",
                "vector_weight": 0.70,
                "entity_weight": 0.25,
                "dual_channel_weight": 0.05,
            },
        },
        "sample_size": {
            "min_queries_per_variant": 500,
            "min_days": 7,
        },
    }

    def assign_group(self, query: str) -> str:
        """确定用户分组（基于查询hash）"""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return "control" if int(query_hash[-1], 16) < 8 else "treatment"

    def get_weights(self, group: str) -> Dict:
        """获取对应组的权重"""
        return self.TEST_CONFIG["variants"][group]

    def calculate_seed_score(self, result: Dict, weights: Dict) -> float:
        """计算seed_score"""
        vector_score = result.get("_similarity", 0)
        entity_score = result.get("_entity_hit", 0)
        dual_channel_score = result.get("_dual_channel", 0)

        return (
            weights["vector_weight"] * vector_score +
            weights["entity_weight"] * entity_score +
            weights["dual_channel_weight"] * dual_channel_score
        )

# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
    async def record_test_data(self, query: str, group: str,
                                results: List[Dict], trace_id: str = ""):
        """记录测试数据"""
        os.makedirs(TEST_DIR, exist_ok=True)

        test_data = {
            "timestamp": time.time(),
            "trace_id": trace_id,
            "query": query,
            "group": group,
            "top_k_scores": [r.get("seed_score", 0) for r in results[:5]],
            "user_click": None,
            "user_feedback": None,
        }

        test_file = os.path.join(TEST_DIR, f"{self.TEST_CONFIG['test_name']}.jsonl")
        def _write_test():
            with open(test_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(test_data, ensure_ascii=False) + "\n")
        await asyncio.to_thread(_write_test)


class SeedScoreEvaluator:
    """seed_score 评估器"""

# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
    async def evaluate(self, test_name: str = "seed_score_weight_optimization") -> Dict:
        """评估A/B测试结果"""
        test_file = os.path.join(TEST_DIR, f"{test_name}.jsonl")

        if not os.path.exists(test_file):
            return {"error": "测试数据不存在"}

        data = []
        def _read_test():
            result = []
            with open(test_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        result.append(json.loads(line.strip()))
                    except Exception as e:
                        logger.warning("JSON解析A/B测试数据失败: %s", e, exc_info=True)
            return result
        data = await asyncio.to_thread(_read_test)

        control_data = [d for d in data if d.get("group") == "control"]
        treatment_data = [d for d in data if d.get("group") == "treatment"]

        control_scores = [s for d in control_data for s in d.get("top_k_scores", [])]
        treatment_scores = [s for d in treatment_data for s in d.get("top_k_scores", [])]

        results = {
            "control": {
                "sample_size": len(control_data),
                "avg_score": sum(control_scores) / len(control_scores) if control_scores else 0,
            },
            "treatment": {
                "sample_size": len(treatment_data),
                "avg_score": sum(treatment_scores) / len(treatment_scores) if treatment_scores else 0,
            },
            "recommendation": "继续测试，样本量不足",
        }

        if len(control_data) >= 100 and len(treatment_data) >= 100:
            if results["treatment"]["avg_score"] > results["control"]["avg_score"] * 1.05:
                results["recommendation"] = "采用中文优化权重"
            elif results["control"]["avg_score"] > results["treatment"]["avg_score"] * 1.05:
                results["recommendation"] = "保持SAG论文权重"
            else:
                results["recommendation"] = "无显著差异，继续测试"

        return results
