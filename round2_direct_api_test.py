"""
伏羲知识库系统第二轮全维度测试 - 直接API测试
"""
import requests
import json
import time

BASE_URL = "http://localhost:8080"
TEST_USER = "testuser2026"
TEST_PASS = "Test123456"

def login():
    """登录获取token"""
    try:
        resp = requests.post(f"{BASE_URL}/api/auth/login", 
                           json={"username": TEST_USER, "password": TEST_PASS},
                           timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("token")
        else:
            print(f"登录失败: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        print(f"登录异常: {e}")
        return None

def test_search(token, query, top_k=5):
    """测试搜索功能"""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.post(f"{BASE_URL}/api/rag/search",
                           json={"query": query, "top_k": top_k},
                           headers=headers,
                           timeout=15)
        
        print(f"\n查询: '{query}'")
        print(f"状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            print(f"结果数: {len(results)}")
            
            if results:
                print("前3条结果:")
                for i, result in enumerate(results[:3]):
                    text = result.get("text", result.get("content", ""))
                    score = result.get("score", 0)
                    source = result.get("source", result.get("metadata", {}).get("source", ""))
                    print(f"  {i+1}. 分数: {score:.3f}, 来源: {source}")
                    print(f"     内容: {text[:100]}...")
            else:
                print("无结果")
            
            return data
        else:
            print(f"错误: {resp.text}")
            return None
    except Exception as e:
        print(f"异常: {e}")
        return None

def main():
    print("🚀 伏羲知识库系统第二轮全维度测试")
    print("="*60)
    
    # 登录
    token = login()
    if not token:
        print("❌ 登录失败，无法继续测试")
        return
    
    print("✅ 登录成功")
    
    # 测试查询
    test_queries = [
        # Foxconn相关
        "端子压接工艺要求",
        "连接器设计规范",
        
        # Mini-fakraTE相关
        "自动化产线检测流程",
        "装配工艺控制要点",
        
        # 标准件相关
        "轴承型号大全",
        "标准件采购清单",
        
        # 非标准机械相关
        "齿轮设计计算",
        "机械零件强度校核",
        
        # 通用测试
        "连接器",
        "轴承",
        "齿轮",
        "压接",
    ]
    
    print("\n" + "="*60)
    print("【搜索质量测试】")
    print("="*60)
    
    results = []
    for query in test_queries:
        result = test_search(token, query)
        results.append(result)
        time.sleep(0.5)  # 避免请求过快
    
    # 分析结果
    print("\n" + "="*60)
    print("【测试结果分析】")
    print("="*60)
    
    successful_queries = sum(1 for r in results if r is not None)
    total_results = sum(len(r.get("results", [])) for r in results if r)
    
    print(f"成功查询: {successful_queries}/{len(test_queries)}")
    print(f"总结果数: {total_results}")
    print(f"平均结果数: {total_results/len(test_queries):.1f}")
    
    # 检查是否有结果
    if total_results == 0:
        print("\n⚠️ 所有查询都返回0条结果")
        print("可能原因:")
        print("1. 知识库未正确加载数据")
        print("2. 搜索功能实现有问题")
        print("3. 向量数据库未初始化")
        
        # 检查文档状态
        print("\n检查文档状态...")
        try:
            resp = requests.get(f"{BASE_URL}/api/documents", 
                              headers={"Authorization": f"Bearer {token}"},
                              timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                files = data.get("files", [])
                print(f"文档数: {len(files)}")
                for f in files:
                    print(f"  - {f['file_name']}: {f['chunk_count']} chunks")
            else:
                print(f"获取文档失败: {resp.status_code}")
        except Exception as e:
            print(f"检查文档异常: {e}")
    
    # 测试边界条件
    print("\n" + "="*60)
    print("【边界条件测试】")
    print("="*60)
    
    boundary_queries = [
        ("空查询", ""),
        ("单字符", "a"),
        ("特殊字符", "!@#$%^&*()"),
        ("超长查询", "连接" * 100),
        ("SQL注入", "'; DROP TABLE users; --"),
    ]
    
    for test_name, query in boundary_queries:
        print(f"\n{test_name}: '{query[:50]}{'...' if len(query) > 50 else ''}'")
        result = test_search(token, query)
        if result:
            print(f"  状态: 正常处理")
        else:
            print(f"  状态: 错误处理")
    
    print("\n" + "="*60)
    print("【测试完成】")
    print("="*60)

if __name__ == "__main__":
    main()
