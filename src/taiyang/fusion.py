"""
fusion — 从 retrieval.py 拆分
1.40 天梯计划 P2：上帝类拆分
"""

"""
services/retrieval.py — 混合检索服务（v10.0）
负责：BM25 + 向量双路召回 → RRF 融合 → 精排 → 去重 → 上下文扩展
"""
import logging; logger = logging.getLogger(__name__)
import re, asyncio
from typing import List, Dict

# v11: Concurrent control for ChromaDB
_VECTOR_SEM = asyncio.Semaphore(8)

try:
    import jieba
    jieba.setLogLevel(20)
except ImportError:
    jieba = None

from src.db.memory_store import get_store
from src.db.vector_store import get_vector_store, embed_texts
from src.taiyang.graph_router import route_to_categories, expand_query_with_synonyms, get_entity_context
from src.config import EMBEDDER_URL
from src.taiyang.synonym_loader import load_synonyms
# 兼容别名
_SYNONYM_MAP = load_synonyms()




def rrf_fusion(bm25_results: list, vector_results: list, k: int = 60) -> list:
    """L3: RRF 倒数排序融合"""
    rrf_scores = {}
    all_results = {}
    for i, r in enumerate(bm25_results):
        key = f"{r.get('file_hash','')}:{r.get('chunk_index',0)}"
        rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (k + i + 1)
        all_results[key] = r
    for i, r in enumerate(vector_results):
        key = f"{r.get('file_hash','')}:{r.get('chunk_index',0)}"
        rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (k + i + 1)
        if key not in all_results:
            all_results[key] = r
    sorted_keys = sorted(rrf_scores, key=rrf_scores.get, reverse=True)
    merged = []
    for key in sorted_keys:
        r = all_results[key]
        r["score"] = round(rrf_scores[key] * 100, 2)
        r["_rrf_score"] = round(rrf_scores[key], 6)
        merged.append(r)
    return merged


def weighted_fusion_adjust(query: str, merged: list, bm25_results: list, vector_results: list) -> list:
    """L3-P4: 动态 alpha 加权调整"""
    q_len = len(query.replace(" ", ""))
    is_exact = bool(re.search(
        r"[A-Z]{2,}-?\d+|S7-\d+|M\d+[×xX]|\d+\.\d+mm|\d+[A-Z]{2,}|"
        r"LSW\d+|AR\d+|GE\d+/\d+|VLAN\s*\d+|IP\s*\d+\.\d+|"
        r"GP-\d+|EP-\d+|RP-\d+|SB-\d+",  # v10.1: 标准件型号
        query, re.IGNORECASE
    ))
    is_semantic = bool(re.search(r"如何|怎么|为什么|什么意思|方法|流程|步骤|方案|有哪些|是什么", query))
    if is_exact and not is_semantic:
        alpha = 0.78  # 精确查询更偏 BM25
    elif is_semantic and not is_exact:
        alpha = 0.25  # 语义查询更偏向量
    elif q_len < 5:
        alpha = 0.40
    else:
        alpha = 0.50
    for r in merged:
        bm25_rank = r.get("_bm25_rank", 999)
        vector_rank = r.get("_vector_rank", 999)
        bm25_k = 60 * (1 - alpha + 0.15)
        vector_k = 60 * (alpha + 0.15)
        weighted_score = 0
        if bm25_rank < 999:
            weighted_score += 1.0 / (bm25_k + bm25_rank)
        if vector_rank < 999:
            weighted_score += 1.0 / (vector_k + vector_rank)
        r["_weighted_score"] = round(weighted_score, 6)
        r["_alpha"] = alpha
    merged.sort(key=lambda x: x.get("_weighted_score", 0), reverse=True)
    return merged


