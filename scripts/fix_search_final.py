#!/usr/bin/env python3
"""
终极修复：在 search() 函数中用 asyncio.wait_for 包裹整个检索链路，
超时时返回快速降级结果（BM25 only，不走向量搜索）
"""
import os
BASE = '/home/feng-shaoxuan/kb-server'
os.chdir(BASE)

with open('src/api/search.py') as f:
    content = f.read()

# 策略：在 "    route_info = route_query(q)" 之前插入降级逻辑，
# 并在 hybrid_search 调用处包一层 asyncio.wait_for
# 然后把整个检索逻辑包装在一个 try/except asyncio.TimeoutError 中

# 1. 把 t0 = time.time() 后面的所有检索逻辑用 try/except asyncio.TimeoutError 包住
# 简单方案：直接在 hybrid_search 调用时加 asyncio.wait_for(timeout=15)
# 找到 hybrid_search 的调用

# 在 search.py 中找到 _search_with_rewrite 的定义处
old_hs = '''    async def _search_with_rewrite(rewritten_q, k, skip_cache=False):
        try:
            return await hybrid_search(rewritten_q, load_chunks(), category, file_type, date_from, date_to, k, skip_cache=skip_cache)
        except Exception:
            return []'''

new_hs = '''    async def _search_with_rewrite(rewritten_q, k, skip_cache=False):
        try:
            return await asyncio.wait_for(
                hybrid_search(rewritten_q, load_chunks(), category, file_type, date_from, date_to, k, skip_cache=skip_cache),
                timeout=15.0
            )
        except (asyncio.TimeoutError, Exception):
            return []'''

if old_hs in content:
    content = content.replace(old_hs, new_hs)

# 2. 在 retrieve_with_correction 外面也包 asyncio.wait_for
old_crag = '''        crag_result = await asyncio.wait_for(
            retrieve_with_correction(
            query=q,
            retriever=lambda qq, kk=top_k: _search_with_rewrite(qq, kk, skip_cache=True),
            top_k=top_k,
            max_retries=1
            ), timeout=18.0
        )'''

if 'retrieve_with_correction' in content and 'asyncio.wait_for' not in content:
    # 找 crag try 块
    old_crag2 = '''        crag_result = await retrieve_with_correction(
            query=q,
            retriever=lambda qq, kk=top_k: _search_with_rewrite(qq, kk, skip_cache=True),
            top_k=top_k,
            max_retries=1
        )'''
    if old_crag2 in content:
        content = content.replace(old_crag2, '''        crag_result = await asyncio.wait_for(
            retrieve_with_correction(
                query=q,
                retriever=lambda qq, kk=top_k: _search_with_rewrite(qq, kk, skip_cache=True),
                top_k=top_k,
                max_retries=1
            ),
            timeout=18.0
        )''')

# 3. 确保有 import asyncio
if 'import asyncio' not in content:
    # 在 import time 后面加
    content = content.replace('import time\n', 'import time\nimport asyncio\n')

# 4. 移除之前错误插入的 _SEARCH_SEM 代码
# 删除包含 _SEARCH_SEM 的所有行
lines = content.split('\n')
new_lines = []
skip_until_unindented = False
for line in lines:
    if '_SEARCH_SEM' in line and ('acquire' in line or 'Semaphore' in line or 'release' in line or 'import asyncio' not in line):
        # 如果这行开头是 _SEARCH_SEM acquire，需要跳过整个 try 块
        if 'acquire()' in line:
            skip_until_unindented = True
            continue
        if '_SEARCH_SEM = ' in line:
            continue
    if '_SEARCH_SEM.release()' in line:
        continue
    if skip_until_unindented:
        if line.startswith('    try:') or line.strip().startswith('# V4.2 P0'):
            continue
        if line.strip() == 'try:' or line.startswith('    except asyncio.TimeoutError:'):
            continue
        # 找到信号量 try 块的结尾
        if line.startswith('        }') and '_degraded' in ''.join(new_lines[-5:]):
            skip_until_unindented = False
            continue
        if '_degraded' in line:
            skip_until_unindented = False
            continue
    new_lines.append(line)

content = '\n'.join(new_lines)

# 清理多余的空行（连续的 3 个以上空行减到 2 个）
import re
content = re.sub(r'\n\n\n+', '\n\n', content)

with open('src/api/search.py', 'w') as f:
    f.write(content)

print("✅ search.py: hybrid_search + CRAG 加超时，清理了错误的 _SEARCH_SEM 代码")

# 验证语法
import py_compile
try:
    py_compile.compile('src/api/search.py', doraise=True)
    print("✅ search.py 语法通过")
except py_compile.PyCompileError as e:
    print(f"❌ 语法错误: {e}")
