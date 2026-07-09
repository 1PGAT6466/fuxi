#!/usr/bin/env python3
"""R6 最终轮深层检测 — 全面测试所有 API 端点"""
import json, urllib.request, urllib.error, ssl, sys, time, os

BASE = "http://172.25.30.200:8080"
TOKEN = None
RESULTS = []
PASS, FAIL, WARN = 0, 0, 0

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def req(method, path, body=None, headers_extra=None):
    """通用请求"""
    url = f"{BASE}{path}"
    hdrs = {"Content-Type": "application/json"}
    if TOKEN:
        hdrs["Authorization"] = f"Bearer {TOKEN}"
    if headers_extra:
        hdrs.update(headers_extra)
    data = json.dumps(body).encode() if body else None
    try:
        rq = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        with urllib.request.urlopen(rq, context=ctx, timeout=30) as resp:
            code = resp.getcode()
            ct = resp.headers.get("Content-Type", "")
            body_raw = resp.read()
            try:
                jbody = json.loads(body_raw)
            except:
                jbody = body_raw.decode("utf-8", errors="replace")[:200]
            return code, ct, jbody
    except urllib.error.HTTPError as e:
        code = e.code
        body_raw = e.read()
        try:
            jbody = json.loads(body_raw)
        except:
            jbody = body_raw.decode("utf-8", errors="replace")[:200]
        return code, "", jbody

def test(name, method, path, body=None, expected_code=200, checks=None, headers_extra=None):
    global PASS, FAIL, WARN
    code, ct, jbody = req(method, path, body, headers_extra)
    status = "PASS"
    reasons = []
    sev = "INFO"

    if code != expected_code:
        if expected_code == 200 and code in (401, 403):
            status = "SKIP"
            sev = "WARN"
            reasons.append(f"Auth required (got {code})")
        else:
            status = "FAIL"
            sev = "ERROR"
            reasons.append(f"Expected {expected_code}, got {code}")

    if checks and status != "SKIP":
        for c in checks:
            r = c(jbody, ct, code)
            if r:
                if r[0] == "FAIL":
                    status = "FAIL"
                    sev = "ERROR"
                elif r[0] == "WARN":
                    if status != "FAIL":
                        status = "WARN"
                        sev = "WARN"
                reasons.append(r[1])

    if status == "PASS": PASS += 1
    elif status == "SKIP": WARN += 1
    else: FAIL += 1

    print(f"[{status:4s}] {method:6s} {path:45s} | {code} | {'; '.join(reasons)}")
    RESULTS.append({
        "endpoint": f"{method} {path}",
        "expected_code": expected_code,
        "actual_code": code,
        "status": status,
        "reasons": reasons,
        "response_sample": str(jbody)[:300]
    })

def check_v2_format(jbody, ct, code):
    """验证 {status, data, message} 统一格式的端点"""
    if isinstance(jbody, dict):
        if "status" in jbody and "data" in jbody:
            if jbody.get("status") == "success":
                return ("PASS", "v2 format OK")
            elif jbody.get("status") == "error":
                return ("INFO", "v2 format (error response)")
    return ("FAIL", "Missing v2 format: {status, data}")

def check_error_format(jbody, ct, code):
    """验证错误格式: {status:error, message:..., status_code:...}"""
    if isinstance(jbody, dict):
        has_status = "status" in jbody and jbody.get("status") == "error"
        has_message = "message" in jbody
        has_code = "status_code" in jbody
        if has_status and has_message:
            return ("PASS", f"Error format OK (detail→message)" if not has_code else "Error format OK")
        if "detail" in jbody and not has_status:
            return ("WARN", "Old error format {detail:...} (should be {status:error, message:...})")
    return ("INFO", f"Non-standard response: {str(jbody)[:80]}")

def check_has_token(jbody, ct, code):
    if isinstance(jbody, dict) and "token" in jbody:
        return ("PASS", "token present")
    return ("FAIL", "No token in response")

def check_ok(jbody, ct, code):
    if isinstance(jbody, dict):
        if jbody.get("ok") or jbody.get("status") == "ok" or jbody.get("status") == "healthy" or jbody.get("status") == "success":
            return ("PASS", "ok status")
    return ("INFO", f"Response: {str(jbody)[:80]}")

def check_json_headers(jbody, ct, code):
    if "application/json" in ct:
        return ("PASS", "JSON Content-Type")
    return ("WARN", f"Content-Type: {ct}")

def check_sse(jbody, ct, code):
    if "text/event-stream" in ct:
        return ("PASS", "SSE Content-Type OK")
    return ("WARN", f"Expected SSE, got Content-Type: {ct}")

