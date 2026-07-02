"""
query_expansion.py — 太阳·查询扩展
同义词扩展 + 意图识别 + 实体提取
"""
import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger("taiyang.query_expansion")

# 同义词映射（从synonyms.yaml加载）
_SYNONYM_MAP: Dict[str, List[str]] = {}


def _load_synonyms():
    """加载同义词映射"""
    global _SYNONYM_MAP
    if _SYNONYM_MAP:
        return
    try:
        from src.services.synonym_loader import load_synonyms
        _SYNONYM_MAP = load_synonyms()
    except Exception:
        _SYNONYM_MAP = {}


def expand_query(query: str) -> str:
    """查询扩展主入口"""
    _load_synonyms()

    expanded_terms = [query]

    # 1. 同义词扩展
    synonyms = _expand_synonyms(query)
    expanded_terms.extend(synonyms)

    # 2. 型号变体扩展
    variants = _expand_model_variants(query)
    expanded_terms.extend(variants)

    # 去重
    seen = set()
    result = []
    for term in expanded_terms:
        term = term.strip()
        if term and term not in seen:
            seen.add(term)
            result.append(term)

    return " ".join(result)


def _expand_synonyms(query: str) -> List[str]:
    """同义词扩展"""
    if not _SYNONYM_MAP:
        return []

    expanded = []
    q_lower = query.lower()

    for term, synonyms in _SYNONYM_MAP.items():
        if term.lower() in q_lower:
            for syn in synonyms[:3]:  # 最多3个同义词
                if syn.lower() not in q_lower:
                    expanded.append(syn)

    return expanded


def _expand_model_variants(query: str) -> List[str]:
    """型号变体扩展"""
    variants = []

    # PA66 → PA66-GF30, PA66-GF25, Nylon 66
    model_patterns = [
        (r'\bPA66\b', ['PA66-GF30', 'PA66-GF25', 'Nylon 66']),
        (r'\bPA6\b', ['PA6-GF30', 'Nylon 6']),
        (r'\bPOM\b', ['POM-C', 'POM-H', 'Delrin']),
        (r'\bABS\b', ['ABS+PC', 'ABS-M30']),
        (r'\bPP\b', ['PP-GF30', 'PP-TD20']),
        (r'\bPE\b', ['PE-HD', 'PE-LD', 'PE-UHMW']),
    ]

    for pattern, expansion in model_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            variants.extend(expansion)

    return variants


def extract_keywords(query: str) -> List[str]:
    """提取查询关键词"""
    try:
        import jieba
        jieba.setLogLevel(20)
        words = list(jieba.cut(query))
        # 过滤停用词
        stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
        keywords = [w for w in words if len(w) > 1 and w not in stopwords]
        return keywords
    except ImportError:
        # 降级：简单分词
        return [w for w in query.split() if len(w) > 1]


def classify_query_type(query: str) -> str:
    """查询类型分类"""
    # 数字查询
    if re.search(r'多少|数值|参数|规格|强度|硬度|密度|熔点|温度', query):
        return 'numeric_lookup'

    # 对比查询
    if re.search(r'对比|比较|区别|优劣|vs|VS', query):
        return 'compare'

    # 表格查询
    if re.search(r'表格|表|清单|列表|一览', query):
        return 'table_query'

    # 定义查询
    if re.search(r'什么是|定义|含义|解释|意思', query):
        return 'definition'

    # 操作查询
    if re.search(r'如何|怎么|怎样|方法|步骤|流程', query):
        return 'how_to'

    # 材料选择
    if re.search(r'推荐|选择|选用|适合|替代', query):
        return 'material_selector'

    return 'general_search'
