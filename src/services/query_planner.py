"""
query_planner.py — Phase 8.2: 查询规划与分解
分解复杂查询为子查询，规划检索策略
"""
import json, re, logging
from typing import List, Dict
from dataclasses import dataclass

logger = logging.getLogger("query_planner")

@dataclass
class PlanStep:
    step_id: int
    query: str
    source: str  # "graph" | "vector" | "wiki" | "hybrid"
    reason: str

def plan_query(query: str) -> List[PlanStep]:
    """规划查询策略"""
    steps = []
    
    # 检测多实体查询（含"和""与"等连接词）
    multi_patterns = [
        (r"(.+)和(.+)的区别", "comparison"),
        (r"(.+)与(.+)对比", "comparison"),
        (r"(.+)的(.+)参数", "attribute_lookup"),
    ]
    
    for pattern, ptype in multi_patterns:
        m = re.match(pattern, query)
        if m:
            if ptype == "comparison":
                steps.extend([
                    PlanStep(1, m.group(1), "hybrid", f"检索实体A: {m.group(1)}"),
                    PlanStep(2, m.group(2), "hybrid", f"检索实体B: {m.group(2)}"),
                    PlanStep(3, query, "graph", "图遍历对比关系"),
                ])
                logger.info(f"[Planner] 对比查询 → {len(steps)} 步")
                return steps
            elif ptype == "attribute_lookup":
                steps.extend([
                    PlanStep(1, m.group(1), "graph", f"图定位实体: {m.group(1)}"),
                    PlanStep(2, f"{m.group(1)} {m.group(2)}", "vector", f"向量检索属性: {m.group(2)}"),
                ])
                return steps
    
    # 默认: 混合检索
    steps.append(PlanStep(1, query, "hybrid", "标准混合检索"))
    return steps
