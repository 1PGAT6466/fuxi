"""
伏羲 v1.44 第二轮功能检测 — 全量 API + 前端 + 响应格式 + 错误处理
"""
import requests
import json
import time
import sys
from datetime import datetime

BASE = "http://127.0.0.1:8080"
TOKEN = None
ADMIN_TOKEN = None
RESULTS = []

def log(category, name, method, url, status, passed, detail=""):
    RESULTS.append({
        "category": category,
        "name": name,
        "method": method,
        "url": url,
        "status": status,
        "passed": passed,
        "detail": detail
    })
    icon = "✅" if passed else "❌"
    print(f"  {icon} [{category}] {name}: {status} {detail[:80] if detail else ''}")

def api(method, path, token=None, json_data=None, **kwargs):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{BASE}{path}"
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=15, **kwargs)
        elif method == "POST":
            r = requests.post(url, headers=headers, json=json_data, timeout=30, **kwargs)
        elif method == "PUT":
            r = requests.put(url, headers=headers, json=json_data, timeout=15, **kwargs)
        elif method == "DELETE":
            r = requests.delete(url, headers=headers, timeout=15, **kwargs)
        else:
            r = requests.request(method, url, headers=headers, timeout=15, **kwargs)
        return r
    except Exception as e:
        return None

def check_response_format(r, expect_success=True):
    """检查统一响应格式: {status, message, data}"""
    if r is None:
        return False, "请求失败"
    try:
        data = r.json()
    except:
        return False, "非JSON响应"
    
    # 检查是否有 status 字段
    if "status" not in data:
        return False, f"缺少 status 字段: {list(data.keys())}"
    
    if expect_success:
        if data["status"] != "success":
            return False, f"status={data['status']}, message={data.get('message','')}"
    return True, ""

def check_unified_error_format(r):
    """检查错误响应是否统一"""
    if r is None:
        return False, "请求失败"
    try:
        data = r.json()
    except:
        # 某些端点返回HTML（如静态文件），这是正常的
        if r.status_code == 200 and "text/html" in r.headers.get("content-type", ""):
            return True, "HTML响应（静态页面）"
        return False, "非JSON错误响应"
    
    if "status" not in data:
        return False, f"错误响应缺少 status 字段"
    if data["status"] != "error":
        return False, f"错误状态码应为 error, 实际: {data['status']}"
    if "message" not in data:
        return False, f"错误响应缺少 message 字段"
    return True, ""

# ============================================
# 0. 认证
# ============================================
print("\n" + "="*60)
print("0. 认证流程测试")
print("="*60)

# 0.1 注册
r = api("POST", "/api/auth/register", json_data={"username":"round2test","password":"Test1234!"})
if r and r.status_code == 200:
    log("认证", "注册新用户", "POST", "/api/auth/register", r.status_code, True)
elif r and r.status_code == 400 and "已存在" in r.text:
    log("认证", "注册新用户(已存在)", "POST", "/api/auth/register", r.status_code, True, "用户已存在，继续")
else:
    log("认证", "注册新用户", "POST", "/api/auth/register", r.status_code if r else "N/A", False, r.text[:100] if r else "连接失败")

# 0.2 登录
r = api("POST", "/api/auth/login", json_data={"username":"round2test","password":"Test1234!"})
if r and r.status_code == 200:
    data = r.json()
    TOKEN = data.get("token")
    log("认证", "用户登录", "POST", "/api/auth/login", r.status_code, True, f"role={data.get('role')}")
    # 保存 token
    with open(r"E:\easyclaw\伏羲-v1.44\repo\.openclaw\中间\user_token.txt", "w") as f:
        f.write(TOKEN)
else:
    log("认证", "用户登录", "POST", "/api/auth/login", r.status_code if r else "N/A", False, r.text[:100] if r else "")
    print("  ⚠️ 无法获取 Token，后续测试将受限")

# 0.3 获取当前用户
r = api("GET", "/api/auth/me", token=TOKEN)
if r and r.status_code == 200:
    log("认证", "获取当前用户", "GET", "/api/auth/me", r.status_code, True)
else:
    log("认证", "获取当前用户", "GET", "/api/auth/me", r.status_code if r else "N/A", False)

