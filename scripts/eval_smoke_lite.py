"""eval_smoke_lite.py — 轻量评测 v2.0（50 条，6 分类）"""
import requests, time, json, os

API = os.getenv("FUXI_API_URL", "http://localhost:8080/api/search")
TOKEN = os.getenv("FUXI_API_TOKEN", "")

CASES = [
    ("权限管理","组织"),("如何创建部门","部门"),("流程引擎功能","流程"),
    ("证照管理操作","证照"),("组织架构管理","组织"),("岗位设置","岗位"),
    ("密码复杂度设置","密码"),("分部管理","分部"),("人员卡片字段","人员"),
    ("用户权限分配","权限"),
    ("移动引擎是什么","移动"),("门户引擎配置","门户"),("SAP集成设置","SAP"),
    ("资产管理模块","资产"),("项目管理使用","项目"),("预算管理位置","预算"),
    ("公文管理流程","公文"),("报表导出方法","报表"),("系统参数设置","系统参数"),
    ("日程管理功能","日程"),
    ("创建审批流程","流程"),("配置表单字段","表单"),("添加用户权限","权限"),
    ("设置流程路径","流程"),("导出报表数据","报表"),("流程审批失败","流程"),
    ("权限不足原因","权限"),("无法登录系统","登录"),("流程卡住原因","流程"),
    ("报表数据不对","报表"),
    ("权限证照区别","权限"),("门户移动区别","门户"),("项目预算关系","项目"),
    ("系统有哪些模块","模块"),("支持文件格式","上传"),("OA和ERP区别","OA"),
    ("流程和表单关系","流程"),("门户和移动对比","门户"),("权限角色区别","权限"),
    ("报表和查询区别","报表"),
    ("VLAN配置方法","VLAN"),("IP地址规划","IP"),("网络拓扑设计","网络"),
    ("数据库备份策略","备份"),("系统监控配置","监控"),("接口对接文档","接口"),
    ("单点登录配置","单点"),("SSL证书配置","SSL"),("负载均衡设置","负载"),
    ("日志查看方法","日志"),
]

CATS = {"组织/权限": CASES[0:10], "系统/模块": CASES[10:20], "操作/流程": CASES[20:30],
        "对比/分析": CASES[30:40], "技术/配置": CASES[40:50]}

print(f"=== 伏羲 RAG 评测 v2.0: {len(CASES)} 条 ===\n")
passed = 0; total_latency = 0; cat_stats = {c: {"p":0,"t":len(v)} for c,v in CATS.items()}
cur_cat = ""; details = []

for i, (query, ek) in enumerate(CASES):
    for cat, cases in CATS.items():
        if (query, ek) in cases: cur_cat = cat; break
    t0 = time.time()
    try:
        r = requests.get(API, params={"q": query}, headers={"Authorization": f"Bearer {TOKEN}"}, timeout=15)
        latency = (time.time()-t0)*1000; total_latency += latency
        d = r.json(); res = d.get("results",[]); count = len(res)
        hit = False
        if res:
            top = " ".join([(sr.get("text","")+sr.get("file_name","")).lower() for sr in res[:3]])
            hit = ek.lower() in top
        if count > 0 and hit: passed += 1; cat_stats[cur_cat]["p"] += 1
        status = "✅" if hit else ("⚠️" if count > 0 else "❌")
        print(f"  {status} [{i+1:2d}] {query}: {count}条 {latency:.0f}ms")
        details.append({"q":query,"n":count,"hit":hit,"ms":round(latency)})
    except Exception as e:
        print(f"  ❌ [{i+1:2d}] {query}: {e}")
        details.append({"q":query,"n":0,"hit":False,"ms":0})

recall = passed/len(CASES)
print(f"\n{'='*50}\n📊 Recall@10: {recall:.1%} ({passed}/{len(CASES)})  延迟: {total_latency/len(CASES):.0f}ms\n")
for cat, s in cat_stats.items():
    cr = s["p"]/s["t"] if s["t"] else 0
    print(f"  {cat:8s} {'█'*int(cr*10)}{'░'*(10-int(cr*10))} {cr:.0%} ({s['p']}/{s['t']})")
print(f"\n{'✅ 达标' if recall >= 0.6 else '⚠️ 未达标'} (目标 > 60%)")
