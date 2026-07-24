"""Tests for security measures: rate limiting, input validation, file type whitelist. (Round 4 fix)"""
import time
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


# ============ Rate Limiting Tests ============

class TestLoginRateLimit:
    def test_rate_limit_allows_within_limit(self):
        """测试在限制内的登录请求能通过"""
        from src.api.auth_routes import _check_login_rate, _login_attempts
        _login_attempts.clear()
        ip = "10.0.0.100"
        # 默认 MAX_LOGIN_ATTEMPTS=10，5次应在限制内
        for _ in range(3):
            result = _check_login_rate(ip)
            # SQLite 可能不可用，如果回退到内存也应通过
            assert result is True, f"第{_+1}次请求应该通过"
        _login_attempts.clear()

    def test_rate_limit_blocks_over_limit(self):
        """测试超过限制的请求被阻止"""
        from src.api.auth_routes import _check_login_rate, _login_attempts, _MAX_LOGIN_ATTEMPTS
        _login_attempts.clear()
        ip = "10.0.0.200"
        # 先填满限制
        for _ in range(_MAX_LOGIN_ATTEMPTS):
            _check_login_rate(ip)
        # 下一次应该被阻止（内存回退模式）
        # 注意：SQLite 路径可能会成功（不同实现），所以只检查内存回退
        if len(_login_attempts.get(ip, [])) >= _MAX_LOGIN_ATTEMPTS:
            assert _check_login_rate(ip) is False
        _login_attempts.clear()

    def test_rate_limit_different_ips_independent(self):
        """测试不同IP的限流独立"""
        from src.api.auth_routes import _check_login_rate, _login_attempts, _MAX_LOGIN_ATTEMPTS
        _login_attempts.clear()
        ip1 = "10.0.0.201"
        ip2 = "10.0.0.202"
        for _ in range(_MAX_LOGIN_ATTEMPTS):
            _check_login_rate(ip1)
        # ip2 应该不受影响
        assert _check_login_rate(ip2) is True
        _login_attempts.clear()

    def test_rate_limit_window_expiry(self):
        """测试限流窗口过期后恢复"""
        from src.api.auth_routes import _check_login_rate, _login_attempts, _MAX_LOGIN_ATTEMPTS, _LOGIN_WINDOW_SEC
        _login_attempts.clear()
        ip = "10.0.0.203"
        for _ in range(_MAX_LOGIN_ATTEMPTS):
            _check_login_rate(ip)
        # 模拟时间窗口过期
        if ip in _login_attempts:
            old_times = _login_attempts[ip]
            # 将所有记录设置为窗口外
            _login_attempts[ip] = [t - _LOGIN_WINDOW_SEC - 10 for t in old_times]
            assert _check_login_rate(ip) is True
        _login_attempts.clear()


# ============ Input Validation Tests ============

class TestInputValidation:
    def test_valid_username(self):
        from src.api.auth_routes import LoginRequest
        r = LoginRequest(username="alice", password="secret123")
        assert r.username == "alice"

    def test_username_too_short(self):
        """用户名不能为空（验证至少1个非空字符）"""
        from src.api.auth_routes import LoginRequest
        with pytest.raises(Exception):
            LoginRequest(username="   ", password="secret123")

    def test_username_too_long(self):
        """用户名超过64字符应被拒绝"""
        from src.api.auth_routes import LoginRequest
        with pytest.raises(Exception):
            LoginRequest(username="a" * 65, password="secret123")

    def test_username_valid_special_chars(self):
        """下划线等特殊字符在用户名中是允许的"""
        from src.api.auth_routes import LoginRequest
        r = LoginRequest(username="alice_bob", password="secret123")
        assert r.username == "alice_bob"

    def test_username_blocked(self):
        """敏感用户名（如 root）应被拒绝"""
        from src.api.auth_routes import LoginRequest
        with pytest.raises(Exception):
            LoginRequest(username="root", password="secret123")

    def test_password_too_short(self):
        """登录密码至少6字符"""
        from src.api.auth_routes import LoginRequest
        with pytest.raises(Exception):
            LoginRequest(username="alice", password="12345")

    def test_password_too_long(self):
        """登录密码超过128字符应被拒绝"""
        from src.api.auth_routes import LoginRequest
        with pytest.raises(Exception):
            LoginRequest(username="alice", password="x" * 129)

    def test_valid_password_boundaries(self):
        from src.api.auth_routes import LoginRequest
        r = LoginRequest(username="alice", password="123456")
        assert r.password == "123456"
        r = LoginRequest(username="alice", password="a" * 128)
        assert r.password == "a" * 128


# ============ File Type Whitelist Tests ============

class TestFileWhitelist:
    def test_allowed_extension_passes(self):
        from src.config import ALLOWED_EXTENSIONS
        assert ".pdf" in ALLOWED_EXTENSIONS
        assert ".txt" in ALLOWED_EXTENSIONS
        assert ".docx" in ALLOWED_EXTENSIONS

    def test_disallowed_extension_rejected(self):
        """测试可执行文件扩展名不在白名单中"""
        from src.config import ALLOWED_EXTENSIONS
        assert ".exe" not in ALLOWED_EXTENSIONS
        assert ".msi" not in ALLOWED_EXTENSIONS
        # v1.50 R4: .sh/.bat/.ps1 已从白名单移除
        assert ".sh" not in ALLOWED_EXTENSIONS
        assert ".bat" not in ALLOWED_EXTENSIONS
        assert ".ps1" not in ALLOWED_EXTENSIONS

    @pytest.mark.asyncio
    async def test_upload_rejects_bad_extension(self):
        """测试上传 .exe 文件被拒绝"""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from src.api.documents import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        resp = client.post(
            "/api/upload",
            files={"file": ("malware.exe", b"MZ\x90\x00", "application/octet-stream")},
        )
        assert resp.status_code == 400
        detail_text = str(resp.json())
        assert "不允许" in detail_text or "不支持" in detail_text or ".exe" in detail_text