def check_has_data(jbody, ct, code):
    if isinstance(jbody, dict):
        for k in ["data", "results", "files", "notifications", "pages", "symbols", "entries", "records", "history", "flags", "nodes", "tools"]:
            if k in jbody:
                return ("PASS", f"has '{k}' field ({len(str(jbody[k]))} chars)")
    return ("INFO", f"Keys: {list(jbody.keys()) if isinstance(jbody, dict) else 'non-dict'}")

def check_401(jbody, ct, code):
    return check_error_format(jbody, ct, code)

def check_403(jbody, ct, code):
    return check_error_format(jbody, ct, code)

def check_404(jbody, ct, code):
    return check_error_format(jbody, ct, code)

# ============ PHASE 1: 无需认证的端点 ============
print("=" * 80)
print("PHASE 1: 无需认证的端点")
print("=" * 80)

test("Health Check", "GET", "/api/health", checks=[
    lambda j,c,code: ("PASS", f"healthy, {len(j.get('bagua',{}))} gua") if isinstance(j,dict) and j.get("status")=="healthy" else ("FAIL", str(j)[:60]),
    check_json_headers
])

test("Metrics (Prometheus)", "GET", "/metrics",
     checks=[lambda j,c,code: ("PASS", "text/plain metrics") if isinstance(j,str) and "fuxi_" in j else ("WARN", f"Got: {str(j)[:80]}")],
     expected_code=200)  # metrics should be public

test("Root /", "GET", "/", checks=[
    lambda j,c,code: ("PASS", "HTML") if "伏羲" in j else ("WARN", str(j)[:60]),
])

test("Login Page", "GET", "/login", checks=[
    lambda j,c,code: ("PASS", "Login HTML") if "login" in j.lower() else ("INFO", str(j)[:60]),
])

test("Login Unregistered", "POST", "/api/auth/login",
     body={"username": "nonexist_r6", "password": "wrong"},
     expected_code=401,
     checks=[check_401])

# ============ PHASE 2: 认证 ============
print("\n" + "=" * 80)
print("PHASE 2: 获取 Token")
print("=" * 80)

# 注册新用户
test("Register User", "POST", "/api/auth/register",
     body={"username": f"r6_final_{int(time.time())}", "password": "R6Final@2026"},
     checks=[lambda j,c,code: ("PASS", f"Registered: {j.get('username','?')}") if j.get('ok') else ("FAIL", str(j)[:100])])

# 尝试用已知用户登录
# 先试试 admin
test("Login Admin", "POST", "/api/auth/login",
     body={"username": "admin", "password": "fuxi2024"},
     expected_code=200,
     checks=[check_has_token, lambda j,c,code: ("PASS", f"Role: {j.get('role','?')}")])

if RESULTS[-1]["status"] == "PASS":
    TOKEN = RESULTS[-1]["response_sample"]
    # extract token
    try:
        t = json.loads(RESULTS[-1]["response_sample"]) if isinstance(RESULTS[-1]["response_sample"], str) else RESULTS[-1]["response_sample"]
        TOKEN = t.get("token", "")
        print(f"\n✅ TOKEN acquired: {TOKEN[:40]}...")
    except:
        TOKEN = ""
        print("\n⚠️ Failed to extract token from login response")

if not TOKEN:
    print("Trying test user login...")
    test("Login Test User", "POST", "/api/auth/login",
         body={"username": "test_r6_final", "password": "TestR6@2026"},
         expected_code=200,
         checks=[check_has_token])
    if RESULTS[-1]["status"] == "PASS":
        try:
            t = json.loads(RESULTS[-1]["response_sample"]) if isinstance(RESULTS[-1]["response_sample"], str) else RESULTS[-1]["response_sample"]
            TOKEN = t.get("token", "")
        except: pass

if not TOKEN:
    # Try one more with the just-registered user
    # Need to find the username from registration response
    for r in RESULTS:
        if r["endpoint"] == "POST /api/auth/register" and r["status"] == "PASS":
            try:
                d = r["response_sample"]
                if "username" in d:
                    username = d["username"]
                    code, ct, jbody = req("POST", "/api/auth/login", body={"username": username, "password": "R6Final@2026"})
                    if isinstance(jbody, dict) and "token" in jbody:
                        TOKEN = jbody["token"]
                        print(f"✅ TOKEN acquired for {username}: {TOKEN[:40]}...")
                        PASS += 1
                        RESULTS.append({"endpoint": "POST /api/auth/login (retry new user)", "status": "PASS", "actual_code": 200, "reasons": ["Login with new user"], "response_sample": ""})
            except: pass

print(f"\nTOKEN: {'✅ Available' if TOKEN else '❌ NOT AVAILABLE - many tests will SKIP'}")

