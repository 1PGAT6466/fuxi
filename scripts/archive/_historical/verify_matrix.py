#!/usr/bin/env python3
"""伏羲 V4.2 完整功能验证矩阵 + 差距分析"""
import os, sys, urllib.request, json, time

BASE = 'http://localhost:8080'
results = {}

def test(name, url, method='GET', timeout=15, validator=None):
    t0 = time.time()
    try:
        req = urllib.request.Request(url, method=method)
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = resp.read().decode()
        elapsed = round(time.time() - t0, 2)
        if validator:
            ok, msg = validator(data, resp.status)
        else:
            ok = resp.status == 200
            msg = f"status={resp.status}"
        results[name] = {"ok": ok, "msg": f"{msg} ({elapsed}s)"}
    except Exception as e:
        results[name] = {"ok": False, "msg": str(e)[:80]}

# ============ 测试矩阵 ============
# L0 基础
test("L0-health", f"{BASE}/api/health", validator=lambda d,s: (s==200 and '"ok":true' in d, f"health {s}"))

# L1 搜索
def v_search(d, s):
    if s != 200: return False, f"HTTP {s}"
    try:
        j = json.loads(d)
        return len(j.get("results",[])) > 0, f"results={len(j.get('results',[]))} cache={j.get('_from_cache',False)}"
    except: return False, "parse fail"
test("L1-search-POM", f"{BASE}/api/search?q=POM", validator=v_search)
test("L1-search-motor", f"{BASE}/api/search?q=伺服电机", validator=v_search)
test("L1-search-empty", f"{BASE}/api/search?q=zxcvbnm123456", validator=lambda d,s: (s==200, f"status {s}"))

# L2 器官状态
def v_v2(d, s):
    try:
        j = json.loads(d)
        alive = sum(1 for o in j.get("bagua",[]) if o.get("alive"))
        return alive >= 6, f"health={j.get('health_score')} alive={alive}/8"
    except: return False, "parse fail"
test("L2-v2-status", f"{BASE}/api/v2/status", validator=v_v2)

test("L2-admin-organs", f"{BASE}/api/admin/organ-status", validator=lambda d,s: (s==200, f"status {s}"))

# L3 Wiki
test("L3-wiki-pages", f"{BASE}/api/wiki/pages?limit=3", validator=lambda d,s: (s==200, f"status {s}"))
test("L3-wiki-search", f"{BASE}/api/wiki/search?q=test", validator=lambda d,s: (s==200, f"status {s}"))

# L4 前端
test("L4-frontend", f"{BASE}/", validator=lambda d,s: (s==200, f"HTML {len(d)}bytes"))
test("L4-admin-frontend", f"{BASE}/admin/", validator=lambda d,s: (s==200, f"HTML {len(d)}bytes"))

# L5 文档
test("L5-documents", f"{BASE}/api/documents", validator=lambda d,s: (s==200, f"docs {len(d)}bytes"))
test("L5-metadata", f"{BASE}/api/metadata", validator=lambda d,s: (s==200 or s==500, f"status {s}"))
test("L5-feedback", f"{BASE}/api/feedback", validator=lambda d,s: (s in (200,405), f"status {s}"))

# L6 图表/评估
test("L6-evaluation", f"{BASE}/api/evaluation", validator=lambda d,s: (s in (200,404), f"status {s}"))
test("L6-graph", f"{BASE}/api/graph", validator=lambda d,s: (s in (200,404), f"status {s}"))

# L7 Chat
test("L7-chat-post", f"{BASE}/api/chat", method='POST', timeout=30, validator=lambda d,s: (s in (200,422), f"status {s}"))

# 输出
passed = sum(1 for v in results.values() if v["ok"])
total = len(results)
print(f"\n{'='*60}")
print(f"  伏羲 V4.2 功能验证矩阵: {passed}/{total} 通过")
print(f"{'='*60}")
for name, r in results.items():
    icon = "✅" if r["ok"] else "❌"
    print(f"  {icon} {name}: {r['msg']}")
print(f"\n通过率: {round(passed/total*100)}%")
