"""
strategy.py — 少阴·策略选择
SAG式映射：快速/深度/表格三种模式
"""
import logging
from typing import Dict, Any

logger = logging.getLogger("shaoyin.strategy")


# 策略映射表
STRATEGY_MAP = {
    "definition": "fast",
    "how_to": "fast",
    "general_search": "fast",
    "numeric_lookup": "deep",
    "material_selector": "deep",
    "compare": "deep",
    "table_query": "table",
}


def select_strategy(intent: Dict) -> str:
    """根据意图选择检索策略"""
    primary = intent.get("intent", "general_search")

    # 优先检查特殊意图
    if "table_query" in intent.get("intents", {}):
        return "table"
    if "compare" in intent.get("intents", {}):
        return "deep"

    return STRATEGY_MAP.get(primary, "fast")


def get_strategy_params(strategy: str) -> Dict[str, Any]:
    """获取策略参数 — v1.50: 任务 5 五层路由接入 SAG
    
    L1 (fast): Path B 向量直接（不用 SAG）
    L2 (standard): 标准混合检索（不用 SAG）
    L3 (deep): 完整 SAG 三阶段管线（Path A + Path B + 多跳 + Rerank）
    L4 (agent): Agent 循环（可选启用 SAG）
    L5 (crag): 纠正检索（可选启用 SAG）
    """
    if strategy == "fast":
        return {
            "top_k": 5,
            "use_multi_hop": False,
            "use_rerank": False,
            "use_sag": False,  # L1: 不用 SAG
            "granularity": "chunk",
            "timeout": 3.0,
        }
    elif strategy == "standard":
        return {
            "top_k": 10,
            "use_multi_hop": False,
            "use_rerank": True,
            "use_sag": False,  # L2: 不用 SAG
            "granularity": "chunk",
            "timeout": 5.0,
        }
    elif strategy == "deep":
        return {
            "top_k": 15,
            "use_multi_hop": True,
            "use_rerank": True,
            "use_sag": True,  # L3: 完整 SAG 三阶段
            "granularity": "event",
            "timeout": 10.0,
        }
    elif strategy == "agent":
        return {
            "top_k": 15,
            "use_multi_hop": True,
            "use_rerank": True,
            "use_sag": True,  # L4: 可选 SAG（降级前先走 SAG）
            "granularity": "event",
            "timeout": 15.0,
        }
    elif strategy == "crag":
        return {
            "top_k": 15,
            "use_multi_hop": True,
            "use_rerank": True,
            "use_sag": True,  # L5: 可选 SAG（纠正检索前先走 SAG）
            "granularity": "event",
            "timeout": 20.0,
        }
    elif strategy == "table":
        return {
            "top_k": 10,
            "use_multi_hop": False,
            "use_rerank": False,
            "use_table_search": True,
            "use_sag": False,
            "granularity": "chunk",
            "timeout": 5.0,
        }
    else:
        return {
            "top_k": 10,
            "use_multi_hop": False,
            "use_rerank": False,
            "use_sag": False,
            "granularity": "chunk",
            "timeout": 5.0,
        }
