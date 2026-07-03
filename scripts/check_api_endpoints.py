#!/usr/bin/env python3
"""
Phase 0.6.3: API 端点检查脚本
自动检测所有 API 端点是否返回 200
"""
import json, sys, os
import urllib.request

BASE_URL = os.getenv("KB_BASE_URL", "http://localhost:8080")
TOKEN = os.getenv("FUXI_API_TOKEN", "fuxi-v1.50-token")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

ENDPOINTS = [
    {"path": "/api/health", "method": "GET", "name": "健康检查"},
    {"path": "/api/search?q=PLC", "method": "GET", "name": "搜索"},
    {"path": "/api/documents", "method": "GET", "name": "文档列表"},
    {"path": "/api/v2/status", "method": "GET", "name": "状态"},
    {"path": "/api/wiki/pages", "method": "GET", "name": "Wiki列表"},
    {"path": "/api/worldtree/stats", "method": "GET", "name": "世界树"},
    {"path": "/api/faq", "method": "GET", "name": "FAQ"},
]


def check_endpoint(method, path, name):
    try:
        url = f"{BASE_URL}{path}"
        req = urllib.request.Request(url, headers=HEADERS, method=method)
        resp = urllib.request.urlopen(req, timeout=10)
        status = resp.status
        if status in (200, 201, 204):
            return "PASS", status
        else:
            return "WARN", status
    except urllib.error.HTTPError as e:
        return "FAIL", e.code
    except Exception as e:
        return "ERROR", str(e)[:100]


if __name__ == "__main__":
    print(f"=== API Endpoint Check ===")
    print(f"Base URL: {BASE_URL}\n")
    passed = 0
    failed = 0
    for ep in ENDPOINTS:
        result, detail = check_endpoint(ep["method"], ep["path"], ep["name"])
        status = "✅" if result == "PASS" else "❌"
        print(f"{status} {ep['name']:12s} {ep['method']:4s} {ep['path']:30s} → {result} ({detail})")
        if result == "PASS":
            passed += 1
        else:
            failed += 1
    print(f"\nResults: {passed} passed, {failed} failed, {len(ENDPOINTS)} total")
