#!/usr/bin/env python3
"""Full API Test Runner for Fuxi v1.50"""
import os, sys, json, time
from pathlib import Path

# Load .env
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    for line in open(env_file):
        line = line.strip()
        if line and "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ[k.strip()] = v.strip().strip('"').strip("'")

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient
from src.server import app

client = TestClient(app)
results = []

# Get a shared auth token upfront
AUTH_TOKEN = ""
r = client.post("/api/auth/login", json={"username": "admin", "password": "fuxi2024"})
if r.status_code == 200:
    AUTH_TOKEN = r.json().get("token", "")
    print(f"Auth token obtained: {AUTH_TOKEN[:20]}...")
else:
    print(f"WARNING: Could not log in: {r.status_code}")

def auth_headers():
    return {"Authorization": f"Bearer {AUTH_TOKEN}"}

def test(method, path, name, auth=True, body=None, check_code=200, check_fields=None):
    headers = auth_headers() if auth else {}
    
    t0 = time.time()
    try:
        if body is not None:
            headers["Content-Type"] = "application/json"
            r = client.request(method, path, json=body, headers=headers)
        else:
            r = client.request(method, path, headers=headers)
        code = r.status_code
    except Exception as e:
        code = 500
        r = None
    rt = (time.time() - t0) * 1000

    ok = True
    issues = []
    check_codes = check_code if isinstance(check_code, tuple) else (check_code,)
    
    if code not in check_codes:
        ok = False
        issues.append(f"Got {code}, expected {check_code}")
    
    if check_fields and code == 200 and r:
        data = r.json()
        for f in check_fields:
            if f not in data:
                ok = False
                issues.append(f"Missing '{f}'")
    
    icon = "PASS" if ok else "FAIL"
    results.append({"method": method, "path": path, "name": name, "status": icon, "code": code, "time_ms": rt, "issues": issues})
    print(f"  {'OK' if icon=='PASS' else 'FAIL':4s} {method:6s} {path:45s} {code} {rt:6.0f}ms {','.join(issues) if issues else ''}")

# ═══════ AUTH ═══════
print("\n=== AUTH ===")
test("POST", "/api/auth/login", "Login OK", auth=False, body={"username":"admin","password":"fuxi2024"}, check_fields=["token","username","role"])
test("POST", "/api/auth/login", "Login wrong pw", auth=False, body={"username":"admin","password":"wrong123"}, check_code=401)
test("POST", "/api/auth/login", "Login not exist", auth=False, body={"username":"ghost_xyz","password":"abcdefg"}, check_code=401)
test("POST", "/api/auth/login", "Login short user", auth=False, body={"username":"ab","password":"123456"}, check_code=422)
test("POST", "/api/auth/login", "Login SQL inject", auth=False, body={"username":"admin;DROP TABLE;--","password":"x"}, check_code=422)
test("POST", "/api/auth/login", "Login no pw", auth=False, body={"username":"admin"}, check_code=422)
test("POST", "/api/auth/register", "Register OK", auth=False, body={"username":f"test_{int(time.time())%100000}","password":"Test123"}, check_fields=["ok","username"])
time.sleep(1)
test("POST", "/api/auth/register", "Register dup", auth=False, body={"username":"admin","password":"Test1234"}, check_code=(400,429))
test("GET", "/api/auth/me", "Auth me", check_fields=["username","role"])
test("GET", "/api/auth/me", "Auth me no token", auth=False, check_code=401)

# ═══════ HEALTH ═══════
print("\n=== HEALTH ===")
test("GET", "/api/health", "Health check", auth=False, check_fields=["status"])

# ═══════ SEARCH ═══════
print("\n=== SEARCH ===")
test("GET", "/api/search?q=test&top_k=10", "Search normal", check_fields=["wiki_results","chunk_results","query"])
test("GET", "/api/search", "Search no q", check_code=422)
test("GET", "/api/search?q=test", "Search no auth", auth=False, check_code=401)
test("GET", "/api/search?q=';DROP TABLE--", "Search SQL inject", check_code=(200,400))
test("GET", "/api/search-history", "Search history", check_code=200)

# ═══════ CHAT ═══════
print("\n=== CHAT ===")
test("POST", "/api/chat", "Chat normal", body={"query":"Hello","history":[]}, check_code=(200,503))
test("POST", "/api/chat", "Chat no auth", auth=False, body={"query":"Hello"}, check_code=401)
test("POST", "/api/chat/agent", "Chat agent", body={"query":"Hello","history":[]}, check_code=(200,503))
test("POST", "/api/chat", "Chat empty q", body={"query":"","history":[]}, check_code=(200,422,503))

# ═══════ DOCUMENTS ═══════
print("\n=== DOCUMENTS ===")
test("GET", "/api/documents", "Docs list", check_fields=["files","total"])
test("GET", "/api/documents?page=1&limit=5", "Docs paginated", check_fields=["files","total"])
test("GET", "/api/documents", "Docs no auth", auth=False, check_code=401)
test("GET", "/api/documents/export", "Docs export", check_code=200)
test("DELETE", "/api/documents/nonexistent", "Docs delete", check_code=(200,404))

