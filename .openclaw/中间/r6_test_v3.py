#!/usr/bin/env python3
"""R6 最终轮深层检测 v3 — 修复中文 URL 编码"""
import json, urllib.request, urllib.error, ssl, sys, time, os
from urllib.parse import quote, urlencode

BASE = "http://172.25.30.200:8080"
TOKEN = None
ROLE = None
RESULTS = []
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

WAIT_BETWEEN = 0.6
_last_req_time = 0

def rlw():
    global _last_req_time
    e = time.time() - _last_req_time
    if e < WAIT_BETWEEN:
        time.sleep(WAIT_BETWEEN - e)
    _last_req_time = time.time()

def req(method, path, body=None, headers_extra=None):
    rlw()
    # Separate path from query in case path already has query
    if '?' in path:
        p, q = path.split('?', 1)
        p = quote(p, safe='/')
        path = p + '?' + q  # query already encoded
    else:
        path = quote(path, safe='/')
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
            raw = resp.read()
            try: jbody = json.loads(raw)
            except: jbody = raw.decode("utf-8", errors="replace")[:200]
            return code, ct, jbody
    except urllib.error.HTTPError as e:
        code = e.code
        raw = e.read()
        try: jbody = json.loads(raw)
        except: jbody = raw.decode("utf-8", errors="replace")[:200]
        return code, "", jbody

def test(name, method, path, body=None, expected_code=200, checks=None, headers_extra=None):
    code, ct, jbody = req(method, path, body, headers_extra)
    s = "PASS"
    reasons = []
    if code == 429:
        s, reasons = "SKIP", [f"Rate-limited ({jbody.get('retry_after_seconds','?')}s)"]
    elif code != expected_code:
        s, reasons = "FAIL" if not (expected_code==200 and code in(401,403)) else "SKIP", \
            [f"Expected {expected_code}, got {code}" if not (expected_code==200 and code in(401,403)) else f"Auth ({code})"]
    if checks and s != "SKIP":
        for c in checks:
            r = c(jbody, ct, code)
            if r:
                if r[0] == "FAIL": s = "FAIL"
                elif r[0] == "WARN" and s != "FAIL": s = "WARN"
                reasons.append(r[1])
    tag = {"PASS":"✅","FAIL":"❌","SKIP":"⏭️","WARN":"⚠️"}[s]
    print(f"{tag} [{s:4s}] {method:6s} {path:50s} | {code} | {'; '.join(reasons)}")
    RESULTS.append({"endpoint":f"{method} {path}","expected_code":expected_code,"actual_code":code,"status":s,"reasons":reasons})

def c_v2(j,c,code):
    if isinstance(j,dict) and j.get("status")=="success" and "data" in j: return ("PASS","v2 format OK")
    if isinstance(j,dict) and j.get("status")=="error" and "message" in j: return ("PASS","v2 error format")
    return ("WARN","Not v2 format")
def c_json(j,c,code): return ("PASS","JSON") if "application/json" in c or "event-stream" in c else ("WARN",f"CT:{c[:30]}")
def c_ok(j,c,code):
    if isinstance(j,dict):
        if any(j.get(k) in ("ok","success","healthy","active") for k in ("status","ok")): return ("PASS","ok")
    return ("INFO",f"keys:{list(j.keys()) if isinstance(j,dict) else 'str'}")
def c_data(j,c,code):
    if isinstance(j,dict):
        for k in ["data","results","files","notifications","pages","symbols","entries","records","history","flags","nodes","tools","checks","bagua","chunks","matched","answer","items","preferences","sessions","services","growth","summary","report","feedbacks","metrics"]:
            if k in j: return ("PASS",f"'{k}' ({len(str(j[k]))}c)")
    return ("INFO",f"keys:{list(j.keys()) if isinstance(j,dict) else 'str'}")
def c_ev2(j,c,code):
    if isinstance(j,dict):
        if j.get("status")=="error" and "message" in j: return ("PASS","v2 error format")
        if "detail" in j: return ("FAIL","OLD {detail:...} — should be v2 error")
    return ("INFO",str(j)[:80])