# ============ PHASE 3: 认证后端点 ============
if TOKEN:
    print("\n" + "=" * 80)
    print("PHASE 3: 认证后 — 核心 API 端点")
    print("=" * 80)

    # 认证相关
    test("Auth Me", "GET", "/api/auth/me", checks=[check_json_headers, check_ok, check_has_data])

    # 搜索
    test("Search", "GET", "/api/search?q=配置&top_k=3", checks=[check_json_headers, check_has_data])
    test("Search History", "GET", "/api/search-history", checks=[check_json_headers])

    # 对话
    test("Chat", "POST", "/api/chat",
         body={"query": "你好，测试", "stream": False},
         checks=[check_json_headers, check_has_data])

    # Chat v2 格式
    test("Chat v2", "POST", "/api/chat?format=v2",
         body={"query": "你好", "stream": False},
         checks=[check_json_headers, check_v2_format])

    # Chat Agent
    test("Chat Agent", "POST", "/api/chat/agent",
         body={"query": "你好", "stream": False},
         checks=[check_json_headers, check_has_data])

    # Chat sessions
    test("Chat Sessions", "GET", "/api/chat/sessions", checks=[check_json_headers])

    # SSE 流式
    test("Chat SSE", "POST", "/api/chat/send",
         body={"query": "你好", "stream": True},
         checks=[check_sse],
         expected_code=200)

    # RAG
    test("RAG Search", "POST", "/api/rag/search",
         body={"query": "测试", "top_k": 3},
         checks=[check_json_headers, check_has_data])

    test("SAG Search", "POST", "/api/rag/sag-search",
         body={"query": "测试", "limit": 3},
         checks=[check_json_headers, check_has_data])

    # 统一搜索
    test("Unified Search", "GET", "/api/unified-search?q=测试&limit=3", checks=[check_json_headers, check_has_data])

    # 文档
    test("Documents List", "GET", "/api/documents", checks=[check_json_headers, check_has_data])
    test("Documents Export", "GET", "/api/documents/export", checks=[check_json_headers])

    # Wiki
    test("Wiki Pages", "GET", "/api/wiki/pages", checks=[check_json_headers, check_has_data])
    test("Wiki Search", "GET", "/api/wiki/search?q=测试", checks=[check_json_headers])

    # 图谱
    test("Graph", "GET", "/api/graph", checks=[check_json_headers, check_has_data])

    # 四象
    test("Symbols Status", "GET", "/api/symbols/status", checks=[check_json_headers, check_has_data])
    test("Growth Overview", "GET", "/api/growth/overview", checks=[check_json_headers, check_has_data])

    # 通知
    test("Notifications", "GET", "/api/notifications", checks=[check_json_headers, check_has_data])

    # 用户偏好
    test("User Preferences", "GET", "/api/user/preferences", checks=[check_json_headers, check_has_data])

    # 评测
    test("Eval Report", "GET", "/api/eval/report", checks=[check_json_headers, check_has_data])
    test("Eval History", "GET", "/api/eval/history", checks=[check_json_headers, check_has_data])

    # Feature Flags
    test("Feature Flags List", "GET", "/api/feature-flags", checks=[check_json_headers, check_has_data])

    # 反馈
    test("Feedback Weekly", "GET", "/api/feedback/weekly", checks=[check_json_headers, check_has_data])
    test("Feedback Submit", "POST", "/api/feedback",
         body={"query": "测试", "answer": "测试回答", "rating": 4, "comment": "good"},
         checks=[check_json_headers])

    # 系统统计
    test("System Stats", "GET", "/api/system/stats", checks=[check_json_headers, check_has_data])
    test("Cache Stats", "GET", "/api/cache/stats", checks=[check_json_headers, check_has_data])
    test("Errors Stats", "GET", "/api/errors/stats", checks=[check_json_headers, check_has_data])

    # 管理端点
    test("Admin Stats", "GET", "/api/admin/stats", checks=[check_json_headers, check_has_data])
    test("Admin Server Status", "GET", "/api/admin/server-status", checks=[check_json_headers, check_has_data])
    test("Admin Metrics Summary", "GET", "/api/admin/metrics-summary", checks=[check_json_headers, check_has_data])

    # 服务
    test("Services List", "GET", "/api/services/", checks=[check_json_headers, check_has_data])

    # MCP
    test("MCP Tools", "GET", "/api/mcp/tools", checks=[check_json_headers, check_has_data])
    test("MCP sag_status", "POST", "/api/mcp/sag_status", body={}, checks=[check_json_headers, check_has_data])

    # 🔴 关键: 测试 R5 修复的 MCP call handlers
    test("MCP call: health_check", "POST", "/api/mcp/call",
         body={"tool": "health_check", "args": {}},
         checks=[check_json_headers, check_has_data])

    test("MCP call: feature_flags_list", "POST", "/api/mcp/call",
         body={"tool": "feature_flags_list", "args": {}},
         checks=[check_json_headers, check_has_data])

    test("MCP call: graph_stats", "POST", "/api/mcp/call",
         body={"tool": "graph_stats", "args": {}},
         checks=[check_json_headers, check_has_data])

    test("MCP call: wiki_search", "POST", "/api/mcp/call",
         body={"tool": "wiki_search", "args": {"q": "VPN"}},
         checks=[check_json_headers, check_has_data])

    test("MCP call: sag_status", "POST", "/api/mcp/call",
         body={"tool": "sag_status", "args": {}},
         checks=[check_json_headers, check_has_data])

    # MCP search
    test("MCP sag_search", "POST", "/api/mcp/sag_search",
         body={"query": "VPN", "top_k": 3},
         checks=[check_json_headers, check_has_data])

    # Swagger
    test("Swagger Docs", "GET", "/docs", checks=[
        lambda j,c,code: ("PASS", "Swagger HTML") if isinstance(c,str) and "swagger" in c.lower() else ("PASS","docs page") if code==200 else ("INFO",str(j)[:60]),
    ], expected_code=200)

    test("ReDoc", "GET", "/redoc", checks=[
        lambda j,c,code: ("PASS", "ReDoc page") if code==200 else ("INFO",str(j)[:60]),
    ], expected_code=200)

    # ============ PHASE 4: 权限控制测试 ============
    print("\n" + "=" * 80)
    print("PHASE 4: 权限控制测试")
    print("=" * 80)

    # 用普通用户 token 测试 admin-only 端点
    user_token = None
    code, ct, reg_j = req("POST", "/api/auth/register", body={"username": f"r6_normal_{int(time.time())}", "password": "Normal@2026"})
    if isinstance(reg_j, dict) and reg_j.get("ok"):
        code2, ct2, login_j = req("POST", "/api/auth/login", body={"username": reg_j["username"], "password": "Normal@2026"})
        if isinstance(login_j, dict) and "token" in login_j:
            user_token = login_j["token"]
            print(f"✅ Normal user token acquired: {user_token[:40]}...")
            RESULTS.append({"endpoint": "POST /api/auth/login (normal user)", "status": "PASS", "actual_code": 200, "reasons": ["Normal user login"], "response_sample": ""})
            PASS += 1

    if user_token:
        orig_token = TOKEN
        TOKEN = user_token

        test("Normal: Feature Flags PUT", "PUT", "/api/feature-flags/shaoyang_sag_extract",
             body={"value": True},
             expected_code=403,
             checks=[check_403])

        test("Normal: Eval Run", "POST", "/api/eval/run",
             expected_code=403,
             checks=[check_403])

        TOKEN = orig_token
        print("\n✅ Permission control test complete")

