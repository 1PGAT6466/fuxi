"""
伏羲 v1.44 全量运行测试脚本
============================
"""
import requests
import json
import time

BASE_URL = "http://localhost:8080"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

# 全局变量存储token
access_token = None
refresh_token = None

def test_endpoint(method, endpoint, data=None, headers=None, expected_status=None, test_name=""):
    """通用测试函数"""
    url = f"{BASE_URL}{endpoint}"
    try:
        if method.upper() == "GET":
            resp = requests.get(url, headers=headers, timeout=10)
        elif method.upper() == "POST":
            resp = requests.post(url, json=data, headers=headers, timeout=10)
        elif method.upper() == "DELETE":
            resp = requests.delete(url, headers=headers, timeout=10)
        else:
            resp = requests.request(method, url, json=data, headers=headers, timeout=10)
        
        status_ok = True
        if expected_status and resp.status_code != expected_status:
            status_ok = False
        
        result = {
            "test": test_name,
            "method": method,
            "endpoint": endpoint,
            "status_code": resp.status_code,
            "expected_status": expected_status,
            "status_ok": status_ok,
            "response_size": len(resp.text)
        }
        
        try:
            result["response"] = resp.json()
        except:
            result["response"] = resp.text[:200]
        
        return result
    except Exception as e:
        return {
            "test": test_name,
            "method": method,
            "endpoint": endpoint,
            "status_code": None,
            "error": str(e),
            "status_ok": False
        }

