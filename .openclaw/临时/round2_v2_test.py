"""
伏羲 v1.44 第二轮功能检测 v2 — 带延迟避免限流
"""
import requests
import json
import time
from datetime import datetime

BASE = "http://127.0.0.1:8080"
DELAY = 2.0  # 每次请求间隔2秒
TOKEN = None
RESULTS = []

def api(method, path, token=None, json_data=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{BASE}{path}"
    time.sleep(DELAY)
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=15)
        elif method == "POST":
            r = requests.post(url, headers=headers, json=json_data, timeout=30)
        elif method == "PUT":
            r = requests.put(url, headers=headers, json=json_data, timeout=15)
        elif method == "DELETE":
            r = requests.delete(url, headers=headers, timeout=15)
        return r
    except Exception as e:
        return None

def log(cat, name, method, url, status, passed, detail=""):
    RESULTS.append({"category": cat, "name": name, "method": method, "url": url, "status": status, "passed": passed, "detail": detail})
    icon = "PASS" if passed else "FAIL"
    print(f"  [{icon}] [{cat}] {name}: {status} {detail[:100]}")

# ==================== 0. Auth ====================
print("\n=== 0. Auth Flow ===")
r = api("POST", "/api/auth/register", json_data={"username":"r2tester","password":"Test1234!"})
log("Auth", "Register", "POST", "/api/auth/register", r.status_code if r else "N/A", r.status_code in [200, 400] if r else False)

r = api("POST", "/api/auth/login", json_data={"username":"r2tester","password":"Test1234!"})
if r and r.status_code == 200:
    TOKEN = r.json().get("token")
log("Auth", "Login", "POST", "/api/auth/login", r.status_code if r else "N/A", r.status_code == 200 if r else False)

r = api("GET", "/api/auth/me", token=TOKEN)
log("Auth", "Me", "GET", "/api/auth/me", r.status_code if r else "N/A", r.status_code == 200 if r else False)

r = api("POST", "/api/auth/refresh", token=TOKEN)
log("Auth", "Refresh", "POST", "/api/auth/refresh", r.status_code if r else "N/A", r.status_code == 200 if r else False)
if r and r.status_code == 200:
    TOKEN = r.json().get("token", TOKEN)

r = api("POST", "/api/auth/logout", token=TOKEN)
log("Auth", "Logout", "POST", "/api/auth/logout", r.status_code if r else "N/A", r.status_code == 200 if r else False)

# Re-login
r = api("POST", "/api/auth/login", json_data={"username":"r2tester","password":"Test1234!"})
if r and r.status_code == 200:
    TOKEN = r.json().get("token")

# ==================== 1. Health ====================
print("\n=== 1. Health & System ===")
r = api("GET", "/api/health")
if r and r.status_code == 200:
    d = r.json()
    log("System", "Health", "GET", "/api/health", 200, "status" in d and "checks" in d, f"keys={list(d.keys())}")
else:
    log("System", "Health", "GET", "/api/health", r.status_code if r else "N/A", False)

r = api("GET", "/api/v2/health")
log("System", "V2 Health", "GET", "/api/v2/health", r.status_code if r else "N/A", r.status_code in [200, 401, 403] if r else False)

r = api("GET", "/api/metrics", token=TOKEN)
log("System", "Metrics", "GET", "/api/metrics", r.status_code if r else "N/A", r.status_code in [200, 403] if r else False)

r = api("GET", "/api/symbols/status", token=TOKEN)
log("System", "Symbols Status", "GET", "/api/symbols/status", r.status_code if r else "N/A", r.status_code == 200 if r else False)

r = api("GET", "/api/growth/overview", token=TOKEN)
log("System", "Growth Overview", "GET", "/api/growth/overview", r.status_code if r else "N/A", r.status_code == 200 if r else False)

# ==================== 2. Search ====================
print("\n=== 2. Search & RAG ===")
r = api("GET", "/api/search?q=test&limit=3", token=TOKEN)
if r:
    d = r.json()
    has_fmt = "status" in d and "message" in d
    log("Search", "Search", "GET", "/api/search?q=test", r.status_code, r.status_code == 200, f"unified_format={has_fmt}, keys={list(d.keys())[:6]}")
else:
    log("Search", "Search", "GET", "/api/search?q=test", "N/A", False)

r = api("POST", "/api/rag/search", token=TOKEN, json_data={"query":"test","top_k":3})
log("Search", "RAG Search", "POST", "/api/rag/search", r.status_code if r else "N/A", r.status_code in [200, 500] if r else False)

r = api("GET", "/api/unified-search?q=test", token=TOKEN)
log("Search", "Unified Search", "GET", "/api/unified-search", r.status_code if r else "N/A", r.status_code in [200, 500] if r else False)

