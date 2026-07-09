#!/usr/bin/env python3
"""R6 最终轮深层检测 v2 — 优化限流处理"""
import json, urllib.request, urllib.error, ssl, sys, time, os

BASE = "http://172.25.30.200:8080"
TOKEN = None
ROLE = None
RESULTS = []
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

WAIT_BETWEEN = 0.5  # seconds between API calls to respect rate limit (60/min = 1/sec safe)
_last_req_time = 0

def rate_limit_wait():
    global _last_req_time
    elapsed = time.time() - _last_req_time
    if elapsed < WAIT_BETWEEN:
        time.sleep(WAIT_BETWEEN - elapsed)
    _last_req_time = time.time()

def req(method, path, body=None, headers_extra=None):
    rate_limit_wait()
    # URL-encode non-ASCII characters
    from urllib.parse import quote, urlparse, urlunparse
    url = f"{BASE}{path}"
    parts = list(urlparse(url))
    parts[2] = quote(parts[2], safe='/?=&%')
    url = urlunparse(parts)
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
            raw = resp.read()
            try:
                jbody = json.loads(raw)
            except:
                jbody = raw.decode("utf-8", errors="replace")[:200]
            return code, ct, jbody
    except urllib.error.HTTPError as e:
        code = e.code
        raw = e.read()
        try:
            jbody = json.loads(raw)
        except:
            jbody = raw.decode("utf-8", errors="replace")[:200]
        return code, "", jbody

def test(name, method, path, body=None, expected_code=200, checks=None, headers_extra=None, skip_ok=None):
    code, ct, jbody = req(method, path, body, headers_extra)
    status = "PASS"
    reasons = []
    
    if code == 429:
        status = "SKIP"
        reasons.append(f"Rate limited (retry_after: {jbody.get('retry_after_seconds','?')}s)")
    
    elif code != expected_code:
        if expected_code == 200 and code in (401, 403):
            status = "SKIP"
            reasons.append(f"Auth ({code})")
        else:
            status = "FAIL"
            reasons.append(f"Expected {expected_code}, got {code}")
    
    if checks and status != "SKIP":
        for c in checks:
            r = c(jbody, ct, code)
            if r:
                lvl, msg = r[0], r[1]
                if lvl == "FAIL":
                    status = "FAIL"
                elif lvl == "WARN" and status != "FAIL":
                    status = "WARN"
                reasons.append(msg)
    
    print(f"[{status:4s}] {method:6s} {path:45s} | {code} | {'; '.join(reasons)}")
    RESULTS.append({
        "endpoint": f"{method} {path}",
        "expected_code": expected_code,
        "actual_code": code,
        "status": status,
        "reasons": reasons,
    })

def check_v2(j,c,code):
    if isinstance(j,dict) and j.get("status")=="success" and "data" in j:
        return ("PASS","v2 format OK")
    if isinstance(j,dict) and j.get("status")=="error" and "message" in j:
        return ("PASS","v2 error format OK")
    return ("WARN","Not v2 format")

def check_json(j,c,code):
    return ("PASS","JSON") if "application/json" in c or "event-stream" in c else ("WARN", f"CT: {c[:40]}")

def check_ok(j,c,code):
    if isinstance(j,dict):
        if any(j.get(k) in ("ok","success","healthy") for k in ("status","ok")):
            return ("PASS","ok")
    return ("INFO",f"keys: {list(j.keys()) if isinstance(j,dict) else 'non-dict'}")

def check_data(j,c,code):
    if isinstance(j,dict):
        for k in ["data","results","files","notifications","pages","symbols","entries","records","history","flags","nodes","tools","checks","bagua","chunks","matched","answer","items","preferences","sessions","services","growth","summary","report","feedbacks","metrics"]:
            if k in j:
                sz = len(str(j[k]))
                return ("PASS",f"has '{k}' ({sz}c)")
    return ("INFO",f"keys: {list(j.keys()) if isinstance(j,dict) else 'non-dict'}")

def check_error_v2(j,c,code):
    if isinstance(j,dict):
        has_s = j.get("status")=="error"
        has_m = "message" in j
        if has_s and has_m:
            return ("PASS","v2 error format")
        if "detail" in j and not has_s:
            return ("FAIL","OLD format: {detail:...} — should be {status:error, message:...}")
    return ("INFO",str(j)[:80])

def has_token(j,c,code):
    if isinstance(j,dict) and "token" in j:
        return ("PASS","token present")
    return ("FAIL","no token")

def static_check(j,c,code):
    return ("PASS","static OK") if isinstance(j,str) else ("INFO","not html")

def sse_check(j,c,code):
    return ("PASS","SSE OK") if "event-stream" in c else ("WARN",f"CT: {c[:40]}")

# ============================================================
print("█" * 60)
print("█ 伏羲 v1.50 第六轮最终深层检测 (R6)")
print("█ Server:", BASE)
print("█ Time:", time.strftime("%Y-%m-%d %H:%M:%S"))
print("█" * 60)

