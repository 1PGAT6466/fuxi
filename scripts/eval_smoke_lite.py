"""eval_smoke_lite.py — 轻量评测（无 LLM judge，纯召回率）"""
import requests, time, json

API = "http://172.25.30.200:8080/api/search"
TOKEN = "fuxi-v1.43-token"

# 30 条评测用例
CASES = [
    ("权限管理", "组织权限中心"), ("如何创建部门", "组织"), ("流程引擎功能", "流程引擎"),
    ("证照管理操作", "证照"), ("移动引擎是什么", "移动"), ("门户引擎配置", "门户"),
    ("SAP集成设置", "SAP"), ("资产管理模块", "资产"), ("项目管理使用", "项目"),
    ("预算管理位置", "预算"), ("公文管理流程", "公文"), ("报表导出方法", "报表"),
    ("系统参数设置", "系统参数"), ("日程管理功能", "日程"), ("组织架构管理", "组织"),
    ("权限证照区别", "权限"), ("门户移动区别", "门户"), ("项目预算关系", "项目"),
    ("创建审批流程", "流程"), ("配置表单字段", "表单"), ("添加用户权限", "权限"),
    ("设置流程路径", "流程"), ("导出报表数据", "报表"), ("流程审批失败", "流程"),
    ("权限不足原因", "权限"), ("无法登录系统", "登录"), ("流程卡住原因", "流程"),
    ("报表数据不对", "报表"), ("系统有哪些模块", "模块"), ("支持文件格式", "上传"),
]

print(f"=== 轻量评测: {len(CASES)} 条 ===\n")
passed = 0
total_latency = 0
results_detail = []

for i, (query, expected_keyword) in enumerate(CASES):
    t0 = time.time()
    try:
        r = requests.get(API, params={"q": query}, headers={"Authorization": f"Bearer {TOKEN}"}, timeout=15)
        latency = (time.time() - t0) * 1000
        total_latency += latency
        d = r.json()
        search_results = d.get("results", [])
        count = len(search_results)
        
        # 检查是否命中预期关键词
        hit = False
        if search_results:
            top_text = (search_results[0].get("text", "") + search_results[0].get("file_name", "")).lower()
            hit = expected_keyword.lower() in top_text
        
        status = "✅" if count > 0 and hit else ("⚠️" if count > 0 else "❌")
        if count > 0 and hit:
            passed += 1
        print(f"  {status} [{i+1:2d}] {query}: {count}条 {latency:.0f}ms {'命中' if hit else '未命中关键词'}")
        results_detail.append({"q": query, "n": count, "hit": hit, "ms": latency})
    except Exception as e:
        print(f"  ❌ [{i+1:2d}] {query}: {e}")
        results_detail.append({"q": query, "n": 0, "hit": False, "ms": 0})

recall = passed / len(CASES)
avg_ms = total_latency / len(CASES)
print(f"\n=== 结果 ===")
print(f"Recall@10: {recall:.1%} ({passed}/{len(CASES)})")
print(f"平均延迟: {avg_ms:.0f}ms")
print(f"{'✅ 达标' if recall >= 0.6 else '⚠️ 未达标'} (目标 > 60%)")