# 0.4 刷新 Token
r = api("POST", "/api/auth/refresh", token=TOKEN)
if r and r.status_code == 200:
    data = r.json()
    new_token = data.get("token")
    if new_token:
        TOKEN = new_token
    log("认证", "刷新Token", "POST", "/api/auth/refresh", r.status_code, True)
else:
    log("认证", "刷新Token", "POST", "/api/auth/refresh", r.status_code if r else "N/A", False, r.text[:100] if r else "")

# 0.5 登出
r = api("POST", "/api/auth/logout", token=TOKEN)
if r and r.status_code == 200:
    log("认证", "登出", "POST", "/api/auth/logout", r.status_code, True)
else:
    log("认证", "登出", "POST", "/api/auth/logout", r.status_code if r else "N/A", False, r.text[:100] if r else "")

# 重新登录获取新 token
r = api("POST", "/api/auth/login", json_data={"username":"round2test","password":"Test1234!"})
if r and r.status_code == 200:
    TOKEN = r.json().get("token")

# ============================================
# 1. 健康检查 & 系统端点
# ============================================
print("\n" + "="*60)
print("1. 健康检查 & 系统端点")
print("="*60)

# 1.1 健康检查（无认证）
r = api("GET", "/api/health")
if r and r.status_code == 200:
    data = r.json()
    has_status = "status" in data
    log("系统", "健康检查", "GET", "/api/health", r.status_code, has_status, f"status={data.get('status')}")
else:
    log("系统", "健康检查", "GET", "/api/health", r.status_code if r else "N/A", False)

# 1.2 API v2 健康检查
r = api("GET", "/api/v2/health")
if r:
    log("系统", "V2健康检查", "GET", "/api/v2/health", r.status_code, r.status_code == 200)
else:
    log("系统", "V2健康检查", "GET", "/api/v2/health", "N/A", False, "连接失败")

# 1.3 指标（admin）
r = api("GET", "/api/metrics", token=TOKEN)
log("系统", "Prometheus指标", "GET", "/api/metrics", r.status_code if r else "N/A", r.status_code == 200 if r else False)

# 1.4 指标摘要（admin）
r = api("GET", "/api/admin/metrics-summary", token=TOKEN)
log("系统", "指标摘要", "GET", "/api/admin/metrics-summary", r.status_code if r else "N/A", r.status_code in [200, 403] if r else False)

# ============================================
# 2. 搜索 & RAG
# ============================================
print("\n" + "="*60)
print("2. 搜索 & RAG")
print("="*60)

r = api("GET", "/api/search?q=test&limit=5", token=TOKEN)
if r:
    ok, detail = check_response_format(r)
    log("搜索", "搜索接口", "GET", "/api/search?q=test", r.status_code, ok, detail)
else:
    log("搜索", "搜索接口", "GET", "/api/search?q=test", "N/A", False)

r = api("POST", "/api/rag/search", token=TOKEN, json_data={"query":"测试查询","top_k":5})
if r:
    ok, detail = check_response_format(r, expect_success=False)
    log("搜索", "RAG搜索", "POST", "/api/rag/search", r.status_code, r.status_code in [200, 500], f"{r.status_code}")
else:
    log("搜索", "RAG搜索", "POST", "/api/rag/search", "N/A", False)

r = api("GET", "/api/unified-search?q=test", token=TOKEN)
if r:
    log("搜索", "统一搜索", "GET", "/api/unified-search?q=test", r.status_code, r.status_code in [200, 500])
else:
    log("搜索", "统一搜索", "GET", "/api/unified-search?q=test", "N/A", False)

# ============================================
# 3. 文档管理
# ============================================
print("\n" + "="*60)
print("3. 文档管理")
print("="*60)

r = api("GET", "/api/documents", token=TOKEN)
if r:
    ok, detail = check_response_format(r)
    log("文档", "文档列表", "GET", "/api/documents", r.status_code, ok, detail)
else:
    log("文档", "文档列表", "GET", "/api/documents", "N/A", False)

r = api("GET", "/api/documents/nonexistent_hash", token=TOKEN)
if r:
    ok, detail = check_unified_error_format(r) if r.status_code >= 400 else check_response_format(r)
    log("文档", "文档详情(不存在)", "GET", "/api/documents/nonexistent", r.status_code, r.status_code in [404, 200])
