"""eval_smoke_lite.py — 轻量评测（无 LLM judge，纯召回率）v2.0
50 条评测用例，覆盖 6 个分类
"""
import requests, time, json, os

API = os.getenv("FUXI_API_URL", "http://localhost:8080/api/search")
TOKEN = os.getenv("FUXI_API_TOKEN", "")

# 50 条评测用例，按分类组织
CASES = [
    # === 组织/权限 (10) ===
    ("权限管理", "组织"), ("如何创建部门", "部门"), ("流程引擎功能", "流程"),
    ("证照管理操作", "证照"), ("组织架构管理", "组织"), ("岗位设置", "岗位"),
    ("密码复杂度设置", "密码"), ("分部管理", "分部"), ("人员卡片字段", "人员"),
    ("用户权限分配", "权限"),
    
    # === 系统/模块 (10) ===
    ("移动引擎是什么", "移动"), ("门户引擎配置", "门户"), ("SAP集成设置", "SAP"),
    ("资产管理模块", "资产"), ("项目管理使用", "项目"), ("预算管理位置", "预算"),
    ("公文管理流程", "公文"), ("报表导出方法", "报表"), ("系统参数设置", "系统参数"),
    ("日程管理功能", "日程"),
    
    # === 操作/流程 (10) ===
    ("创建审批流程", "流程"), ("配置表单字段", "表单"), ("添加用户权限", "权限"),
    ("设置流程路径", "流程"), ("导出报表数据", "报表"), ("流程审批失败", "流程"),
    ("权限不足原因", "权限"), ("无法登录系统", "登录"), ("流程卡住原因", "流程"),
    ("报表数据不对", "报表"),
    
    # === 对比/分析 (10) ===
    ("权限证照区别", "权限"), ("门户移动区别", "门户"), ("项目预算关系", "项目"),
    ("系统有哪些模块", "模块"), ("支持文件格式", "上传"), ("OA 和 ERP 区别", "OA"),
    ("流程和表单关系", "流程"), ("门户和移动对比", "门户"), ("权限角色区别", "权限"),
    ("报表和查询区别", "报表"),
    
    # === 技术/配置 (10) ===
    ("VLAN 配置方法", "VLAN"), ("IP 地址规划", "IP"), ("网络拓扑设计", "网络"),
    ("数据库备份策略", "备份"), ("系统监控配置", "监控"), ("接口对接文档", "接口"),
    ("单点登录配置", "单点"), ("SSL 证书配置", "SSL"), ("负载均衡设置", "负载"),
    ("日志查看方法", "日志"),
]

print(f"=== 伏羲 RAG 评测 v2.0: {len(CASES)} 条 ===\n")

# 分类统计
categories = {
    "组织/权限": CASES[0:10],
    "系统/模块": CASES[10:20],
    "操作/流程": CASES[20:30],
    "对比/分析": CASES[30:40],
    "技术/配置": CASES[40:50],
}

passed = 0
total_latency = 0
results_detail = []
cat_results = {cat: {"passed": 0, "total": len(cases)} for cat, cases in categories.items()}

current_cat = ""
for i, (query, expected_keyword) in enumerate(CASES):
    # 确定当前分类
    for cat, cases in categories.items():
        if (query, expected_keyword) in cases:
            current_cat = cat
            break

    t0 = time.time()
    try:
        r = requests.get(API, params={"q": query}, headers={"Authorization": f"Bearer {TOKEN}"}, timeout=15)
        latency = (time.time() - t0) * 1000
        total_latency += latency
        d = r.json()
        search_results = d.get("results", [])
        count = len(search_results)
        
        hit = False
        if search_results:
            top_text = " ".join([
                (r.get("text", "") + r.get("file_name", "")).lower()
                for r in search_results[:3]
            ])
            hit = expected_keyword.lower() in top_text
        
        status = "✅" if count > 0 and hit else ("⚠️" if count > 0 else "❌")
        if count > 0 and hit:
            passed += 1
            cat_results[current_cat]["passed"] += 1
        print(f"  {status} [{i+1:2d}] {query}: {count}条 {latency:.0f}ms {'命中' if hit else '未命中'}")
        results_detail.append({"q": query, "n": count, "hit": hit, "ms": round(latency), "cat": current_cat})
    except Exception as e:
        print(f"  ❌ [{i+1:2d}] {query}: {e}")
        results_detail.append({"q": query, "n": 0, "hit": False, "ms": 0, "cat": current_cat})

# 汇总
recall = passed / len(CASES)
avg_ms = total_latency / len(CASES)

print(f"\n{'='*50}")
print(f"📊 评测结果")
print(f"{'='*50}")
print(f"  Recall@10: {recall:.1%} ({passed}/{len(CASES)})")
print(f"  平均延迟:  {avg_ms:.0f}ms")
print()

print(f"📋 分类详情:")
for cat, stats in cat_results.items():
    cat_recall = stats["passed"] / stats["total"] if stats["total"] > 0 else 0
    bar = "█" * int(cat_recall * 10) + "░" * (10 - int(cat_recall * 10))
    print(f"  {cat:8s} {bar} {cat_recall:.0%} ({stats['passed']}/{stats['total']})")

print()
print(f"{'✅ 达标' if recall >= 0.6 else '⚠️ 未达标'} (目标 > 60%)")

# 保存结果
results_file = os.path.join(os.path.dirname(__file__), "..", "data", "eval_results.json")
os.makedirs(os.path.dirname(results_file), exist_ok=True)
with open(results_file, "w", encoding="utf-8") as f:
    json.dump({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(CASES),
        "passed": passed,
        "recall": round(recall, 4),
        "avg_latency_ms": round(avg_ms),
        "by_category": cat_results,
        "details": results_detail,
    }, f, ensure_ascii=False, indent=2)
print(f"\n结果已保存到 {results_file}")