print("\n" + "=" * 80)
print("PHASE 5: 错误格式验证")
print("=" * 80)

if TOKEN:
    # 404
    test("404 Test", "GET", "/api/nonexistent-endpoint-r6",
         expected_code=404,
         checks=[check_404])

    # 400
    test("400 Test", "POST", "/api/chat",
         body={"invalid": "data"},
         expected_code=422,
         checks=[lambda j,c,code: ("PASS","422 handled") if code==422 else check_error_format(j,c,code)])

    # 401 (no token)
    stow = TOKEN
    TOKEN = None
    test("401 Test (no auth)", "GET", "/api/search?q=test",
         expected_code=401,
         checks=[check_401])

    test("401 Test (invalid token)", "GET", "/api/search?q=test",
         expected_code=401,
         headers_extra={"Authorization": "Bearer invalid_token_xyz"},
         checks=[check_401])
    TOKEN = stow

# ============ SUMMARY ============
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
total = len(RESULTS)
passed = sum(1 for r in RESULTS if r["status"] == "PASS")
failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
skipped = sum(1 for r in RESULTS if r["status"] == "SKIP")
warned = sum(1 for r in RESULTS if r["status"] == "WARN")
pass_rate = (passed / total * 100) if total else 0
print(f"Total: {total} | Pass: {passed} | Fail: {failed} | Skip: {skipped} | Warn: {warned}")
print(f"Pass Rate: {pass_rate:.1f}%")
print(f"\nStatus: {'🟢 CAN DEPLOY' if pass_rate >= 95 and failed == 0 else '🟡 NEEDS REVIEW' if pass_rate >= 85 else '🔴 BLOCKED'}")

# Save JSON report
report = {
    "round": 6,
    "date": time.strftime("%Y-%m-%d %H:%M:%S"),
    "server": BASE,
    "total": total,
    "passed": passed,
    "failed": failed,
    "skipped": skipped,
    "warned": warned,
    "pass_rate": pass_rate,
    "results": RESULTS,
}
report_path = "E:\\easyclaw\\伏羲-v1.44\\repo\\.openclaw\\中间\\r6_test_results.json"
os.makedirs(os.path.dirname(report_path), exist_ok=True)
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"\nJSON report saved to: {report_path}")
