#!/usr/bin/env python3
"""修复 LLM 调用超时导致搜索卡住的问题"""
import os

BASE = '/home/feng-shaoxuan/kb-server'
os.chdir(BASE)

# 1. query_expansion.py: llm_rewrite_query 和 hyde_expand_query 加 10s 超时
fp = 'src/services/query_expansion.py'
with open(fp) as f:
    content = f.read()

# 把 call_ai_raw 包装成带超时的版本
old_rewrite = "        rewritten = await call_ai_raw(prompt, max_tokens=80)"
new_rewrite = '''        rewritten = await asyncio.wait_for(
            call_ai_raw(prompt, max_tokens=80), timeout=10.0
        )'''
if old_rewrite in content:
    content = content.replace(old_rewrite, new_rewrite)

old_hyde = "        hyde_response = await call_ai_raw(prompt, max_tokens=150)"
new_hyde = '''        hyde_response = await asyncio.wait_for(
            call_ai_raw(prompt, max_tokens=150), timeout=10.0
        )'''
if old_hyde in content:
    content = content.replace(old_hyde, new_hyde)

# 确保 import asyncio
if 'import asyncio' not in content:
    content = 'import asyncio\n' + content

with open(fp, 'w') as f:
    f.write(content)
print("query_expansion.py: LLM rewrite + HyDE 已加 10s 超时")

# 2. 检查 retrieval.py 中的 hyde_task 等待 — 如果超时，不要阻塞整体
fp2 = 'src/services/retrieval.py'
with open(fp2) as f:
    content2 = f.read()

# 确保对已经 await hyde_task 的地方用 asyncio.wait_for 包一下
# 找到 await hyde_task
if '    vector_results = await hyde_task' in content2:
    content2 = content2.replace(
        '    vector_results = await hyde_task',
        '''    try:
        vector_results = await asyncio.wait_for(hyde_task, timeout=15.0)
    except asyncio.TimeoutError:
        logger.warning("[Retrieval] HyDE task timeout, continuing without it")
        vector_results = []'''
    )
    with open(fp2, 'w') as f:
        f.write(content2)
    print("retrieval.py: HyDE task 已加 15s 超时保护")

# 3. 同样保护 llm_rewrite_task
if '    llm_rewritten = await llm_rewrite_task' in content2:
    content2 = content2.replace(
        '    llm_rewritten = await llm_rewrite_task',
        '''    try:
        llm_rewritten = await asyncio.wait_for(llm_rewrite_task, timeout=10.0)
    except (asyncio.TimeoutError, Exception):
        llm_rewritten = None'''
    )
    with open(fp2, 'w') as f:
        f.write(content2)
    print("retrieval.py: LLM rewrite task 已加 10s 超时保护")

print("\n✅ LLM 超时保护修复完成")
