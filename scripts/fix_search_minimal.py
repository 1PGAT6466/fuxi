#!/usr/bin/env python3
"""最小侵入修复：search.py 中的 hybrid_search 调用加 asyncio.wait_for(15s)"""
import os
BASE = '/home/feng-shaoxuan/kb-server'
os.chdir(BASE)

with open('src/api/search.py') as f:
    content = f.read()

# 1. 确保有 import asyncio
if 'import asyncio' not in content:
    content = content.replace('import time\n', 'import time\nimport asyncio\n')
    print("added import asyncio")

# 2. 给 _search_with_rewrite 中的 hybrid_search 加超时
old = '''    async def _search_with_rewrite(rewritten_q, k, skip_cache=False):
        try:
            return await hybrid_search(rewritten_q, load_chunks(), category, file_type, date_from, date_to, k, skip_cache=skip_cache)
        except Exception:
            return []'''

new = '''    async def _search_with_rewrite(rewritten_q, k, skip_cache=False):
        try:
            return await asyncio.wait_for(
                hybrid_search(rewritten_q, load_chunks(), category, file_type, date_from, date_to, k, skip_cache=skip_cache),
                timeout=15.0
            )
        except (asyncio.TimeoutError, Exception):
            return []'''

if old in content:
    content = content.replace(old, new)
    with open('src/api/search.py', 'w') as f:
        f.write(content)
    print("✅ hybrid_search 调用加 15s 超时")
else:
    print("❌ OLD PATTERN NOT FOUND")
    # 显示现有的
    idx = content.find('async def _search_with_rewrite')
    if idx > 0:
        print(content[idx:idx+300])

# 3. 语法检查
import py_compile
try:
    py_compile.compile('src/api/search.py', doraise=True)
    print("✅ 语法通过")
except py_compile.PyCompileError as e:
    print(f"❌ {e}")
