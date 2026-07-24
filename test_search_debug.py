import requests
import json
import time

# 登录获取token
r = requests.post('http://localhost:8080/api/auth/login', json={'username':'testuser_round3','password':'Test@Round3Pass1'})
if r.status_code != 200:
    print(f'Login failed: {r.status_code} - {r.text}')
    exit(1)

token = r.json().get('token')
print(f'Token obtained: {token[:30]}...')

# 测试搜索
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

# 测试简单查询
test_queries = ['连接器', '轴承', '齿轮', '压接']

for query in test_queries:
    print(f'\nTesting query: {query}')
    r2 = requests.post('http://localhost:8080/api/rag/search', 
                      json={'query': query, 'top_k': 5},
                      headers=headers)
    print(f'Status: {r2.status_code}')
    if r2.status_code == 200:
        data = r2.json()
        results = data.get('results', [])
        print(f'Results: {len(results)}')
        for i, res in enumerate(results[:3]):
            text = res.get('text', res.get('content', ''))[:80]
            score = res.get('score', 0)
            print(f'  [{i+1}] Score: {score:.3f}, Text: {text}...')
    else:
        print(f'Error: {r2.text[:200]}')
