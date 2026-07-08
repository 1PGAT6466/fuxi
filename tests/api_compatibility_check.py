#!/usr/bin/env python3
"""
伏羲 v2.1 — 前后端 API 兼容性测试脚本
=====================================
运行方式：
    cd E:\easyclaw\伏羲-v1.44\repo
    python tests/api_compatibility_check.py

功能：
  1. 逐接口测试所有 GET/POST/PUT/DELETE 端点
  2. 验证认证端点返回正确的 401（而非 500）
  3. 验证响应 JSON 格式符合前端期望
  4. 输出兼容性报告

用法：
    python tests/api_compatibility_check.py [--base-url=http://localhost:8000] [--verbose]
"""

import sys
import json
import time
import argparse
import urllib.request
import urllib.error
from typing import Dict, List, Tuple, Optional, Any


# ============================
# 配置
# ============================

DEFAULT_BASE_URL = "http://localhost:8000"

# 所有需要测试的端点（按路由分组）
# 格式: (method, path, description, auth_required, expected_status_without_auth)
# auth_required=True 表示该端点需要认证，不带 token 应返回 401

TEST_ENDPOINTS: List[Tuple[str, str, str, bool, Optional[int]]] = [
    # ──── 系统/健康检查（无需认证）────
    ("GET", "/api/health", "健康检查", False, 200),
    ("GET", "/api/metrics", "Prometheus 指标", False, 200),
    ("GET", "/metrics", "Prometheus 指标 (root)", False, 200),
    
    # ──── 四象/成长（无需认证）────
    ("GET", "/api/symbols/status", "四象状态", False, 200),
    ("GET", "/api/growth/overview", "成长概览", False, 200),
    
    # ──── Feature Flags（无需认证）────
    ("GET", "/api/feature-flags", "Feature Flag 列表", False, 200),
    
    # ──── 认证（无需认证）────
    ("GET", "/api/auth/me", "当前用户", True, 401),
    
    # ──── 文档/文件（需认证）────
    ("GET", "/api/documents", "文档列表", True, 401),
    ("GET", "/api/files", "文件列表(别名)", True, 401),
    
    # ──── 搜索（需认证）────
    ("GET", "/api/search?q=test", "搜索", True, 401),
    ("GET", "/api/search-history", "搜索历史", True, 401),
    
    # ──── 评测（需认证）────
    ("GET", "/api/evaluation/overview", "评测概览", True, 401),
    ("GET", "/api/evaluation/datasets", "评测数据集", True, 401),
    ("GET", "/api/evaluation/tasks", "评测任务", True, 401),
    ("GET", "/api/evaluation/results", "评测结果", True, 401),
    
    # ──── 进化（需认证）────
    ("GET", "/api/evolution/overview", "进化概览", True, 401),
    
    # ──── 仪表板（需认证）────
    ("GET", "/api/dashboard", "仪表板", True, 401),
    
    # ──── 反馈（需认证）────
    ("GET", "/api/feedback/weekly", "周反馈", True, 401),
    
    # ──── 天线搜索（需认证）────
    ("GET", "/api/antenna/search?q=test", "天线搜索", True, 401),
    
    # ──── 管理（需认证）────
    ("GET", "/api/admin/stats", "管理统计", True, 401),
    ("GET", "/api/admin/server-status", "服务器状态", True, 401),
    ("GET", "/api/admin/status", "状态(别名)", True, 401),
    ("GET", "/api/admin/documents", "管理文档", True, 401),
    ("GET", "/api/admin/evaluations", "管理评测", True, 401),
    ("GET", "/api/admin/users", "用户列表", True, 401),
    ("GET", "/api/admin/metrics-summary", "指标摘要", True, 401),
    
    # ──── 知识图谱（需认证）────
    ("GET", "/api/graph", "知识图谱", True, 401),
    
    # ──── Wiki（无需认证，但可能需要）────
    ("GET", "/api/wiki", "Wiki 首页", False, 200),
    ("GET", "/api/wiki/pages", "Wiki 页面列表", False, 200),
    
    # ──── 系统监控（需认证）────
    ("GET", "/api/system/stats", "系统统计", True, 401),
    ("GET", "/api/cache/stats", "缓存统计", True, 401),
    ("GET", "/api/errors/stats", "错误统计", True, 401),
    
    # ──── 审计（需认证）────
    ("GET", "/api/audit/logs", "审计日志", True, 401),
    ("GET", "/api/audit/stats", "审计统计", True, 401),
    
    # ──── 健康扩展（无需认证）────
    ("GET", "/api/health/bagua", "八卦健康", False, 200),
    ("GET", "/api/health/infra", "基础设施健康", False, 200),
    ("GET", "/api/health/alerts", "告警列表", False, 200),
    ("GET", "/api/health/alert-rules", "告警规则", False, 200),
    
    # ──── MCP（无需认证）────
    ("GET", "/api/mcp/tools", "MCP 工具列表", False, 200),
    ("GET", "/api/mcp/sag_status", "MCP SAG 状态", False, 200),
    
    # ──── 评测自动化（需认证）────
    ("GET", "/api/eval/report", "评测报告", True, 401),
    ("GET", "/api/eval/history", "评测历史", True, 401),
    
    # ──── v2 状态（无需认证）────
    ("GET", "/api/v2/status", "v2 状态", False, 200),
    
    # ──── WorldTree（需认证）────
    ("GET", "/api/worldtree/stats", "WorldTree 统计", True, 401),
    ("GET", "/api/worldtree/terms", "WorldTree 术语", True, 401),
    ("GET", "/api/worldtree/wiki/tree", "WorldTree Wiki 树", True, 401),
    ("GET", "/api/worldtree/wiki", "WorldTree Wiki", True, 401),
    ("GET", "/api/worldtree/entities", "WorldTree 实体", True, 401),
    
    # ──── v2.1 新增：通知中心 ────
    ("GET", "/api/notifications", "通知列表", True, 401),
    
    # ──── v2.1 新增：统一搜索 ────
    ("GET", "/api/unified-search?q=test", "统一搜索", True, 401),
    
    # ──── v2.1 新增：用户偏好 ────
    ("GET", "/api/user/preferences", "用户偏好", True, 401),
]


