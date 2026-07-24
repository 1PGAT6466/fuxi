"""
创建测试用户脚本
"""
import requests
import json

BASE_URL = "http://localhost:8080"

def create_test_user():
    """创建测试用户"""
    try:
        # 尝试注册新用户
        resp = requests.post(f"{BASE_URL}/api/auth/register",
                           json={
                               "username": "testuser2026",
                               "password": "Test123456"
                           },
                           timeout=10)
        
        if resp.status_code == 200:
            print("✅ 测试用户创建成功")
            return True
        else:
            print(f"❌ 创建用户失败: {resp.status_code}")
            print(f"响应: {resp.text}")
            return False
    except Exception as e:
        print(f"❌ 创建用户异常: {e}")
        return False

def test_login():
    """测试登录"""
    try:
        resp = requests.post(f"{BASE_URL}/api/auth/login",
                           json={
                               "username": "testuser2026",
                               "password": "Test123456"
                           },
                           timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            print("✅ 登录成功")
            print(f"Token: {data.get('token', 'N/A')[:50]}...")
            return data.get('token')
        else:
            print(f"❌ 登录失败: {resp.status_code}")
            print(f"响应: {resp.text}")
            return None
    except Exception as e:
        print(f"❌ 登录异常: {e}")
        return None

if __name__ == "__main__":
    print("创建测试用户...")
    if create_test_user():
        print("\n测试登录...")
        token = test_login()
        if token:
            print(f"\n✅ 测试用户创建并登录成功！")
            print(f"用户名: testuser2026")
            print(f"密码: Test123456")
        else:
            print("\n❌ 登录失败")
    else:
        print("\n❌ 用户创建失败")
