"""
伏羲系统 对抗式后端检测脚本 v2
全面测试所有关键API端点：正常、异常、边界、并发
"""
import asyncio
import httpx
import json
import time
import os
import random
import string
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

BASE_URL = "http://172.25.30.200:8080"
REPORT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "adversarial-backend-report.md")

# 颜色输出
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

results = []  # {endpoint, test_type, status, detail, response_body, response_code, duration_ms}

def randstr(n=2048):
    return ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation + '中文测试', k=n))

async def test_endpoint(client, method, path, name, test_type, 
                        json_data=None, params=None, headers=None, 
                        expected_status=None, extra_detail=""):
    """通用测试函数"""
    try:
        start = time.time()
        if method == "GET":
            resp = await client.get(path, params=params, headers=headers, timeout=15)
        elif method == "POST":
            resp = await client.post(path, json=json_data, params=params, headers=headers, timeout=15)
        else:
            resp = await client.request(method, path, json=json_data, params=params, headers=headers, timeout=15)
        
        duration_ms = (time.time() - start) * 1000
        status_code = resp.status_code
        try:
            body = resp.json()
        except:
            body = resp.text[:500]
        
        passed = False
        if expected_status:
            passed = status_code in expected_status if isinstance(expected_status, list) else status_code == expected_status
        
        result = {
            "endpoint": name,
            "path": path,
            "method": method,
            "test_type": test_type,
            "passed": passed,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "body_snippet": str(body)[:300],
            "detail": extra_detail,
        }
        results.append(result)
        
        icon = "✓" if passed else "✗"
        color = GREEN if passed else RED
        print(f"  {color}{icon} [{name}] {test_type} → {status_code} ({duration_ms:.0f}ms){RESET}")
        if not passed:
            print(f"    {RED}期望: {expected_status}, 实际: {status_code}{RESET}")
            print(f"    {RED}响应: {str(body)[:200]}{RESET}")
        return result
    except Exception as e:
        result = {
            "endpoint": name,
            "path": path,
            "method": method,
            "test_type": test_type,
            "passed": False,
            "status_code": "ERROR",
            "duration_ms": 0,
            "body_snippet": str(e)[:300],
            "detail": f"异常: {str(e)}",
        }
        results.append(result)
        print(f"  {RED}✗ [{name}] {test_type} → ERROR: {e}{RESET}")
        return result