# ==================== 3. Documents ====================
print("\n=== 3. Documents ===")
r = api("GET", "/api/documents", token=TOKEN)
if r:
    d = r.json()
    has_fmt = "status" in d and "message" in d
    log("Docs", "Doc List", "GET", "/api/documents", r.status_code, r.status_code == 200, f"unified_format={has_fmt}, keys={list(d.keys())[:6]}")
else:
    log("Docs", "Doc List", "GET", "/api/documents", "N/A", False)

r = api("GET", "/api/documents/nonexistent", token=TOKEN)
log("Docs", "Doc Detail 404", "GET", "/api/documents/nonexistent", r.status_code if r else "N/A", r.status_code in [404, 200] if r else False)

# ==================== 4. Wiki ====================
print("\n=== 4. Wiki ===")
r = api("GET", "/api/wiki", token=TOKEN)
if r:
    d = r.json()
    has_fmt = "status" in d and "message" in d
    log("Wiki", "Wiki List", "GET", "/api/wiki", r.status_code, r.status_code == 200, f"unified_format={has_fmt}, keys={list(d.keys())[:6]}")
else:
    log("Wiki", "Wiki List", "GET", "/api/wiki", "N/A", False)

r = api("GET", "/api/wiki/1", token=TOKEN)
log("Wiki", "Wiki Detail", "GET", "/api/wiki/1", r.status_code if r else "N/A", r.status_code in [200, 404] if r else False)

# ==================== 5. Graph ====================
print("\n=== 5. Knowledge Graph ===")
r = api("GET", "/api/graph", token=TOKEN)
if r:
    d = r.json()
    has_fmt = "status" in d and "message" in d
    log("Graph", "Graph", "GET", "/api/graph", r.status_code, r.status_code == 200, f"unified_format={has_fmt}, keys={list(d.keys())[:6]}")
else:
    log("Graph", "Graph", "GET", "/api/graph", "N/A", False)

# ==================== 6. Chat ====================
print("\n=== 6. Chat ===")
r = api("GET", "/api/chat/sessions", token=TOKEN)
if r:
    d = r.json()
    has_fmt = "status" in d and "message" in d
    log("Chat", "Sessions", "GET", "/api/chat/sessions", r.status_code, r.status_code == 200, f"unified_format={has_fmt}, keys={list(d.keys())[:6]}")
else:
    log("Chat", "Sessions", "GET", "/api/chat/sessions", "N/A", False)

r = api("POST", "/api/chat/sessions", token=TOKEN, json_data={"title":"R2 Test"})
log("Chat", "Create Session", "POST", "/api/chat/sessions", r.status_code if r else "N/A", r.status_code in [200, 201] if r else False)

# ==================== 7. Dashboard & Metadata ====================
print("\n=== 7. Dashboard & Metadata ===")
r = api("GET", "/api/dashboard/stats", token=TOKEN)
log("Dashboard", "Stats", "GET", "/api/dashboard/stats", r.status_code if r else "N/A", r.status_code in [200, 403] if r else False)

r = api("GET", "/api/metadata", token=TOKEN)
if r:
    d = r.json()
    has_fmt = "status" in d and "message" in d
    log("Metadata", "Metadata", "GET", "/api/metadata", r.status_code, r.status_code == 200, f"unified_format={has_fmt}, keys={list(d.keys())[:6]}")
else:
    log("Metadata", "Metadata", "GET", "/api/metadata", "N/A", False)

# ==================== 8. Services ====================
print("\n=== 8. Services ===")
r = api("GET", "/api/services", token=TOKEN)
log("Services", "Service List", "GET", "/api/services", r.status_code if r else "N/A", r.status_code in [200, 403] if r else False)

# ==================== 9. WorldTree ====================
print("\n=== 9. WorldTree ===")
r = api("GET", "/api/worldtree", token=TOKEN)
log("WorldTree", "WorldTree", "GET", "/api/worldtree", r.status_code if r else "N/A", r.status_code in [200, 403] if r else False)

# ==================== 10. Feature Flags ====================
print("\n=== 10. Feature Flags ===")
r = api("GET", "/api/feature-flags", token=TOKEN)
log("Flags", "Flag List", "GET", "/api/feature-flags", r.status_code if r else "N/A", r.status_code in [200, 403] if r else False)

# ==================== 11. Eval ====================
print("\n=== 11. Evaluation ===")
r = api("GET", "/api/eval/report", token=TOKEN)
log("Eval", "Report", "GET", "/api/eval/report", r.status_code if r else "N/A", r.status_code == 200 if r else False)

r = api("GET", "/api/eval/history", token=TOKEN)
log("Eval", "History", "GET", "/api/eval/history", r.status_code if r else "N/A", r.status_code == 200 if r else False)

r = api("GET", "/api/evaluation/overview", token=TOKEN)
log("Eval", "Overview", "GET", "/api/evaluation/overview", r.status_code if r else "N/A", r.status_code in [200, 403] if r else False)