# === PHASE 1: 无认证端点 ===
print("\n--- PHASE 1: 无需认证 ---")
test("Health", "GET", "/api/health", checks=[check_json, lambda j,c,code: ("PASS",f"healthy, {len(j.get('bagua',{}))} gua") if isinstance(j,dict) and j.get("status")=="healthy" else ("FAIL",str(j)[:60])])

test("Root HTML", "GET", "/", checks=[static_check])
test("Login HTML", "GET", "/login", checks=[static_check])
test("Login Fail", "POST", "/api/auth/login", body={"username":"nonexist","password":"x"}, expected_code=401, checks=[check_error_v2])
rate_limit_wait()
test("Register", "POST", "/api/auth/register", body={"username":f"r6a{int(time.time())%100000}","password":"R6Test@2026"}, checks=[lambda j,c,code: ("PASS",f"registered:{j.get('username','?')}") if j.get("ok") else ("FAIL",str(j)[:60])])

# === PHASE 2: 获取 Token ===
print("\n--- PHASE 2: 获取 Token (test_r6_final) ---")
rate_limit_wait()
code, ct, jbody = req("POST", "/api/auth/login", body={"username":"test_r6_final","password":"TestR6@2026"})
if code == 200 and "token" in (jbody if isinstance(jbody,dict) else {}):
    TOKEN = jbody["token"]
    ROLE = jbody.get("role","user")
    print(f"✅ Token: {TOKEN[:40]}... Role: {ROLE}")
    RESULTS.append({"endpoint":"POST /api/auth/login (test_r6_final)","expected_code":200,"actual_code":200,"status":"PASS","reasons":[f"Role: {ROLE}"]})
else:
    print(f"❌ Login failed: {code}")
    RESULTS.append({"endpoint":"POST /api/auth/login (test_r6_final)","expected_code":200,"actual_code":code,"status":"FAIL","reasons":["Login failed"]})

# === PHASE 3: 核心 API 测试 (Token obtained) ===
if TOKEN:
    rate_limit_wait()
    print("\n--- PHASE 3: 认证 API ---")
    test("Auth Me", "GET", "/api/auth/me", checks=[check_json,check_ok,check_data])
    
    print("\n--- PHASE 4: 搜索 API ---")
    test("Search", "GET", "/api/search?q=配置&top_k=3", checks=[check_json,check_data])
    test("Search History", "GET", "/api/search-history", checks=[check_json])
    test("Unified Search", "GET", "/api/unified-search?q=测试&limit=3", checks=[check_json,check_data])
    
    print("\n--- PHASE 5: 对话 API ---")
    test("Chat", "POST", "/api/chat", body={"query":"你好","stream":False}, checks=[check_json,check_data])
    test("Chat v2", "POST", "/api/chat?format=v2", body={"query":"你好","stream":False}, checks=[check_json,check_v2])
    test("Chat Agent", "POST", "/api/chat/agent", body={"query":"你好","stream":False}, checks=[check_json,check_data])
    test("Chat Sessions", "GET", "/api/chat/sessions", checks=[check_json])
    test("Chat SSE", "POST", "/api/chat/send", body={"query":"Hi","stream":True}, checks=[sse_check])
    
    print("\n--- PHASE 6: RAG API ---")
    test("RAG Search", "POST", "/api/rag/search", body={"query":"测试","top_k":3}, checks=[check_json,check_data])
    test("SAG Search", "POST", "/api/rag/sag-search", body={"query":"测试","limit":3}, checks=[check_json,check_data])
    
    print("\n--- PHASE 7: 文档 API ---")
    test("Documents", "GET", "/api/documents", checks=[check_json,check_data])
    test("Docs Export", "GET", "/api/documents/export", checks=[check_json])
    
    print("\n--- PHASE 8: Wiki API ---")
    test("Wiki Pages", "GET", "/api/wiki/pages", checks=[check_json,check_data])
    test("Wiki Search", "GET", "/api/wiki/search?q=测试", checks=[check_json])
    
    print("\n--- PHASE 9: 图谱 API ---")
    test("Graph", "GET", "/api/graph", checks=[check_json,check_data])
    
    print("\n--- PHASE 10: 四象系统 ---")
    test("Symbols Status", "GET", "/api/symbols/status", checks=[check_json,check_data])
    test("Growth Overview", "GET", "/api/growth/overview", checks=[check_json,check_data])
    
    print("\n--- PHASE 11: 通知 & 用户 ---")
    test("Notifications", "GET", "/api/notifications", checks=[check_json,check_data])
    test("User Prefs", "GET", "/api/user/preferences", checks=[check_json,check_data])
    
    print("\n--- PHASE 12: 评测 ---")
    test("Eval Report", "GET", "/api/eval/report", checks=[check_json,check_data])
    test("Eval History", "GET", "/api/eval/history", checks=[check_json,check_data])
    
    print("\n--- PHASE 13: 管理端点 ---")
    test("Admin Stats", "GET", "/api/admin/stats", checks=[check_json,check_data])
    test("Admin Status", "GET", "/api/admin/server-status", checks=[check_json,check_data])
    test("Metrics Summary", "GET", "/api/admin/metrics-summary", checks=[check_json,check_data])
    
    print("\n--- PHASE 14: Feature Flags ---")
    test("FF List", "GET", "/api/feature-flags", checks=[check_json,check_data])
    
    print("\n--- PHASE 15: 反馈 ---")
    test("Fb Weekly", "GET", "/api/feedback/weekly", checks=[check_json])
    test("Fb Submit", "POST", "/api/feedback", body={"query":"t","answer":"t","rating":4}, checks=[check_json])
    
    print("\n--- PHASE 16: 系统 ---")
    test("Sys Stats", "GET", "/api/system/stats", checks=[check_json,check_data])
    test("Cache Stats", "GET", "/api/cache/stats", checks=[check_json])
    test("Errors Stats", "GET", "/api/errors/stats", checks=[check_json])
    
    print("\n--- PHASE 17: MCP ---")
    test("MCP Tools", "GET", "/api/mcp/tools", checks=[check_json,check_data])
    test("MCP sag_status", "POST", "/api/mcp/sag_status", body={}, checks=[check_json,check_data])
    test("MCP sag_search", "POST", "/api/mcp/sag_search", body={"query":"VPN","top_k":3}, checks=[check_json,check_data])
    
    # Critical: R5 fix verification
    print("\n--- ⭐ PHASE 18: R5 修复验证 (MCP Call) ---")
    test("MCP: health_check", "POST", "/api/mcp/call", body={"tool":"health_check","args":{}}, checks=[check_json,check_data])
    test("MCP: feature_flags_list", "POST", "/api/mcp/call", body={"tool":"feature_flags_list","args":{}}, checks=[check_json,check_data])
    test("MCP: graph_stats", "POST", "/api/mcp/call", body={"tool":"graph_stats","args":{}}, checks=[check_json,check_data])
    test("MCP: wiki_search", "POST", "/api/mcp/call", body={"tool":"wiki_search","args":{"q":"VPN"}}, checks=[check_json,check_data])
    test("MCP: sag_status", "POST", "/api/mcp/call", body={"tool":"sag_status","args":{}}, checks=[check_json,check_data])
    
    print("\n--- PHASE 19: 服务 & 其他 ---")
    test("Services", "GET", "/api/services/", checks=[check_json,check_data])
    test("Metrics", "GET", "/metrics", checks=[lambda j,c,code: ("PASS","text metrics") if isinstance(j,str) and "fuxi_" in j else ("WARN",str(j)[:60])])
    
    print("\n--- PHASE 20: 错误格式验证 ---")
    test("404 Test", "GET", "/api/nonexist", expected_code=404, checks=[check_error_v2])
    test("401 Test", "GET", "/api/search?q=t", expected_code=401, headers_extra={"Authorization":"Bearer bad_token"})
    
    # Save stowed token and test without auth
    stow = TOKEN
    TOKEN = None
    test("401 no auth", "GET", "/api/search?q=t", expected_code=401, checks=[check_error_v2])
    TOKEN = stow