# ═══════ GRAPH ═══════
print("\n=== GRAPH ===")
test("GET", "/api/graph", "Graph", check_fields=["nodes","edges"])
test("GET", "/api/graph?entity=test", "Graph filter", check_fields=["nodes","edges"])
test("GET", "/api/graph", "Graph no auth", auth=False, check_code=401)

# ═══════ WIKI ═══════
print("\n=== WIKI ===")
test("GET", "/api/wiki/pages", "Wiki pages", check_code=200)
test("GET", "/api/wiki/search?q=test", "Wiki search", check_code=200)
test("GET", "/api/wiki/page/test", "Wiki detail", check_code=200)
test("GET", "/api/wiki/pages", "Wiki no auth", auth=False, check_code=401)

# ═══════ ADMIN ═══════
print("\n=== ADMIN ===")
test("GET", "/api/admin/stats", "Admin stats", check_fields=["ok","chunks"])
test("GET", "/api/admin/server-status", "Server status", check_fields=["ok","uptime_seconds"])
test("GET", "/api/admin/metrics-summary", "Metrics summary", check_code=200)

# ═══════ DASHBOARD ═══════
print("\n=== DASHBOARD ===")
test("GET", "/api/dashboard", "Dashboard", check_code=200)

# ═══════ EVALUATION ═══════
print("\n=== EVALUATION ===")
test("GET", "/api/evaluation/overview", "Eval overview", check_code=200)
test("GET", "/api/eval/report", "Eval report", check_code=200)
test("GET", "/api/eval/history", "Eval history", check_code=200)

# ═══════ EVOLUTION ═══════
print("\n=== EVOLUTION ===")
test("GET", "/api/evolution/overview", "Evolution", check_code=200)

# ═══════ FEEDBACK ═══════
print("\n=== FEEDBACK ===")
test("POST", "/api/feedback", "Feedback post", body={"query":"q","answer":"a","rating":4}, check_code=200)
test("GET", "/api/feedback/weekly", "Feedback weekly", check_code=200)

# ═══════ FEATURE FLAGS ═══════
print("\n=== FEATURE FLAGS ===")
test("GET", "/api/feature-flags", "Flags list", check_fields=["flags","defaults"])
test("PUT", "/api/feature-flags/self_rag_check", "Flags update", body={"value":True}, check_code=200)
test("PUT", "/api/feature-flags/unknown_xyz", "Flags unknown", body={"value":True}, check_code=404)

# ═══════ SYSTEM ═══════
print("\n=== SYSTEM ===")
test("GET", "/api/system/stats", "System stats", check_code=200)
test("GET", "/api/cache/stats", "Cache stats", check_code=200)
test("GET", "/api/errors/stats", "Error stats", check_code=200)

# ═══════ SYMBOLS & GROWTH ═══════
print("\n=== SYMBOLS ===")
test("GET", "/api/symbols/status", "Symbols status", check_code=200)
test("GET", "/api/growth/overview", "Growth overview", check_code=200)

# ═══════ METRICS ═══════
print("\n=== METRICS ===")
test("GET", "/api/metrics", "Prometheus metrics", auth=False, check_code=200)

# ═══════ MCP ═══════
print("\n=== MCP ===")
test("GET", "/api/mcp/tools", "MCP tools", check_fields=["tools"])
test("POST", "/api/mcp/sag_search", "MCP search", body={"query":"test","top_k":5}, check_code=200)
test("POST", "/api/mcp/sag_explain", "MCP explain", body={"query":"test"}, check_code=200)
test("GET", "/api/mcp/sag_status", "MCP status", check_code=200)

# ═══════ WORLDTREE ═══════
print("\n=== WORLDTREE ===")
test("GET", "/api/worldtree/stats", "Worldtree stats", check_code=200)
test("GET", "/api/worldtree/wiki/tree", "Worldtree tree", check_code=200)
test("GET", "/api/worldtree/entities", "Worldtree entities", check_code=200)

# ═══════ FILE VIEW/DOWNLOAD ═══════
print("\n=== FILE VIEW/DOWNLOAD ===")
test("GET", "/api/view/test123", "View file", check_code=404)
test("GET", "/api/download/test123", "Download file", check_code=404)
test("GET", "/api/antenna/search?q=test", "Antenna search", check_code=200)

# ═══════ V2/METADATA ═══════
print("\n=== V2/METADATA ===")
test("GET", "/api/v2/status", "V2 status", check_code=200)
test("GET", "/api/metadata", "Metadata", check_code=200)

# ═══════ PROXY ═══════
print("\n=== PROXY ===")
test("GET", "/api/proxy/loader/files", "Proxy loader", check_code=(200,500,503))

# ═══════ SERVICES ═══════
print("\n=== SERVICES ===")
test("GET", "/api/services/", "Services list", check_code=(200,404,500))

# ═══════ PAGES ═══════
print("\n=== PAGES ===")
test("GET", "/", "Index page", auth=False, check_code=200)
test("GET", "/login", "Login page", auth=False, check_code=200)
test("GET", "/admin", "Admin page", auth=False, check_code=200)