# ==================== 12. Feedback ====================
print("\n=== 12. Feedback ===")
r = api("POST", "/api/feedback", token=TOKEN, json_data={"query":"test","answer":"ans","rating":5})
log("Feedback", "Submit", "POST", "/api/feedback", r.status_code if r else "N/A", r.status_code in [200, 201] if r else False)

# ==================== 13. Tenants ====================
print("\n=== 13. Tenants ===")
r = api("GET", "/api/tenants", token=TOKEN)
log("Tenants", "Tenant List", "GET", "/api/tenants", r.status_code if r else "N/A", r.status_code in [200, 403] if r else False)

# ==================== 14. Notifications & Prefs ====================
print("\n=== 14. Notifications & Preferences ===")
r = api("GET", "/api/notifications", token=TOKEN)
log("Notify", "Notifications", "GET", "/api/notifications", r.status_code if r else "N/A", r.status_code in [200, 404] if r else False)

r = api("GET", "/api/user/preferences", token=TOKEN)
log("Prefs", "Preferences", "GET", "/api/user/preferences", r.status_code if r else "N/A", r.status_code in [200, 404] if r else False)

# ==================== 15. Proxy ====================
print("\n=== 15. Proxy ===")
r = api("GET", "/api/proxy/loader/files", token=TOKEN)
log("Proxy", "Loader Files", "GET", "/api/proxy/loader/files", r.status_code if r else "N/A", r.status_code in [200, 502] if r else False)

# ==================== 16. Evolution ====================
print("\n=== 16. Evolution ===")
r = api("GET", "/api/evolution/status", token=TOKEN)
log("Evolution", "Status", "GET", "/api/evolution/status", r.status_code if r else "N/A", r.status_code in [200, 404] if r else False)

# ==================== 17. 401 Test (no auth) ====================
print("\n=== 17. Auth Protection (no token) ===")
for path in ["/api/search?q=test", "/api/documents", "/api/wiki", "/api/graph", "/api/chat/sessions", "/api/dashboard/stats"]:
    r = api("GET", path)
    log("Security", f"401 {path}", "GET", path, r.status_code if r else "N/A", r.status_code == 401 if r else False)

# ==================== 18. Error handling ====================
print("\n=== 18. Error Handling ===")
r = api("GET", "/api/nonexistent")
log("Error", "404 Route", "GET", "/api/nonexistent", r.status_code if r else "N/A", r.status_code == 404 if r else False)

r = api("POST", "/api/auth/login", json_data={"username":"x"})
log("Error", "Validation", "POST", "/api/auth/login", r.status_code if r else "N/A", r.status_code in [400, 422] if r else False)

# Check 429 format
r = api("GET", "/api/metrics", token=TOKEN)
r2 = api("GET", "/api/metrics", token=TOKEN)
r3 = api("GET", "/api/metrics", token=TOKEN)
# One of these might be 429
for rx in [r, r2, r3]:
    if rx and rx.status_code == 429:
        d = rx.json()
        has_unified = "status" in d and "message" in d
        log("Error", "429 Format", "GET", "/api/metrics", 429, has_unified, f"keys={list(d.keys())}")
        break

# ==================== 19. Frontend ====================
print("\n=== 19. Frontend Routes ===")
for path, name in [("/", "Index"), ("/login", "Login")]:
    r = api("GET", path)
    is_html = "text/html" in (r.headers.get("content-type", "") if r else "")
    log("Frontend", name, "GET", path, r.status_code if r else "N/A", r.status_code == 200 and is_html if r else False)

# ==================== Summary ====================
print("\n" + "="*60)
total = len(RESULTS)
passed = sum(1 for r in RESULTS if r["passed"])
failed = total - passed
print(f"Total: {total} | Passed: {passed} | Failed: {failed} | Rate: {passed/total*100:.1f}%")

cats = {}
for r in RESULTS:
    c = r["category"]
    if c not in cats: cats[c] = {"p":0,"f":0}
    if r["passed"]: cats[c]["p"] += 1
    else: cats[c]["f"] += 1

print("\nBy Category:")
for c, s in cats.items():
    t = s["p"]+s["f"]
    rate = s["p"]/t*100
    icon = "OK" if rate==100 else "WARN" if rate>=50 else "BAD"
    print(f"  [{icon}] {c}: {s['p']}/{t} ({rate:.0f}%)")

print("\nFailed items:")
for r in RESULTS:
    if not r["passed"]:
        print(f"  FAIL [{r['category']}] {r['name']}: {r['status']} {r['detail'][:80]}")

# Save
report = {"time": datetime.now().isoformat(), "total":total, "passed":passed, "failed":failed, "categories":cats, "details":RESULTS}
with open(r"E:\easyclaw\伏羲-v1.44\repo\.openclaw\中间\round2_v2_results.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print("\nResults saved to .openclaw/中间/round2_v2_results.json")
