"""
dynamic_alpha.py — 动态融合权重 (v1.43)
根据 query 类型动态调整 RRF alpha
"""
from typing import Tuple


def classify_query(query: str) -> str:
    """分类查询类型"""
    q = query.lower()
    
    # 事实型：找具体数据/参数/型号
    factual_kw = ["多少", "什么型号", "参数", "规格", "尺寸", "温度", "压力", "材质", "标准", "GB", "ISO", "型号"]
    if any(kw in q for kw in factual_kw):
        return "factual"
    
    # 语义型：找概念/解释/对比
    semantic_kw = ["区别", "对比", "优缺点", "原理", "为什么", "怎么选", "推荐", "适合"]
    if any(kw in q for kw in semantic_kw):
        return "semantic"
    
    # 操作型：找步骤/方法/教程
    action_kw = ["怎么", "如何", "步骤", "方法", "操作", "设置", "配置", "安装", "使用"]
    if any(kw in q for kw in action_kw):
        return "action"
    
    # 混合型（默认）
    return "hybrid"


def get_dynamic_alpha(query: str) -> Tuple[float, float]:
    """
    根据查询类型返回 (vector_weight, bm25_weight)
    
    规则：
    - 事实型：BM25 权重高（关键词精确匹配更重要）
    - 语义型：向量权重高（语义理解更重要）
    - 操作型：均衡（既需要关键词也需要语义）
    - 混合型：默认 0.6/0.4
    """
    qtype = classify_query(query)
    
    alpha_map = {
        "factual":  (0.35, 0.65),  # BM25 为主
        "semantic": (0.75, 0.25),  # 向量为主
        "action":   (0.55, 0.45),  # 均衡偏向量
        "hybrid":   (0.60, 0.40),  # 默认
    }
    
    return alpha_map.get(qtype, (0.60, 0.40))


def get_similarity_threshold(query: str, result_count: int) -> float:
    """
    自适应向量相似度阈值
    
    规则：
    - 结果多（>20）：收紧阈值，提高精度
    - 结果少（<5）：放宽阈值，提高召回
    - 事实型查询：阈值稍高（要精确）
    - 语义型查询：阈值稍低（允许模糊匹配）
    """
    base = 0.15
    qtype = classify_query(query)
    
    # 根据查询类型调整
    type_adj = {
        "factual": 0.05,    # 收紧
        "semantic": -0.05,  # 放宽
        "action": 0.0,
        "hybrid": 0.0,
    }
    
    # 根据结果数量调整
    if result_count > 20:
        count_adj = 0.05
    elif result_count < 5:
        count_adj = -0.05
    else:
        count_adj = 0.0
    
    threshold = base + type_adj.get(qtype, 0) + count_adj
    return max(0.05, min(0.30, threshold))  # 限制在 0.05-0.30 之间
