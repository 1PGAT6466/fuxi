#!/usr/bin/env python3
"""
伏羲 v1.50 API 全面测试脚本
=============================
测试范围：
1. API 接口清单 — 完整端点测试
2. 前后端匹配度 — 前端调用 vs 后端实现
3. 接口功能测试 — 正常/异常/边界/权限
4. 性能测试 — 响应时间/并发
5. 安全测试 — 认证/授权/输入校验/SQL注入
"""

import os
import sys
import json
import time
import hashlib
import asyncio
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

# Load .env
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient
from src.server import app

client = TestClient(app)

# ─── Test result tracking ───
@dataclass
class TestResult:
    endpoint: str
    method: str
    name: str
    status: str = "SKIP"  # PASS, FAIL, WARN, SKIP
    response_code: int = 0
    response_time_ms: float = 0.0
    detail: str = ""
    expected: str = ""
    actual: str = ""

results: list[TestResult] = []

def add_result(method, endpoint, name, status, code, rt, detail="", expected="", actual=""):
    results.append(TestResult(
        endpoint=endpoint, method=method, name=name,
        status=status, response_code=code, response_time_ms=rt,
        detail=detail, expected=expected, actual=actual
    ))
    status_icon = "✅" if status == "PASS" else ("⚠️" if status == "WARN" else "❌")
    print(f"  {status_icon} {method:6s} {endpoint:40s} → {code} in {rt:.0f}ms {detail}")

def get_auth_header(token=None):
    if token is None:
        # Login to get token
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "fuxi2024"})
        if resp.status_code == 200:
            token = resp.json().get("token", "")
    return {"Authorization": f"Bearer {token}"}

# ══════════════════════════════════════════════════════
# Section 1: API 接口清单完整测试
# ══════════════════════════════════════════════════════

def test_health():
    """GET /api/health — 健康检查（无需认证）"""
    method, endpoint = "GET", "/api/health"
    t0 = time.time()
    resp = client.get(endpoint)
    rt = (time.time() - t0) * 1000

    issues = []
    if resp.status_code != 200:
        add_result(method, endpoint, "健康检查", "FAIL", resp.status_code, rt, f"Expected 200")
        return

    data = resp.json()
    if "status" not in data:
        issues.append("Missing 'status' field")

    status = "PASS" if not issues else "WARN"
    add_result(method, endpoint, "健康检查", status, resp.status_code, rt, "; ".join(issues) if issues else "OK")

def test_auth_login_normal():
    """POST /api/auth/login — 正常登录"""
    method, endpoint = "POST", "/api/auth/login"
    t0 = time.time()
    resp = client.post(endpoint, json={"username": "admin", "password": "fuxi2024"})
    rt = (time.time() - t0) * 1000

    issues = []
    if resp.status_code != 200:
        add_result(method, endpoint, "登录-正常", "FAIL", resp.status_code, rt, f"Expected 200")
        return
    data = resp.json()
    for field in ["token", "username", "role"]:
        if field not in data:
            issues.append(f"Missing '{field}'")
    if data.get("role") != "admin":
        issues.append(f"Expected role=admin, got {data.get('role')}")

    status = "PASS" if not issues else "WARN"
    add_result(method, endpoint, "登录-正常", status, resp.status_code, rt, "; ".join(issues) if issues else f"user={data.get('username')}")

def test_auth_login_wrong_pw():
    """POST /api/auth/login — 错误密码"""
    method, endpoint = "POST", "/api/auth/login"
    t0 = time.time()
    resp = client.post(endpoint, json={"username": "admin", "password": "wrong"})
    rt = (time.time() - t0) * 1000

    if resp.status_code == 401:
        add_result(method, endpoint, "登录-错误密码", "PASS", resp.status_code, rt, "Correctly rejected")
    else:
        add_result(method, endpoint, "登录-错误密码", "FAIL", resp.status_code, rt, f"Expected 401, got {resp.status_code}")

