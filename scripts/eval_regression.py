"""eval_regression.py — 评测回归测试 v2.0
对比当前版本与基线，检测退化
"""
import json, time, sys, os, requests
from pathlib import Path
from datetime import datetime

API = os.getenv("FUXI_API_URL", "http://localhost:8080/api/search")
TOKEN = os.getenv("FUXI_API_TOKEN", "")
BASELINE_PATH = Path(os.getenv("FUXI_DATA_DIR", "data")) / "eval_baseline.json"
RESULTS_DIR = Path(os.getenv("FUXI_DATA_DIR", "data")) / "eval_results"

# 50 条评测集
CASES = [
    # 组织/权限 (10)
    ("权限管理","组织"),("如何创建部门","部门"),("流程引擎功能","流程"),
    ("证照管理操作","证照"),("组织架构管理","组织"),("岗位设置","岗位"),
    ("密码复杂度设置","密码"),("分部管理","分部"),("人员卡片字段","人员"),
    ("用户权限分配","权限"),
    # 系统/模块 (10)
    ("移动引擎是什么","移动"),("门户引擎配置","门户"),("SAP集成设置","SAP"),
    ("资产管理模块","资产"),("项目管理使用","项目"),("预算管理位置","预算"),
    ("公文管理流程","公文"),("报表导出方法","报表"),("系统参数设置","系统参数"),
    ("日程管理功能","日程"),
    # 操作/流程 (10)
    ("创建审批流程","流程"),("配置表单字段","表单"),("添加用户权限","权限"),
    ("设置流程路径","流程"),("导出报表数据","报表"),("流程审批失败","流程"),
    ("权限不足原因","权限"),("无法登录系统","登录"),("流程卡住原因","流程"),
    ("报表数据不对","报表"),
    # 对比/分析 (10)
    ("权限证照区别","权限"),("门户移动区别","门户"),("项目预算关系","项目"),
    ("系统有哪些模块","模块"),("支持文件格式","上传"),("OA和ERP区别","OA"),
    ("流程和表单关系","流程"),("门户和移动对比","门户"),("权限角色区别","权限"),
    ("报表和查询区别","报表"),
    # 技术/配置 (10)
    ("VLAN配置方法","VLAN"),("IP地址规划","IP"),("网络拓扑设计","网络"),
    ("数据库备份策略","备份"),("系统监控配置","监控"),("接口对接文档","接口"),
    ("单点登录配置","单点"),("SSL证书配置","SSL"),("负载均衡设置","负载"),
    ("日志查看方法","日志"),
]


def run_evaluation():
    results = []
    for query, expected_keyword in CASES:
        t0 = time.time()
        try:
            r = requests.get(API, params={"q": query},
                           headers={"Authorization": f"Bearer {TOKEN}"},
                           timeout=15)
            latency = (time.time() - t0) * 1000
            d = r.json()
            search_results = d.get("results", [])
            hit = False
            if search_results:
                top_text = " ".join([(sr.get("text","")+sr.get("file_name","")).lower() for sr in search_results[:3]])
                hit = expected_keyword.lower() in top_text
            rank = 0
            for i, sr in enumerate(search_results[:10]):
                if expected_keyword.lower() in (sr.get("text","")+sr.get("file_name","")).lower():
                    rank = i + 1; break
            results.append({"query": query, "hit": hit, "mrr": 1.0/rank if rank else 0,
                          "latency_ms": round(latency), "count": len(search_results)})
        except Exception:
            results.append({"query": query, "hit": False, "mrr": 0, "latency_ms": 0, "count": 0})
    return results


def main():
    print("=" * 50)
    print("伏羲 RAG 评测回归测试 v2.0")
    print("=" * 50)
    results = run_evaluation()
    n = len(results)
    recall = sum(1 for r in results if r["hit"]) / n
    mrr = sum(r["mrr"] for r in results) / n
    avg_latency = sum(r["latency_ms"] for r in results) / n
    report = {"timestamp": datetime.now().isoformat(), "total": n,
              "recall_at_10": round(recall, 4), "mrr": round(mrr, 4), "avg_latency_ms": round(avg_latency)}

    baseline = None
    if BASELINE_PATH.exists():
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        report["diff"] = {
            "recall": round(recall - baseline.get("recall_at_10", 0), 4),
            "mrr": round(mrr - baseline.get("mrr", 0), 4),
        }

    print(f"\n📊 Recall@10: {recall:.1%}  MRR: {mrr:.3f}  延迟: {avg_latency:.0f}ms")
    if report.get("diff"):
        for metric, delta in report["diff"].items():
            print(f"  {metric}: {'↑' if delta>0 else '↓'} {abs(delta):.1%}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    (RESULTS_DIR / f"eval_{ts}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not baseline or recall >= baseline.get("recall_at_10", 0):
        BASELINE_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("✅ 已更新基线")
    if report.get("diff"):
        for delta in report["diff"].values():
            if delta < -0.05:
                print("❌ 检测到退化！"); sys.exit(1)
    print("✅ 评测通过")


if __name__ == "__main__":
    main()
