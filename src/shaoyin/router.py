"""
router.py — 少阴·意图路由
route_query
"""
import re
import logging
from typing import Tuple

logger = logging.getLogger("shaoyin.router")


def route_query(query: str) -> Tuple[str, str]:
    """路由查询，返回 (意图, 搜索模式)"""
    query_lower = query.lower()

    patterns = {
        "compare": [r"和.*比较", r"区别", r"vs", r"对比"],
        "numeric_lookup": [r"参数", r"温度", r"密度", r"强度", r"多少"],
        "table_query": [r"bom", r"清单", r"型号表"],
        "definition": [r"是什么", r"定义", r"含义"],
        "how_to": [r"怎么", r"如何", r"步骤"],
        "material_selector": [r"选材", r"用什么材料"],
    }

    for intent, pats in patterns.items():
        for pat in pats:
            if re.search(pat, query_lower):
                mode = "deep" if intent in ["compare", "numeric_lookup", "material_selector"] else "fast"
                return intent, mode

    return "general", "fast"