def test_auth_login_invalid_input():
    """POST /api/auth/login — 无效输入"""
    method, endpoint = "POST", "/api/auth/login"

    # Short username
    t0 = time.time()
    resp = client.post(endpoint, json={"username": "ab", "password": "fuxi2024"})
    rt = (time.time() - t0) * 1000
    if resp.status_code == 422:
        add_result(method, endpoint, "登录-用户名过短", "PASS", resp.status_code, rt, "Validation rejected 2-char username")
    else:
        add_result(method, endpoint, "登录-用户名过短", "WARN", resp.status_code, rt, f"Expected 422, got {resp.status_code}")

    # Special chars in username
    t0 = time.time()
    resp = client.post(endpoint, json={"username": "admin';DROP TABLE users;--", "password": "fuxi2024"})
    rt = (time.time() - t0) * 1000
    if resp.status_code == 422:
        add_result(method, endpoint, "登录-SQL注入用户", "PASS", resp.status_code, rt, "Input validation rejected")
    else:
        add_result(method, endpoint, "登录-SQL注入用户", "WARN", resp.status_code, rt, f"Expected 422, got {resp.status_code}")

    # Missing fields
    t0 = time.time()
    resp = client.post(endpoint, json={"username": "admin"})
    rt = (time.time() - t0) * 1000
    if resp.status_code == 422:
        add_result(method, endpoint, "登录-缺少密码", "PASS", resp.status_code, rt, "Validation rejected")
    else:
        add_result(method, endpoint, "登录-缺少密码", "WARN", resp.status_code, rt, f"Expected 422, got {resp.status_code}")

def test_auth_login_nonexistent():
    """POST /api/auth/login — 不存在的用户"""
    method, endpoint = "POST", "/api/auth/login"
    t0 = time.time()
    resp = client.post(endpoint, json={"username": "nonexistent123", "password": "fuxi2024"})
    rt = (time.time() - t0) * 1000
    if resp.status_code == 401:
        add_result(method, endpoint, "登录-不存在用户", "PASS", resp.status_code, rt, "Correctly rejected")
    else:
        add_result(method, endpoint, "登录-不存在用户", "FAIL", resp.status_code, rt, f"Expected 401, got {resp.status_code}")

def test_auth_register_normal():
    """POST /api/auth/register — 正常注册"""
    method, endpoint = "POST", "/api/auth/register"
    import random
    test_user = f"testuser_{random.randint(10000, 99999)}"

    t0 = time.time()
    resp = client.post(endpoint, json={"username": test_user, "password": "test123456"})
    rt = (time.time() - t0) * 1000

    issues = []
    if resp.status_code != 200:
        add_result(method, endpoint, "注册-正常", "FAIL", resp.status_code, rt, f"Expected 200, got {resp.status_code}")
        return
    data = resp.json()
    if data.get("ok") != True:
        issues.append("Missing 'ok' field")
    if data.get("username") != test_user:
        issues.append(f"Username mismatch: expected {test_user}, got {data.get('username')}")

    status = "PASS" if not issues else "WARN"
    add_result(method, endpoint, "注册-正常", status, resp.status_code, rt, "; ".join(issues) if issues else f"Created {test_user}")

def test_auth_register_duplicate():
    """POST /api/auth/register — 重复注册"""
    method, endpoint = "POST", "/api/auth/register"
    t0 = time.time()
    resp = client.post(endpoint, json={"username": "admin", "password": "fuxi2024"})
    rt = (time.time() - t0) * 1000
    if resp.status_code == 400:
        add_result(method, endpoint, "注册-重复用户", "PASS", resp.status_code, rt, "Correctly rejected duplicate")
    else:
        add_result(method, endpoint, "注册-重复用户", "FAIL", resp.status_code, rt, f"Expected 400, got {resp.status_code}")

def test_auth_me():
    """GET /api/auth/me — 获取当前用户"""
    method, endpoint = "GET", "/api/auth/me"
    # Login first
    login_resp = client.post("/api/auth/login", json={"username": "admin", "password": "fuxi2024"})
    token = login_resp.json().get("token", "")

    t0 = time.time()
    resp = client.get(endpoint, headers={"Authorization": f"Bearer {token}"})
    rt = (time.time() - t0) * 1000

    issues = []
    if resp.status_code != 200:
        add_result(method, endpoint, "获取当前用户", "FAIL", resp.status_code, rt, f"Expected 200")
        return
    data = resp.json()
    for field in ["username", "role"]:
        if field not in data:
            issues.append(f"Missing '{field}'")
    if data.get("username") != "admin":
        issues.append(f"Expected username=admin, got {data.get('username')}")

    status = "PASS" if not issues else "WARN"
    add_result(method, endpoint, "获取当前用户", status, resp.status_code, rt, "; ".join(issues) if issues else f"user={data.get('username')}")

