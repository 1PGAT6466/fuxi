"""
tests/test_smoke.py — Phase 0.6 冒烟测试
验证核心 API 端点可用
"""
import sys, os, json, asyncio
import pytest
sys.path.insert(0, os.path.expanduser("~/kb-server"))

BASE_URL = "http://localhost:8080"
TOKEN = "fuxi-v1.43-token"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# 跳过所有冒烟测试（需要运行中的服务器）
pytestmark = pytest.mark.skip(reason="Smoke tests require running server")

def test_health():
    """0.6.1: /api/health 返回 200"""
    import urllib.request
    req = urllib.request.Request(f"{BASE_URL}/api/health")
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    assert resp.status == 200, f"Expected 200, got {resp.status}"
    assert "status" in data, "Missing 'status' in response"
    print(f"✅ /api/health: {data['status']}")

def test_search():
    """0.6.2: /api/search 返回结果"""
    import urllib.request, urllib.parse
    q = urllib.parse.quote("PLC")
    req = urllib.request.Request(f"{BASE_URL}/api/search?q={q}&top_k=3", headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read())
    assert resp.status == 200, f"Expected 200, got {resp.status}"
    print(f"✅ /api/search: returned {len(data.get('results', []))} results")

def test_documents():
    """0.6.3: /api/documents 返回文件列表"""
    import urllib.request
    req = urllib.request.Request(f"{BASE_URL}/api/documents", headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    assert resp.status == 200, f"Expected 200, got {resp.status}"
    print(f"✅ /api/documents: {data.get('total', 0)} files")

def test_chat():
    """0.6.4: /api/chat 返回回答"""
    import urllib.request
    payload = json.dumps({"query": "PLC是什么", "stream": False}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/api/chat",
        data=payload,
        headers={**HEADERS, "Content-Type": "application/json"},
        method="POST"
    )
    resp = urllib.request.urlopen(req, timeout=60)
    data = json.loads(resp.read())
    assert resp.status == 200, f"Expected 200, got {resp.status}"
    assert "answer" in data or "error" in data, "Missing 'answer' in response"
    answer = data.get("answer", "")
    print(f"✅ /api/chat: {len(answer)} chars, mode={data.get('mode', '?')}")

def test_v2_status():
    """0.6.5: /api/v2/status 返回系统状态"""
    import urllib.request
    req = urllib.request.Request(f"{BASE_URL}/api/v2/status")
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    assert resp.status == 200, f"Expected 200, got {resp.status}"
    print(f"✅ /api/v2/status: health_score={data.get('health_score', '?')}")

if __name__ == "__main__":
    tests = [test_health, test_search, test_documents, test_chat, test_v2_status]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            failed += 1
    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