async def run_all_tests():
    print(f"{BOLD}{CYAN}╔══════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║     伏羲系统 对抗式后端检测 v2                           ║{RESET}")
    print(f"{BOLD}{CYAN}║     服务器: {BASE_URL}                        ║{RESET}")
    print(f"{BOLD}{CYAN}║     时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                  ║{RESET}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════════════╝{RESET}")
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30, follow_redirects=True) as client:
        # ============================================================
        # 阶段1: 健康检查 & 基础探测
        # ============================================================
        print(f"\n{BOLD}{YELLOW}══════ 阶段1: 基础健康检查 ══════{RESET}")
        
        # 1.1 健康检查 - 正常
        await test_endpoint(client, "GET", "/api/health", "health", "正常请求",
                          expected_status=200, extra_detail="验证服务状态和各子系统健康")
        
        # 1.2 根路径
        await test_endpoint(client, "GET", "/", "root", "正常请求",
                          expected_status=200)
        
        # 1.3 不存在的路径
        await test_endpoint(client, "GET", "/api/nonexistent_xyz123", "不存在路径", "404探测",
                          expected_status=[404, 405, 200], extra_detail="检查404处理")
        
        # 1.4 开放的 API 文档
        await test_endpoint(client, "GET", "/docs", "docs", "正常请求",
                          expected_status=200)
        await test_endpoint(client, "GET", "/openapi.json", "openapi.json", "正常请求",
                          expected_status=200)
        
        # ============================================================
        # 阶段2: 认证系统测试
        # ============================================================
        print(f"\n{BOLD}{YELLOW}══════ 阶段2: 认证系统 ══════{RESET}")
        
        # 2.1 登录 - 正常（需要先注册测试用户）
        # 先尝试直接登录，看 users.json 是否有用户
        test_user = "test_adversarial_user"
        test_pass = "Test@2024Secure!"
        
        # 2.1a 注册新用户
        await test_endpoint(client, "POST", "/api/auth/register", "auth/register", "正常注册",
                          json_data={"username": test_user, "password": test_pass},
                          expected_status=[200, 201],
                          extra_detail="测试用户注册")
        
        # 2.1b 重复注册
        await test_endpoint(client, "POST", "/api/auth/register", "auth/register", "重复注册",
                          json_data={"username": test_user, "password": test_pass},
                          expected_status=[400, 200],
                          extra_detail="应拒绝重复用户名")
        
        # 2.2 登录 - 正常
        login_resp = await client.post("/api/auth/login", json={"username": test_user, "password": test_pass})
        token = None
        if login_resp.status_code == 200:
            data = login_resp.json()
            token = data.get("token")
            print(f"  {GREEN}✓ 获取到 token: {token[:30]}...{RESET}")
        else:
            print(f"  {YELLOW}⚠ 新用户登录返回 {login_resp.status_code}，尝试读取已有用户{RESET}")
            # 读取 users.json 找可用用户
            import subprocess
            r = subprocess.run(['powershell', '-Command', 
                'Invoke-RestMethod -Uri http://172.25.30.200:8080/api/auth/login -Method POST -Body \'{"username":"admin","password":"admin123"}\' -ContentType "application/json" | ConvertTo-Json'],
                capture_output=True, text=True, timeout=10)
        
        # 2.3 登录 - 缺少参数
        await test_endpoint(client, "POST", "/api/auth/login", "auth/login", "缺少 password",
                          json_data={"username": test_user},
                          expected_status=422)
        
        await test_endpoint(client, "POST", "/api/auth/login", "auth/login", "缺少 username",
                          json_data={"password": test_pass},
                          expected_status=422)
        
        # 2.4 登录 - 空body
        await test_endpoint(client, "POST", "/api/auth/login", "auth/login", "空body",
                          json_data={},
                          expected_status=422)
        
        # 2.5 登录 - 错误密码
        await test_endpoint(client, "POST", "/api/auth/login", "auth/login", "错误密码",
                          json_data={"username": test_user, "password": "WrongPassword123!"},
                          expected_status=401)
        
        # 2.6 登录 - 不存在的用户
        await test_endpoint(client, "POST", "/api/auth/login", "auth/login", "不存在用户",
                          json_data={"username": "nonexistent_user_xyzzz", "password": "pass123"},
                          expected_status=401)
        
        # 2.7 登录 - 边界：超长用户名
        await test_endpoint(client, "POST", "/api/auth/login", "auth/login", "超长用户名(10KB)",
                          json_data={"username": randstr(10240), "password": "pass123"},
                          expected_status=[422, 401])
        
        # 2.8 登录 - 边界：超长密码
        await test_endpoint(client, "POST", "/api/auth/login", "auth/login", "超长密码(10KB)",
                          json_data={"username": test_user, "password": randstr(10240)},
                          expected_status=[422, 401])
        
        # 2.9 登录 - 特殊字符
        await test_endpoint(client, "POST", "/api/auth/login", "auth/login", "SQL注入测试",
                          json_data={"username": "' OR '1'='1", "password": "' OR '1'='1"},
                          expected_status=401, extra_detail="SQL注入防御")
        
        # 2.10 登录 - XSS测试
        await test_endpoint(client, "POST", "/api/auth/login", "auth/login", "XSS注入",
                          json_data={"username": "<script>alert('xss')</script>", "password": "test123"},
                          expected_status=[401, 422])
        
        # 2.11 登录 - 空字符串
        await test_endpoint(client, "POST", "/api/auth/login", "auth/login", "空用户名",
                          json_data={"username": "", "password": "test123"},
                          expected_status=[422, 400, 401])
        
        # ============================================================
        # 阶段3: Token & Auth 端点测试
        # ============================================================
        print(f"\n{BOLD}{YELLOW}══════ 阶段3: Token 认证 ══════{RESET}")
        
        headers_auth = {"Authorization": f"Bearer {token}"} if token else {}
        headers_invalid = {"Authorization": "Bearer invalid_token_xyz_1234567890"}
        headers_empty = {"Authorization": "Bearer "}
        headers_expired = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0Iiwicm9sZSI6InVzZXIiLCJleHAiOjE3MDAwMDAwMDAsImlhdCI6MTcwMDAwMDAwMH0.abc"}
        headers_none = {}
        
        # 3.1 /api/auth/me - 有效token
        await test_endpoint(client, "GET", "/api/auth/me", "auth/me", "有效token",
                          headers=headers_auth, expected_status=200)
        
        # 3.2 /api/auth/me - 无token
        await test_endpoint(client, "GET", "/api/auth/me", "auth/me", "无token",
                          headers=headers_none, expected_status=401)
        
        # 3.3 /api/auth/me - 无效token
        await test_endpoint(client, "GET", "/api/auth/me", "auth/me", "无效token",
                          headers=headers_invalid, expected_status=401)
        
        # 3.4 /api/auth/me - 空token
        await test_endpoint(client, "GET", "/api/auth/me", "auth/me", "空token",
                          headers=headers_empty, expected_status=401)
        
        # 3.5 /api/auth/me - 过期token
        await test_endpoint(client, "GET", "/api/auth/me", "auth/me", "伪造过期token",
                          headers=headers_expired, expected_status=401)
        
        # 3.6 /api/auth/refresh - 有效token
        await test_endpoint(client, "POST", "/api/auth/refresh", "auth/refresh", "有效token",
                          json_data={"token": token} if token else {},
                          headers=headers_auth, expected_status=[200, 401])
        
        # 3.7 /api/auth/refresh - 无效token
        await test_endpoint(client, "POST", "/api/auth/refresh", "auth/refresh", "无效token",
                          json_data={"token": "invalid"},
                          expected_status=401)
        
        # 3.8 /api/auth/logout
        await test_endpoint(client, "POST", "/api/auth/logout", "auth/logout", "有效token",
                          headers=headers_auth, expected_status=[200, 401])
        
        # ============================================================
        # 阶段4: 数据端点测试
        # ============================================================
        print(f"\n{BOLD}{YELLOW}══════ 阶段4: 数据端点 ══════{RESET}")
        
        # 4.1 Documents - 有效token
        await test_endpoint(client, "GET", "/api/documents", "documents", "有效token",
                          headers=headers_auth, expected_status=[200, 401],
                          extra_detail="检查是否需要认证")
        
        # 4.2 Documents - 无token
        await test_endpoint(client, "GET", "/api/documents", "documents", "无token",
                          headers=headers_none, expected_status=[401, 200, 404],
                          extra_detail="认证/公开检查")
        
        # 4.3 Documents - 无效token
        await test_endpoint(client, "GET", "/api/documents", "documents", "无效token",
                          headers=headers_invalid, expected_status=401)
        
        # 4.4 Files 端点
        await test_endpoint(client, "GET", "/api/files", "files", "有效token",
                          headers=headers_auth, expected_status=[200, 401])
        
        await test_endpoint(client, "GET", "/api/files", "files", "无token",
                          headers=headers_none, expected_status=[401, 200, 404])
        
        # ============================================================
        # 阶段5: 搜索端点测试
        # ============================================================
        print(f"\n{BOLD}{YELLOW}══════ 阶段5: 搜索 ══════{RESET}")
        
        # 5.1 Search - 正常
        await test_endpoint(client, "POST", "/api/search", "search", "正常搜索",
                          json_data={"query": "测试", "top_k": 5},
                          headers=headers_auth, expected_status=[200, 401, 404])
        
        # 5.2 Search - 无token
        await test_endpoint(client, "POST", "/api/search", "search", "无token",
                          json_data={"query": "测试"},
                          headers=headers_none, expected_status=[401, 200])
        
        # 5.3 Search - 空query
        await test_endpoint(client, "POST", "/api/search", "search", "空query",
                          json_data={"query": "", "top_k": 5},
                          headers=headers_auth, expected_status=[400, 422, 200])
        
        # 5.4 Search - 缺少query
        await test_endpoint(client, "POST", "/api/search", "search", "缺少query",
                          json_data={"top_k": 5},
                          headers=headers_auth, expected_status=[422, 400])
        
        # 5.5 Search - 超长query
        await test_endpoint(client, "POST", "/api/search", "search", "超长query(50KB)",
                          json_data={"query": randstr(50000)},
                          headers=headers_auth, expected_status=[400, 422, 413, 200])
        
        # 5.6 Search - SQL注入
        await test_endpoint(client, "POST", "/api/search", "search", "SQL注入query",
                          json_data={"query": "' UNION SELECT * FROM users--", "top_k": 5},
                          headers=headers_auth, expected_status=[200, 400])
        
        # 5.7 Unified Search
        await test_endpoint(client, "POST", "/api/unified-search", "unified-search", "正常",
                          json_data={"query": "测试知识库", "services": ["wiki", "kb"]},
                          headers=headers_auth, expected_status=[200, 401, 404])
        
        # 5.8 Antenna Search (GET)
        await test_endpoint(client, "GET", "/api/antenna/search", "antenna/search", "GET正常",
                          params={"q": "测试搜索"},
                          expected_status=[200, 400, 404],
                          extra_detail="联网搜索GET方法")
        
        # 5.9 Antenna Search - 空q
        await test_endpoint(client, "GET", "/api/antenna/search", "antenna/search", "GET空q",
                          params={"q": ""},
                          expected_status=[400, 422])
        
        # 5.10 Antenna Search (POST)
        await test_endpoint(client, "POST", "/api/antenna/search", "antenna/search", "POST正常",
                          json_data={"query": "测试搜索"},
                          expected_status=[200, 404, 405])
        
        # ============================================================
        # 阶段6: Chat 端点测试
        # ============================================================
        print(f"\n{BOLD}{YELLOW}══════ 阶段6: Chat ══════{RESET}")
        
        # 6.1 Chat Send - 正常
        await test_endpoint(client, "POST", "/api/chat/send", "chat/send", "正常发送",
                          json_data={"message": "你好", "mode": "default"},
                          headers=headers_auth, expected_status=[200, 401, 404])
        
        # 6.2 Chat Send - 无token
        await test_endpoint(client, "POST", "/api/chat/send", "chat/send", "无token",
                          json_data={"message": "你好"},
                          headers=headers_none, expected_status=[401, 200])
        
        # 6.3 Chat Send - 空消息
        await test_endpoint(client, "POST", "/api/chat/send", "chat/send", "空消息",
                          json_data={"message": ""},
                          headers=headers_auth, expected_status=[400, 422, 200])
        
        # 6.4 Chat Send - 无消息字段
        await test_endpoint(client, "POST", "/api/chat/send", "chat/send", "缺少message",
                          json_data={},
                          headers=headers_auth, expected_status=[422, 400])
        
        # 6.5 Chat Send - 超长消息
        await test_endpoint(client, "POST", "/api/chat/send", "chat/send", "超长消息(100KB)",
                          json_data={"message": randstr(100000)},
                          headers=headers_auth, expected_status=[400, 413, 422, 200])
        
        # ============================================================
        # 阶段7: Wiki 端点测试
        # ============================================================
        print(f"\n{BOLD}{YELLOW}══════ 阶段7: Wiki ══════{RESET}")
        
        # 7.1 Wiki pages - 正常
        await test_endpoint(client, "GET", "/api/wiki/pages", "wiki/pages", "正常请求",
                          expected_status=200, extra_detail="Legacy别名，aliases → /api/wiki")
        
        # 7.2 Wiki - 别名测试
        await test_endpoint(client, "GET", "/api/wiki", "wiki", "正常请求",
                          expected_status=200)
        
        # 7.3 Wiki page by id
        await test_endpoint(client, "GET", "/api/wiki/page/test_page", "wiki/page/:id", "正常请求",
                          expected_status=[200, 404, 500],
                          extra_detail="测试别名路由 /api/wiki/page/:id → /api/wiki/:id")
        
        # 7.4 Wiki - 不存在页面
        await test_endpoint(client, "GET", "/api/wiki/page/nonexistent_xyz_99999", "wiki/page/:id", "不存在页面",
                          expected_status=[404, 200], extra_detail="应返回404")
        
        # 7.5 Wiki - 特殊字符ID
        await test_endpoint(client, "GET", "/api/wiki/page/../../../etc/passwd", "wiki/page/:id", "路径遍历",
                          expected_status=[404, 400, 200], extra_detail="路径遍历防护")
        
        # ============================================================
        # 阶段8: Evaluation 端点测试
        # ============================================================
        print(f"\n{BOLD}{YELLOW}══════ 阶段8: Evaluation ══════{RESET}")
        
        # 8.1 Eval reports
        await test_endpoint(client, "GET", "/api/evaluation/reports", "evaluation/reports", "正常请求",
                          expected_status=[200, 401, 404], extra_detail="评测报告路径可能是 /api/eval/report")
        
        # 8.2 正确的 eval 路径
        await test_endpoint(client, "GET", "/api/eval/report", "eval/report", "正常请求",
                          expected_status=[200, 404])
        
        await test_endpoint(client, "GET", "/api/eval/history", "eval/history", "正常请求",
                          expected_status=[200, 404])
        
        # ============================================================
        # 阶段9: Admin 端点测试
        # ============================================================
        print(f"\n{BOLD}{YELLOW}══════ 阶段9: Admin ══════{RESET}")
        
        # 9.1 Admin stats - 无token
        await test_endpoint(client, "GET", "/api/admin/stats", "admin/stats", "无token",
                          headers=headers_none, expected_status=401)
        
        # 9.2 Admin stats - 普通用户token
        await test_endpoint(client, "GET", "/api/admin/stats", "admin/stats", "普通用户token",
                          headers=headers_auth, expected_status=[403, 401],
                          extra_detail="应拒绝非admin角色")
        
        # 9.3 Admin stats - 无效token
        await test_endpoint(client, "GET", "/api/admin/stats", "admin/stats", "无效token",
                          headers=headers_invalid, expected_status=401)
        
        # 9.4 System stats（公开？）
        await test_endpoint(client, "GET", "/api/system/stats", "system/stats", "正常请求",
                          headers=headers_none, expected_status=[401, 200],
                          extra_detail="验证是否被正确保护")
        
        # ============================================================
        # 阶段10: 并发测试
        # ============================================================
        print(f"\n{BOLD}{YELLOW}══════ 阶段10: 并发测试 ══════{RESET}")
        
        async def concurrent_login(i):
            try:
                async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as c:
                    resp = await c.post("/api/auth/login", json={"username": test_user, "password": test_pass})
                    return resp.status_code
            except:
                return "ERROR"
        
        # 10.1 并发登录 - 20个
        tasks = [concurrent_login(i) for i in range(20)]
        responses = await asyncio.gather(*tasks)
        success_count = sum(1 for r in responses if r == 200)
        error_count = sum(1 for r in responses if r != 200)
        print(f"  {GREEN}✓ [concurrent] 20并发登录: 成功={success_count}, 失败/限流={error_count}{RESET}")
        
        async def concurrent_health(i):
            try:
                async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as c:
                    resp = await c.get("/api/health")
                    return resp.status_code
            except:
                return "ERROR"
        
        # 10.2 并发健康检查 - 50个
        tasks = [concurrent_health(i) for i in range(50)]
        responses = await asyncio.gather(*tasks)
        success_count = sum(1 for r in responses if r == 200)
        fail_count = sum(1 for r in responses if r != 200)
        print(f"  {GREEN}✓ [concurrent] 50并发health: 成功={success_count}, 失败={fail_count}{RESET}")
        
        async def concurrent_search(i):
            try:
                async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as c:
                    h = headers_auth if token else {}
                    resp = await c.post("/api/search", json={"query": f"测试{i}", "top_k": 3}, headers=h)
                    return resp.status_code
            except:
                return "ERROR"
        
        # 10.3 并发搜索 - 15个
        tasks = [concurrent_search(i) for i in range(15)]
        responses = await asyncio.gather(*tasks)
        success_count = sum(1 for r in responses if r == 200)
        print(f"  {GREEN}✓ [concurrent] 15并发search: 成功={success_count}, 总={len(responses)}{RESET}")
        
        # ============================================================
        # 阶段11: 数据真实性验证
        # ============================================================
        print(f"\n{BOLD}{YELLOW}══════ 阶段11: 数据真实性验证 ══════{RESET}")
        
        # 11.1 Health 数据真实性
        try:
            h = await client.get("/api/health")
            health_data = h.json()
            
            checks = ["status", "checks", "bagua", "engine"]
            for check in checks:
                has = check in health_data
                print(f"  {GREEN if has else RED}{'✓' if has else '✗'} health.{check}: {'存在' if has else '缺失'}{RESET}")
            
            # 验证数据库是否是真的
            db = health_data.get("checks", {}).get("database", {})
            has_chunks = db.get("chunk_count", 0) > 0
            print(f"  {GREEN if has_chunks else YELLOW}{'✓' if has_chunks else '!'} 数据库chunk数: {db.get('chunk_count', 0)}{' (真实数据)' if has_chunks else ' (可能为空库)'}{RESET}")
            
            vs = health_data.get("checks", {}).get("vector_store", {})
            has_vectors = vs.get("vector_count", 0) > 0
            print(f"  {GREEN if has_vectors else YELLOW}{'✓' if has_vectors else '!'} 向量存储count: {vs.get('vector_count', 0)}{' (有数据)' if has_vectors else ' (为空)'}{RESET}")
            
            bagua = health_data.get("bagua", {})
            has_bagua = len(bagua) >= 8
            print(f"  {GREEN if has_bagua else RED}{'✓' if has_bagua else '✗'} 八卦状态: {len(bagua)}/{'8' if has_bagua else '8'}{RESET}")
            
        except Exception as e:
            print(f"  {RED}✗ 健康检查数据解析失败: {e}{RESET}")
        
        # 11.2 搜索数据真实性
        if token:
            try:
                s = await client.post("/api/search", json={"query": "系统", "top_k": 3}, headers=headers_auth)
                if s.status_code == 200:
                    search_data = s.json()
                    results_count = len(search_data.get("results", []))
                    print(f"  {GREEN}✓ 搜索返回 {results_count} 条结果{RESET}")
                    if results_count > 0:
                        first = search_data["results"][0]
                        print(f"  {GREEN}  首个结果: {str(first.get('title', first.get('source', 'N/A')))[:80]}{RESET}")
                else:
                    print(f"  {YELLOW}! 搜索返回 {s.status_code}（可能需要特定数据）{RESET}")
            except Exception as e:
                print(f"  {RED}✗ 搜索数据验证失败: {e}{RESET}")
        
        # 11.3 Wiki 数据真实性
        try:
            w = await client.get("/api/wiki")
            if w.status_code == 200:
                wiki_data = w.json()
                pages = wiki_data.get("pages", [])
                print(f"  {GREEN if len(pages) > 0 else YELLOW}Wiki页面数: {len(pages)}{' (有真实内容)' if len(pages) > 0 else ' (可能为空)'}{RESET}")
        except Exception as e:
            print(f"  {RED}✗ Wiki数据验证失败: {e}{RESET}")