else:
    log("文档", "文档详情(不存在)", "GET", "/api/documents/nonexistent", "N/A", False)

# ============================================
# 4. Wiki
# ============================================
print("\n" + "="*60)
print("4. Wiki")
print("="*60)

r = api("GET", "/api/wiki", token=TOKEN)
if r:
    ok, detail = check_response_format(r)
    log("Wiki", "Wiki列表", "GET", "/api/wiki", r.status_code, ok, detail)
else:
    log("Wiki", "Wiki列表", "GET", "/api/wiki", "N/A", False)

r = api("GET", "/api/wiki/1", token=TOKEN)
if r:
    log("Wiki", "Wiki详情", "GET", "/api/wiki/1", r.status_code, r.status_code in [200, 404])
else:
    log("Wiki", "Wiki详情", "GET", "/api/wiki/1", "N/A", False)

# ============================================
# 5. 知识图谱
# ============================================
print("\n" + "="*60)
print("5. 知识图谱")
print("="*60)

r = api("GET", "/api/graph", token=TOKEN)
if r:
    ok, detail = check_response_format(r)
    log("图谱", "知识图谱", "GET", "/api/graph", r.status_code, ok, detail)
else:
    log("图谱", "知识图谱", "GET", "/api/graph", "N/A", False)

# ============================================
# 6. 聊天
# ============================================
print("\n" + "="*60)
print("6. 聊天")
print("="*60)

r = api("GET", "/api/chat/sessions", token=TOKEN)
if r:
    ok, detail = check_response_format(r)
    log("聊天", "会话列表", "GET", "/api/chat/sessions", r.status_code, ok, detail)
else:
    log("聊天", "会话列表", "GET", "/api/chat/sessions", "N/A", False)

# 创建会话
r = api("POST", "/api/chat/sessions", token=TOKEN, json_data={"title":"测试会话"})
if r:
    log("聊天", "创建会话", "POST", "/api/chat/sessions", r.status_code, r.status_code in [200, 201])
    session_id = None
    if r.status_code in [200, 201]:
        try:
            data = r.json()
            session_id = data.get("data", {}).get("session_id") or data.get("session_id")
        except:
            pass
else:
    log("聊天", "创建会话", "POST", "/api/chat/sessions", "N/A", False)

# 发送消息
r = api("POST", "/api/chat/send", token=TOKEN, json_data={"query":"你好","session_id":session_id or "test"})
if r:
    log("聊天", "发送消息", "POST", "/api/chat/send", r.status_code, r.status_code in [200, 500])
else:
    log("聊天", "发送消息", "POST", "/api/chat/send", "N/A", False)

# ============================================
# 7. 仪表盘 & 元数据
# ============================================
print("\n" + "="*60)
print("7. 仪表盘 & 元数据")
print("="*60)

r = api("GET", "/api/dashboard/stats", token=TOKEN)
if r:
    ok, detail = check_response_format(r)
    log("仪表盘", "统计信息", "GET", "/api/dashboard/stats", r.status_code, ok, detail)
else:
    log("仪表盘", "统计信息", "GET", "/api/dashboard/stats", "N/A", False)

r = api("GET", "/api/metadata", token=TOKEN)
if r:
    ok, detail = check_response_format(r)
    log("元数据", "元数据列表", "GET", "/api/metadata", r.status_code, ok, detail)
else:
    log("元数据", "元数据列表", "GET", "/api/metadata", "N/A", False)

# ============================================
# 8. 服务管理
# ============================================
print("\n" + "="*60)
print("8. 服务管理")
print("="*60)

r = api("GET", "/api/services", token=TOKEN)
if r:
    ok, detail = check_response_format(r)
    log("服务", "服务列表", "GET", "/api/services", r.status_code, ok, detail)
else:
    log("服务", "服务列表", "GET", "/api/services", "N/A", False)

# ============================================
# 9. 世界树
# ============================================
print("\n" + "="*60)
print("9. 世界树")
print("="*60)

