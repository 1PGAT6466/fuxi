"""
eval_smoke.py — Phase 6.3: 自动评测脚本
CI/CD 中可自动运行，输出 Recall@10 / MRR
"""
import sys, os, time, json
sys.path.insert(0, os.path.expanduser('~/kb-server'))

# 基于实际入库文档内容的评测查询
TEST_QUERIES = [
    ("组织权限管理", "组织"),
    ("部门如何创建", "部门"),
    ("人员卡片字段", "人员"),
    ("密码复杂度设置", "密码"),
    ("分部管理", "分部"),
    ("岗位设置", "岗位"),
    ("流程引擎", "流程"),
    ("办公地点", "办公"),
    ("导入功能", "导入"),
    ("权限管理", "权限"),
]


async def run_eval():
    from src.db.memory_store import get_store
    store = get_store()
    
    results = []
    total_hits = 0
    total_mrr = 0.0
    
    for query, expected_keyword in TEST_QUERIES:
        start = time.time()
        docs = store.keyword_search(query, top_k=10)
        latency = (time.time() - start) * 1000
        
        # Recall@10: 是否命中至少一篇相关文档
        hit = any(expected_keyword.lower() in (d.get("text", "") or "").lower() for d in docs)
        if hit:
            total_hits += 1
        
        # MRR: 第一个相关文档的排名
        rank = 0
        for i, d in enumerate(docs):
            if expected_keyword.lower() in (d.get("text", "") or "").lower():
                rank = i + 1
                break
        if rank > 0:
            total_mrr += 1.0 / rank
        
        results.append({
            "query": query,
            "hit": hit,
            "results": len(docs),
            "latency_ms": round(latency, 1),
        })
    
    n = len(TEST_QUERIES)
    recall = total_hits / n if n > 0 else 0
    mrr = total_mrr / n if n > 0 else 0
    
    report = {
        "total_queries": n,
        "recall_at_10": round(recall, 2),
        "mrr": round(mrr, 2),
        "results": results,
    }
    
    print(json.dumps(report, ensure_ascii=False, indent=2))
    
    if recall < 0.6:
        print(f"\nWARNING: Recall@10={recall:.2f} below threshold 0.6")
        sys.exit(1)
    else:
        print(f"\nPASS: Recall@10={recall:.2f}, MRR={mrr:.2f}")
        sys.exit(0)


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_eval())
