#!/usr/bin/env python3
"""修复 ChromaDB 同步调用阻塞事件循环的问题"""
import os

BASE = '/home/feng-shaoxuan/kb-server'
os.chdir(BASE)

# 1. 修复 retrieval.py: vs.query -> run_in_executor
fp = 'src/services/retrieval.py'
with open(fp) as f:
    content = f.read()

old = '        async with _VECTOR_SEM:\n            vr = vs.query(q_emb[0], n_results=n_results, where=chroma_filter)'
new = '''        async with _VECTOR_SEM:
            loop = asyncio.get_running_loop()
            vr = await loop.run_in_executor(
                None, 
                lambda: vs.query(q_emb[0], n_results=n_results, where=chroma_filter)
            )'''

if old in content:
    content = content.replace(old, new)
    # 确保 import asyncio
    if 'import asyncio' not in content:
        content = 'import asyncio\n' + content
    with open(fp, 'w') as f:
        f.write(content)
    print("FIXED: retrieval.py vs.query -> run_in_executor")
else:
    print("OLD PATTERN NOT FOUND in retrieval.py")

# 2. 检查是否有其他 ChromaDB 同步调用阻塞点
check_files = [
    'src/services/ingest.py',
    'src/services/wiki.py', 
    'src/services/auto_classifier.py',
]
for cf in check_files:
    if os.path.exists(cf):
        with open(cf) as f:
            fc = f.read()
        if '.query(' in fc and 'run_in_executor' not in fc and 'async def' in fc:
            print(f"WARNING: {cf} has sync .query() without run_in_executor")

# 3. 检查 embed_texts 调用是否也有问题 — 它是 async 的，OK
print("\n✅ ChromaDB 阻塞修复完成")
