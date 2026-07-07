"""
degradation_chain.py — 四层降级链（L1→L2→L3→L4）
支持 trace_id 追踪和模式分析
"""
import asyncio
import uuid
import time
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("taiyang.degradation_chain")


class DegradationChain:
    """四层降级链 — 齿轮级精密控制"""
    
    DEGRADATION_CONFIG = {
        "L1_FAST": {
            "conditions": [
                {"metric": "result_count", "operator": "<", "value": 1, "target": "L2_STANDARD"},
                {"metric": "result_count", "operator": "<", "value": 3, "target": "L2_STANDARD"},
                {"metric": "max_score", "operator": "<", "value": 0.3, "target": "L2_STANDARD"},
            ],
            "timeout_ms": 500,
        },
        "L2_STANDARD": {
            "conditions": [
                {"metric": "reflection_pass", "operator": "==", "value": False, "target": "L3_DEEP"},
                {"metric": "crag_success", "operator": "==", "value": False, "target": "L3_DEEP"},
                {"metric": "confidence", "operator": "<", "value": 0.4, "target": "L3_DEEP"},
            ],
            "timeout_ms": 2000,
        },
        "L3_DEEP": {
            "conditions": [
                {"metric": "graph_entities", "operator": "<", "value": 1, "target": "L4_AGENT"},
                {"metric": "hop_results", "operator": "<", "value": 1, "target": "L4_AGENT"},
                {"metric": "confidence", "operator": "<", "value": 0.3, "target": "L4_AGENT"},
            ],
            "timeout_ms": 3000,
        },
        "L4_AGENT": {
            "conditions": [
                {"metric": "agent_loops", "operator": ">", "value": 3, "target": "L5_CRAG"},
                {"metric": "total_tokens", "operator": ">", "value": 4000, "target": "L5_CRAG"},
                {"metric": "agent_confidence", "operator": "<", "value": 0.3, "target": "L5_CRAG"},
                {"metric": "agent_timeout", "operator": "==", "value": True, "target": "L5_CRAG"},
            ],
            "timeout_ms": 10000,
        },
        "L5_CRAG": {
            "conditions": [
                {"metric": "crag_success", "operator": "==", "value": False, "target": "RETURN_EMPTY"},
                {"metric": "confidence", "operator": "<", "value": 0.2, "target": "RETURN_EMPTY"},
            ],
            "timeout_ms": 5000,
        },
    }
    
    async def execute_with_degradation(self, query: str, start_level: str = "L1_FAST") -> Dict:
        """执行带降级的查询"""
        trace_id = str(uuid.uuid4())[:8]
        trace_log = []
        current_level = start_level
        
        logger.info(f"[降级链] trace_id={trace_id}, 开始执行, 起始层级={current_level}")
        
        while current_level != "RETURN_EMPTY":
            trace_log.append({
                "trace_id": trace_id,
                "from_level": current_level,
                "timestamp": time.time(),
            })
            
            try:
                result = await self._execute_level(query, current_level, trace_id)
                
                # 检查降级条件
                degradation = self._check_degradation(current_level, result)
                
                if degradation is None:
                    # 无需降级，记录完整轨迹
                    result["_trace"] = trace_log
                    result["_trace_id"] = trace_id
                    logger.info(f"[降级链] trace_id={trace_id}, {current_level} 完成, 无需降级")
                    return result
                
                # 记录降级原因
                trace_log[-1]["to_level"] = degradation["target"]
                trace_log[-1]["reason"] = degradation["reason"]
                
                logger.info(f"[降级链] trace_id={trace_id}, {current_level} → {degradation['target']}, 原因: {degradation['reason']}")
                
                current_level = degradation["target"]
                
            except asyncio.TimeoutError:
                next_level = self._get_next_level(current_level)
                trace_log[-1]["to_level"] = next_level
                trace_log[-1]["reason"] = "timeout"
                
                logger.warning(f"[降级链] trace_id={trace_id}, {current_level} 超时, 降级到 {next_level}")
                current_level = next_level
                
            except Exception as e:
                next_level = self._get_next_level(current_level)
                trace_log[-1]["to_level"] = next_level
                trace_log[-1]["reason"] = str(e)[:100]
                
                logger.error(f"[降级链] trace_id={trace_id}, {current_level} 异常: {e}, 降级到 {next_level}")
                current_level = next_level
        
        # 所有层级都失败
        logger.warning(f"[降级链] trace_id={trace_id}, 所有层级都失败, 返回空结果")
        return {
            "results": [],
            "answer": "知识库中未找到相关信息",
            "_trace": trace_log,
            "_trace_id": trace_id,
        }
    
    async def _execute_level(self, query: str, level: str, trace_id: str) -> Dict:
        """执行指定层级的检索"""
        if level == "L1_FAST":
            return await self._execute_l1(query, trace_id)
        elif level == "L2_STANDARD":
            return await self._execute_l2(query, trace_id)
        elif level == "L3_DEEP":
            return await self._execute_l3(query, trace_id)
        elif level == "L4_AGENT":
            return await self._execute_l4(query, trace_id)
        elif level == "L5_CRAG":
            return await self._execute_l5(query, trace_id)
        else:
            raise ValueError(f"Unknown level: {level}")
    
    async def _execute_l1(self, query: str, trace_id: str) -> Dict:
        """L1 快速模式：Simple RAG"""
        from src.taiyang.retrieval import hybrid_search
        results = await hybrid_search(query, top_k=10)
        max_score = max([r.get("score", 0) for r in results], default=0)
        return {
            "results": results,
            "result_count": len(results),
            "max_score": max_score,
            "level": "L1_FAST",
        }
    
    async def _execute_l2(self, query: str, trace_id: str) -> Dict:
        """L2 标准模式：Self-RAG"""
        from src.taiyang.retrieval import hybrid_search
        from src.shaoyin.validator import YinAgent
        
        results = await hybrid_search(query, top_k=15)
        
        # Self-RAG 反思
        validator = YinAgent()
        if results:
            reflection = validator._rule_check(
                answer=results[0].get("text", ""),
                sources=results,
                query=query,
            )
            return {
                "results": results,
                "result_count": len(results),
                "max_score": max([r.get("score", 0) for r in results], default=0),
                "reflection_pass": reflection.get("passed", False),
                "confidence": reflection.get("score", 0) / 100,
                "level": "L2_STANDARD",
            }
        
        return {
            "results": results,
            "result_count": len(results),
            "max_score": 0,
            "reflection_pass": False,
            "confidence": 0,
            "level": "L2_STANDARD",
        }
    
    async def _execute_l3(self, query: str, trace_id: str) -> Dict:
        """L3 深度模式：GraphRAG + 多跳"""
        from src.taiyang.retrieval import hybrid_search
        from src.taiyang.multi_hop import multi_hop_search
        
        # 先尝试多跳检索
        try:
            hop_results = await multi_hop_search(query, max_hops=2, top_k=15)
        except Exception:
            hop_results = []
        
        # 如果多跳无结果，降级为普通检索
        if not hop_results:
            hop_results = await hybrid_search(query, top_k=15)
        
        max_score = max([r.get("score", 0) for r in hop_results], default=0)
        return {
            "results": hop_results,
            "result_count": len(hop_results),
            "max_score": max_score,
            "hop_results": len(hop_results),
            "level": "L3_DEEP",
        }
    
    async def _execute_l4(self, query: str, trace_id: str) -> Dict:
        """L4 Agent 模式：触发在太阳，执行在少阴"""
        # 发送 need_agent 信号给少阴
        logger.info(f"[降级链] trace_id={trace_id}, 触发 L4 Agent 模式")
        
        # 简化实现：直接调用少阴的 brain
        from src.shaoyin.brain import ShaoyinBrain
        from src.hypothalamus.meridian import Meridian
        
        meridian = Meridian()
        brain = ShaoyinBrain(meridian)
        result = await brain.think(query)
        
        return {
            "results": result.get("sources", []),
            "answer": result.get("answer", ""),
            "confidence": result.get("confidence", 0),
            "agent_loops": 1,
            "total_tokens": 0,
            "level": "L4_AGENT",
        }
    
    async def _execute_l5(self, query: str, trace_id: str) -> Dict:
        """L5 CRAG 模式：纠正检索"""
        logger.info(f"[降级链] trace_id={trace_id}, 触发 L5 CRAG 模式")
        
        from src.taiyang.l5_crag import L5CRAGExecutor
        
        executor = L5CRAGExecutor()
        # 获取之前的结果作为部分结果
        partial_results = []
        result = await executor.execute(query, partial_results, trace_id)
        
        return {
            "results": result.get("results", []),
            "result_count": len(result.get("results", [])),
            "max_score": max([r.get("score", 0) for r in result.get("results", [])], default=0),
            "crag_success": result.get("mode") == "l5_crag",
            "confidence": max([r.get("score", 0) for r in result.get("results", [])], default=0),
            "level": "L5_CRAG",
        }
    
    def _check_degradation(self, level: str, result: Dict) -> Optional[Dict]:
        """检查是否需要降级"""
        config = self.DEGRADATION_CONFIG.get(level)
        if not config:
            return None
        
        for condition in config["conditions"]:
            metric_value = result.get(condition["metric"])
            if metric_value is None:
                continue
            
            if self._evaluate_condition(metric_value, condition["operator"], condition["value"]):
                return {
                    "target": condition["target"],
                    "reason": f"{condition['metric']} {condition['operator']} {condition['value']} (实际={metric_value})",
                }
        
        return None
    
    def _evaluate_condition(self, value: Any, operator: str, expected: Any) -> bool:
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
    
    def _get_next_level(self, current_level: str) -> str:
        """获取下一层级"""
        level_order = ["L1_FAST", "L2_STANDARD", "L3_DEEP", "L4_AGENT", "L5_CRAG", "RETURN_EMPTY"]
        try:
            current_index = level_order.index(current_level)
            return level_order[min(current_index + 1, len(level_order) - 1)]
        except ValueError:
            return "RETURN_EMPTY"