def test_auth_me_no_token():
    """GET /api/auth/me — 无Token访问"""
    method, endpoint = "GET", "/api/auth/me"
    t0 = time.time()
    resp = client.get(endpoint)
    rt = (time.time() - t0) * 1000
    # /api/auth/me 不在白名单，应该被 AuthMiddleware 拦截
    if resp.status_code == 401:
        add_result(method, endpoint, "获取用户-无Token", "PASS", resp.status_code, rt, "Correctly rejected")
    elif resp.status_code == 200:
        add_result(method, endpoint, "获取用户-无Token", "FAIL", resp.status_code, rt, "Should require auth but returned 200")
    else:
        add_result(method, endpoint, "获取用户-无Token", "WARN", resp.status_code, rt, f"Got {resp.status_code}")

def test_search_normal():
    """GET /api/search — 正常搜索"""
    method, endpoint = "GET", "/api/search?q=test&top_k=10"
    headers = get_auth_header()
    t0 = time.time()
    resp = client.get(endpoint, headers=headers)
    rt = (time.time() - t0) * 1000

    issues = []
    if resp.status_code != 200:
        add_result(method, endpoint, "搜索-正常", "FAIL", resp.status_code, rt, f"Expected 200")
        return
    data = resp.json()
    for field in ["wiki_results", "chunk_results", "query"]:
        if field not in data:
            issues.append(f"Missing '{field}'")

    status = "PASS" if not issues else "WARN"
    add_result(method, endpoint, "搜索-正常", status, resp.status_code, rt, "; ".join(issues) if issues else f"total={data.get('total',0)}")

def test_search_no_query():
    """GET /api/search — 缺少查询参数"""
    method, endpoint = "GET", "/api/search"
    headers = get_auth_header()
    t0 = time.time()
    resp = client.get(endpoint, headers=headers)
    rt = (time.time() - t0) * 1000
    # q 是必填参数 (Query(...))
    if resp.status_code == 422:
        add_result(method, endpoint, "搜索-缺少查询", "PASS", resp.status_code, rt, "Validation rejected")
    else:
        add_result(method, endpoint, "搜索-缺少查询", "WARN", resp.status_code, rt, f"Expected 422, got {resp.status_code}")

def test_search_no_auth():
    """GET /api/search — 无认证"""
    method, endpoint = "GET", "/api/search?q=test"
    t0 = time.time()
    resp = client.get(endpoint)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 401:
        add_result(method, endpoint, "搜索-无认证", "PASS", resp.status_code, rt, "Required auth rejected")
    else:
        add_result(method, endpoint, "搜索-无认证", "FAIL", resp.status_code, rt, f"Expected 401, got {resp.status_code}")

def test_search_sql_injection():
    """GET /api/search — SQL注入测试"""
    method, endpoint = "GET", "/api/search?q=';DROP TABLE chunks;--&top_k=10"
    headers = get_auth_header()
    t0 = time.time()
    resp = client.get(endpoint, headers=headers)
    rt = (time.time() - t0) * 1000
    # Should handle gracefully (return results or empty), not crash
    if resp.status_code in (200, 400):
        add_result(method, endpoint, "搜索-SQL注入", "PASS", resp.status_code, rt, "Handled gracefully")
    elif resp.status_code == 500:
        add_result(method, endpoint, "搜索-SQL注入", "FAIL", resp.status_code, rt, "Server error on SQL injection!")
    else:
        add_result(method, endpoint, "搜索-SQL注入", "WARN", resp.status_code, rt, f"Unexpected {resp.status_code}")

