"""
伏羲知识库系统第三轮全维度测试
测试重点：搜索准确性、中文编码、结果去重、响应性能
"""
import requests
import json
import time
import hashlib
from datetime import datetime

BASE_URL = "http://localhost:8080"
ADMIN_USER = "admin"
ADMIN_PASS = "Admin@123456"  # 需要先确认密码

# 测试用户
TEST_USER = "testuser_round3"
TEST_PASS = "Test@Round3Pass1"

def get_admin_token():
    """获取管理员token"""
    # 尝试常见密码
    passwords = ["admin123", "Admin@123456", "admin", "Admin123!"]
    for pwd in passwords:
        try:
            resp = requests.post(f"{BASE_URL}/api/auth/login",
                               json={"username": ADMIN_USER, "password": pwd},
                               timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                print(f"✅ 管理员登录成功 (密码: {pwd[:3]}...)")
                return data.get("token")
        except Exception:
            continue
    return None

def create_test_user(admin_token):
    """创建测试用户"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    try:
        # 先检查用户是否存在
        resp = requests.post(f"{BASE_URL}/api/auth/register",
                           json={
                               "username": TEST_USER,
                               "password": TEST_PASS,
                               "email": "test@fuxi.local"
                           },
                           timeout=10)
        if resp.status_code == 200:
            print(f"✅ 测试用户 '{TEST_USER}' 创建成功")
            return True
        else:
            print(f"⚠️ 创建用户响应: {resp.status_code} - {resp.text[:100]}")
            # 如果用户已存在，继续尝试登录
            return True
    except Exception as e:
        print(f"❌ 创建用户异常: {e}")
        return False

def login_test_user():
    """测试用户登录"""
    try:
        resp = requests.post(f"{BASE_URL}/api/auth/login",
                           json={"username": TEST_USER, "password": TEST_PASS},
                           timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ 测试用户登录成功")
            return data.get("token")
        else:
            print(f"❌ 登录失败: {resp.status_code} - {resp.text[:100]}")
            return None
    except Exception as e:
        print(f"❌ 登录异常: {e}")
        return None

def test_search(token, query, top_k=5):
    """测试搜索功能并记录性能"""
    headers = {"Authorization": f"Bearer {token}"}
    start_time = time.time()
    
    try:
        resp = requests.post(f"{BASE_URL}/api/rag/search",
                           json={"query": query, "top_k": top_k},
                           headers=headers,
                           timeout=30)
        
        elapsed = time.time() - start_time
        
        result = {
            "query": query,
            "status_code": resp.status_code,
            "elapsed_ms": round(elapsed * 1000, 2),
            "success": resp.status_code == 200
        }
        
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            result["result_count"] = len(results)
            result["results"] = []
            
            for r in results[:top_k]:
                text = r.get("text", r.get("content", ""))
                score = r.get("score", 0)
                source = r.get("source", r.get("metadata", {}).get("source", ""))
                chunk_id = r.get("id", r.get("chunk_id", ""))
                
                result["results"].append({
                    "score": round(score, 4),
                    "source": source,
                    "chunk_id": chunk_id,
                    "text_preview": text[:150] if text else "",
                    "text_hash": hashlib.md5(text.encode()).hexdigest() if text else ""
                })
        else:
            result["error"] = resp.text[:200]
            result["result_count"] = 0
            result["results"] = []
        
        return result
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "query": query,
            "status_code": 0,
            "elapsed_ms": round(elapsed * 1000, 2),
            "success": False,
            "error": str(e),
            "result_count": 0,
            "results": []
        }

def check_chinese_encoding(results):
    """检查中文编码是否正常"""
    issues = []
    for r in results:
        text = r.get("text_preview", "")
        # 检查是否有乱码特征
        if "\\x" in text or "\\u" in text:
            issues.append(f"查询 '{r['query']}' 结果包含转义字符")
        # 检查是否有常见乱码模式
        garbled_patterns = ["锟斤拷", "烫烫烫", "屯屯屯", "?", "??"]
        for pattern in garbled_patterns:
            if pattern in text:
                issues.append(f"查询 '{r['query']}' 结果包含乱码: {pattern}")
    return issues

def analyze_duplicates(all_results):
    """分析搜索结果中的重复"""
    total_results = 0
    unique_results = set()
    duplicate_count = 0
    
    for query_result in all_results:
        for r in query_result.get("results", []):
            total_results += 1
            text_hash = r.get("text_hash", "")
            if text_hash:
                if text_hash in unique_results:
                    duplicate_count += 1
                else:
                    unique_results.add(text_hash)
    
    return {
        "total": total_results,
        "unique": len(unique_results),
        "duplicates": duplicate_count,
        "duplicate_ratio": round(duplicate_count / total_results * 100, 2) if total_results > 0 else 0
    }

def main():
    print("=" * 70)
    print("🔍 伏羲知识库系统第三轮全维度测试")
    print(f"📅 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # 1. 检查服务状态
    print("\n【1. 服务状态检查】")
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        if resp.status_code == 200:
            health = resp.json()
            print(f"✅ 服务状态: {health.get('status')}")
            print(f"   版本: {health.get('version')}")
            print(f"   运行时间: {health.get('uptime')}")
        else:
            print(f"❌ 服务异常: {resp.status_code}")
            return
    except Exception as e:
        print(f"❌ 无法连接服务: {e}")
        return
    
    # 2. 获取认证
    print("\n【2. 认证测试】")
    admin_token = get_admin_token()
    if not admin_token:
        print("❌ 无法获取管理员token，尝试直接创建测试用户...")
    
    # 创建并登录测试用户
    create_test_user(admin_token)
    token = login_test_user()
    if not token:
        print("❌ 无法获取测试用户token，测试终止")
        return
    
    # 3. 检查文档状态
    print("\n【3. 文档状态检查】")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{BASE_URL}/api/documents", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            files = data.get("files", [])
            print(f"📄 已加载文档数: {len(files)}")
            total_chunks = 0
            for f in files:
                chunks = f.get("chunk_count", 0)
                total_chunks += chunks
                print(f"   - {f.get('file_name', 'N/A')}: {chunks} chunks")
            print(f"📊 总chunks数: {total_chunks}")
        else:
            print(f"⚠️ 获取文档列表失败: {resp.status_code}")
    except Exception as e:
        print(f"⚠️ 检查文档异常: {e}")
    
    # 4. 执行搜索测试
    print("\n【4. 搜索准确性测试】")
    print("-" * 70)
    
    test_queries = [
        # Foxconn 相关
        {"query": "端子压接工艺要求", "category": "Foxconn", "expected_source": "连接器设计手册"},
        {"query": "连接器设计规范", "category": "Foxconn", "expected_source": "连接器设计手册"},
        
        # Mini-fakraTE 相关
        {"query": "自动化产线检测流程", "category": "Mini-fakraTE", "expected_source": "Mini-fakraTE"},
        {"query": "装配工艺控制要点", "category": "Mini-fakraTE", "expected_source": "Mini-fakraTE"},
        
        # 标准件相关
        {"query": "轴承型号大全", "category": "标准件", "expected_source": "标准件"},
        {"query": "标准件采购清单", "category": "标准件", "expected_source": "标准件"},
        
        # 非标准机械相关
        {"query": "齿轮设计计算", "category": "非标准机械", "expected_source": "非标准机械设计手册"},
        {"query": "机械零件强度校核", "category": "非标准机械", "expected_source": "非标准机械设计手册"},
    ]
    
    all_results = []
    for i, test_case in enumerate(test_queries, 1):
        query = test_case["query"]
        print(f"\n[{i}/8] 查询: '{query}' (类别: {test_case['category']})")
        print("  " + "-" * 50)
        
        result = test_search(token, query, top_k=5)
        all_results.append(result)
        
        if result["success"]:
            print(f"  ✅ 状态: 成功")
            print(f"  ⏱️  响应时间: {result['elapsed_ms']}ms")
            print(f"  📊 结果数: {result['result_count']}")
            
            if result["results"]:
                print(f"  📝 结果预览:")
                for j, r in enumerate(result["results"][:3], 1):
                    print(f"     [{j}] 分数: {r['score']}, 来源: {r['source'][:30]}...")
                    print(f"         内容: {r['text_preview'][:80]}...")
            else:
                print(f"  ⚠️ 无搜索结果")
        else:
            print(f"  ❌ 状态: 失败")
            print(f"  错误: {result.get('error', 'N/A')[:100]}")
        
        time.sleep(0.3)  # 避免请求过快
    
    # 5. 中文编码测试
    print("\n【5. 中文编码测试】")
    print("-" * 70)
    
    encoding_queries = [
        "连接器设计",
        "压接工艺",
        "轴承型号",
        "齿轮计算",
        "强度校核",
        "自动化产线",
        "装配工艺",
        "标准件"
    ]
    
    encoding_results = []
    for query in encoding_queries:
        result = test_search(token, query, top_k=3)
        encoding_results.append({
            "query": query,
            "success": result["success"],
            "result_count": result["result_count"],
            "has_results": result["result_count"] > 0
        })
    
    # 检查编码问题
    encoding_issues = check_chinese_encoding(
        [{"query": q, "text_preview": r.get("results", [{}])[0].get("text_preview", "") if r.get("results") else ""} 
         for q, r in zip(encoding_queries, [test_search(token, q, top_k=1) for q in encoding_queries])]
    )
    
    if encoding_issues:
        print("⚠️ 发现编码问题:")
        for issue in encoding_issues:
            print(f"   - {issue}")
    else:
        print("✅ 中文编码正常，未发现乱码")
    
    # 6. 结果去重分析
    print("\n【6. 结果去重分析】")
    print("-" * 70)
    
    dedup_stats = analyze_duplicates(all_results)
    print(f"📊 总结果数: {dedup_stats['total']}")
    print(f"📊 唯一结果数: {dedup_stats['unique']}")
    print(f"📊 重复结果数: {dedup_stats['duplicates']}")
    print(f"📊 重复率: {dedup_stats['duplicate_ratio']}%")
    
    # 7. 性能统计
    print("\n【7. 响应性能统计】")
    print("-" * 70)
    
    response_times = [r["elapsed_ms"] for r in all_results if r["success"]]
    if response_times:
        avg_time = sum(response_times) / len(response_times)
        max_time = max(response_times)
        min_time = min(response_times)
        print(f"📊 平均响应时间: {avg_time:.2f}ms")
        print(f"📊 最大响应时间: {max_time:.2f}ms")
        print(f"📊 最小响应时间: {min_time:.2f}ms")
        print(f"📊 成功查询数: {len(response_times)}/{len(all_results)}")
    else:
        print("⚠️ 无成功查询，无法统计性能")
    
    # 8. 评分
    print("\n【8. 评分结果】")
    print("=" * 70)
    
    # 搜索准确性评分 (4分)
    successful_queries = sum(1 for r in all_results if r["success"])
    queries_with_results = sum(1 for r in all_results if r["success"] and r["result_count"] > 0)
    
    if queries_with_results == len(all_results):
        search_score = 4.0
    elif queries_with_results >= len(all_results) * 0.75:
        search_score = 3.0
    elif queries_with_results >= len(all_results) * 0.5:
        search_score = 2.0
    elif queries_with_results > 0:
        search_score = 1.0
    else:
        search_score = 0.0
    
    # 检查结果相关性
    relevant_count = 0
    for i, result in enumerate(all_results):
        if result["success"] and result["result_count"] > 0:
            # 简单检查：结果中是否包含查询关键词
            query = test_queries[i]["query"]
            for r in result["results"]:
                text = r.get("text_preview", "")
                if any(kw in text for kw in query.split()):
                    relevant_count += 1
                    break
    
    relevance_bonus = (relevant_count / len(all_results)) * 0.5 if all_results else 0
    search_score = min(4.0, search_score + relevance_bonus)
    
    # 中文编码评分 (2分)
    if not encoding_issues:
        encoding_score = 2.0
    elif len(encoding_issues) <= 2:
        encoding_score = 1.5
    elif len(encoding_issues) <= 4:
        encoding_score = 1.0
    else:
        encoding_score = 0.5
    
    # 结果去重评分 (2分)
    if dedup_stats["total"] == 0:
        dedup_score = 2.0  # 无结果时给满分
    elif dedup_stats["duplicate_ratio"] == 0:
        dedup_score = 2.0
    elif dedup_stats["duplicate_ratio"] <= 10:
        dedup_score = 1.5
    elif dedup_stats["duplicate_ratio"] <= 20:
        dedup_score = 1.0
    else:
        dedup_score = 0.5
    
    # 响应性能评分 (2分)
    if response_times:
        if avg_time < 500:
            perf_score = 2.0
        elif avg_time < 1000:
            perf_score = 1.5
        elif avg_time < 2000:
            perf_score = 1.0
        else:
            perf_score = 0.5
    else:
        perf_score = 0.0
    
    total_score = search_score + encoding_score + dedup_score + perf_score
    
    print(f"🎯 搜索准确性: {search_score:.1f}/4.0")
    print(f"   - 成功查询: {successful_queries}/{len(all_results)}")
    print(f"   - 有结果查询: {queries_with_results}/{len(all_results)}")
    print(f"   - 相关结果查询: {relevant_count}/{len(all_results)}")
    
    print(f"🔤 中文编码处理: {encoding_score:.1f}/2.0")
    print(f"   - 编码问题数: {len(encoding_issues)}")
    
    print(f"🔄 结果去重: {dedup_score:.1f}/2.0")
    print(f"   - 重复率: {dedup_stats['duplicate_ratio']}%")
    
    print(f"⚡ 响应性能: {perf_score:.1f}/2.0")
    if response_times:
        print(f"   - 平均响应: {avg_time:.0f}ms")
    
    print(f"\n{'='*70}")
    print(f"🏆 总分: {total_score:.1f}/10.0")
    
    if total_score >= 9:
        rating = "优秀 ⭐⭐⭐⭐⭐"
    elif total_score >= 8:
        rating = "良好 ⭐⭐⭐⭐"
    elif total_score >= 7:
        rating = "合格 ⭐⭐⭐"
    elif total_score >= 6:
        rating = "及格 ⭐⭐"
    else:
        rating = "不及格 ⭐"
    
    print(f"📊 评级: {rating}")
    
    # 9. 发现的问题
    print("\n【9. 发现的问题】")
    print("-" * 70)
    
    issues = []
    if queries_with_results < len(all_results):
        issues.append(f"⚠️ {len(all_results) - queries_with_results} 个查询无结果")
    if encoding_issues:
        issues.append(f"⚠️ 发现 {len(encoding_issues)} 个编码问题")
    if dedup_stats["duplicates"] > 0:
        issues.append(f"⚠️ 发现 {dedup_stats['duplicates']} 个重复结果")
    if response_times and max(response_times) > 2000:
        issues.append(f"⚠️ 最大响应时间 {max(response_times):.0f}ms 超过2秒")
    
    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  ✅ 未发现严重问题")
    
    # 10. 改进建议
    print("\n【10. 改进建议】")
    print("-" * 70)
    
    suggestions = []
    if queries_with_results < len(all_results) * 0.8:
        suggestions.append("📌 提高搜索召回率，考虑优化向量模型或增加混合检索")
    if dedup_stats["duplicate_ratio"] > 10:
        suggestions.append("📌 优化去重逻辑，减少重复结果")
    if response_times and avg_time > 1000:
        suggestions.append("📌 优化搜索性能，考虑缓存或索引优化")
    if encoding_issues:
        suggestions.append("📌 检查文档导入时的编码处理")
    
    if suggestions:
        for sug in suggestions:
            print(f"  {sug}")
    else:
        print("  ✅ 系统表现良好，暂无改进建议")
    
    # 11. 保存测试报告
    print("\n【11. 保存测试报告】")
    print("-" * 70)
    
    report = {
        "test_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "test_round": 3,
        "total_score": round(total_score, 2),
        "rating": rating,
        "scores": {
            "search_accuracy": round(search_score, 2),
            "chinese_encoding": round(encoding_score, 2),
            "duplicate_detection": round(dedup_score, 2),
            "response_performance": round(perf_score, 2)
        },
        "statistics": {
            "total_queries": len(all_results),
            "successful_queries": successful_queries,
            "queries_with_results": queries_with_results,
            "relevant_queries": relevant_count,
            "encoding_issues": len(encoding_issues),
            "duplicate_stats": dedup_stats,
            "performance": {
                "avg_ms": round(avg_time, 2) if response_times else 0,
                "max_ms": round(max_time, 2) if response_times else 0,
                "min_ms": round(min_time, 2) if response_times else 0
            }
        },
        "query_results": all_results,
        "encoding_results": encoding_results,
        "issues_found": issues,
        "suggestions": suggestions
    }
    
    report_path = "E:\\easyclaw\\伏羲-v1.44\\repo\\round3_test_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"✅ 测试报告已保存: {report_path}")
    
    print("\n" + "=" * 70)
    print("🏁 第三轮全维度测试完成")
    print("=" * 70)

if __name__ == "__main__":
    main()
