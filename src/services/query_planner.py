"""
query_planner.py — Phase 8.2: 查询规划与分解 v2.0
正则快速匹配 + LLM 深度分解
"""
import json, re, logging
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger("query_planner")

@dataclass
class PlanStep:
    step_id: int
    query: str
    source: str  # "graph" | "vector" | "wiki" | "hybrid"
    reason: str


# 正则快速匹配（零延迟）
QUICK_PATTERNS = [
    (r"(.+)和(.+)的区别", "comparison"),
    (r"(.+)与(.+)对比", "comparison"),
    (r"(.+)和(.+)哪个", "comparison"),
    (r"(.+)vs\.?(.+)", "comparison"),
    (r"(.+)的(.+)参数", "attribute_lookup"),
    (r"(.+)的(.+)规格", "attribute_lookup"),
    (r"(.+)的(.+)是多少", "attribute_lookup"),
    (r"怎么(.+)", "how_to"),
    (r"如何(.+)", "how_to"),
    (r"(.+)有哪些(.+)", "enumeration"),
]


def _quick_plan(query: str) -> Optional[List[PlanStep]]:
    """正则快速匹配（<1ms）"""
    for pattern, ptype in QUICK_PATTERNS:
        m = re.match(pattern, query)
        if not m:
            continue
        if ptype == "comparison":
            return [
                PlanStep(1, m.group(1).strip(), "hybrid", f"检索实体A"),
                PlanStep(2, m.group(2).strip(), "hybrid", f"检索实体B"),
                PlanStep(3, query, "graph", "图遍历对比关系"),
            ]
        elif ptype == "attribute_lookup":
            return [
                PlanStep(1, m.group(1).strip(), "graph", f"图定位实体"),
                PlanStep(2, f"{m.group(1).strip()} {m.group(2).strip()}", "vector", f"向量检索属性"),
            ]
    return None


async def _llm_plan(query: str) -> Optional[List[PlanStep]]:
    """LLM 深度分解（1-3s，仅复杂查询触发）"""
    try:
        from src.services.llm import call_llm_fast
        prompt = f"""分析以下查询，分解为子查询。只输出 JSON 数组。

查询：{query}

示例输出：
[
  {{"q": "子查询1", "source": "hybrid", "reason": "原因"}},
  {{"q": "子查询2", "source": "graph", "reason": "原因"}}
]

规则：
- 简单查询返回空数组 []
- 对比类拆为分别查询 + 关系查询
- 多实体拆为独立查询
- 只输出 JSON，不要解释"""

        result = await call_llm_fast(prompt, max_tokens=300)
        if not result:
            return None

        # 清理 JSON
        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[1].rsplit("```", 1)[0]

        items = json.loads(result)
        if not items or not isinstance(items, list):
            return None

        steps = []
        for i, item in enumerate(items):
            steps.append(PlanStep(
                step_id=i + 1,
                query=item.get("q", ""),
                source=item.get("source", "hybrid"),
                reason=item.get("reason", "LLM 分解"),
            ))

        if steps:
            logger.info(f"[Planner] LLM 分解: {len(steps)} 步")
            return steps

    except Exception as e:
        logger.debug(f"[Planner] LLM 分解失败: {e}")

    return None


def plan_query(query: str) -> List[PlanStep]:
    """同步入口：正则快速匹配"""
    result = _quick_plan(query)
    if result:
        return result
    return [PlanStep(1, query, "hybrid", "标准混合检索")]


async def plan_query_async(query: str) -> List[PlanStep]:
    """异步入口：正则 + LLM 深度分解"""
    # Step 1: 正则快速匹配
    result = _quick_plan(query)
    if result:
        return result

    # Step 2: 复杂查询用 LLM 分解
    if len(query) > 20:
        result = await _llm_plan(query)
        if result:
            return result

    # Step 3: 默认
    return [PlanStep(1, query, "hybrid", "标准混合检索")]