def test_search_history():
    """GET /api/search-history — 搜索历史"""
    method, endpoint = "GET", "/api/search-history"
    headers = get_auth_header()
    t0 = time.time()
    resp = client.get(endpoint, headers=headers)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 200:
        add_result(method, endpoint, "搜索历史", "PASS", resp.status_code, rt, "OK (empty)")
    else:
        add_result(method, endpoint, "搜索历史", "FAIL", resp.status_code, rt, f"Expected 200, got {resp.status_code}")

def test_chat_normal():
    """POST /api/chat — 正常对话"""
    method, endpoint = "POST", "/api/chat"
    headers = get_auth_header()
    headers["Content-Type"] = "application/json"
    t0 = time.time()
    resp = client.post(endpoint, json={"query": "测试问题", "history": []}, headers=headers)
    rt = (time.time() - t0) * 1000

    if resp.status_code == 503:
        # 伏羲未就绪 (no LLM configured)
        add_result(method, endpoint, "对话-正常", "WARN", resp.status_code, rt, "Fuxi not ready (no LLM) - expected in test env")
    elif resp.status_code == 200:
        data = resp.json()
        issues = []
        for field in ["answer", "sources", "mode"]:
            if field not in data:
                issues.append(f"Missing '{field}'")
        status = "PASS" if not issues else "WARN"
        add_result(method, endpoint, "对话-正常", status, resp.status_code, rt, "; ".join(issues) if issues else f"mode={data.get('mode')}")
    else:
        add_result(method, endpoint, "对话-正常", "FAIL", resp.status_code, rt, f"Unexpected {resp.status_code}")

def test_chat_no_auth():
    """POST /api/chat — 无认证"""
    method, endpoint = "POST", "/api/chat"
    t0 = time.time()
    resp = client.post(endpoint, json={"query": "test"})
    rt = (time.time() - t0) * 1000
    if resp.status_code == 401:
        add_result(method, endpoint, "对话-无认证", "PASS", resp.status_code, rt, "Required auth rejected")
    else:
        add_result(method, endpoint, "对话-无认证", "FAIL", resp.status_code, rt, f"Expected 401, got {resp.status_code}")

def test_chat_empty_query():
    """POST /api/chat — 空查询"""
    method, endpoint = "POST", "/api/chat"
    headers = get_auth_header()
    headers["Content-Type"] = "application/json"
    t0 = time.time()
    resp = client.post(endpoint, json={"query": "", "history": []}, headers=headers)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 422:
        add_result(method, endpoint, "对话-空查询", "PASS", resp.status_code, rt, "Validation rejected empty query")
    elif resp.status_code in (200, 503):
        add_result(method, endpoint, "对话-空查询", "WARN", resp.status_code, rt, f"Empty query accepted ({resp.status_code})")
    else:
        add_result(method, endpoint, "对话-空查询", "WARN", resp.status_code, rt, f"Unexpected {resp.status_code}")

def test_chat_agent():
    """POST /api/chat/agent — Agent对话"""
    method, endpoint = "POST", "/api/chat/agent"
    headers = get_auth_header()
    headers["Content-Type"] = "application/json"
    t0 = time.time()
    resp = client.post(endpoint, json={"query": "test", "history": []}, headers=headers)
    rt = (time.time() - t0) * 1000
    if resp.status_code in (200, 503):
        add_result(method, endpoint, "Agent对话", "PASS", resp.status_code, rt, f"Returned {resp.status_code}")
    else:
        add_result(method, endpoint, "Agent对话", "FAIL", resp.status_code, rt, f"Expected 200/503, got {resp.status_code}")

def test_documents_list():
    """GET /api/documents — 文档列表"""
    method, endpoint = "GET", "/api/documents"
    headers = get_auth_header()
    t0 = time.time()
    resp = client.get(endpoint, headers=headers)
    rt = (time.time() - t0) * 1000

    issues = []
    if resp.status_code != 200:
        add_result(method, endpoint, "文档列表", "FAIL", resp.status_code, rt, f"Expected 200")
        return
    data = resp.json()
    for field in ["files", "total"]:
        if field not in data:
            issues.append(f"Missing '{field}'")

    status = "PASS" if not issues else "WARN"
    add_result(method, endpoint, "文档列表", status, resp.status_code, rt, f"total={data.get('total',0)}")