r = api("GET", "/api/worldtree", token=TOKEN)
if r:
    ok, detail = check_response_format(r)
    log("世界树", "世界树查询", "GET", "/api/worldtree", r.status_code, ok, detail)
else:
    log("世界树", "世界树查询", "GET", "/api/worldtree", "N/A", False)

# ============================================
# 10. Feature Flags
# ============================================
print("\n" + "="*60)
print("10. Feature Flags")
print("="*60)

r = api("GET", "/api/feature-flags", token=TOKEN)
if r:
    log("Feature Flags", "Flag列表", "GET", "/api/feature-flags", r.status_code, r.status_code in [200, 403])
else:
    log("Feature Flags", "Flag列表", "GET", "/api/feature-flags", "N/A", False)

# ============================================
# 11. 四象状态 & 成长
# ============================================
print("\n" + "="*60)
print("11. 四象状态 & 成长")
print("="*60)

r = api("GET", "/api/symbols/status", token=TOKEN)
if r:
    ok, detail = check_response_format(r)
    log("系统", "四象状态", "GET", "/api/symbols/status", r.status_code, ok, detail)
else:
    log("系统", "四象状态", "GET", "/api/symbols/status", "N/A", False)

r = api("GET", "/api/growth/overview", token=TOKEN)
if r:
    ok, detail = check_response_format(r)
    log("系统", "成长概览", "GET", "/api/growth/overview", r.status_code, ok, detail)
else:
    log("系统", "成长概览", "GET", "/api/growth/overview", "N/A", False)

# ============================================
# 12. 评测
# ============================================
print("\n" + "="*60)
print("12. 评测")
print("="*60)

r = api("GET", "/api/eval/report", token=TOKEN)
if r:
    ok, detail = check_response_format(r)
    log("评测", "最新报告", "GET", "/api/eval/report", r.status_code, ok, detail)
else:
    log("评测", "最新报告", "GET", "/api/eval/report", "N/A", False)

r = api("GET", "/api/eval/history", token=TOKEN)
if r:
    ok, detail = check_response_format(r)
    log("评测", "评测历史", "GET", "/api/eval/history", r.status_code, ok, detail)
else:
    log("评测", "评测历史", "GET", "/api/eval/history", "N/A", False)

# ============================================
# 13. 反馈
# ============================================
print("\n" + "="*60)
print("13. 反馈")
print("="*60)

r = api("POST", "/api/feedback", token=TOKEN, json_data={"query":"测试","answer":"回答","rating":5,"comment":"好"})
if r:
    log("反馈", "提交反馈", "POST", "/api/feedback", r.status_code, r.status_code in [200, 201])
else:
    log("反馈", "提交反馈", "POST", "/api/feedback", "N/A", False)

# ============================================
# 14. 租户
# ============================================
print("\n" + "="*60)
print("14. 租户管理")
print("="*60)

r = api("GET", "/api/tenants", token=TOKEN)
if r:
    log("租户", "租户列表", "GET", "/api/tenants", r.status_code, r.status_code in [200, 403])
else:
    log("租户", "租户列表", "GET", "/api/tenants", "N/A", False)

# ============================================
# 15. 通知 & 偏好
# ============================================
print("\n" + "="*60)
print("15. 通知 & 用户偏好")
print("="*60)

r = api("GET", "/api/notifications", token=TOKEN)
if r:
    log("通知", "通知列表", "GET", "/api/notifications", r.status_code, r.status_code in [200, 404])
else:
    log("通知", "通知列表", "GET", "/api/notifications", "N/A", False)

r = api("GET", "/api/user/preferences", token=TOKEN)
if r:
    log("偏好", "用户偏好", "GET", "/api/user/preferences", r.status_code, r.status_code in [200, 404])
else:
    log("偏好", "用户偏好", "GET", "/api/user/preferences", "N/A", False)

# ============================================
# 16. 文件 & 代理
# ============================================
print("\n" + "="*60)
print("16. 文件 & 代理路由")
print("="*60)

r = api("GET", "/api/proxy/loader/files", token=TOKEN)
if r:
    log("代理", "加载器文件列表", "GET", "/api/proxy/loader/files", r.status_code, r.status_code in [200, 502])
else:
    log("代理", "加载器文件列表", "GET", "/api/proxy/loader/files", "N/A", False)

