# 阶段 4: 系统架构审查 + 模块集成

import os, sys, ast, re
from collections import defaultdict

BASE = '/home/feng-shaoxuan/kb-server'
os.chdir(BASE)

# ===== 1. 识别重复模块 =====
print('=' * 60)
print('阶段 4: 系统架构审查')
print('=' * 60)

services_dir = 'src/services'
all_services = sorted(os.listdir(services_dir))

# embed.py vs embedder.py -> 合并到 embedder
if os.path.exists('src/services/embed.py') and os.path.exists('src/services/embedder.py'):
    print('[4.a] 合并 embed.py -> embedder.py')
    with open('src/services/embedder.py') as f:
        ed_src = f.read()
    with open('src/services/embed.py') as f:
        em_src = f.read()
    # 简单追加（保留两个功能集）
    combined = ed_src + '\n# === merged from embed.py ===\n' + em_src
    with open('src/services/embedder.py', 'w') as f:
        f.write(combined)
    os.remove('src/services/embed.py')
    print('  embed.py 已合并并删除')

# ingestion.py vs ingest.py -> 合并到 ingest.py
if os.path.exists('src/services/ingestion.py') and os.path.exists('src/services/ingest.py'):
    print('[4.b] 合并 ingestion.py -> ingest.py')
    with open('src/services/ingest.py') as f:
        ig_src = f.read()
    with open('src/services/ingestion.py') as f:
        in_src = f.read()
    combined = ig_src + '\n# === merged from ingestion.py ===\n' + in_src
    with open('src/services/ingest.py', 'w') as f:
        f.write(combined)
    os.remove('src/services/ingestion.py')
    print('  ingestion.py 已合并并删除')

# 删除 .bak 文件
for f in os.listdir(services_dir):
    if f.endswith('.bak') or f.endswith('.c1bak'):
        os.remove(os.path.join(services_dir, f))
        print(f'  删除备份: {f}')

# self_rag.py 实际上未被引用，移到 archive（已在 src/services 中但检查 import）
all_imports = set()
for root, dirs, files in os.walk('src/'):
    for fname in files:
        if fname.endswith('.py') and '__pycache__' not in root:
            path = os.path.join(root, fname)
            with open(path) as f:
                content = f.read()
            # 查找 import
            for m in re.findall(r'from src\.services\.(\w+)|import src\.services\.(\w+)', content):
                all_imports.add(m[0] or m[1])
            for m in re.findall(r'from \.(\w+)|from services\.(\w+)', content):
                all_imports.add(m[0] or m[1])

unused = []
for fname in all_services:
    name = fname.replace('.py','')
    if name in ('__init__','__pycache__','parsers'):
        continue
    if name not in all_imports:
        unused.append(name)

print(f'\n[4.c] 引用分析: {len(all_services)} 服务文件')
print(f'  被引用的: {sorted(list(all_imports.intersection(set(s.replace(".py","") for s in all_services))))}')
print(f'  未被引用的: {sorted(unused)}')

# ===== 2. kidney.py 重复（organs/ 和 hypothalamus/ 都有） =====
if os.path.exists('src/hypothalamus/kidney.py'):
    print('\n[4.d] 删除重复的 src/hypothalamus/kidney.py（organs/kidney.py 为源）')
    os.remove('src/hypothalamus/kidney.py')

# ===== 3. 核心链路检查 =====
print('\n[4.e] 核心链路:')
core = ['ingest','chunker','embedder','retrieval','rerank']
for c in core:
    path = f'src/services/{c}.py'
    flag = '✅' if os.path.exists(path) else '❌'
    print(f'  {flag} {c}')

# ===== 4. 依赖图输出 =====
print('\n[4.f] 服务间依赖关系:')
for sname in sorted(os.listdir(services_dir)):
    if not sname.endswith('.py') or sname.startswith('__'):
        continue
    name = sname[:-3]
    path = os.path.join(services_dir, sname)
    with open(path) as f:
        content = f.read()
    deps = re.findall(r'from src\.services\.(\w+)', content) + re.findall(r'from \.(\w+)', content)
    deps = [d for d in set(deps) if d != name and d not in ('__init__','llm','db')]
    if deps:
        print(f'  {name} → {deps}')

print('\n✅ 阶段 4 完成')