def test_documents_no_auth():
    """GET /api/documents — 无认证"""
    method, endpoint = "GET", "/api/documents"
    t0 = time.time()
    resp = client.get(endpoint)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 401:
        add_result(method, endpoint, "文档列表-无认证", "PASS", resp.status_code, rt, "Required auth rejected")
    else:
        add_result(method, endpoint, "文档列表-无认证", "FAIL", resp.status_code, rt, f"Expected 401, got {resp.status_code}")

def test_documents_delete():
    """DELETE /api/documents/{hash} — 删除不存在的文档"""
    method, endpoint = "DELETE", "/api/documents/nonexistent_hash_12345"
    headers = get_auth_header()
    t0 = time.time()
    resp = client.delete(endpoint, headers=headers)
    rt = (time.time() - t0) * 1000
    if resp.status_code in (200, 404):
        data = resp.json()
        add_result(method, endpoint, "文档删除", "PASS", resp.status_code, rt, f"removed={data.get('removed',0)}")
    else:
        add_result(method, endpoint, "文档删除", "FAIL", resp.status_code, rt, f"Unexpected {resp.status_code}")

def test_documents_export():
    """GET /api/documents/export — 导出文档"""
    method, endpoint = "GET", "/api/documents/export"
    headers = get_auth_header()
    t0 = time.time()
    resp = client.get(endpoint, headers=headers)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 200:
        content_type = resp.headers.get("content-type", "")
        if "csv" in content_type:
            add_result(method, endpoint, "文档导出", "PASS", resp.status_code, rt, "CSV returned")
        else:
            add_result(method, endpoint, "文档导出", "WARN", resp.status_code, rt, f"Content-Type: {content_type}")
    else:
        add_result(method, endpoint, "文档导出", "FAIL", resp.status_code, rt, f"Expected 200, got {resp.status_code}")

def test_graph_normal():
    """GET /api/graph — 知识图谱查询"""
    method, endpoint = "GET", "/api/graph"
    headers = get_auth_header()
    t0 = time.time()
    resp = client.get(endpoint, headers=headers)
    rt = (time.time() - t0) * 1000

    issues = []
    if resp.status_code != 200:
        add_result(method, endpoint, "知识图谱", "FAIL", resp.status_code, rt, f"Expected 200")
        return
    data = resp.json()
    for field in ["nodes", "edges"]:
        if field not in data:
            issues.append(f"Missing '{field}'")

    status = "PASS" if not issues else "WARN"
    add_result(method, endpoint, "知识图谱", status, resp.status_code, rt, f"nodes={len(data.get('nodes',{}))}")

def test_graph_no_auth():
    """GET /api/graph — 无认证"""
    method, endpoint = "GET", "/api/graph"
    t0 = time.time()
    resp = client.get(endpoint)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 401:
        add_result(method, endpoint, "知识图谱-无认证", "PASS", resp.status_code, rt, "Required auth rejected")
    else:
        add_result(method, endpoint, "知识图谱-无认证", "FAIL", resp.status_code, rt, f"Expected 401, got {resp.status_code}")

def test_wiki_pages():
    """GET /api/wiki/pages — Wiki页面列表"""
    method, endpoint = "GET", "/api/wiki/pages"
    headers = get_auth_header()
    t0 = time.time()
    resp = client.get(endpoint, headers=headers)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 200:
        add_result(method, endpoint, "Wiki页面", "PASS", resp.status_code, rt, "OK (empty)")
    else:
        add_result(method, endpoint, "Wiki页面", "FAIL", resp.status_code, rt, f"Expected 200, got {resp.status_code}")

def test_wiki_search():
    """GET /api/wiki/search — Wiki搜索"""
    method, endpoint = "GET", "/api/wiki/search?q=test"
    headers = get_auth_header()
    t0 = time.time()
    resp = client.get(endpoint, headers=headers)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 200:
        add_result(method, endpoint, "Wiki搜索", "PASS", resp.status_code, rt, "OK (empty)")
    else:
        add_result(method, endpoint, "Wiki搜索", "FAIL", resp.status_code, rt, f"Expected 200, got {resp.status_code}")