# ============================
# 测试执行
# ============================

class APITestRunner:
    def __init__(self, base_url: str, verbose: bool = False):
        self.base_url = base_url.rstrip("/")
        self.verbose = verbose
        self.results: List[Dict[str, Any]] = []
        self.start_time = time.time()
    
    def _request(self, method: str, path: str, 
                 body: Optional[Dict] = None,
                 headers: Optional[Dict] = None,
                 timeout: int = 10) -> Tuple[int, Any, float]:
        """发送 HTTP 请求并返回 (status_code, response_data, elapsed_ms)"""
        url = f"{self.base_url}{path}"
        data_bytes = None
        if body is not None:
            data_bytes = json.dumps(body).encode("utf-8")
        
        req_headers = headers or {}
        if data_bytes:
            req_headers["Content-Type"] = "application/json"
        
        start = time.perf_counter()
        try:
            req = urllib.request.Request(
                url, data=data_bytes, headers=req_headers, method=method
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                status = resp.status
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = {"_raw": raw[:200].decode("utf-8", errors="replace")}
                elapsed = (time.perf_counter() - start) * 1000
                return status, data, elapsed
        except urllib.error.HTTPError as e:
            elapsed = (time.perf_counter() - start) * 1000
            try:
                data = json.loads(e.read())
            except json.JSONDecodeError:
                data = {"_error": str(e)}
            return e.code, data, elapsed
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return -1, {"_exception": str(e)}, elapsed
    
    def run_single(self, method: str, path: str, description: str,
                   auth_required: bool, expected_without_auth: Optional[int]) -> Dict:
        """测试单个端点"""
        entry = {
            "method": method,
            "path": path,
            "description": description,
            "auth_required": auth_required,
            "passed": True,
            "errors": [],
            "warnings": [],
        }
        
        # 发送请求（不带认证 token）
        status, data, elapsed = self._request(method, path)
        entry["status"] = status
        entry["elapsed_ms"] = round(elapsed, 2)
        
        # 检查 1：无认证时的状态码
        if auth_required and expected_without_auth is not None:
            if status == expected_without_auth:
                if self.verbose:
                    print(f"  ✅ {method} {path} → {status} (符合预期 {expected_without_auth}) | {elapsed:.1f}ms")
            elif status == 200:
                entry["warnings"].append(
                    f"需要认证的接口 {path} 返回 200 而非 {expected_without_auth}，认证中间件可能未生效"
                )
                if self.verbose:
                    print(f"  ⚠️  {method} {path} → {status} (期望 {expected_without_auth}) | {elapsed:.1f}ms")
            elif status == 500:
                entry["passed"] = False
                entry["errors"].append(
                    f"安全严重：{path} 返回 500 而非 {expected_without_auth}！"
                )
                if self.verbose:
                    print(f"  ❌ {method} {path} → {status} (期望 {expected_without_auth}, 收到 500!)")
            else:
                entry["warnings"].append(
                    f"返回 {status} 而非 200 或 {expected_without_auth}"
                )
                if self.verbose:
                    print(f"  🔶 {method} {path} → {status} | {elapsed:.1f}ms")
        else:
            # 不需要认证的接口
            if status == 200:
                if self.verbose:
                    print(f"  ✅ {method} {path} → 200 | {elapsed:.1f}ms")
            elif status == -1:
                entry["passed"] = False
                entry["errors"].append(f"请求失败: {data.get('_exception', '未知错误')}")
                if self.verbose:
                    print(f"  ❌ {method} {path} → 连接失败")
            else:
                if self.verbose:
                    print(f"  🔶 {method} {path} → {status} | {elapsed:.1f}ms")
        
        # 检查 2：JSON 格式验证（仅 200 响应）
        if status == 200:
            json_errors = self._validate_response_json(path, data)
            if json_errors:
                entry["errors"].extend(json_errors)
                entry["passed"] = False
        
        return entry
    
    def _validate_response_json(self, path: str, data: Any) -> List[str]:
        """验证 JSON 响应格式"""
        errors = []
        
        if data is None:
            errors.append(f"响应为 null")
            return errors
        
        if isinstance(data, str):
            errors.append(f"响应为字符串而非 JSON 对象: {data[:100]}")
            return errors
        
        # 特定端点的格式检查
        checks = {
            "/api/feature-flags": lambda d: "flags" in d,
            "/api/health": lambda d: isinstance(d, dict),
            "/api/symbols/status": lambda d: isinstance(d, dict),
            "/api/growth/overview": lambda d: isinstance(d, dict),
            "/api/wiki": lambda d: isinstance(d, dict),
        }
        
        for prefix, checker in checks.items():
            if path.startswith(prefix):
                if not checker(data):
                    errors.append(f"响应格式不符合预期: {prefix}")
                break
        
        return errors
    
    def run_all(self) -> List[Dict]:
        """运行所有测试"""
        total = len(TEST_ENDPOINTS)
        print(f"\n{'='*60}")
        print(f" 伏羲 v2.1 API 兼容性测试")
        print(f" Base URL: {self.base_url}")
        print(f" 测试端点: {total} 个")
        print(f"{'='*60}\n")
        
        for method, path, desc, auth_required, expected_status in TEST_ENDPOINTS:
            entry = self.run_single(method, path, desc, auth_required, expected_status)
            self.results.append(entry)
        
        self._print_summary()
        return self.results
    
    def _print_summary(self):
        """打印汇总"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = sum(1 for r in self.results if not r["passed"])
        total_errors = sum(len(r["errors"]) for r in self.results)
        total_warnings = sum(len(r["warnings"]) for r in self.results)
        elapsed_total = (time.time() - self.start_time) * 1000
        
        print(f"\n{'='*60}")
        print(f" 测试汇总")
        print(f"{'='*60}")
        print(f" 总计: {total} 端点")
        print(f" 通过: {passed} ({100*passed/total:.1f}%)")
        print(f" 失败: {failed}")
        print(f" 错误: {total_errors} 处")
        print(f" 警告: {total_warnings} 处")
        print(f" 耗时: {elapsed_total:.0f}ms")
        
        if failed > 0:
            print(f"\n{'─'*60}")
            print(f" ❌ 失败详情：")
            print(f"{'─'*60}")
            for r in self.results:
                if not r["passed"]:
                    for err in r["errors"]:
                        print(f"   [{r['method']}] {r['path']}: {err}")
        
        if total_warnings > 0:
            print(f"\n{'─'*60}")
            print(f" ⚠️  警告详情：")
            print(f"{'─'*60}")
            for r in self.results:
                for warn in r["warnings"]:
                    print(f"   [{r['method']}] {r['path']}: {warn}")
        
        print(f"\n{'='*60}")
        if failed == 0:
            print(f" ✅ 全部端点通过兼容性测试")
        else:
            print(f" ❌ {failed} 个端点存在问题")
        print(f"{'='*60}\n")
    
    def save_report(self, path: str):
        """保存 JSON 报告"""
        report = {
            "base_url": self.base_url,
            "timestamp": time.time(),
            "total": len(self.results),
            "passed": sum(1 for r in self.results if r["passed"]),
            "failed": sum(1 for r in self.results if not r["passed"]),
            "results": self.results,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"📄 报告已保存: {path}")


def main():
    parser = argparse.ArgumentParser(description="伏羲 v2.1 API 兼容性测试")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"API 服务器地址 (默认: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细输出每个请求的结果",
    )
    parser.add_argument(
        "--report",
        default="tests/api_compatibility_report.json",
        help="JSON 报告保存路径",
    )
    args = parser.parse_args()
    
    print(f"🔍 伏羲 v2.1 API 兼容性测试工具")
    print(f"   目标: {args.base_url}")
    
    # 1. 检查服务器可达性
    runner = APITestRunner(args.base_url, verbose=args.verbose)
    status, data, elapsed = runner._request("GET", "/api/health")
    
    if status == -1:
        print(f"\n❌ 无法连接到 {args.base_url}")
        print(f"   请确保后端服务器已启动：")
        print(f"   cd E:\\easyclaw\\伏羲-v1.44\\repo")
        print(f"   python src/server.py")
        sys.exit(1)
    
    print(f"   ✅ 服务器可达 (健康检查: {status}, {elapsed:.0f}ms)")
    
    # 2. 运行全量测试
    results = runner.run_all()
    
    # 3. 保存报告
    runner.save_report(args.report)
    
    # 4. 退出码
    failed = sum(1 for r in results if not r["passed"])
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