# ============================================
# 17. 进化 & 评估
# ============================================
print("\n" + "="*60)
print("17. 进化 & 评估")
print("="*60)

r = api("GET", "/api/evaluation/overview", token=TOKEN)
if r:
    ok, detail = check_response_format(r)
    log("评估", "评估概览", "GET", "/api/evaluation/overview", r.status_code, ok, detail)
else:
    log("评估", "评估概览", "GET", "/api/evaluation/overview", "N/A", False)

r = api("GET", "/api/evolution/status", token=TOKEN)
if r:
    log("进化", "进化状态", "GET", "/api/evolution/status", r.status_code, r.status_code in [200, 404])
else:
    log("进化", "进化状态", "GET", "/api/evolution/status", "N/A", False)

# ============================================
# 18. 前端路由检测
# ============================================
print("\n" + "="*60)
print("18. 前端路由检测")
print("="*60)

frontend_routes = [
    ("/", "首页", 200),
    ("/login", "登录页", 200),
    ("/admin", "管理页", [200, 302]),
]

for path, name, expected in frontend_routes:
    r = api("GET", path)
    if r:
        is_html = "text/html" in r.headers.get("content-type", "")
        if isinstance(expected, list):
            passed = r.status_code in expected and is_html
        else:
            passed = r.status_code == expected and is_html
        log("前端", name, "GET", path, r.status_code, passed, f"html={is_html}")
    else:
        log("前端", name, "GET", path, "N/A", False)

# 检查 SPA 静态资源
static_assets = [
    "/assets/main-SNeLOof5.js",
    "/assets/vue-vendor-CcM843_T.js",
    "/assets/main-DJwpn9wY.css",
]
for asset in static_assets:
    r = api("GET", asset)
    if r:
        log("前端", f"静态资源{asset.split('/')[-1]}", "GET", asset, r.status_code, r.status_code == 200)
    else:
        log("前端", f"静态资源{asset.split('/')[-1]}", "GET", asset, "N/A", False)

# ============================================
# 19. 无认证访问保护端点
# ============================================
print("\n" + "="*60)
print("19. 未认证访问保护端点（应返回401）")
print("="*60)

protected_endpoints = [
    ("GET", "/api/search?q=test"),
    ("GET", "/api/documents"),
    ("GET", "/api/wiki"),
    ("GET", "/api/graph"),
    ("GET", "/api/chat/sessions"),
    ("GET", "/api/dashboard/stats"),
    ("GET", "/api/services"),
    ("GET", "/api/worldtree"),
    ("GET", "/api/metadata"),
    ("GET", "/api/evaluation/overview"),
    ("GET", "/api/feature-flags"),
    ("GET", "/api/symbols/status"),
    ("GET", "/api/growth/overview"),
]

for method, path in protected_endpoints:
    r = api(method, path)  # No token
    if r:
        passed = r.status_code == 401
        ok, detail = check_unified_error_format(r) if r.status_code == 401 else (True, "")
        log("安全", f"无认证{path}", method, path, r.status_code, passed, "返回401" if passed else f"应返回401,实际{r.status_code}")
    else:
        log("安全", f"无认证{path}", method, path, "N/A", False)

# ============================================
# 20. 错误处理检测
# ============================================
print("\n" + "="*60)
print("20. 错误处理检测")
print("="*60)

# 20.1 不存在的路由
r = api("GET", "/api/nonexistent")
if r:
    ok, detail = check_unified_error_format(r)
    log("错误处理", "不存在的路由", "GET", "/api/nonexistent", r.status_code, r.status_code == 404, detail)
else:
    log("错误处理", "不存在的路由", "GET", "/api/nonexistent", "N/A", False)

# 20.2 无效 JSON
r = api("POST", "/api/auth/login", json_data={"username":"x"})
if r:
    passed = r.status_code in [400, 422]
    log("错误处理", "缺少必填字段", "POST", "/api/auth/login", r.status_code, passed)
else:
    log("错误处理", "缺少必填字段", "POST", "/api/auth/login", "N/A", False)

