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
    """获取策略参数"""
    if strategy == "fast":
        return {
            "top_k": 5,
            "use_multi_hop": False,
            "use_rerank": False,
            "timeout": 3.0,
        }
    elif strategy == "deep":
        return {
            "top_k": 15,
            "use_multi_hop": True,
            "use_rerank": True,
            "timeout": 10.0,
        }
    elif strategy == "table":
        return {
            "top_k": 10,
            "use_multi_hop": False,
            "use_rerank": False,
            "use_table_search": True,
            "timeout": 5.0,
        }
    else:
        return {
            "top_k": 10,
            "use_multi_hop": False,
            "use_rerank": False,
            "timeout": 5.0,
        }