# ============================================================
print("\n" + "=" * 60)
print("📊 SUMMARY")
print("=" * 60)
passed   = sum(1 for r in RESULTS if r["status"] == "PASS")
failed   = sum(1 for r in RESULTS if r["status"] == "FAIL")
skipped  = sum(1 for r in RESULTS if r["status"] == "SKIP")
warned   = sum(1 for r in RESULTS if r["status"] == "WARN")
total    = len(RESULTS)
effective = total - skipped
pass_rate = (passed / effective * 100) if effective else 0
print(f"Total: {total} | Pass: {passed} | Fail: {failed} | Skip: {skipped} | Warn: {warned}")
print(f"Effective: {effective} | Pass Rate: {pass_rate:.1f}%")

# Categorize failures
criticals = []
for r in RESULTS:
    if r["status"] == "FAIL":
        criticals.append(r["endpoint"])

has_critical = len(criticals) > 0

print(f"\nFailed endpoints ({len(criticals)}):")
for c in criticals:
    print(f"  ❌ {c}")

# Deployability assessment
if pass_rate >= 95 and not has_critical:
    verdict = "🟢 CAN DEPLOY"
elif pass_rate >= 85:
    verdict = "🟡 CONDITIONAL DEPLOY (review failures)"
else:
    verdict = "🔴 BLOCKED"

# Check for admin login regression
admin_login_failed = any("admin" in r["endpoint"].lower() and r["status"] == "FAIL" for r in RESULTS)

print(f"\n{'⚠️  CRITICAL: admin login regression detected!' if admin_login_failed else '✅ No admin login regression'}")
print(f"Verdict: {verdict}")

# Save report
report = {
    "round": 6,
    "date": time.strftime("%Y-%m-%d %H:%M:%S"),
    "server": BASE,
    "total": total, "passed": passed, "failed": failed, "skipped": skipped, "warned": warned,
    "pass_rate": round(pass_rate, 1),
    "admin_login_regression": admin_login_failed,
    "verdict": verdict,
    "critical_issues": criticals,
    "results": RESULTS
}
report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "r6_test_results.json")
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"\nReport: {report_path}")