def test_wiki_page_detail():
    """GET /api/wiki/page/{page_id} — Wiki页面详情"""
    method, endpoint = "GET", "/api/wiki/page/test_page"
    headers = get_auth_header()
    t0 = time.time()
    resp = client.get(endpoint, headers=headers)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 200:
        add_result(method, endpoint, "Wiki详情", "PASS", resp.status_code, rt, "OK")
    else:
        add_result(method, endpoint, "Wiki详情", "FAIL", resp.status_code, rt, f"Expected 200, got {resp.status_code}")

def test_admin_stats():
    """GET /api/admin/stats — 管理统计"""
    method, endpoint = "GET", "/api/admin/stats"
    headers = get_auth_header()
    t0 = time.time()
    resp = client.get(endpoint, headers=headers)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 200:
        add_result(method, endpoint, "管理统计", "PASS", resp.status_code, rt, "OK")
    else:
        add_result(method, endpoint, "管理统计", "FAIL", resp.status_code, rt, f"Expected 200, got {resp.status_code}")

def test_admin_server_status():
    """GET /api/admin/server-status — 服务器状态"""
    method, endpoint = "GET", "/api/admin/server-status"
    headers = get_auth_header()
    t0 = time.time()
    resp = client.get(endpoint, headers=headers)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 200:
        data = resp.json()
        if "uptime_seconds" in data:
            add_result(method, endpoint, "服务器状态", "PASS", resp.status_code, rt, f"uptime={data.get('uptime_seconds')}s")
        else:
            add_result(method, endpoint, "服务器状态", "WARN", resp.status_code, rt, "Missing uptime")
    else:
        add_result(method, endpoint, "服务器状态", "FAIL", resp.status_code, rt, f"Expected 200, got {resp.status_code}")

def test_metrics_summary():
    """GET /api/admin/metrics-summary — 可观测性指标"""
    method, endpoint = "GET", "/api/admin/metrics-summary"
    headers = get_auth_header()
    t0 = time.time()
    resp = client.get(endpoint, headers=headers)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 200:
        add_result(method, endpoint, "指标摘要", "PASS", resp.status_code, rt, "OK")
    else:
        add_result(method, endpoint, "指标摘要", "FAIL", resp.status_code, rt, f"Expected 200, got {resp.status_code}")

def test_dashboard():
    """GET /api/dashboard — 仪表板"""
    method, endpoint = "GET", "/api/dashboard"
    headers = get_auth_header()
    t0 = time.time()
    resp = client.get(endpoint, headers=headers)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 200:
        add_result(method, endpoint, "仪表板", "PASS", resp.status_code, rt, "OK")
    else:
        add_result(method, endpoint, "仪表板", "FAIL", resp.status_code, rt, f"Expected 200, got {resp.status_code}")

def test_evaluation_overview():
    """GET /api/evaluation/overview — 评测概览"""
    method, endpoint = "GET", "/api/evaluation/overview"
    headers = get_auth_header()
    t0 = time.time()
    resp = client.get(endpoint, headers=headers)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 200:
        add_result(method, endpoint, "评测概览", "PASS", resp.status_code, rt, "OK")
    else:
        add_result(method, endpoint, "评测概览", "FAIL", resp.status_code, rt, f"Expected 200, got {resp.status_code}")

def test_evolution_overview():
    """GET /api/evolution/overview — 进化概览"""
    method, endpoint = "GET", "/api/evolution/overview"
    headers = get_auth_header()
    t0 = time.time()
    resp = client.get(endpoint, headers=headers)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 200:
        add_result(method, endpoint, "进化概览", "PASS", resp.status_code, rt, "OK")
    else:
        add_result(method, endpoint, "进化概览", "FAIL", resp.status_code, rt, f"Expected 200, got {resp.status_code}")

def test_feedback_post():
    """POST /api/feedback — 提交反馈"""
    method, endpoint = "POST", "/api/feedback"
    headers = get_auth_header()
    headers["Content-Type"] = "application/json"
    t0 = time.time()
    resp = client.post(endpoint, json={"query": "test", "answer": "test answer", "rating": 5}, headers=headers)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 200:
        add_result(method, endpoint, "提交反馈", "PASS", resp.status_code, rt, "OK")
    else:
        add_result(method, endpoint, "提交反馈", "FAIL", resp.status_code, rt, f"Expected 200, got {resp.status_code}")