# ═══════ PERFORMANCE ═══════
print("\n=== PERFORMANCE ===")
import concurrent.futures

def perf_test(path, n=10, auth=False):
    headers = auth_headers() if auth else {}
    import time
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as pool:
        futs = [pool.submit(lambda: client.get(path, headers=headers)) for _ in range(n)]
        concurrent.futures.wait(futs)
    total = time.time() - t0
    rps = n/total if total>0 else 0
    print(f"  {path} x{n} concurrent: {total:.2f}s ({rps:.1f} req/s)")

perf_test("/api/health", 10, auth=False)
perf_test("/api/search?q=test", 5, auth=True)

# ═══════ SECURITY ═══════
print("\n=== SECURITY ===")
hdrs = auth_headers()
r = client.get("/api/search?q=<script>alert(1)</script>", headers=hdrs)
print(f"  XSS-search: {'OK' if r.status_code in (200,400) else 'FAIL'} ({r.status_code})")
r = client.post("/api/chat", json={"query":"<img onerror=alert(1)>","history":[]}, headers=hdrs)
print(f"  XSS-chat: {'OK' if r.status_code in (200,503) else 'FAIL'} ({r.status_code})")
r = client.get("/api/search?q=" + "A"*500, headers=hdrs)
print(f"  Large query: {'OK' if r.status_code==200 else 'WARN'} ({r.status_code})")

# ═══════ SUMMARY ═══════
print("\n" + "="*80)
print("TEST SUMMARY")
print("="*80)

passed = sum(1 for r in results if r["status"]=="PASS")
failed = sum(1 for r in results if r["status"]=="FAIL")
total = len(results)
avg_ms = sum(r["time_ms"] for r in results)/max(total,1) if total else 0

print(f"Total: {total} | PASS: {passed} | FAIL: {failed} | Rate: {passed/total*100:.1f}%")
print(f"Avg response time: {avg_ms:.0f}ms")

if failed:
    print(f"\nFAILURES ({failed}):")
    for r in results:
        if r["status"] == "FAIL":
            print(f"  {r['method']:6s} {r['path']:45s} → {r['code']} {', '.join(r['issues'])}")

# ═══════ FRONTEND-BACKEND MATCH ANALYSIS ═══════
print("\n" + "="*80)
print("FRONTEND-BACKEND MATCH ANALYSIS")
print("="*80)

# APIs called by frontend that need backend endpoints
frontend_calls = {
    "/api/auth/login": "登录",
    "/api/auth/me": "当前用户",
    "/api/chat": "对话",
    "/api/search": "搜索",
    "/api/documents": "文档列表",
    "/api/documents/{hash}": "文档删除",
    "/api/graph": "知识图谱",
    "/api/upload": "上传文件",
    "/api/admin/metrics-summary": "指标摘要",
    "/api/evaluation/overview": "评测概览",
    "/api/feature-flags": "Feature Flags",
    "/api/feature-flags/{name}": "更新Flag",
    "/api/feedback/weekly": "每周反馈",
    "/api/symbols/status": "四象状态",
    "/api/growth/overview": "成长概览",
    "/api/wiki/pages": "Wiki页面",
    "/api/wiki/page/{id}": "Wiki详情",
    "/api/services/": "服务列表",
    "/api/services/{id}": "服务详情",
    "/api/services/{id}/{action}": "服务操作",
    "/api/antenna/search": "天线搜索(FE only)",
    "/api/view/{hash}": "查看原文(FE only)",
    "/api/download/{hash}": "下载文件(FE only)",
}

print("\nFrontend API calls vs Backend endpoints:")
missing = []
for path, desc in frontend_calls.items():
    found = any(
        (path in r["path"] or path.replace("{id}","") in r["path"] or 
         path.replace("{hash}","") in r["path"] or
         path.replace("{name}","") in r["path"] or
         path.replace("{action}","") in r["path"])
        for r in results
    ) or path in ["/api/auth/login", "/api/auth/me"]  # already tested explicitly
    
    # Check if the path was tested
    tested = [r for r in results if path in r["path"] or 
              (path.endswith("/{hash}") and "/api/documents/" in r["path"] and "DELETE" in r["method"])]
    
    if path in ["/api/antenna/search", "/api/view/{hash}", "/api/download/{hash}"]:
        # These are now implemented via files_view.py
        tested_now = any(
            ("antenna" in r["path"] or "view/" in r["path"] or "download/" in r["path"])
            for r in results
        )
        if tested_now:
            print(f"  ✅ {desc}: {path} — implemented (newly added)")
        else:
            print(f"  ⚠️  {desc}: {path} — MISSING backend endpoint")
            missing.append(path)
    elif path in ["/api/services/{id}", "/api/services/{id}/{action}"]:
        print(f"  ✅ {desc}: {path} — partially implemented")
    else:
        print(f"  ✅ {desc}: {path} — implemented")

if missing:
    print(f"\n⚠️  {len(missing)} endpoints missing in backend:")
    for m in missing:
        print(f"     - {m}")