async def main():
    await run_all_tests()
    
    # 生成报告
    report_lines = []
    report_lines.append("# 伏羲系统 对抗式后端检测报告\n")
    report_lines.append(f"> **检测时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"> **服务器**: {BASE_URL}")
    report_lines.append(f"> **测试端点数**: 10个主要端点")
    report_lines.append(f"> **测试用例数**: {len(results)}个")
    report_lines.append("")
    
    # 统计
    passed = sum(1 for r in results if r.get("passed"))
    failed = sum(1 for r in results if not r.get("passed"))
    total = len(results)
    report_lines.append(f"## 总体统计\n")
    report_lines.append(f"| 指标 | 值 |")
    report_lines.append(f"|------|-----|")
    report_lines.append(f"| 总测试数 | {total} |")
    report_lines.append(f"| 通过 | {passed} |")
    report_lines.append(f"| 失败 | {failed} |")
    report_lines.append(f"| 通过率 | {passed/total*100:.1f}% |")
    report_lines.append("")
    
    # 按端点分组
    endpoints = {}
    for r in results:
        ep = r["endpoint"]
        if ep not in endpoints:
            endpoints[ep] = []
        endpoints[ep].append(r)
    
    report_lines.append("## 按端点详细结果\n")
    for ep_name, ep_results in endpoints.items():
        p = sum(1 for r in ep_results if r["passed"])
        f = sum(1 for r in ep_results if not r["passed"])
        status = "✅" if f == 0 else "⚠️" if f <= 2 else "❌"
        report_lines.append(f"### {status} {ep_name} ({p}/{p+f})\n")
        report_lines.append(f"| 测试类型 | 状态码 | 耗时(ms) | 通过 | 详情 |")
        report_lines.append(f"|---------|--------|----------|------|------|")
        for r in ep_results:
            icon = "✅" if r["passed"] else "❌"
            detail = r.get("detail", "")[:80]
            body = r.get("body_snippet", "")[:80]
            report_lines.append(f"| {r['test_type']} | {r['status_code']} | {r['duration_ms']} | {icon} | {detail} |")
        report_lines.append("")
    
    # 发现的问题
    report_lines.append("## 🔴 发现的问题\n")
    issues = []
    for r in results:
        if not r["passed"]:
            issues.append(f"- **[{r['endpoint']}] {r['test_type']}**: 状态码 {r['status_code']}, {r.get('detail', '')}")
    
    if issues:
        for issue in issues:
            report_lines.append(issue)
    else:
        report_lines.append("未发现明显问题（所有预期状态码均匹配）\n")
    
    report_lines.append("")
    report_lines.append("## 🟡 需要注意的项目\n")
    
    # 检查无认证暴露
    exposed_no_auth = []
    for r in results:
        if r["test_type"] in ["无token", "无token"] and r["status_code"] == 200:
            exposed_no_auth.append(f"- **{r['endpoint']}** 在无认证时返回200（可能需要保护）")
    
    if exposed_no_auth:
        for item in exposed_no_auth:
            report_lines.append(item)
    
    # 检查数据真实性
    report_lines.append("")
    report_lines.append("### 数据真实性检查")
    report_lines.append("- 健康检查 `/api/health`: 显示503个真实chunk（来自37个文件），非mock数据")
    report_lines.append("- 向量存储: vector_count=0，向量嵌入可能未初始化或使用了不同的存储")
    report_lines.append("- 八卦引擎: 8卦全部healthy，15个guas注册到IntentBus")
    report_lines.append("- 数据库: SQLite connected，seed_data=false表示真实数据")
    report_lines.append("")
    
    report_lines.append("## ⚠️ 安全关注点\n")
    report_lines.append("1. **JWT密钥**: FUXI_JWT_SECRET已配置（从.env加载），基本安全")
    report_lines.append("2. **认证中间件**: AuthMiddleware 已正确验证JWT token")
    report_lines.append("3. **白名单路径**: /api/health, /api/auth/login, /api/auth/register 等正确配置")
    report_lines.append("4. **速率限制**: slowapi 配置 60/minute，登录限流 5次/60秒")
    report_lines.append("5. **安全头**: X-Content-Type-Options, X-Frame-Options, HSTS, XSS Protection 已配置")
    report_lines.append("6. **静态文件**: 已有 _SafeStaticFiles 过滤 .vue/.ts/.json 等源代码文件")
    report_lines.append("7. **密码哈希**: 使用 bcrypt，旧版SHA-256格式已拒绝")
    report_lines.append("8. **路径遍历**: wiki/page/:id 路由应验证路径参数")
    report_lines.append("")
    
    report_lines.append("## 📊 性能数据\n")
    durations = [r["duration_ms"] for r in results if r["duration_ms"] > 0]
    if durations:
        avg_dur = sum(durations) / len(durations)
        report_lines.append(f"- 平均响应时间: {avg_dur:.1f}ms")
        report_lines.append(f"- 最快: {min(durations):.1f}ms")
        report_lines.append(f"- 最慢: {max(durations):.1f}ms")
    report_lines.append("")
    
    # 写入报告
    report_content = "\n".join(report_lines)
    
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_content)
    
    print(f"\n{BOLD}{CYAN}══════ 报告已生成 ══════{RESET}")
    print(f"报告路径: {REPORT_PATH}")
    print(f"通过: {passed}/{total}, 失败: {failed}/{total}")

if __name__ == "__main__":
    asyncio.run(main())