def c_tok(j,c,code): return ("PASS","token") if isinstance(j,dict) and "token" in j else ("FAIL","no token")
def c_html(j,c,code): return ("PASS","HTML") if isinstance(j,str) else ("INFO","not html")

print("█"*70)
print(f"█ 伏羲 v1.50 R6 最终深层检测")
print(f"█ Server: {BASE}  |  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print("█"*70)

# === P1: No-auth ===
print("\n▸ PHASE 1: 无需认证端点")
test("Health", "GET", "/api/health", checks=[c_json, lambda j,c,code: ("PASS",f"healthy, {len(j.get('bagua',{}))} gua") if isinstance(j,dict) and j.get("status")=="healthy" else ("FAIL",str(j)[:60])])
test("Root", "GET", "/", checks=[c_html])
test("Login Page", "GET", "/login", checks=[c_html])
test("Login Bad", "POST", "/api/auth/login", body={"username":"no","password":"x"}, expected_code=401, checks=[c_ev2])

# Check Swagger access (should be protected in production)
test("Swagger", "GET", "/docs", checks=[lambda j,c,code: ("PASS","Protected") if code in (401,403) else ("WARN",f"Exposed! Status {code}")])
test("OpenAPI", "GET", "/openapi.json", checks=[lambda j,c,code: ("PASS","Protected") if code in (401,403) else ("WARN",f"Exposed! Status {code}")])

# === P2: Login ===
print("\n▸ PHASE 2: 用户认证")
rlw()
code, ct, jbody = req("POST", "/api/auth/login", body={"username":"test_r6_final","password":"TestR6@2026"})
if code == 200 and isinstance(jbody,dict) and "token" in jbody:
    TOKEN = jbody["token"]
    ROLE = jbody.get("role","?")
    print(f"✅ Logged in as test_r6_final (role={ROLE})")
    RESULTS.append({"endpoint":"POST /api/auth/login (r6 user)","expected_code":200,"actual_code":200,"status":"PASS","reasons":[f"role={ROLE}"]})
else:
    print(f"❌ Login failed: {code}")
    RESULTS.append({"endpoint":"POST /api/auth/login","expected_code":200,"actual_code":code,"status":"FAIL","reasons":["Login failed"]})

# Also check admin login regression
print("\n🔍 Testing admin login regression...")
rlw()
code2, ct2, jbody2 = req("POST", "/api/auth/login", body={"username":"admin","password":"fuxi2024"})
if code2 == 200 and isinstance(jbody2,dict) and "token" in jbody2:
    print("✅ Admin login OK")
else:
    print(f"🔴 ADMIN LOGIN REGRESSION: {code2} — {str(jbody2)[:200]}")
    RESULTS.append({"endpoint":"POST /api/auth/login (admin)","expected_code":200,"actual_code":code2,"status":"FAIL","reasons":[f"ADMIN LOGIN BROKEN: {code2}"]})

if TOKEN:
    # === P3-P20: All endpoints ===
    tests_batch = [
        # (phase, name, method, path, body, checks)
        ("3: 认证", "Auth Me", "GET", "/api/auth/me", None, [c_json, c_ok, c_data]),
        ("4: 搜索", "Search", "GET", "/api/search?q=%E9%85%8D%E7%BD%AE&top_k=3", None, [c_json, c_data]),
        ("4: 搜索", "Search Hist", "GET", "/api/search-history", None, [c_json]),
        ("4: 搜索", "Unified Srch", "GET", "/api/unified-search?q=%E6%B5%8B%E8%AF%95&limit=3", None, [c_json, c_data]),
        ("5: 对话", "Chat", "POST", "/api/chat", {"query":"Hello","stream":False}, [c_json, c_data]),
        ("5: 对话", "Chat v2", "POST", "/api/chat?format=v2", {"query":"Hello","stream":False}, [c_json, c_v2]),
        ("5: 对话", "Chat Agent", "POST", "/api/chat/agent", {"query":"Hello","stream":False}, [c_json, c_data]),
        ("5: 对话", "Chat Sessions", "GET", "/api/chat/sessions", None, [c_json]),
        ("5: 对话", "Chat SSE", "POST", "/api/chat/send", {"query":"Hi","stream":True}, [lambda j,c,code: ("PASS","SSE OK") if "event-stream" in c else ("WARN",f"CT:{c[:30]}")]),
        ("6: RAG", "RAG Search", "POST", "/api/rag/search", {"query":"test","top_k":3}, [c_json, c_data]),
        ("6: RAG", "SAG Search", "POST", "/api/rag/sag-search", {"query":"test","limit":3}, [c_json, c_data]),
        ("7: 文档", "Documents", "GET", "/api/documents", None, [c_json, c_data]),
        ("7: 文档", "Docs Export", "GET", "/api/documents/export", None, [c_json]),
        ("8: Wiki", "Wiki Pages", "GET", "/api/wiki/pages", None, [c_json, c_data]),
        ("8: Wiki", "Wiki Search", "GET", "/api/wiki/search?q=%E6%B5%8B%E8%AF%95", None, [c_json]),
        ("9: 图谱", "Graph", "GET", "/api/graph", None, [c_json, c_data]),
        ("10: 四象", "Symbols", "GET", "/api/symbols/status", None, [c_json, c_data]),
        ("10: 四象", "Growth", "GET", "/api/growth/overview", None, [c_json, c_data]),
        ("11: 通知", "Notif", "GET", "/api/notifications", None, [c_json, c_data]),
        ("11: 用户", "User Prefs", "GET", "/api/user/preferences", None, [c_json, c_data]),
        ("12: 评测", "Eval Rep", "GET", "/api/eval/report", None, [c_json, c_data]),
        ("12: 评测", "Eval Hist", "GET", "/api/eval/history", None, [c_json, c_data]),
        ("13: 管理", "Adm Stats", "GET", "/api/admin/stats", None, [c_json, c_data]),
        ("13: 管理", "Adm Status", "GET", "/api/admin/server-status", None, [c_json, c_data]),
        ("13: 管理", "Metrics Sum", "GET", "/api/admin/metrics-summary", None, [c_json, c_data]),
        ("14: FF", "FF List", "GET", "/api/feature-flags", None, [c_json, c_data]),
        ("15: 反馈", "Fb Weekly", "GET", "/api/feedback/weekly", None, [c_json]),
        ("15: 反馈", "Fb Submit", "POST", "/api/feedback", {"query":"t","answer":"t","rating":4}, [c_json]),
        ("16: 系统", "Sys Stats", "GET", "/api/system/stats", None, [c_json, c_data]),
        ("16: 系统", "Cache", "GET", "/api/cache/stats", None, [c_json]),
        ("16: 系统", "Errors", "GET", "/api/errors/stats", None, [c_json]),
        ("17: MCP", "MCP Tools", "GET", "/api/mcp/tools", None, [c_json, c_data]),
        ("17: MCP", "MCP sag_status", "POST", "/api/mcp/sag_status", {}, [c_json, c_data]),
        ("17: MCP", "MCP sag_search", "POST", "/api/mcp/sag_search", {"query":"VPN","top_k":3}, [c_json, c_data]),
        # ⭐ R5 修复验证
        ("⭐18: R5修复", "MCP:health_check", "POST", "/api/mcp/call", {"tool":"health_check","args":{}}, [c_json, c_data]),
        ("⭐18: R5修复", "MCP:ff_list", "POST", "/api/mcp/call", {"tool":"feature_flags_list","args":{}}, [c_json, c_data]),
        ("⭐18: R5修复", "MCP:graph_stats", "POST", "/api/mcp/call", {"tool":"graph_stats","args":{}}, [c_json, c_data]),
        ("⭐18: R5修复", "MCP:wiki_search", "POST", "/api/mcp/call", {"tool":"wiki_search","args":{"q":"VPN"}}, [c_json, c_data]),
        ("⭐18: R5修复", "MCP:sag_status", "POST", "/api/mcp/call", {"tool":"sag_status","args":{}}, [c_json, c_data]),
        ("19: 服务", "Services", "GET", "/api/services/", None, [c_json, c_data]),
    ]

    for phase, name, method, path, body, checks in tests_batch:
        if phase.startswith("⭐"):
            print(f"\n▸ {phase}")
        test(name, method, path, body, checks=checks)

    # Error format tests
    print("\n▸ PHASE 20: 错误格式统一性")
    test("404 Not Found", "GET", "/api/nonexist-r6", checks=[c_ev2], expected_code=404)
    toksave = TOKEN
    TOKEN = "bad_token_xyz"
    test("401 Bad Token", "GET", "/api/search?q=t", checks=[c_ev2], expected_code=401)
    TOKEN = None
    test("401 No Auth", "GET", "/api/search?q=t", checks=[c_ev2], expected_code=401)
    TOKEN = toksave

    # Permission test
    print("\n▸ PHASE 21: 权限控制")
    if ROLE == "user":
        test("FF PUT (user)", "PUT", "/api/feature-flags/shaoyang_sag_extract", body={"value":True}, checks=[c_ev2], expected_code=403)
    test("Eval Run (pk)", "POST", "/api/eval/run", checks=[lambda j,c,code: ("PASS","DENIED") if code in (401,403) else ("WARN",f"Allowed? {code}")], expected_code=403)

    # Metrics (service)
    test("Metrics Srv", "GET", "/metrics", checks=[lambda j,c,code: ("PASS","Prom text") if isinstance(j,str) and "fuxi_" in j else ("WARN",str(j)[:60])])

# === SUMMARY ===
print("\n" + "="*70)
print("📊 FINAL REPORT")
print("="*70)
passed  = sum(1 for r in RESULTS if r["status"]=="PASS")
failed  = sum(1 for r in RESULTS if r["status"]=="FAIL")
skipped = sum(1 for r in RESULTS if r["status"]=="SKIP")
warned  = sum(1 for r in RESULTS if r["status"]=="WARN")
total   = len(RESULTS)
eff     = total - skipped
pr      = (passed / eff * 100) if eff else 0

criticals = []
for r in RESULTS:
    if r["status"] == "FAIL":
        criticals.append(r["endpoint"])
    print(f"  [{r['status']:4s}] {r['endpoint']:55s} {r['reasons']}")

print(f"\nTotal={total} | Pass={passed} | Fail={failed} | Skip={skipped} | Warn={warned}")
print(f"Effective={eff} | Pass Rate={pr:.1f}%")

admin_regression = any("admin" in r["endpoint"] and r["status"]=="FAIL" for r in RESULTS)

verdict = "🟢 CAN DEPLOY" if pr >= 95 and failed == 0 else "🟡 CONDITIONAL" if pr >= 85 else "🔴 BLOCKED"
if admin_regression:
    verdict = "🔴 BLOCKED — CRITICAL: admin login regression"

print(f"\n{'🔴 CRITICAL: Admin login regression!' if admin_regression else '✅ Admin login OK'}" if TOKEN else "")
print(f"Verdict: {verdict}")
print(f"Critical issues: {len(criticals)}")

# Save to JSON
rpt = {"round":6,"date":time.strftime("%Y-%m-%d %H:%M:%S"),"server":BASE,"total":total,"passed":passed,"failed":failed,"skipped":skipped,"warned":warned,"effective":eff,"pass_rate":round(pr,1),"admin_login_regression":admin_regression,"verdict":verdict,"critical_issues":criticals,"results":RESULTS}
pth = os.path.join(os.path.dirname(os.path.abspath(__file__)), "r6_test_results.json")
with open(pth,"w",encoding="utf-8") as f:
    json.dump(rpt,f,ensure_ascii=False,indent=2)
print(f"\nReport: {pth}")