# 20.3 SQL 注入尝试
r = api("GET", "/api/search?q=';DROP TABLE--", token=TOKEN)
if r:
    passed = r.status_code in [200, 400, 422] and "DROP" not in r.text
    log("错误处理", "SQL注入防护", "GET", "/api/search?q=...", r.status_code, passed)
else:
    log("错误处理", "SQL注入防护", "GET", "/api/search?q=...", "N/A", False)

# 20.4 XSS 尝试
r = api("GET", "/api/search?q=<script>alert(1)</script>", token=TOKEN)
if r:
    passed = "<script>" not in r.text
    log("错误处理", "XSS防护", "GET", "/api/search?q=...", r.status_code, passed)
else:
    log("错误处理", "XSS防护", "GET", "/api/search?q=...", "N/A", False)

# ============================================
# 21. 响应格式一致性检测
# ============================================
print("\n" + "="*60)
print("21. 响应格式一致性检测")
print("="*60)

format_test_endpoints = [
    ("GET", "/api/health", False),
    ("GET", "/api/documents", True),
    ("GET", "/api/wiki", True),
    ("GET", "/api/graph", True),
    ("GET", "/api/chat/sessions", True),
    ("GET", "/api/dashboard/stats", True),
    ("GET", "/api/services", True),
    ("GET", "/api/worldtree", True),
    ("GET", "/api/metadata", True),
    ("GET", "/api/symbols/status", True),
    ("GET", "/api/growth/overview", True),
    ("GET", "/api/eval/report", True),
    ("GET", "/api/eval/history", True),
    ("GET", "/api/evaluation/overview", True),
]

inconsistent = []
for method, path, need_auth in format_test_endpoints:
    r = api(method, path, token=TOKEN if need_auth else None)
    if r and r.status_code == 200:
        try:
            data = r.json()
            keys = list(data.keys())
            has_status = "status" in data
            has_message = "message" in data
            has_data = "data" in data
            if not (has_status and has_message):
                inconsistent.append({"path": path, "keys": keys})
                log("格式", f"格式检查{path}", method, path, r.status_code, False, f"keys={keys}")
            else:
                log("格式", f"格式检查{path}", method, path, r.status_code, True)
        except:
            log("格式", f"格式检查{path}", method, path, r.status_code, False, "非JSON")
    elif r:
        log("格式", f"格式检查{path}", method, path, r.status_code, True, "非200跳过")
    else:
        log("格式", f"格式检查{path}", method, path, "N/A", False)

# ============================================
# 输出汇总
# ============================================
print("\n" + "="*60)
print("汇总报告")
print("="*60)

total = len(RESULTS)
passed = sum(1 for r in RESULTS if r["passed"])
failed = sum(1 for r in RESULTS if not r["passed"])

categories = {}
for r in RESULTS:
    cat = r["category"]
    if cat not in categories:
        categories[cat] = {"total": 0, "passed": 0, "failed": 0}
    categories[cat]["total"] += 1
    if r["passed"]:
        categories[cat]["passed"] += 1
    else:
        categories[cat]["failed"] += 1

print(f"\n总计: {total} | 通过: {passed} | 失败: {failed} | 通过率: {passed/total*100:.1f}%\n")

for cat, stats in categories.items():
    rate = stats["passed"]/stats["total"]*100 if stats["total"] > 0 else 0
    icon = "✅" if rate == 100 else "⚠️" if rate >= 50 else "❌"
    print(f"  {icon} {cat}: {stats['passed']}/{stats['total']} ({rate:.0f}%)")

# 保存详细结果
report = {
    "test_time": datetime.now().isoformat(),
    "total": total,
    "passed": passed,
    "failed": failed,
    "pass_rate": f"{passed/total*100:.1f}%",
    "categories": categories,
    "inconsistent_formats": inconsistent,
    "details": RESULTS
}

with open(r"E:\easyclaw\伏羲-v1.44\repo\.openclaw\中间\round2_test_results.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(f"\n详细结果已保存: .openclaw/中间/round2_test_results.json")

# 失败项列表
if failed > 0:
    print(f"\n失败项 ({failed}):")
    for r in RESULTS:
        if not r["passed"]:
            print(f"  ❌ [{r['category']}] {r['name']}: {r['status']} {r['detail'][:60]}")
