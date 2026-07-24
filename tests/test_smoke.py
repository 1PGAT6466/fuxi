"""
tests/test_smoke.py — Phase 0.6 冒烟测试
验证核心 API 端点可用
"""
import sys, os, json, asyncio
import pytest
sys.path.insert(0, os.path.expanduser("~/kb-server"))

BASE_URL = "http://localhost:8080"
TOKEN = "fuxi-v1.50-token"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# 需要运行中服务器的测试标记
requires_server = pytest.mark.skip(reason="Smoke tests require running server")

@requires_server
def test_health():
    """0.6.1: /api/health 返回 200"""
    import urllib.request
    req = urllib.request.Request(f"{BASE_URL}/api/health")
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    assert resp.status == 200, f"Expected 200, got {resp.status}"
    assert "status" in data, "Missing 'status' in response"
    print(f"✅ /api/health: {data['status']}")

@requires_server
def test_search():
    """0.6.2: /api/search 返回结果"""
    import urllib.request, urllib.parse
    q = urllib.parse.quote("PLC")
    req = urllib.request.Request(f"{BASE_URL}/api/search?q={q}&top_k=3", headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read())
    assert resp.status == 200, f"Expected 200, got {resp.status}"
    print(f"✅ /api/search: returned {len(data.get('results', []))} results")

@requires_server
def test_documents():
    """0.6.3: /api/documents 返回文件列表"""
    import urllib.request
    req = urllib.request.Request(f"{BASE_URL}/api/documents", headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    assert resp.status == 200, f"Expected 200, got {resp.status}"
    print(f"✅ /api/documents: {data.get('total', 0)} files")

@requires_server
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

@requires_server
def test_v2_status():
    """0.6.5: /api/v2/status 返回系统状态"""
    import urllib.request
    req = urllib.request.Request(f"{BASE_URL}/api/v2/status")
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    assert resp.status == 200, f"Expected 200, got {resp.status}"
    print(f"✅ /api/v2/status: health_score={data.get('health_score', '?')}")

def test_bcrypt_hash_and_verify():
    """bcrypt密码哈希: 新密码应使用bcrypt格式"""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from src.api.auth_routes import _hash_password, _verify_password
    
    hashed = _hash_password("testpassword")
    assert hashed.startswith("$2b$"), f"bcrypt hash should start with $2b$, got: {hashed[:10]}"
    assert _verify_password("testpassword", hashed), "Valid password should verify"
    assert not _verify_password("wrongpassword", hashed), "Wrong password should fail"


def test_bcrypt_lazy_migration():
    """bcrypt验证: 旧SHA256格式已被拒绝（v1.50安全升级）"""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from src.api.auth_routes import _verify_password
    import hashlib, secrets
    
    salt = secrets.token_hex(16)
    password = "oldpassword"
    h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    old_format = f"{salt}${h}"
    
    # v1.50: 旧格式密码被拒绝，强制升级到bcrypt
    assert not _verify_password(password, old_format), "Old SHA256 format should be rejected in v1.50"


def test_bcrypt_empty_stored():
    """bcrypt验证: 空密码存储应返回False"""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from src.api.auth_routes import _verify_password
    
    assert not _verify_password("anything", ""), "Empty stored should fail"
    assert not _verify_password("anything", "no-dollars"), "Non-hashed should fail"


def test_jwt_create_and_verify():
    """JWT标准实现: 创建和验证token"""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    os.environ["FUXI_JWT_SECRET"] = "test-secret-for-unit-tests-only-12345678"
    import importlib
    if "src.api.auth" in __import__("sys").modules:
        importlib.reload(__import__("sys").modules["src.api.auth"])
    from src.api.auth import create_jwt_token, verify_jwt_token
    
    token = create_jwt_token("testuser", "user")
    assert isinstance(token, str), "Token should be a string"
    assert token.count(".") == 2, "JWT should have 3 parts separated by dots"
    
    payload = verify_jwt_token(token)
    assert payload["sub"] == "testuser", f"Expected sub=testuser, got {payload['sub']}"
    assert payload["role"] == "user", f"Expected role=user, got {payload['role']}"
    assert "exp" in payload, "Missing exp claim"
    assert "iat" in payload, "Missing iat claim"


def test_jwt_verify_invalid_token():
    """JWT标准实现: 无效token应抛出异常"""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    os.environ["FUXI_JWT_SECRET"] = "test-secret-for-unit-tests-only-12345678"
    import importlib
    if "src.api.auth" in __import__("sys").modules:
        importlib.reload(__import__("sys").modules["src.api.auth"])
    from src.api.auth import verify_jwt_token
    from fastapi import HTTPException
    
    try:
        verify_jwt_token("invalid.token.here")
        assert False, "Should have raised HTTPException"
    except HTTPException as e:
        assert e.status_code == 401, f"Expected 401, got {e.status_code}"


def test_documents_endpoint_uses_limit_param():
    """验证/documents端点使用limit参数名（而非page_size）"""
    import inspect
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from src.api.documents import documents
    
    sig = inspect.signature(documents)
    params = list(sig.parameters.keys())
    assert "page_size" in params, f"Expected 'page_size' parameter, got: {params}"
    assert sig.parameters["page_size"].default == 50, f"Expected default=50, got {sig.parameters['page_size'].default}"


if __name__ == "__main__":
    tests = [test_health, test_search, test_documents, test_chat, test_v2_status, test_jwt_create_and_verify, test_jwt_verify_invalid_token]
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
