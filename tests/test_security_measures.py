"""Tests for security measures: rate limiting, input validation, file type whitelist."""
import time
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


# ============ Rate Limiting Tests ============

class TestLoginRateLimit:
    def test_rate_limit_allows_within_limit(self):
        from src.api.auth_routes import _check_login_rate, _login_attempts
        _login_attempts.clear()
        ip = "10.0.0.1"
        for _ in range(5):
            assert _check_login_rate(ip) is True
        _login_attempts.clear()

    def test_rate_limit_blocks_over_limit(self):
        from src.api.auth_routes import _check_login_rate, _login_attempts
        _login_attempts.clear()
        ip = "10.0.0.2"
        for _ in range(5):
            _check_login_rate(ip)
        assert _check_login_rate(ip) is False
        _login_attempts.clear()

    def test_rate_limit_different_ips_independent(self):
        from src.api.auth_routes import _check_login_rate, _login_attempts
        _login_attempts.clear()
        for _ in range(5):
            _check_login_rate("10.0.0.3")
        assert _check_login_rate("10.0.0.4") is True
        _login_attempts.clear()

    def test_rate_limit_window_expiry(self):
        from src.api.auth_routes import _check_login_rate, _login_attempts
        _login_attempts.clear()
        ip = "10.0.0.5"
        for _ in range(5):
            _check_login_rate(ip)
        assert _check_login_rate(ip) is False
        _login_attempts[ip] = [t - 61 for t in _login_attempts[ip]]
        assert _check_login_rate(ip) is True
        _login_attempts.clear()


# ============ Input Validation Tests ============

class TestInputValidation:
    def test_valid_username(self):
        from src.api.auth_routes import LoginRequest
        r = LoginRequest(username="alice", password="secret123")
        assert r.username == "alice"

    def test_username_too_short(self):
        from src.api.auth_routes import LoginRequest
        with pytest.raises(Exception):
            LoginRequest(username="ab", password="secret123")

    def test_username_too_long(self):
        from src.api.auth_routes import LoginRequest
        with pytest.raises(Exception):
            LoginRequest(username="a" * 21, password="secret123")

    def test_username_invalid_chars(self):
        from src.api.auth_routes import LoginRequest
        with pytest.raises(Exception):
            LoginRequest(username="alice@bob", password="secret123")

    def test_username_with_underscore(self):
        from src.api.auth_routes import LoginRequest
        r = LoginRequest(username="alice_bob", password="secret123")
        assert r.username == "alice_bob"

    def test_password_too_short(self):
        from src.api.auth_routes import LoginRequest
        with pytest.raises(Exception):
            LoginRequest(username="alice", password="12345")

    def test_password_too_long(self):
        from src.api.auth_routes import LoginRequest
        with pytest.raises(Exception):
            LoginRequest(username="alice", password="a" * 51)

    def test_valid_password_boundaries(self):
        from src.api.auth_routes import LoginRequest
        r = LoginRequest(username="alice", password="123456")
        assert r.password == "123456"
        r = LoginRequest(username="alice", password="a" * 50)
        assert r.password == "a" * 50


# ============ File Type Whitelist Tests ============

class TestFileWhitelist:
    def test_allowed_extension_passes(self):
        from src.config import ALLOWED_EXTENSIONS
        assert ".pdf" in ALLOWED_EXTENSIONS
        assert ".txt" in ALLOWED_EXTENSIONS
        assert ".docx" in ALLOWED_EXTENSIONS

    def test_disallowed_extension_rejected(self):
        from src.config import ALLOWED_EXTENSIONS
        assert ".exe" not in ALLOWED_EXTENSIONS
        assert ".bat" not in ALLOWED_EXTENSIONS  # v1.50 security fix: 可执行文件已禁止
        assert ".msi" not in ALLOWED_EXTENSIONS

    @pytest.mark.asyncio
    async def test_upload_rejects_bad_extension(self):
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
        assert "不支持" in resp.json()["detail"]