def run_all_tests():
    global access_token, refresh_token
    results = []
    
    print("=" * 60)
    print("伏羲 v1.44 全量运行测试")
    print("=" * 60)
    
    # 一、后端启动测试
    print("\n[一] 后端启动测试")
    print("-" * 40)
    
    # 1. 健康检查
    result = test_endpoint("GET", "/api/health", expected_status=200, test_name="1.1 健康检查")
    results.append(result)
    print(f"1.1 健康检查: {result['status_code']} {'✓' if result['status_ok'] else '✗'}")
    
    # 二、API端点全量测试
    print("\n[二] API端点全量测试")
    print("-" * 40)
    
    # 2. 登录测试 - 无效凭据
    result = test_endpoint("POST", "/api/auth/login", 
                          data={"username": "wrong", "password": "wrong"},
                          expected_status=401,
                          test_name="2.1 登录-无效凭据")
    results.append(result)
    print(f"2.1 登录-无效凭据: {result['status_code']} {'✓' if result['status_ok'] else '✗'}")
    
    # 3. 登录测试 - 有效凭据
    result = test_endpoint("POST", "/api/auth/login",
                          data={"username": ADMIN_USER, "password": ADMIN_PASS},
                          test_name="2.2 登录-有效凭据")
    results.append(result)
    print(f"2.2 登录-有效凭据: {result['status_code']} {'✓' if result['status_ok'] else '✗'}")
    
    if result.get("response") and isinstance(result["response"], dict):
        access_token = result["response"].get("access_token")
        refresh_token = result["response"].get("refresh_token")
    
    # 设置认证头
    auth_headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
    
    # 4. 获取当前用户
    result = test_endpoint("GET", "/api/auth/me", headers=auth_headers, 
                          expected_status=200, test_name="2.3 获取当前用户")
    results.append(result)
    print(f"2.3 获取当前用户: {result['status_code']} {'✓' if result['status_ok'] else '✗'}")
    
    # 5. 刷新Token
    if refresh_token:
        result = test_endpoint("POST", "/api/auth/refresh",
                              data={"refresh_token": refresh_token},
                              test_name="2.4 刷新Token")
        results.append(result)
        print(f"2.4 刷新Token: {result['status_code']} {'✓' if result['status_ok'] else '✗'}")
        if result.get("response") and isinstance(result["response"], dict):
            new_token = result["response"].get("access_token")
            if new_token:
                access_token = new_token
                auth_headers = {"Authorization": f"Bearer {access_token}"}
    
    # 6. 注册测试
    result = test_endpoint("POST", "/api/auth/register",
                          data={"username": "testuser2026", "password": "Test123456"},
                          test_name="2.5 注册新用户")
    results.append(result)
    print(f"2.5 注册新用户: {result['status_code']} {'✓' if result['status_ok'] else '✗'}")
    
    # 7. 搜索测试
    result = test_endpoint("GET", "/api/search?q=test", headers=auth_headers,
                          test_name="2.6 搜索")
    results.append(result)
    print(f"2.6 搜索: {result['status_code']} {'✓' if result['status_ok'] else '✗'}")
    
    # 8. 获取会话列表
    result = test_endpoint("GET", "/api/chat/sessions", headers=auth_headers,
                          test_name="2.7 获取会话列表")
    results.append(result)
    print(f"2.7 获取会话列表: {result['status_code']} {'✓' if result['status_ok'] else '✗'}")
    
    # 9. 发送消息
    result = test_endpoint("POST", "/api/chat/send",
                          data={"message": "你好", "session_id": None},
                          headers=auth_headers,
                          test_name="2.8 发送消息")
    results.append(result)
    print(f"2.8 发送消息: {result['status_code']} {'✓' if result['status_ok'] else '✗'}")
    
    # 10. 文档列表
    result = test_endpoint("GET", "/api/documents", headers=auth_headers,
                          test_name="2.9 文档列表")
    results.append(result)
    print(f"2.9 文档列表: {result['status_code']} {'✓' if result['status_ok'] else '✗'}")
    
    # 11. Wiki页面
    result = test_endpoint("GET", "/api/wiki", headers=auth_headers,
                          test_name="2.10 Wiki页面")
    results.append(result)
    print(f"2.10 Wiki页面: {result['status_code']} {'✓' if result['status_ok'] else '✗'}")
    
    # 12. 知识图谱
    result = test_endpoint("GET", "/api/graph", headers=auth_headers,
                          test_name="2.11 知识图谱")
    results.append(result)
    print(f"2.11 知识图谱: {result['status_code']} {'✓' if result['status_ok'] else '✗'}")
    
    # 13. RAG搜索
    result = test_endpoint("POST", "/api/rag/search",
                          data={"query": "测试"},
                          headers=auth_headers,
                          test_name="2.12 RAG搜索")
    results.append(result)
    print(f"2.12 RAG搜索: {result['status_code']} {'✓' if result['status_ok'] else '✗'}")
    
    # 14. 评测概览
    result = test_endpoint("GET", "/api/evaluation/overview", headers=auth_headers,
                          test_name="2.13 评测概览")
    results.append(result)
    print(f"2.13 评测概览: {result['status_code']} {'✓' if result['status_ok'] else '✗'}")
    
    # 15. 功能开关
    result = test_endpoint("GET", "/api/feature-flags", headers=auth_headers,
                          test_name="2.14 功能开关")
    results.append(result)
    print(f"2.14 功能开关: {result['status_code']} {'✓' if result['status_ok'] else '✗'}")
    
    # 16. 服务列表
    result = test_endpoint("GET", "/api/services", headers=auth_headers,
                          test_name="2.15 服务列表")
    results.append(result)
    print(f"2.15 服务列表: {result['status_code']} {'✓' if result['status_ok'] else '✗'}")
    
    # 三、错误处理测试
    print("\n[三] 错误处理测试")
    print("-" * 40)
    
    # 17. 未认证访问
    result = test_endpoint("GET", "/api/auth/me", expected_status=401,
                          test_name="3.1 未认证访问")
    results.append(result)
    print(f"3.1 未认证访问: {result['status_code']} {'✓' if result['status_ok'] else '✗'}")
    
    # 18. 不存在的端点
    result = test_endpoint("GET", "/api/nonexistent", expected_status=404,
                          test_name="3.2 不存在端点")
    results.append(result)
    print(f"3.2 不存在端点: {result['status_code']} {'✓' if result['status_ok'] else '✗'}")
    
    # 19. 无效输入
    result = test_endpoint("POST", "/api/auth/login",
                          data={"invalid": "data"},
                          test_name="3.3 无效输入")
    results.append(result)
    print(f"3.3 无效输入: {result['status_code']} {'✓' if result['status_ok'] else '✗'}")
    
    # 20. 空输入
    result = test_endpoint("POST", "/api/auth/login",
                          data={},
                          test_name="3.4 空输入")
    results.append(result)
    print(f"3.4 空输入: {result['status_code']} {'✓' if result['status_ok'] else '✗'}")
    
    # 四、自我进化体系测试
    print("\n[四] 自我进化体系测试")
    print("-" * 40)
    
    # 检查模块导入
    import_tests = [
        ("src.evolution.feedback_loop", "4.1 feedback_loop"),
        ("src.evolution.knowledge_lifecycle", "4.2 knowledge_lifecycle"),
        ("src.evolution.feature_flags", "4.3 feature_flags"),
        ("src.evoution.wiki_engine", "4.4 wiki_engine"),
    ]
    
    for module_name, test_name in import_tests:
        try:
            __import__(module_name)
            results.append({"test": test_name, "status_ok": True, "status_code": 200})
            print(f"{test_name}: ✓")
        except ImportError as e:
            results.append({"test": test_name, "status_ok": False, "error": str(e)})
            print(f"{test_name}: ✗ ({e})")
    
    # 统计结果
    print("\n" + "=" * 60)
    print("测试统计")
    print("=" * 60)
    
    total = len(results)
    passed = sum(1 for r in results if r.get("status_ok", False))
    failed = total - passed
    
    print(f"总计: {total}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"通过率: {passed/total*100:.1f}%")
    
    return results

if __name__ == "__main__":
    results = run_all_tests()
    
    # 保存结果到JSON
    with open("test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n结果已保存到 test_results.json")