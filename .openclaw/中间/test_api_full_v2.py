#!/usr/bin/env python3
"""
伏羲 v1.44 全量API端点测试脚本 - V2版本
包含完整的认证流程
"""
import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8081"
TOKEN = None
HEADERS = {}

# 测试结果存储
results = []

def log_result(name, method, url, status_code, response_data, passed, note=""):
    results.append({
        "name": name,
        "method": method,
        "url": url,
        "status_code": status_code,
        "response_summary": response_data[:200] if response_data else "N/A",
        "passed": passed,
        "note": note
    })
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} [{status_code}] {method} {url} - {note}")

def test_endpoint(name, method, url, expected_status=200, data=None, headers=None, use_token=False):
    """通用测试函数"""
    test_url = f"{BASE_URL}{url}"
    test_headers = headers or {}
    if use_token and TOKEN:
        test_headers["Authorization"] = f"Bearer {TOKEN}"
    
    try:
        if method == "GET":
            response = requests.get(test_url, headers=test_headers, timeout=10)
        elif method == "POST":
            response = requests.post(test_url, json=data, headers=test_headers, timeout=10)
        elif method == "PUT":
            response = requests.put(test_url, json=data, headers=test_headers, timeout=10)
        elif method == "DELETE":
            response = requests.delete(test_url, headers=test_headers, timeout=10)
        else:
            response = requests.request(method, test_url, json=data, headers=test_headers, timeout=10)
        
        try:
            resp_data = response.json()
            resp_summary = json.dumps(resp_data, ensure_ascii=False)
        except:
            resp_summary = response.text[:200]
        
        passed = response.status_code == expected_status
        note = f"期望 {expected_status}, 实际 {response.status_code}" if not passed else "成功"
        log_result(name, method, url, response.status_code, resp_summary, passed, note)
        return response, resp_data if 'resp_data' in dir() else None
    except Exception as e:
        log_result(name, method, url, 0, str(e), False, f"请求异常: {str(e)}")
        return None, None

# 等待服务器启动
print("等待服务器启动...")
time.sleep(5)
print("开始测试...\n")

# 1. GET /api/health
print("=" * 60)
print("1. GET /api/health")
test_endpoint("健康检查", "GET", "/api/health")

# 2. POST /api/auth/register (有效输入)
print("\n" + "=" * 60)
print("2. POST /api/auth/register (有效输入)")
test_endpoint("注册-有效输入", "POST", "/api/auth/register", 
    data={"username": "testuser", "password": "TestPass123", "email": "test@example.com"})

# 3. POST /api/auth/register (无效输入)
print("\n" + "=" * 60)
print("3. POST /api/auth/register (无效输入)")
test_endpoint("注册-无效输入", "POST", "/api/auth/register", 
    data={"username": "", "password": "", "email": ""}, expected_status=422)

# 4. POST /api/auth/login (有效输入)
print("\n" + "=" * 60)
print("4. POST /api/auth/login (有效输入)")
response, data = test_endpoint("登录-有效输入", "POST", "/api/auth/login", 
    data={"username": "testuser", "password": "TestPass123"})
if response and response.status_code == 200:
    try:
        resp_json = response.json()
        if "access_token" in resp_json:
            TOKEN = resp_json["access_token"]
            print(f"获取到Token: {TOKEN[:20]}...")
    except:
        pass

# 5. POST /api/auth/login (无效输入)
print("\n" + "=" * 60)
print("5. POST /api/auth/login (无效输入)")
test_endpoint("登录-无效密码", "POST", "/api/auth/login", 
    data={"username": "testuser", "password": "wrongpassword"}, expected_status=401)

# 6. GET /api/auth/me
print("\n" + "=" * 60)
print("6. GET /api/auth/me")
test_endpoint("当前用户信息", "GET", "/api/auth/me", use_token=True)

# 7. POST /api/auth/refresh
print("\n" + "=" * 60)
print("7. POST /api/auth/refresh")
test_endpoint("刷新Token", "POST", "/api/auth/refresh", use_token=True)

# 8. GET /api/search?q=test
print("\n" + "=" * 60)
print("8. GET /api/search?q=test")
test_endpoint("搜索", "GET", "/api/search?q=test", use_token=True)

# 9. POST /api/rag/search
print("\n" + "=" * 60)
print("9. POST /api/rag/search")
test_endpoint("RAG搜索", "POST", "/api/rag/search", 
    data={"query": "测试查询", "top_k": 5}, use_token=True)

# 10. GET /api/documents
print("\n" + "=" * 60)
print("10. GET /api/documents")
test_endpoint("文档列表", "GET", "/api/documents", use_token=True)

# 11. GET /api/documents/{hash}
print("\n" + "=" * 60)
print("11. GET /api/documents/{hash}")
test_endpoint("文档详情", "GET", "/api/documents/test_hash_123", use_token=True)

# 12. DELETE /api/documents/{hash}
print("\n" + "=" * 60)
print("12. DELETE /api/documents/{hash}")
test_endpoint("删除文档", "DELETE", "/api/documents/test_hash_123", use_token=True)

# 13. GET /api/wiki
print("\n" + "=" * 60)
print("13. GET /api/wiki")
test_endpoint("Wiki列表", "GET", "/api/wiki", use_token=True)

# 14. GET /api/wiki/{id}
print("\n" + "=" * 60)
print("14. GET /api/wiki/{id}")
test_endpoint("Wiki详情", "GET", "/api/wiki/1", use_token=True)

