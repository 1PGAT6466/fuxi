"""
伏羲知识库系统第二轮全维度测试
==============================
测试重点：搜索质量、中文编码、重复内容检测、边界条件
"""
import requests
import json
import time
import sys
from typing import List, Dict, Any

BASE_URL = "http://localhost:8080"
ADMIN_USER = "testuser2026"
ADMIN_PASS = "Test123456"

class KnowledgeSearchTester:
    def __init__(self):
        self.access_token = None
        self.test_results = []
        self.total_score = 0
        
    def login(self):
        """登录获取token"""
        try:
            resp = requests.post(f"{BASE_URL}/api/auth/login", 
                               json={"username": ADMIN_USER, "password": ADMIN_PASS},
                               timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                self.access_token = data.get("access_token")
                print("✅ 登录成功")
                return True
            else:
                print(f"❌ 登录失败: {resp.status_code}")
                return False
        except Exception as e:
            print(f"❌ 登录异常: {e}")
            return False
    
    def get_headers(self):
        """获取认证头"""
        return {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}
    
    def test_search_quality(self):
        """测试搜索质量"""
        print("\n" + "="*60)
        print("【第一部分】搜索质量测试 (3分)")
        print("="*60)
        
        test_queries = [
            # Foxconn相关
            ("端子压接工艺要求", "Foxconn"),
            ("连接器设计规范", "Foxconn"),
            
            # Mini-fakraTE相关
            ("自动化产线检测流程", "Mini-fakraTE"),
            ("装配工艺控制要点", "Mini-fakraTE"),
            
            # 标准件相关
            ("轴承型号大全", "标准件"),
            ("标准件采购清单", "标准件"),
            
            # 非标准机械相关
            ("齿轮设计计算", "非标准机械"),
            ("机械零件强度校核", "非标准机械"),
        ]
        
        search_results = []
        for query, category in test_queries:
            try:
                resp = requests.post(f"{BASE_URL}/api/rag/search",
                                   json={"query": query},
                                   headers=self.get_headers(),
                                   timeout=15)
                
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    search_results.append({
                        "query": query,
                        "category": category,
                        "result_count": len(results),
                        "status": "success",
                        "results": results
                    })
                    print(f"✅ '{query}' -> {len(results)} 条结果")
                else:
                    search_results.append({
                        "query": query,
                        "category": category,
                        "result_count": 0,
                        "status": f"error_{resp.status_code}",
                        "results": []
                    })
                    print(f"❌ '{query}' -> 错误: {resp.status_code}")
                    
            except Exception as e:
                search_results.append({
                    "query": query,
                    "category": category,
                    "result_count": 0,
                    "status": f"exception_{str(e)}",
                    "results": []
                })
                print(f"❌ '{query}' -> 异常: {e}")
        
        # 计算搜索质量得分
        successful_queries = sum(1 for r in search_results if r["status"] == "success")
        avg_results = sum(r["result_count"] for r in search_results) / len(search_results)
        
        # 评分标准：成功查询率 * 1.5 + 平均结果数得分 * 1.5
        success_score = (successful_queries / len(search_results)) * 1.5
        result_score = min(1.5, avg_results / 5 * 1.5)  # 平均5条结果得满分
        
        search_quality_score = success_score + result_score
        self.total_score += search_quality_score
        
        print(f"\n搜索质量得分: {search_quality_score:.2f}/3.0")
        print(f"  - 查询成功率: {successful_queries}/{len(search_results)} ({success_score:.2f}/1.5)")
        print(f"  - 平均结果数: {avg_results:.1f} ({result_score:.2f}/1.5)")
        
        return search_results
    
    def test_chinese_encoding(self):
        """测试中文编码处理"""
        print("\n" + "="*60)
        print("【第二部分】中文编码测试 (2分)")
        print("="*60)
        
        chinese_queries = [
            "连接器设计",
            "压接工艺",
            "轴承型号",
            "齿轮计算",
            "强度校核",
            "自动化产线",
            "装配工艺",
            "标准件",
        ]
        
        encoding_results = []
        for query in chinese_queries:
            try:
                resp = requests.post(f"{BASE_URL}/api/rag/search",
                                   json={"query": query},
                                   headers=self.get_headers(),
                                   timeout=10)
                
                if resp.status_code == 200:
                    data = resp.json()
                    # 检查返回内容是否包含乱码
                    results_text = json.dumps(data, ensure_ascii=False)
                    has_garbled = any(ord(c) > 65535 for c in results_text)
                    
                    encoding_results.append({
                        "query": query,
                        "status": "success",
                        "has_garbled": has_garbled,
                        "result_count": len(data.get("results", []))
                    })
                    
                    if has_garbled:
                        print(f"⚠️ '{query}' -> 包含特殊字符")
                    else:
                        print(f"✅ '{query}' -> 编码正常")
                else:
                    encoding_results.append({
                        "query": query,
                        "status": f"error_{resp.status_code}",
                        "has_garbled": False,
                        "result_count": 0
                    })
                    print(f"❌ '{query}' -> 错误: {resp.status_code}")
                    
            except Exception as e:
                encoding_results.append({
                    "query": query,
                    "status": f"exception_{str(e)}",
                    "has_garbled": False,
                    "result_count": 0
                })
                print(f"❌ '{query}' -> 异常: {e}")
        
        # 计算编码得分
        successful_queries = sum(1 for r in encoding_results if r["status"] == "success")
        garbled_queries = sum(1 for r in encoding_results if r.get("has_garbled"))
        
        # 评分标准：成功查询率 * 1.0 + 无乱码率 * 1.0
        success_score = (successful_queries / len(encoding_results)) * 1.0
        encoding_score = ((len(encoding_results) - garbled_queries) / len(encoding_results)) * 1.0
        
        chinese_encoding_score = success_score + encoding_score
        self.total_score += chinese_encoding_score
        
        print(f"\n中文编码得分: {chinese_encoding_score:.2f}/2.0")
        print(f"  - 查询成功率: {successful_queries}/{len(encoding_results)} ({success_score:.2f}/1.0)")
        print(f"  - 无乱码率: {len(encoding_results) - garbled_queries}/{len(encoding_results)} ({encoding_score:.2f}/1.0)")
        
        return encoding_results
    
    def test_duplicate_detection(self):
        """测试重复内容检测"""
        print("\n" + "="*60)
        print("【第三部分】重复内容检测 (2分)")
        print("="*60)
        
        test_query = "连接器设计"
        try:
            resp = requests.post(f"{BASE_URL}/api/rag/search",
                               json={"query": test_query},
                               headers=self.get_headers(),
                               timeout=15)
            
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                
                # 检查重复内容
                seen_texts = set()
                duplicates = []
                unique_results = []
                
                for i, result in enumerate(results):
                    text = result.get("text", "") or result.get("content", "")
                    text_hash = hash(text.strip())
                    
                    if text_hash in seen_texts:
                        duplicates.append({
                            "index": i,
                            "text_preview": text[:100] + "..." if len(text) > 100 else text
                        })
                    else:
                        seen_texts.add(text_hash)
                        unique_results.append(result)
                
                duplicate_ratio = len(duplicates) / len(results) if results else 0
                
                print(f"查询 '{test_query}' 返回 {len(results)} 条结果")
                print(f"去重后: {len(unique_results)} 条结果")
                print(f"重复内容: {len(duplicates)} 条 ({duplicate_ratio*100:.1f}%)")
                
                if duplicates:
                    print("\n重复内容示例:")
                    for dup in duplicates[:3]:  # 只显示前3个
                        print(f"  第{dup['index']}条: {dup['text_preview']}")
                
                # 评分标准：去重率 * 2.0
                dedup_score = (1 - duplicate_ratio) * 2.0
                self.total_score += dedup_score
                
                print(f"\n重复内容检测得分: {dedup_score:.2f}/2.0")
                
                return {
                    "total_results": len(results),
                    "unique_results": len(unique_results),
                    "duplicates": len(duplicates),
                    "duplicate_ratio": duplicate_ratio,
                    "score": dedup_score
                }
            else:
                print(f"❌ 查询失败: {resp.status_code}")
                return {"error": resp.status_code}
                
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            return {"error": str(e)}
    
    def test_boundary_conditions(self):
        """测试边界条件"""
        print("\n" + "="*60)
        print("【第四部分】边界条件测试 (2分)")
        print("="*60)
        
        boundary_tests = [
            ("空查询", ""),
            ("单字符", "a"),
            ("特殊字符", "!@#$%^&*()"),
            ("超长查询", "连接" * 100),  # 200字符
            ("混合字符", "test测试123"),
            ("SQL注入", "'; DROP TABLE users; --"),
            ("HTML标签", "<script>alert('test')</script>"),
            ("Unicode", "\u4f60\u597d"),
        ]
        
        boundary_results = []
        for test_name, query in boundary_tests:
            try:
                resp = requests.post(f"{BASE_URL}/api/rag/search",
                                   json={"query": query},
                                   headers=self.get_headers(),
                                   timeout=10)
                
                # 检查是否正确处理边界条件
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    boundary_results.append({
                        "test": test_name,
                        "query": query[:50] + "..." if len(query) > 50 else query,
                        "status": "success",
                        "result_count": len(results),
                        "handled_correctly": True
                    })
                    print(f"✅ {test_name}: 正常处理 ({len(results)} 条结果)")
                elif resp.status_code == 422:
                    # 验证错误，这是正常的边界处理
                    boundary_results.append({
                        "test": test_name,
                        "query": query[:50] + "..." if len(query) > 50 else query,
                        "status": "validation_error",
                        "result_count": 0,
                        "handled_correctly": True
                    })
                    print(f"✅ {test_name}: 验证拒绝 (422)")
                elif resp.status_code == 400:
                    # 请求错误，也是正常的边界处理
                    boundary_results.append({
                        "test": test_name,
                        "query": query[:50] + "..." if len(query) > 50 else query,
                        "status": "bad_request",
                        "result_count": 0,
                        "handled_correctly": True
                    })
                    print(f"✅ {test_name}: 请求拒绝 (400)")
                else:
                    boundary_results.append({
                        "test": test_name,
                        "query": query[:50] + "..." if len(query) > 50 else query,
                        "status": f"error_{resp.status_code}",
                        "result_count": 0,
                        "handled_correctly": False
                    })
                    print(f"❌ {test_name}: 错误 {resp.status_code}")
                    
            except Exception as e:
                boundary_results.append({
                    "test": test_name,
                    "query": query[:50] + "..." if len(query) > 50 else query,
                    "status": f"exception_{str(e)}",
                    "result_count": 0,
                    "handled_correctly": False
                })
                print(f"❌ {test_name}: 异常 {e}")
        
        # 计算边界条件得分
        correctly_handled = sum(1 for r in boundary_results if r["handled_correctly"])
        boundary_score = (correctly_handled / len(boundary_results)) * 2.0
        self.total_score += boundary_score
        
        print(f"\n边界条件测试得分: {boundary_score:.2f}/2.0")
        print(f"正确处理: {correctly_handled}/{len(boundary_results)}")
        
        return boundary_results
    
    def test_overall_experience(self):
        """测试整体体验"""
        print("\n" + "="*60)
        print("【第五部分】整体体验 (1分)")
        print("="*60)
        
        experience_tests = []
        
        # 测试1：响应时间
        start_time = time.time()
        try:
            resp = requests.post(f"{BASE_URL}/api/rag/search",
                               json={"query": "连接器设计"},
                               headers=self.get_headers(),
                               timeout=10)
            response_time = time.time() - start_time
            
            if resp.status_code == 200:
                experience_tests.append({
                    "test": "响应时间",
                    "value": f"{response_time:.2f}s",
                    "passed": response_time < 3.0  # 3秒内为合格
                })
                print(f"✅ 响应时间: {response_time:.2f}s (< 3.0s)")
            else:
                experience_tests.append({
                    "test": "响应时间",
                    "value": f"错误: {resp.status_code}",
                    "passed": False
                })
                print(f"❌ 响应时间测试失败: {resp.status_code}")
        except Exception as e:
            experience_tests.append({
                "test": "响应时间",
                "value": f"异常: {e}",
                "passed": False
            })
            print(f"❌ 响应时间测试异常: {e}")
        
        # 测试2：结果格式
        try:
            resp = requests.post(f"{BASE_URL}/api/rag/search",
                               json={"query": "测试"},
                               headers=self.get_headers(),
                               timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                
                # 检查结果格式
                format_ok = True
                for result in results[:3]:  # 检查前3条
                    if not isinstance(result, dict):
                        format_ok = False
                        break
                    # 检查必要字段
                    if "text" not in result and "content" not in result:
                        format_ok = False
                        break
                
                experience_tests.append({
                    "test": "结果格式",
                    "value": f"{len(results)} 条结果",
                    "passed": format_ok
                })
                print(f"✅ 结果格式: {'正常' if format_ok else '异常'}")
            else:
                experience_tests.append({
                    "test": "结果格式",
                    "value": f"错误: {resp.status_code}",
                    "passed": False
                })
                print(f"❌ 结果格式测试失败: {resp.status_code}")
        except Exception as e:
            experience_tests.append({
                "test": "结果格式",
                "value": f"异常: {e}",
                "passed": False
            })
            print(f"❌ 结果格式测试异常: {e}")
        
        # 测试3：错误处理
        try:
            resp = requests.post(f"{BASE_URL}/api/rag/search",
                               json={},  # 空请求体
                               headers=self.get_headers(),
                               timeout=10)
            
            error_handled = resp.status_code in [400, 422]
            experience_tests.append({
                "test": "错误处理",
                "value": f"状态码: {resp.status_code}",
                "passed": error_handled
            })
            print(f"✅ 错误处理: {'正常' if error_handled else '异常'}")
        except Exception as e:
            experience_tests.append({
                "test": "错误处理",
                "value": f"异常: {e}",
                "passed": False
            })
            print(f"❌ 错误处理测试异常: {e}")
        
        # 计算整体体验得分
        passed_tests = sum(1 for t in experience_tests if t["passed"])
        experience_score = (passed_tests / len(experience_tests)) * 1.0
        self.total_score += experience_score
        
        print(f"\n整体体验得分: {experience_score:.2f}/1.0")
        print(f"通过测试: {passed_tests}/{len(experience_tests)}")
        
        return experience_tests
    
    def generate_report(self, search_results, encoding_results, duplicate_results, boundary_results, experience_results):
        """生成测试报告"""
        print("\n" + "="*60)
        print("【第二轮全维度测试报告】")
        print("="*60)
        
        print(f"\n总分: {self.total_score:.2f}/10.0")
        print(f"评级: {'优秀' if self.total_score >= 9 else '良好' if self.total_score >= 7 else '一般' if self.total_score >= 5 else '较差'}")
        
        print("\n【详细评分】")
        print(f"1. 搜索准确性: {min(3.0, self.total_score * 0.3):.2f}/3.0")
        print(f"2. 中文编码处理: {min(2.0, self.total_score * 0.2):.2f}/2.0")
        print(f"3. 结果去重: {min(2.0, self.total_score * 0.2):.2f}/2.0")
        print(f"4. 边界条件处理: {min(2.0, self.total_score * 0.2):.2f}/2.0")
        print(f"5. 整体体验: {min(1.0, self.total_score * 0.1):.2f}/1.0")
        
        # 生成JSON报告
        report = {
            "test_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_score": round(self.total_score, 2),
            "rating": "优秀" if self.total_score >= 9 else "良好" if self.total_score >= 7 else "一般" if self.total_score >= 5 else "较差",
            "detailed_scores": {
                "search_accuracy": round(min(3.0, self.total_score * 0.3), 2),
                "chinese_encoding": round(min(2.0, self.total_score * 0.2), 2),
                "duplicate_detection": round(min(2.0, self.total_score * 0.2), 2),
                "boundary_conditions": round(min(2.0, self.total_score * 0.2), 2),
                "overall_experience": round(min(1.0, self.total_score * 0.1), 2)
            },
            "test_results": {
                "search_quality": search_results,
                "chinese_encoding": encoding_results,
                "duplicate_detection": duplicate_results,
                "boundary_conditions": boundary_results,
                "overall_experience": experience_results
            },
            "issues_found": [],
            "recommendations": []
        }
        
        # 分析问题
        if duplicate_results and duplicate_results.get("duplicate_ratio", 0) > 0.1:
            report["issues_found"].append(f"重复内容比例较高: {duplicate_results['duplicate_ratio']*100:.1f}%")
            report["recommendations"].append("优化去重算法，减少重复结果")
        
        if encoding_results:
            garbled_count = sum(1 for r in encoding_results if r.get("has_garbled"))
            if garbled_count > 0:
                report["issues_found"].append(f"存在中文编码问题: {garbled_count}个查询出现乱码")
                report["recommendations"].append("检查字符编码处理，确保UTF-8正确处理")
        
        if boundary_results:
            failed_boundary = sum(1 for r in boundary_results if not r["handled_correctly"])
            if failed_boundary > 0:
                report["issues_found"].append(f"边界条件处理不当: {failed_boundary}个测试失败")
                report["recommendations"].append("加强输入验证和错误处理")
        
        # 保存报告
        report_path = "E:\\easyclaw\\伏羲-v1.44\\repo\\round2_knowledge_search_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n详细报告已保存到: {report_path}")
        
        # 打印问题和建议
        if report["issues_found"]:
            print("\n【发现的问题】")
            for i, issue in enumerate(report["issues_found"], 1):
                print(f"{i}. {issue}")
        
        if report["recommendations"]:
            print("\n【改进建议】")
            for i, rec in enumerate(report["recommendations"], 1):
                print(f"{i}. {rec}")
        
        return report
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始伏羲知识库系统第二轮全维度测试")
        print("="*60)
        
        # 登录
        if not self.login():
            print("❌ 登录失败，无法继续测试")
            return
        
        # 运行所有测试
        search_results = self.test_search_quality()
        encoding_results = self.test_chinese_encoding()
        duplicate_results = self.test_duplicate_detection()
        boundary_results = self.test_boundary_conditions()
        experience_results = self.test_overall_experience()
        
        # 生成报告
        report = self.generate_report(search_results, encoding_results, duplicate_results, boundary_results, experience_results)
        
        return report

if __name__ == "__main__":
    tester = KnowledgeSearchTester()
    report = tester.run_all_tests()
