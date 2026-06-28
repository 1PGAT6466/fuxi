"""
auto_tune_alpha.py — Phase 1.4.3: 自动调优 RRF alpha
从 feedback_log 中提取低分 query，分析最佳 alpha 组合
"""
import json, os, sys, sqlite3
sys.path.insert(0, os.path.expanduser("~/kb-server"))

DB_PATH = os.path.expanduser("~/kb-server/data/chunks.db")


def get_feedback_queries():
    """从 feedback_log 中提取 👎 query"""
    conn = sqlite3.connect(DB_PATH)
    try:
        # 查找 feedback 相关表
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "feedback_log" in tables:
            rows = conn.execute("SELECT query, rating FROM feedback_log WHERE rating <= 2 ORDER BY created_at DESC LIMIT 50").fetchall()
            return [{"query": r[0], "rating": r[1]} for r in rows]
    except:
        pass
    finally:
        conn.close()
    return []


def analyze_alpha_impact(queries):
    """分析不同 alpha 对低分 query 的影响"""
    from src.services.dynamic_alpha import get_dynamic_alpha, classify_query
    
    analysis = []
    for q in queries:
        qtype = classify_query(q["query"])
        vw, bw = get_dynamic_alpha(q["query"])
        analysis.append({
            "query": q["query"],
            "type": qtype,
            "vector_weight": vw,
            "bm25_weight": bw,
            "rating": q.get("rating", 0)
        })
    
    # 按类型汇总
    by_type = {}
    for a in analysis:
        t = a["type"]
        if t not in by_type:
            by_type[t] = {"count": 0, "avg_vw": 0, "avg_bw": 0}
        by_type[t]["count"] += 1
        by_type[t]["avg_vw"] += a["vector_weight"]
        by_type[t]["avg_bw"] += a["bm25_weight"]
    
    for t in by_type:
        n = by_type[t]["count"]
        by_type[t]["avg_vw"] /= n
        by_type[t]["avg_bw"] /= n
    
    return analysis, by_type


def suggest_adjustments(by_type):
    """基于分析建议 alpha 调整"""
    suggestions = []
    for t, stats in by_type.items():
        if stats["count"] >= 3:
            # 如果该类型低分 query 多，建议增加 BM25 权重
            if t == "factual":
                suggestions.append(f"{t}: 考虑增加 BM25 权重 (当前 {stats['avg_bw']:.2f})")
            elif t == "semantic":
                suggestions.append(f"{t}: 考虑增加向量权重 (当前 {stats['avg_vw']:.2f})")
    return suggestions


if __name__ == "__main__":
    queries = get_feedback_queries()
    if not queries:
        print("无 feedback 数据，使用模拟数据")
        queries = [
            {"query": "流程引擎功能", "rating": 1},
            {"query": "权限管理", "rating": 2},
            {"query": "如何创建部门", "rating": 1},
        ]
    
    analysis, by_type = analyze_alpha_impact(queries)
    print(f"=== Alpha 调优分析 ({len(queries)} 条低分 query) ===\n")
    
    for t, stats in by_type.items():
        print(f"  {t}: {stats['count']} 条, avg_vw={stats['avg_vw']:.2f}, avg_bw={stats['avg_bw']:.2f}")
    
    suggestions = suggest_adjustments(by_type)
    if suggestions:
        print("\n建议调整:")
        for s in suggestions:
            print(f"  - {s}")
    else:
        print("\n当前 alpha 配置合理，无需调整")