# 15. GET /api/graph
print("\n" + "=" * 60)
print("15. GET /api/graph")
test_endpoint("知识图谱", "GET", "/api/graph", use_token=True)

# 16. GET /api/chat/sessions
print("\n" + "=" * 60)
print("16. GET /api/chat/sessions")
test_endpoint("聊天会话列表", "GET", "/api/chat/sessions", use_token=True)

# 17. POST /api/chat/send
print("\n" + "=" * 60)
print("17. POST /api/chat/send")
test_endpoint("发送聊天消息", "POST", "/api/chat/send", 
    data={"message": "测试消息", "session_id": "test_session"}, use_token=True)

# 18. GET /api/evaluation/overview
print("\n" + "=" * 60)
print("18. GET /api/evaluation/overview")
test_endpoint("评估概览", "GET", "/api/evaluation/overview", use_token=True)

# 19. GET /api/feature-flags
print("\n" + "=" * 60)
print("19. GET /api/feature-flags")
test_endpoint("功能开关列表", "GET", "/api/feature-flags", use_token=True)

# 20. PUT /api/feature-flags/{name}
print("\n" + "=" * 60)
print("20. PUT /api/feature-flags/{name}")
test_endpoint("更新功能开关", "PUT", "/api/feature-flags/test_flag", 
    data={"enabled": True}, use_token=True)

# 21. GET /api/admin/metrics-summary
print("\n" + "=" * 60)
print("21. GET /api/admin/metrics-summary")
test_endpoint("管理员指标摘要", "GET", "/api/admin/metrics-summary", use_token=True)

# 22. GET /api/services
print("\n" + "=" * 60)
print("22. GET /api/services")
test_endpoint("服务列表", "GET", "/api/services", use_token=True)

# 23. GET /api/services/{id}
print("\n" + "=" * 60)
print("23. GET /api/services/{id}")
test_endpoint("服务详情", "GET", "/api/services/1", use_token=True)

# 24. GET /api/dashboard/stats
print("\n" + "=" * 60)
print("24. GET /api/dashboard/stats")
test_endpoint("仪表盘统计", "GET", "/api/dashboard/stats", use_token=True)

# 25. GET /api/metadata
print("\n" + "=" * 60)
print("25. GET /api/metadata")
test_endpoint("元数据", "GET", "/api/metadata", use_token=True)

# 26. GET /api/worldtree
print("\n" + "=" * 60)
print("26. GET /api/worldtree")
test_endpoint("世界树", "GET", "/api/worldtree", use_token=True)

# 27. GET /api/synthesis
print("\n" + "=" * 60)
print("27. GET /api/synthesis")
test_endpoint("合成", "GET", "/api/synthesis", use_token=True)

# 28. GET /api/proxy/loader/files
print("\n" + "=" * 60)
print("28. GET /api/proxy/loader/files")
test_endpoint("代理加载文件", "GET", "/api/proxy/loader/files", use_token=True)

# 29. GET /api/antenna/search?q=test
print("\n" + "=" * 60)
print("29. GET /api/antenna/search?q=test")
test_endpoint("天线搜索", "GET", "/api/antenna/search?q=test", use_token=True)

# 汇总统计
print("\n" + "=" * 60)
print("测试汇总")
print("=" * 60)

total = len(results)
passed = sum(1 for r in results if r["passed"])
failed = sum(1 for r in results if not r["passed"])

print(f"总测试数: {total}")
print(f"通过数: {passed}")
print(f"失败数: {failed}")
print(f"通过率: {passed/total*100:.1f}%")

# 失败端点清单
if failed > 0:
    print("\n失败端点清单:")
    for r in results:
        if not r["passed"]:
            print(f"- {r['method']} {r['url']}: {r['note']} (状态码: {r['status_code']})")

# 生成Markdown报告
report = f"""# 伏羲 v1.44 全量API测试报告

**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**测试环境**: {BASE_URL}

## 测试汇总

| 指标 | 数值 |
|------|------|
| 总测试数 | {total} |
| 通过数 | {passed} |
| 失败数 | {failed} |
| 通过率 | {passed/total*100:.1f}% |

## 详细测试结果

| 序号 | 端点名称 | 方法 | URL | 状态码 | 结果 | 说明 |
|------|----------|------|-----|--------|------|------|
"""

for i, r in enumerate(results, 1):
    status = "✅" if r["passed"] else "❌"
    report += f"| {i} | {r['name']} | {r['method']} | {r['url']} | {r['status_code']} | {status} | {r['note']} |\n"

if failed > 0:
    report += f"""
## 失败端点清单

| 序号 | 端点 | 失败原因 |
|------|------|----------|
"""
    for i, r in enumerate([r for r in results if not r["passed"]], 1):
        report += f"| {i} | {r['method']} {r['url']} | {r['note']} |\n"

report += f"""
## 响应摘要

"""
for r in results:
    report += f"### {r['name']} ({r['method']} {r['url']})\n"
    report += f"- **状态码**: {r['status_code']}\n"
    report += f"- **结果**: {'通过' if r['passed'] else '失败'}\n"
    report += f"- **响应摘要**: `{r['response_summary']}`\n\n"

# 保存报告
report_path = "E:\\easyclaw\\伏羲-v1.44\\repo\\.openclaw\\交付\\全量API测试-详细报告.md"
with open(report_path, "w", encoding="utf-8") as f:
    f.write(report)

print(f"\n报告已保存到: {report_path}")
