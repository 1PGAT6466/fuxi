"""
l5_crag.py — L5 CRAG 执行器
纠正检索：查询改写 + 重试 + 校验
"""
import asyncio
import logging
from typing import Dict, List

logger = logging.getLogger("taiyang.l5_crag")

# L5 CRAG 配置
L5_CRAG_CONFIG = {
    "conditions": [
        {"metric": "agent_loops", "operator": ">", "value": 3},
        {"metric": "total_tokens", "operator": ">", "value": 4000},
        {"metric": "agent_confidence", "operator": "<", "value": 0.3},
        {"metric": "agent_timeout", "operator": "==", "value": True},
    ],
    "execution": {
        "strategy": "rewrite_and_retry",
        "max_retries": 2,
        "timeout": 5.0,
    },
    "fallback": {
        "action": "return_partial",
        "include_reason": True,
        "log_level": "WARNING",
    },
}


class L5CRAGExecutor:
    """L5 CRAG 执行器"""

    async def execute(self, query: str, partial_results: List[Dict],
                      trace_id: str = "unknown") -> Dict:
        """执行 L5 CRAG"""
        from src.infra.trace_logger import TraceLogger
        trace_logger = TraceLogger(trace_id, "l5_crag")
        trace_logger.log("execute", "开始 L5 CRAG 纠正检索")

        # 1. 改写查询
        rewritten_query = await self._rewrite_query(query, partial_results)
        trace_logger.log("rewrite", f"查询改写: {query[:30]}... → {rewritten_query[:30]}...")

        # 2. 重新检索（使用改写后的查询）
        for attempt in range(L5_CRAG_CONFIG["execution"]["max_retries"]):
            try:
                results = await asyncio.wait_for(
                    self._search_with_taiyang(rewritten_query),
                    timeout=L5_CRAG_CONFIG["execution"]["timeout"]
                )

                # 3. 校验结果质量
                if self._validate_results(results):
                    trace_logger.log("success", f"L5 CRAG 成功, results={len(results)}")
                    return {
                        "results": results,
                        "mode": "l5_crag",
                        "trace_id": trace_id,
                    }

            except asyncio.TimeoutError:
                trace_logger.log("timeout", f"L5 CRAG 超时 (尝试 {attempt + 1})")
            except Exception as e:  # TODO: Narrow exception type
                trace_logger.log("error", f"L5 CRAG 异常: {e}")

        # 4. 所有重试失败，返回部分结果
        trace_logger.log("fallback", "L5 CRAG 失败，返回部分结果")
        return {
            "results": partial_results,
            "mode": "l5_crag_failed",
            "reason": "L5 CRAG 纠正检索失败",
            "trace_id": trace_id,
        }
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

    async def _rewrite_query(self, original_query: str,
                             partial_results: List[Dict]) -> str:
        """改写查询"""
        try:
            from src.infra.llm import call_ai

            context = "\n".join([r.get("text", "")[:100] for r in partial_results[:3]])

            prompt = f"""原始查询：{original_query}

部分结果：
{context}

请改写查询，使其更精确地匹配知识库内容。只输出改写后的查询，不要其他内容。"""

            rewritten = await call_ai(prompt)
            return rewritten.strip() if rewritten else original_query

        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[L5 CRAG] 查询改写失败: {e}")
            return original_query

    async def _search_with_taiyang(self, query: str) -> List[Dict]:
        """使用太阳的检索能力"""
        from src.taiyang.retrieval import hybrid_search
        return await hybrid_search(query, top_k=15)

    def _validate_results(self, results: List[Dict]) -> bool:
        """校验结果质量"""
        if not results:
            return False

        # 检查结果数量
        if len(results) < 2:
            return False

        # 检查结果分数
        max_score = max(r.get("score", 0) for r in results)
        if max_score < 0.3:
            return False

        return True


def should_trigger_l5(result: Dict) -> bool:
    """判断是否触发 L5 CRAG"""
    for condition in L5_CRAG_CONFIG["conditions"]:
        metric_value = result.get(condition["metric"])
        if metric_value is None:
            continue

        if _evaluate_condition(metric_value, condition["operator"], condition["value"]):
            logger.info(f"[L5 CRAG] 触发条件满足: {condition['metric']} {condition['operator']} {condition['value']}")
            return True

    return False


def _evaluate_condition(value, operator: str, expected) -> bool:
    """评估条件"""
    if operator == "<":
        return value < expected
    elif operator == ">":
        return value > expected
    elif operator == "==":
        return value == expected
    elif operator == ">=":
        return value >= expected
    elif operator == "<=":
        return value <= expected
    return False
