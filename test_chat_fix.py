#!/usr/bin/env python3
"""
测试 Chat 接口修复：验证 message 字段可以正常工作
"""
import requests
import json
import sys

# 测试配置
BASE_URL = "http://localhost:8080"
TOKEN = "test-token"  # 需要替换为实际的 token

def test_chat_with_message():
    """测试使用 message 字段发送消息"""
    url = f"{BASE_URL}/api/chat"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "message": "你好"
    }
    
    try:
        print(f"发送请求: POST {url}")
        print(f"请求体: {json.dumps(data, ensure_ascii=False)}")
        
        response = requests.post(url, json=data, headers=headers)
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            print("✅ 测试通过: 使用 message 字段可以正常工作")
            return True
        else:
            print(f"❌ 测试失败: 期望 200，实际 {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        return False

def test_chat_with_query():
    """测试使用 query 字段发送消息（原有方式）"""
    url = f"{BASE_URL}/api/chat"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "query": "你好"
    }
    
    try:
        print(f"\n发送请求: POST {url}")
        print(f"请求体: {json.dumps(data, ensure_ascii=False)}")
        
        response = requests.post(url, json=data, headers=headers)
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            print("✅ 测试通过: 使用 query 字段可以正常工作")
            return True
        else:
            print(f"❌ 测试失败: 期望 200，实际 {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        return False

def test_chat_with_both():
    """测试同时使用 message 和 query 字段"""
    url = f"{BASE_URL}/api/chat"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "message": "你好",
        "query": "测试"
    }
    
    try:
        print(f"\n发送请求: POST {url}")
        print(f"请求体: {json.dumps(data, ensure_ascii=False)}")
        
        response = requests.post(url, json=data, headers=headers)
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            print("✅ 测试通过: 同时使用 message 和 query 字段可以正常工作")
            return True
        else:
            print(f"❌ 测试失败: 期望 200，实际 {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Chat 接口修复测试")
    print("=" * 60)
    
    # 检查服务器是否运行
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=5)
        if response.status_code != 200:
            print(f"❌ 服务器未运行或无法访问: {BASE_URL}")
            sys.exit(1)
    except:
        print(f"❌ 无法连接到服务器: {BASE_URL}")
        print("请先启动服务器: python -m uvicorn src.server:app --host 0.0.0.0 --port 8080")
        sys.exit(1)
    
    # 运行测试
    results = []
    results.append(test_chat_with_message())
    results.append(test_chat_with_query())
    results.append(test_chat_with_both())
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ 所有测试通过: {passed}/{total}")
        sys.exit(0)
    else:
        print(f"❌ 部分测试失败: {passed}/{total}")
        sys.exit(1)