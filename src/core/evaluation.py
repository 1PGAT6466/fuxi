"""
lib/evaluation.py — 评测引擎
支持 Precision/Recall/MRR/NDCG 指标计算
"""
import json, time, os
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import logging; logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent.parent

# ===== 测试集 =====
DEFAULT_TEST_CASES = [
    # (查询, [预期相关文档的关键词列表])
    ("连接器端子正向力设计参数", ["正向力", "端子", "保持力", "接触"]),
    ("泛微E-cology流程引擎怎么配置", ["流程引擎", "表单管理", "路径管理", "流程节点"]),
    ("VLAN 101 配置方法", ["VLAN", "trunk", "access", "port"]),
    ("SMT贴片回流焊温度曲线", ["SMT", "回流焊", "温度", "贴片"]),
    ("公司年假政策", ["年假", "考勤", "人事", "请假"]),
    ("标准件BOM表编码规则", ["BOM", "标准件", "编码", "型号"]),
    ("MISUMI轴承型号查询", ["MISUMI", "轴承", "型号", "规格"]),
    ("DHCP服务器配置步骤", ["DHCP", "IP", "地址池", "子网"]),
    ("塑胶材料PA66特性", ["PA66", "塑胶", "材料", "尼龙"]),
    ("防火墙ACL规则怎么写", ["防火墙", "ACL", "安全策略", "规则"]),
    ("泛微组织权限中心怎么用", ["组织权限", "角色", "人员卡片", "权限管理"]),
    ("板端连接器防水设计", ["连接器", "防水", "板端", "housing"]),
    ("回焊前目检标准", ["目检", "回流焊", "SMT", "品质"]),
    ("OA资产调拨流程", ["资产", "调拨", "OA", "资产卡片"]),
    ("会议管理系统配置", ["会议", "会议室", "会议类型", "泛微"]),
]

def load_test_cases():
    """加载测试集，优先从 data/test_cases.json 读取"""
    tc_file = BASE / "data" / "test_cases.json"
    if tc_file.exists():
        with open(tc_file) as f:
            return json.load(f)
    # 返回默认测试集
    return [{"query": q, "relevant_keywords": kw, "id": f"tc_{i}"} 
            for i, (q, kw) in enumerate(DEFAULT_TEST_CASES)]

def save_test_cases(cases):
    tc_file = BASE / "data" / "test_cases.json"
    tc_file.parent.mkdir(parents=True, exist_ok=True)
    with open(tc_file, "w") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)

# ===== 评测指标 =====
def precision_at_k(relevant: set, retrieved: list, k: int = 10) -> float:
    """Precision@K"""
    hits = sum(1 for r in retrieved[:k] if any(kw in r for kw in relevant))
    return hits / min(k, len(retrieved)) if retrieved else 0.0

def recall_at_k(relevant: set, retrieved: list, k: int = 10) -> float:
    """Recall@K"""
    if not relevant:
        return 0.0
    hits = sum(1 for r in retrieved[:k] if any(kw in r for kw in relevant))
    return hits / len(relevant)

def mrr(relevant_sets: list, retrieved_lists: list) -> float:
    """Mean Reciprocal Rank"""
    total_rr = 0.0
    for rel, ret in zip(relevant_sets, retrieved_lists):
        for i, r in enumerate(ret):
            if any(kw in r for kw in rel):
                total_rr += 1.0 / (i + 1)
                break
    return total_rr / len(relevant_sets) if relevant_sets else 0.0

def ndcg_at_k(relevant: set, retrieved: list, k: int = 10) -> float:
    """NDCG@K (简化版，二值相关)"""
    import math
    dcg = 0.0
    for i, r in enumerate(retrieved[:k]):
        if any(kw in r for kw in relevant):
            dcg += 1.0 / math.log2(i + 2)  # i+2 因为 log(1)=0
    
    ideal_count = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_count))
    
    return dcg / idcg if idcg > 0 else 0.0

# ===== 评测运行器 =====
def run_evaluation(search_fn, test_cases: list = None) -> dict:
    """
    运行评测
    search_fn(query, top_k) -> list of result texts
    """
    if test_cases is None:
        test_cases = load_test_cases()
    
    results = []
    for tc in test_cases:
        t0 = time.time()
        try:
            retrieved_texts = search_fn(tc["query"], 10)
            latency = time.time() - t0
            retrieved = [r.get("text", r.get("content", str(r)))[:200] 
                        if isinstance(r, dict) else str(r)[:200] 
                        for r in retrieved_texts]
        except Exception:
            retrieved = []
            latency = -1
        
        rel = set(tc["relevant_keywords"])
        results.append({
            "id": tc.get("id", ""),
            "query": tc["query"],
            "latency_ms": round(latency * 1000, 1),
            "precision_at_10": round(precision_at_k(rel, retrieved, 10), 4),
            "recall_at_10": round(recall_at_k(rel, retrieved, 10), 4),
            "ndcg_at_10": round(ndcg_at_k(rel, retrieved, 10), 4),
            "result_count": len(retrieved),
        })
    
    # 汇总
    avg_p = sum(r["precision_at_10"] for r in results) / len(results)
    avg_r = sum(r["recall_at_10"] for r in results) / len(results)
    avg_n = sum(r["ndcg_at_10"] for r in results) / len(results)
    mrr_score = mrr(
        [set(tc["relevant_keywords"]) for tc in test_cases],
        [[str(r.get("text", str(r)))[:200] for r in search_fn(tc["query"], 10)] 
         for tc in test_cases]
    )
    avg_latency = sum(r["latency_ms"] for r in results if r["latency_ms"] > 0) / max(1, sum(1 for r in results if r["latency_ms"] > 0))
    
    return {
        "summary": {
            "precision@10": round(avg_p, 4),
            "recall@10": round(avg_r, 4),
            "ndcg@10": round(avg_n, 4),
            "mrr": round(mrr_score, 4),
            "avg_latency_ms": round(avg_latency, 1),
            "test_cases": len(results),
            "timestamp": datetime.now().isoformat(),
        },
        "details": results,
    }

print("lib/evaluation.py 加载完成")
