"""
伏羲系统第三轮对抗式安全检测脚本
模拟攻击者视角进行8个维度的安全测试
"""
import asyncio
import httpx
import json
import time
import random
import string
import hashlib
import base64
import re
from datetime import datetime
from typing import Dict, List, Any
import os

BASE_URL = "http://172.25.30.200:8080"
REPORT_PATH = "E:\\easyclaw\\伏羲-v1.44\\repo\\.openclaw\\交付\\第三轮对抗式安全检测详细报告.md"

class AdversarialTester:
    def __init__(self):
        self.results = []
        self.attack_vectors = {
            "jwt_bypass": [],
            "sql_injection": [],
            "xss_attack": [],
            "path_traversal": [],
            "rate_limit_bypass": [],
            "info_disclosure": [],
            "api_security": [],
            "file_upload": []
        }
        
    async def run_all_tests(self):
        """运行所有对抗式安全测试"""
        print("🎯 开始伏羲系统第三轮对抗式安全检测")
        print(f"目标: {BASE_URL}")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
            # 1. JWT认证绕过测试
            await self.test_jwt_bypass(client)
            
            # 2. SQL注入攻击测试
            await self.test_sql_injection(client)
            
            # 3. XSS攻击测试
            await self.test_xss_attack(client)
            
            # 4. 路径遍历攻击测试
            await self.test_path_traversal(client)
            
            # 5. 速率限制绕过测试
            await self.test_rate_limit_bypass(client)
            
            # 6. 信息泄露风险测试
            await self.test_info_disclosure(client)
            
            # 7. API端点安全性测试
            await self.test_api_security(client)
            
            # 8. 文件上传安全性测试
            await self.test_file_upload_security(client)
        
        # 生成报告
        self.generate_report()
        
    async def test_jwt_bypass(self, client: httpx.AsyncClient):
        """JWT认证绕过测试"""
        print("\n🔐 测试1: JWT认证绕过")
        print("-" * 40)
        
        # 1.1 测试弱密钥
        weak_secrets = [
            "fuxi-v1.50-jwt-production-key-change-in-prod",
            "fuxi-v1.44-jwt-secret",
            "change-me",
            "secret",
            "jwt-secret",
            "your-secret-key",
            "super-secret"
        ]
        
        for secret in weak_secrets:
            try:
                # 模拟使用弱密钥的Token
                fake_payload = {
                    "sub": "admin",
                    "role": "admin",
                    "exp": int(time.time()) + 3600,
                    "iat": int(time.time())
                }
                fake_token = self.create_fake_jwt(fake_payload, secret)
                
                headers = {"Authorization": f"Bearer {fake_token}"}
                resp = await client.get("/api/auth/me", headers=headers)
                
                result = {
                    "test": "弱密钥Token验证",
                    "vector": f"密钥: {secret[:20]}...",
                    "status_code": resp.status_code,
                    "success": resp.status_code == 200,
                    "risk_level": "HIGH" if resp.status_code == 200 else "LOW"
                }
                self.attack_vectors["jwt_bypass"].append(result)
                
                icon = "✅" if resp.status_code != 200 else "❌"
                print(f"  {icon} 弱密钥测试: {resp.status_code}")
                
            except Exception as e:
                print(f"  ⚠️ 测试异常: {e}")
        
        # 1.2 测试算法混淆
        try:
            # 尝试使用none算法
            fake_header = {"alg": "none", "typ": "JWT"}
            fake_payload = {"sub": "admin", "role": "admin", "exp": int(time.time()) + 3600}
            
            # 构造none算法Token
            header_b64 = base64.urlsafe_b64encode(json.dumps(fake_header).encode()).decode()
            payload_b64 = base64.urlsafe_b64encode(json.dumps(fake_payload).encode()).decode()
            none_token = f"{header_b64}.{payload_b64}."
            
            headers = {"Authorization": f"Bearer {none_token}"}
            resp = await client.get("/api/auth/me", headers=headers)
            
            result = {
                "test": "算法混淆攻击(none)",
                "vector": "none算法Token",
                "status_code": resp.status_code,
                "success": resp.status_code == 200,
                "risk_level": "HIGH" if resp.status_code == 200 else "LOW"
            }
            self.attack_vectors["jwt_bypass"].append(result)
            
            icon = "✅" if resp.status_code != 200 else "❌"
            print(f"  {icon} 算法混淆测试: {resp.status_code}")
            
        except Exception as e:
            print(f"  ⚠️ 算法混淆测试异常: {e}")
        
        # 1.3 测试Token重用
        try:
            # 获取有效Token
            login_resp = await client.post("/api/auth/login", json={
                "username": "test_user",
                "password": "Test@2024Secure!"
            })
            
            if login_resp.status_code == 200:
                token = login_resp.json().get("token")
                
                # 刷新Token
                refresh_resp = await client.post("/api/auth/refresh", 
                    json={"token": token},
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if refresh_resp.status_code == 200:
                    # 尝试使用旧Token
                    headers = {"Authorization": f"Bearer {token}"}
                    me_resp = await client.get("/api/auth/me", headers=headers)
                    
                    result = {
                        "test": "Token重用攻击",
                        "vector": "刷新后使用旧Token",
                        "status_code": me_resp.status_code,
                        "success": me_resp.status_code == 200,
                        "risk_level": "HIGH" if me_resp.status_code == 200 else "LOW"
                    }
                    self.attack_vectors["jwt_bypass"].append(result)
                    
                    icon = "✅" if me_resp.status_code != 200 else "❌"
                    print(f"  {icon} Token重用测试: {me_resp.status_code}")
                    
        except Exception as e:
            print(f"  ⚠️ Token重用测试异常: {e}")
    
    async def test_sql_injection(self, client: httpx.AsyncClient):
        """SQL注入攻击测试"""
        print("\n💉 测试2: SQL注入攻击")
        print("-" * 40)
        
        # 2.1 登录SQL注入
        sql_payloads = [
            "' OR '1'='1",
            "admin'--",
            "admin' OR '1'='1'--",
            "' UNION SELECT * FROM users--",
            "1; DROP TABLE users--",
            "' OR 1=1--",
            "admin'/*",
            "' OR ''='",
            "1' OR '1' = '1",
            "admin' OR 1=1#"
        ]
        
        for payload in sql_payloads:
            try:
                resp = await client.post("/api/auth/login", json={
                    "username": payload,
                    "password": "test"
                })
                
                result = {
                    "test": "登录SQL注入",
                    "vector": payload[:30] + "..." if len(payload) > 30 else payload,
                    "status_code": resp.status_code,
                    "success": resp.status_code == 200,
                    "risk_level": "HIGH" if resp.status_code == 200 else "LOW"
                }
                self.attack_vectors["sql_injection"].append(result)
                
                icon = "✅" if resp.status_code != 200 else "❌"
                print(f"  {icon} SQL注入测试: {resp.status_code}")
                
            except Exception as e:
                print(f"  ⚠️ SQL注入测试异常: {e}")
        
        # 2.2 搜索SQL注入
        search_payloads = [
            "' UNION SELECT * FROM users--",
            "1; DROP TABLE chunks--",
            "' OR 1=1--",
            "test' AND 1=1--",
            "' UNION SELECT username,password FROM users--"
        ]
        
        # 先获取Token
        try:
            login_resp = await client.post("/api/auth/login", json={
                "username": "test_user",
                "password": "Test@2024Secure!"
            })
            
            if login_resp.status_code == 200:
                token = login_resp.json().get("token")
                headers = {"Authorization": f"Bearer {token}"}
                
                for payload in search_payloads:
                    try:
                        resp = await client.post("/api/search", 
                            json={"query": payload, "top_k": 5},
                            headers=headers
                        )
                        
                        result = {
                            "test": "搜索SQL注入",
                            "vector": payload[:30] + "..." if len(payload) > 30 else payload,
                            "status_code": resp.status_code,
                            "success": resp.status_code == 200,
                            "risk_level": "HIGH" if resp.status_code == 200 else "LOW"
                        }
                        self.attack_vectors["sql_injection"].append(result)
                        
                        icon = "✅" if resp.status_code != 200 else "❌"
                        print(f"  {icon} 搜索SQL注入测试: {resp.status_code}")
                        
                    except Exception as e:
                        print(f"  ⚠️ 搜索SQL注入测试异常: {e}")
                        
        except Exception as e:
            print(f"  ⚠️ 获取Token失败: {e}")
    
    async def test_xss_attack(self, client: httpx.AsyncClient):
        """XSS攻击测试"""
        print("\n🎭 测试3: XSS攻击")
        print("-" * 40)
        
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<svg onload=alert('xss')>",
            "'-alert('xss')-'",
            "\"><script>alert('xss')</script>",
            "<iframe src=javascript:alert('xss')>",
            "<body onload=alert('xss')>",
            "<input onfocus=alert('xss') autofocus>",
            "<details open ontoggle=alert('xss')>"
        ]
        
        # 测试登录XSS
        for payload in xss_payloads:
            try:
                resp = await client.post("/api/auth/login", json={
                    "username": payload,
                    "password": "test"
                })
                
                result = {
                    "test": "登录XSS",
                    "vector": payload[:30] + "..." if len(payload) > 30 else payload,
                    "status_code": resp.status_code,
                    "success": resp.status_code == 200,
                    "risk_level": "HIGH" if resp.status_code == 200 else "LOW"
                }
                self.attack_vectors["xss_attack"].append(result)
                
                icon = "✅" if resp.status_code != 200 else "❌"
                print(f"  {icon} 登录XSS测试: {resp.status_code}")
                
            except Exception as e:
                print(f"  ⚠️ 登录XSS测试异常: {e}")
        
        # 测试搜索XSS
        try:
            login_resp = await client.post("/api/auth/login", json={
                "username": "test_user",
                "password": "Test@2024Secure!"
            })
            
            if login_resp.status_code == 200:
                token = login_resp.json().get("token")
                headers = {"Authorization": f"Bearer {token}"}
                
                for payload in xss_payloads:
                    try:
                        resp = await client.post("/api/search", 
                            json={"query": payload, "top_k": 5},
                            headers=headers
                        )
                        
                        result = {
                            "test": "搜索XSS",
                            "vector": payload[:30] + "..." if len(payload) > 30 else payload,
                            "status_code": resp.status_code,
                            "success": resp.status_code == 200,
                            "risk_level": "HIGH" if resp.status_code == 200 else "LOW"
                        }
                        self.attack_vectors["xss_attack"].append(result)
                        
                        icon = "✅" if resp.status_code != 200 else "❌"
                        print(f"  {icon} 搜索XSS测试: {resp.status_code}")
                        
                    except Exception as e:
                        print(f"  ⚠️ 搜索XSS测试异常: {e}")
                        
        except Exception as e:
            print(f"  ⚠️ 获取Token失败: {e}")
    
    async def test_path_traversal(self, client: httpx.AsyncClient):
        """路径遍历攻击测试"""
        print("\n📁 测试4: 路径遍历攻击")
        print("-" * 40)
        
        traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%252f..%252f..%252fetc%252fpasswd",
            "..%c0%af..%c0%af..%c0%afetc%c0%afpasswd",
            "..%255c..%255c..%255cwindows%255csystem32%255cconfig%255csam",
            "....\\\\....\\\\....\\\\windows\\\\system32\\\\config\\\\sam",
            "/etc/passwd%00.jpg",
            "....//....//....//etc/passwd%00.jpg"
        ]
        
        # 测试文件上传路径遍历
        for payload in traversal_payloads:
            try:
                # 创建恶意文件名
                files = {"file": (payload, b"test content", "text/plain")}
                resp = await client.post("/api/upload", files=files)
                
                result = {
                    "test": "文件上传路径遍历",
                    "vector": payload[:30] + "..." if len(payload) > 30 else payload,
                    "status_code": resp.status_code,
                    "success": resp.status_code == 200,
                    "risk_level": "HIGH" if resp.status_code == 200 else "LOW"
                }
                self.attack_vectors["path_traversal"].append(result)
                
                icon = "✅" if resp.status_code != 200 else "❌"
                print(f"  {icon} 路径遍历测试: {resp.status_code}")
                
            except Exception as e:
                print(f"  ⚠️ 路径遍历测试异常: {e}")
        
        # 测试API路径遍历
        traversal_paths = [
            "/api/wiki/page/../../../etc/passwd",
            "/api/files/../../../etc/passwd",
            "/api/documents/../../../etc/passwd",
            "/api/static/../../../etc/passwd",
            "/api/uploads/../../../etc/passwd"
        ]
        
        for path in traversal_paths:
            try:
                resp = await client.get(path)
                
                result = {
                    "test": "API路径遍历",
                    "vector": path,
                    "status_code": resp.status_code,
                    "success": resp.status_code == 200,
                    "risk_level": "HIGH" if resp.status_code == 200 else "LOW"
                }
                self.attack_vectors["path_traversal"].append(result)
                
                icon = "✅" if resp.status_code != 200 else "❌"
                print(f"  {icon} API路径遍历测试: {resp.status_code}")
                
            except Exception as e:
                print(f"  ⚠️ API路径遍历测试异常: {e}")
    
    async def test_rate_limit_bypass(self, client: httpx.AsyncClient):
        """速率限制绕过测试"""
        print("\n⏱️ 测试5: 速率限制绕过")
        print("-" * 40)
        
        # 5.1 测试登录限流
        print("  测试登录限流...")
        login_attempts = []
        
        for i in range(15):  # 超过10次/5分钟的限制
            try:
                start = time.time()
                resp = await client.post("/api/auth/login", json={
                    "username": f"test_user_{i}",
                    "password": "wrong_password"
                })
                duration = time.time() - start
                
                login_attempts.append({
                    "attempt": i + 1,
                    "status_code": resp.status_code,
                    "duration": duration
                })
                
                if resp.status_code == 429:
                    print(f"  ✅ 登录限流生效: 第{i+1}次尝试返回429")
                    break
                    
            except Exception as e:
                print(f"  ⚠️ 登录限流测试异常: {e}")
        
        result = {
            "test": "登录限流测试",
            "vector": f"连续{len(login_attempts)}次登录尝试",
            "status_code": login_attempts[-1]["status_code"] if login_attempts else "ERROR",
            "success": any(a["status_code"] == 429 for a in login_attempts),
            "risk_level": "LOW" if any(a["status_code"] == 429 for a in login_attempts) else "HIGH"
        }
        self.attack_vectors["rate_limit_bypass"].append(result)
        
        # 5.2 测试全局限流
        print("  测试全局限流...")
        health_attempts = []
        
        for i in range(65):  # 超过60次/分钟的限制
            try:
                start = time.time()
                resp = await client.get("/api/health")
                duration = time.time() - start
                
                health_attempts.append({
                    "attempt": i + 1,
                    "status_code": resp.status_code,
                    "duration": duration
                })
                
                if resp.status_code == 429:
                    print(f"  ✅ 全局限流生效: 第{i+1}次尝试返回429")
                    break
                    
            except Exception as e:
                print(f"  ⚠️ 全局限流测试异常: {e}")
        
        result = {
            "test": "全局限流测试",
            "vector": f"连续{len(health_attempts)}次健康检查",
            "status_code": health_attempts[-1]["status_code"] if health_attempts else "ERROR",
            "success": any(a["status_code"] == 429 for a in health_attempts),
            "risk_level": "LOW" if any(a["status_code"] == 429 for a in health_attempts) else "HIGH"
        }
        self.attack_vectors["rate_limit_bypass"].append(result)
    
    async def test_info_disclosure(self, client: httpx.AsyncClient):
        """信息泄露风险测试"""
        print("\n🔍 测试6: 信息泄露风险")
        print("-" * 40)
        
        # 6.1 测试错误信息泄露
        error_endpoints = [
            "/api/nonexistent",
            "/api/admin/secret",
            "/api/debug/vars",
            "/api/debug/pprof",
            "/api/status",
            "/api/metrics",
            "/api/config",
            "/api/env"
        ]
        
        for endpoint in error_endpoints:
            try:
                resp = await client.get(endpoint)
                
                # 检查是否泄露敏感信息
                body = resp.text
                sensitive_patterns = [
                    r"password",
                    r"secret",
                    r"token",
                    r"key",
                    r"database",
                    r"mysql",
                    r"redis",
                    r"mongodb",
                    r"stack trace",
                    r"traceback",
                    r"exception"
                ]
                
                leaks = []
                for pattern in sensitive_patterns:
                    if re.search(pattern, body, re.I):
                        leaks.append(pattern)
                
                result = {
                    "test": "错误信息泄露",
                    "vector": endpoint,
                    "status_code": resp.status_code,
                    "success": len(leaks) > 0,
                    "leaks": leaks,
                    "risk_level": "HIGH" if len(leaks) > 0 else "LOW"
                }
                self.attack_vectors["info_disclosure"].append(result)
                
                icon = "❌" if len(leaks) > 0 else "✅"
                print(f"  {icon} 信息泄露测试: {endpoint} - {len(leaks)}项泄露")
                
            except Exception as e:
                print(f"  ⚠️ 信息泄露测试异常: {e}")
        
        # 6.2 测试版本信息泄露
        try:
            resp = await client.get("/api/health")
            body = resp.json()
            
            version_info = {
                "version": body.get("version"),
                "build": body.get("build"),
                "environment": body.get("environment"),
                "server": resp.headers.get("server")
            }
            
            result = {
                "test": "版本信息泄露",
                "vector": "/api/health",
                "status_code": resp.status_code,
                "success": any(v is not None for v in version_info.values()),
                "version_info": version_info,
                "risk_level": "MEDIUM" if any(v is not None for v in version_info.values()) else "LOW"
            }
            self.attack_vectors["info_disclosure"].append(result)
            
            icon = "❌" if any(v is not None for v in version_info.values()) else "✅"
            print(f"  {icon} 版本信息泄露测试: {version_info}")
            
        except Exception as e:
            print(f"  ⚠️ 版本信息泄露测试异常: {e}")
    
    async def test_api_security(self, client: httpx.AsyncClient):
        """API端点安全性测试"""
        print("\n🛡️ 测试7: API端点安全性")
        print("-" * 40)
        
        # 7.1 测试未认证访问受保护端点
        protected_endpoints = [
            "/api/admin/stats",
            "/api/admin/users",
            "/api/documents",
            "/api/chat/send",
            "/api/search",
            "/api/wiki/pages",
            "/api/files"
        ]
        
        for endpoint in protected_endpoints:
            try:
                resp = await client.get(endpoint)
                
                result = {
                    "test": "未认证访问",
                    "vector": endpoint,
                    "status_code": resp.status_code,
                    "success": resp.status_code == 401,
                    "risk_level": "LOW" if resp.status_code == 401 else "HIGH"
                }
                self.attack_vectors["api_security"].append(result)
                
                icon = "✅" if resp.status_code == 401 else "❌"
                print(f"  {icon} 未认证访问测试: {endpoint} - {resp.status_code}")
                
            except Exception as e:
                print(f"  ⚠️ 未认证访问测试异常: {e}")
        
        # 7.2 测试CORS配置
        try:
            headers = {
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
            
            resp = await client.options("/api/auth/login", headers=headers)
            
            cors_headers = {
                "access-control-allow-origin": resp.headers.get("access-control-allow-origin"),
                "access-control-allow-methods": resp.headers.get("access-control-allow-methods"),
                "access-control-allow-headers": resp.headers.get("access-control-allow-headers")
            }
            
            result = {
                "test": "CORS配置",
                "vector": "OPTIONS /api/auth/login",
                "status_code": resp.status_code,
                "success": cors_headers["access-control-allow-origin"] != "https://evil.com",
                "cors_headers": cors_headers,
                "risk_level": "LOW" if cors_headers["access-control-allow-origin"] != "https://evil.com" else "HIGH"
            }
            self.attack_vectors["api_security"].append(result)
            
            icon = "✅" if cors_headers["access-control-allow-origin"] != "https://evil.com" else "❌"
            print(f"  {icon} CORS配置测试: {cors_headers}")
            
        except Exception as e:
            print(f"  ⚠️ CORS配置测试异常: {e}")
    
    async def test_file_upload_security(self, client: httpx.AsyncClient):
        """文件上传安全性测试"""
        print("\n📤 测试8: 文件上传安全性")
        print("-" * 40)
        
        # 8.1 测试恶意文件上传
        malicious_files = [
            ("malware.exe", b"MZ\x90\x00", "application/octet-stream"),
            ("script.php", b"<?php echo 'hacked'; ?>", "application/x-php"),
            ("shell.sh", b"#!/bin/bash\nrm -rf /", "application/x-sh"),
            ("virus.bat", b"@echo off\ndel /f /q *.*", "application/bat"),
            ("trojan.js", b"alert('hacked')", "application/javascript"),
            ("backdoor.py", b"import os; os.system('rm -rf /')", "text/x-python")
        ]
        
        for filename, content, content_type in malicious_files:
            try:
                files = {"file": (filename, content, content_type)}
                resp = await client.post("/api/upload", files=files)
                
                result = {
                    "test": "恶意文件上传",
                    "vector": filename,
                    "status_code": resp.status_code,
                    "success": resp.status_code == 400,
                    "risk_level": "LOW" if resp.status_code == 400 else "HIGH"
                }
                self.attack_vectors["file_upload"].append(result)
                
                icon = "✅" if resp.status_code == 400 else "❌"
                print(f"  {icon} 恶意文件上传测试: {filename} - {resp.status_code}")
                
            except Exception as e:
                print(f"  ⚠️ 恶意文件上传测试异常: {e}")
        
        # 8.2 测试超大文件上传
        try:
            # 创建10MB文件
            large_content = b"0" * (10 * 1024 * 1024)
            files = {"file": ("large_file.txt", large_content, "text/plain")}
            resp = await client.post("/api/upload", files=files)
            
            result = {
                "test": "超大文件上传",
                "vector": "10MB文件",
                "status_code": resp.status_code,
                "success": resp.status_code == 413 or resp.status_code == 400,
                "risk_level": "LOW" if resp.status_code in [413, 400] else "HIGH"
            }
            self.attack_vectors["file_upload"].append(result)
            
            icon = "✅" if resp.status_code in [413, 400] else "❌"
            print(f"  {icon} 超大文件上传测试: {resp.status_code}")
            
        except Exception as e:
            print(f"  ⚠️ 超大文件上传测试异常: {e}")
    
    def create_fake_jwt(self, payload: Dict, secret: str) -> str:
        """创建假的JWT Token"""
        import hmac
        
        header = {"alg": "HS256", "typ": "JWT"}
        
        # Base64编码
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode()
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
        
        # 创建签名
        message = f"{header_b64}.{payload_b64}"
        signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
        signature_b64 = base64.urlsafe_b64encode(signature).decode()
        
        return f"{header_b64}.{payload_b64}.{signature_b64}"
    
    def generate_report(self):
        """生成详细报告"""
        print("\n" + "=" * 60)
        print("📊 生成对抗式安全检测报告")
        print("=" * 60)
        
        report_lines = []
        report_lines.append("# 伏羲系统第三轮对抗式安全检测详细报告")
        report_lines.append("")
        report_lines.append(f"**检测时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"**检测目标**: {BASE_URL}")
        report_lines.append(f"**检测类型**: 对抗式安全检测（模拟攻击者视角）")
        report_lines.append("")
        
        # 统计结果
        total_tests = 0
        successful_attacks = 0
        high_risk = 0
        medium_risk = 0
        low_risk = 0
        
        for category, tests in self.attack_vectors.items():
            for test in tests:
                total_tests += 1
                if test.get("success"):
                    successful_attacks += 1
                
                risk = test.get("risk_level", "LOW")
                if risk == "HIGH":
                    high_risk += 1
                elif risk == "MEDIUM":
                    medium_risk += 1
                else:
                    low_risk += 1
        
        report_lines.append("## 执行摘要")
        report_lines.append("")
        report_lines.append(f"本次对抗式安全检测共执行 **{total_tests}** 项测试，")
        report_lines.append(f"发现 **{successful_attacks}** 项攻击成功，")
        report_lines.append(f"其中高危 **{high_risk}** 项，中危 **{medium_risk}** 项，低危 **{low_risk}** 项。")
        report_lines.append("")
        
        # 详细结果
        report_lines.append("## 详细测试结果")
        report_lines.append("")
        
        category_names = {
            "jwt_bypass": "JWT认证绕过",
            "sql_injection": "SQL注入攻击",
            "xss_attack": "XSS攻击",
            "path_traversal": "路径遍历攻击",
            "rate_limit_bypass": "速率限制绕过",
            "info_disclosure": "信息泄露风险",
            "api_security": "API端点安全",
            "file_upload": "文件上传安全"
        }
        
        for category, tests in self.attack_vectors.items():
            if not tests:
                continue
                
            report_lines.append(f"### {category_names.get(category, category)}")
            report_lines.append("")
            report_lines.append("| 测试项 | 攻击向量 | 状态码 | 风险等级 | 结果 |")
            report_lines.append("|--------|----------|--------|----------|------|")
            
            for test in tests:
                icon = "❌ 攻击成功" if test.get("success") else "✅ 防御有效"
                risk_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(test.get("risk_level"), "⚪")
                
                report_lines.append(f"| {test.get('test')} | {test.get('vector')[:30]}... | {test.get('status_code')} | {risk_icon} {test.get('risk_level')} | {icon} |")
            
            report_lines.append("")
        
        # 风险评估
        report_lines.append("## 风险评估")
        report_lines.append("")
        
        if high_risk > 0:
            report_lines.append(f"🔴 **高危风险**: {high_risk} 项")
            report_lines.append("- 需要立即修复，存在严重安全漏洞")
        
        if medium_risk > 0:
            report_lines.append(f"🟡 **中危风险**: {medium_risk} 项")
            report_lines.append("- 需要尽快修复，存在潜在安全风险")
        
        if low_risk > 0:
            report_lines.append(f"🟢 **低危风险**: {low_risk} 项")
            report_lines.append("- 可以计划修复，风险相对较低")
        
        report_lines.append("")
        
        # 修复建议
        report_lines.append("## 修复建议")
        report_lines.append("")
        report_lines.append("### 紧急修复（P1）")
        report_lines.append("1. 修复所有高危漏洞")
        report_lines.append("2. 加强输入验证和输出编码")
        report_lines.append("3. 完善错误处理机制")
        report_lines.append("")
        
        report_lines.append("### 重要修复（P2）")
        report_lines.append("1. 加强访问控制")
        report_lines.append("2. 完善日志记录")
        report_lines.append("3. 实施安全监控")
        report_lines.append("")
        
        report_lines.append("### 一般修复（P3）")
        report_lines.append("1. 优化安全配置")
        report_lines.append("2. 加强安全培训")
        report_lines.append("3. 定期安全审计")
        report_lines.append("")
        
        # 写入报告
        report_content = "\n".join(report_lines)
        
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write(report_content)
        
        print(f"✅ 报告已生成: {REPORT_PATH}")
        print(f"📊 总测试数: {total_tests}")
        print(f"🎯 攻击成功: {successful_attacks}")
        print(f"🔴 高危风险: {high_risk}")
        print(f"🟡 中危风险: {medium_risk}")
        print(f"🟢 低危风险: {low_risk}")

async def main():
    tester = AdversarialTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())