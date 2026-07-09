"""
query_router.py — 统一查询分类（9种类型）
合并 Brain.Instinct 的6种 + QueryTypeClassifier 的3种
"""
import re
import logging
from typing import Tuple

logger = logging.getLogger("shaoyin.query_router")


class UnifiedQueryType:
    """统一查询类型"""
    COMPARE = "compare"
    NUMERIC_LOOKUP = "numeric_lookup"
    TABLE_QUERY = "table_query"
    DEFINITION = "definition"
    HOW_TO = "how_to"
    MATERIAL_SELECTOR = "material_selector"
    MULTI_HOP = "multi_hop"
    OPEN_ENDED = "open_ended"
    NO_ENTITY = "no_entity"


# 查询类型配置
QUERY_TYPE_CONFIG = {
    "compare": {
        "patterns": [r"和.*比较", r"和.*区别", r"哪个更", r"对比", r"vs\.?", r"差异", r"优缺点"],
        "complexity": "medium",
        "search_mode": "L2_STANDARD",
        "top_k": 15,
    },
    "numeric_lookup": {
        "patterns": [r"参数", r"温度", r"熔点", r"密度", r"收缩率", r"强度", r"硬度", r"多少", r"数值"],
        "complexity": "simple",
        "search_mode": "L1_FAST",
        "top_k": 10,
    },
    "table_query": {
        "patterns": [r"bom", r"清单", r"采购", r"型号表", r"物料表", r"选型表", r"规格表"],
        "complexity": "medium",
        "search_mode": "L2_STANDARD",
        "top_k": 10,
    },
    "definition": {
        "patterns": [r"是什么", r"定义", r"什么叫", r"什么是", r"含义", r"全称"],
        "complexity": "simple",
        "search_mode": "L1_FAST",
        "top_k": 5,
    },
    "how_to": {
        "patterns": [r"怎么", r"如何", r"步骤", r"流程", r"方法", r"操作"],
        "complexity": "medium",
        "search_mode": "L2_STANDARD",
        "top_k": 10,
    },
    "material_selector": {
        "patterns": [r"选材", r"哪种材料", r"用什么材料", r"材料选择", r"替代.*材料"],
        "complexity": "medium",
        "search_mode": "L2_STANDARD",
        "top_k": 10,
    },
    "multi_hop": {
        "patterns": [r"关系", r"关联", r"影响", r"导致", r"因为", r"为什么"],
        "complexity": "complex",
        "search_mode": "L3_DEEP",
        "top_k": 15,
    },
    "open_ended": {
        "patterns": [r"如何提高", r"怎么优化", r"建议", r"方案"],
        "complexity": "medium",
        "search_mode": "L2_STANDARD",
        "top_k": 10,
    },
    "no_entity": {
        "patterns": [r"效率", r"质量", r"性能", r"优化", r"改进"],
        "complexity": "medium",
        "search_mode": "L2_STANDARD",
        "top_k": 10,
        "fallback": "vector_search",
    },
}


def classify_query(query: str) -> Tuple[str, str, str, int]:
    """
    分类查询
    返回: (类型, 复杂度, 搜索模式, top_k)
    """
    query_lower = query.lower().strip()
    
    for qtype, config in QUERY_TYPE_CONFIG.items():
        for pattern in config["patterns"]:
            if re.search(pattern, query_lower):
                logger.info(f"[路由] 查询分类: {qtype} (复杂度={config['complexity']}, 模式={config['search_mode']})")
                return qtype, config["complexity"], config["search_mode"], config["top_k"]
    
    # 默认：中等复杂度
    logger.info(f"[路由] 查询分类: unknown → open_ended (复杂度=medium, 模式=L2_STANDARD)")
    return "open_ended", "medium", "L2_STANDARD", 10