def exact_match_boost(query: str, results: list) -> list:
    """L4-v10.1: 精确匹配 + 型号/编号/模式检测加权"""
    import re as _re
    q_lower = query.lower()
    
    # 检测 query 中的精确实体模式
    exact_patterns = []
    # 型号模式: GP-20-150, EP-123, S7-1200, LSW1, AR1, VLAN 80
    for pat in [r'\b[A-Z]{2,5}[-\s]?\d{2,6}([-\s]?\w+)?\b', r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b']:
        matches = _re.findall(pat, query, _re.IGNORECASE)
        exact_patterns.extend(matches)
    
    for r in results:
        text = (r.get("text", "") or "").lower()
        fn = (r.get("file_name", "") or "").lower()
        boost = 0
        
        # Base: full query match
        if q_lower in text:
            boost += 5
        if len(q_lower) >= 4:
            q_terms = [t for t in q_lower.split() if len(t) >= 2]
            hit_count = sum(1 for t in q_terms if t in text)
            boost += min(hit_count, 5)
        if q_lower in fn or any(t in fn for t in q_lower.split() if len(t) >= 2):
            boost += 3
        
        # v10.1: 型号/编号/模式精确匹配增强
        if exact_patterns:
            for ep in exact_patterns:
                if ep.lower() in text:
                    boost += 3  # 每匹配一个型号+3分
                if ep.lower() in fn:
                    boost += 5  # 文件名匹配+5分
        
        r["score"] = round(float(r.get("score", 0)) + boost, 2)
    results.sort(key=lambda x: float(x.get("score", 0)), reverse=True)
    return results


def dynamic_category_weight(query: str, results: list) -> list:
    """L4-②: 动态分类权重"""
    if not results:
        return results
    CAT_KW = {
        "网络建设": ["vlan","子网","dhcp","交换机","路由","拓扑","ip","acl","nat","wifi","ssid","端口"],
        "机械设计": ["齿轮","轴承","蜗杆","蜗轮","花键","联轴器","公差","配合","凸轮"],
        "模具设计": ["模具","导柱","导套","顶针","滑块","浇口","型腔","分型面"],
        "电气自动化": ["plc","伺服","变频器","传感器","接线图","梯形图","hmi","profinet"],
        "工程技术规范": ["sop","注塑","工艺参数","物性表","msds","操作流程"],
        "品质管理": ["三坐标","grr","cpk","spc","位置度","圆度","检具"],
        "供应商管理": ["供应商","采购","合同","报价","rfq","交货","付款"],
        "行政人事": ["考勤","请假","薪资","社保","报销","入职","离职"],
        "财务文档": ["财务","税务","审计","发票","对账","报表"],
        "项目管理": ["项目","进度","里程碑","预算","交付","验收"],
    }
    q_lower = query.lower()
    cat_weights = {}
    for cat, kws in CAT_KW.items():
        hits = sum(1 for kw in kws if kw in q_lower)
        if hits > 0:
            cat_weights[cat] = min(hits * 2, 8)
    if not cat_weights:
        return results
    for r in results:
        cat = r.get("category", ""); cat = cat if isinstance(cat, str) else str(cat) if cat else ""
        weight = cat_weights.get(cat, 0)
        if weight > 0:
            r["score"] = round(float(r.get("score", 0)) + weight, 2)
    results.sort(key=lambda x: float(x.get("score", 0)), reverse=True)
    return results


def personalized_boost(query: str, results: list) -> list:
    """P1-A: 基于用户历史反馈的个性化术语权重"""
    try:
        from src.services.learner import get_personalized_boost
        boost = get_personalized_boost(query)
        if not boost:
            return results
        for r in results:
            text = (r.get("text", "") or "").lower()
            bonus = sum(w for t, w in boost.items() if t in text)
            if bonus > 0:
                r["score"] = round(float(r.get("score", 0)) + bonus, 2)
        results.sort(key=lambda x: float(x.get("score", 0)), reverse=True)
    except Exception:
        logger.warning(f"[retrieval] suppressed exception", exc_info=True)
        pass
    return results