def test_feedback_weekly():
    """GET /api/feedback/weekly — 每周反馈"""
    method, endpoint = "GET", "/api/feedback/weekly"
    headers = get_auth_header()
    t0 = time.time()
    resp = client.get(endpoint, headers=headers)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 200:
        add_result(method, endpoint, "每周反馈", "PASS", resp.status_code, rt, "OK")
    else:
        add_result(method, endpoint, "每周反馈", "FAIL", resp.status_code, rt, f"Expected 200, got {resp.status_code}")

def test_features_flags_list():
    """GET /api/feature-flags — Feature Flag列表"""
    method, endpoint = "GET", "/api/feature-flags"
    headers = get_auth_header()
    t0 = time.time()
    resp = client.get(endpoint, headers=headers)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 200:
        add_result(method, endpoint, "Feature Flags", "PASS", resp.status_code, rt, "OK")
    else:
        add_result(method, endpoint, "Feature Flags", "FAIL", resp.status_code, rt, f"Expected 200, got {resp.status_code}")

def test_features_flags_update():
    """PUT /api/feature-flags/{name} — 更新Feature Flag"""
    method, endpoint = "PUT", "/api/feature-flags/shaoyang_sag_extract"
    headers = get_auth_header()
    headers["Content-Type"] = "application/json"
    t0 = time.time()
    resp = client.put(endpoint, json={"value": True}, headers=headers)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 200:
        add_result(method, endpoint, "更新Feature Flag", "PASS", resp.status_code, rt, "OK")
    else:
        add_result(method, endpoint, "更新Feature Flag", "FAIL", resp.status_code, rt, f"Expected 200, got {resp.status_code}")

def test_features_flags_unknown():
    """PUT /api/feature-flags/{name} — 未知Flag"""
    method, endpoint = "PUT", "/api/feature-flags/unknown_flag"
    headers = get_auth_header()
    headers["Content-Type"] = "application/json"
    t0 = time.time()
    resp = client.put(endpoint, json={"value": True}, headers=headers)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 404:
        add_result(method, endpoint, "未知Feature Flag", "PASS", resp.status_code, rt, "Correctly rejected")
    else:
        add_result(method, endpoint, "未知Feature Flag", "FAIL", resp.status_code, rt, f"Expected 404, got {resp.status_code}")

def test_system_stats():
    """GET /api/system/stats — 系统统计"""
    method, endpoint = "GET", "/api/system/stats"
    headers = get_auth_header()
    t0 = time.time()
    resp = client.get(endpoint, headers=headers)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 200:
        add_result(method, endpoint, "系统统计", "PASS", resp.status_code, rt, "OK")
    else:
        add_result(method, endpoint, "系统统计", "FAIL", resp.status_code, rt, f"Expected 200, got {resp.status_code}")

def test_cache_stats():
    """GET /api/cache/stats — 缓存统计"""
    method, endpoint = "GET", "/api/cache/stats"
    headers = get_auth_header()
    t0 = time.time()
    resp = client.get(endpoint, headers=headers)
    rt = (time.time() - t0) * 1000
    if resp.status_code == 200:
        add_result(method, endpoint, "缓存统计", "PASS", resp.status_code, rt, "OK")
    else:
        add_result(method, endpoint, "缓存统计", "FAIL", resp.status_code, rt, f"HTTP {resp.status_code}")


# ============ Main ============
if __name__ == "__main__":
    import sys
    # Run all test functions
    test_functions = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for func in test_functions:
        try:
            func()
        except Exception as e:
            print(f"Error in {func.__name__}: {e}")

    # Print results
    print("\n" + "=" * 60)
    print("API 测试结果汇总")
    print("=" * 60)
    for r in _results:
        status = "✓" if r["status"] == "PASS" else "✗"
        print(f"{status} {r['method']:6s} {r['endpoint']:30s} {r['detail']}")

    passed = sum(1 for r in _results if r["status"] == "PASS")
    total = len(_results)
    print(f"\n通过: {passed}/{total}")
    sys.exit(0 if passed == total else 1)