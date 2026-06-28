# 阶段 5: 代码深度审查

import os, sys, ast, re
from collections import defaultdict

BASE = '/home/feng-shaoxuan/kb-server'
os.chdir(BASE)

print('=' * 60)
print('阶段 5: 代码深度审查')
print('=' * 60)

# ===== 5.1 循环依赖检测 =====
print('\n[5.1] 循环依赖检测')
# 构建依赖图
dep_graph = defaultdict(set)
all_modules = {}
for root, dirs, files in os.walk('src/'):
    for fname in files:
        if fname.endswith('.py') and '__pycache__' not in root:
            rel = os.path.relpath(os.path.join(root, fname), BASE).replace('\\','/').replace('.py','').replace('/','.')
            path = os.path.join(root, fname)
            with open(path) as f:
                content = f.read()
            all_modules[rel] = content

for mod, content in all_modules.items():
    # 提取 import
    imports = set()
    for m in re.findall(r'from (src\.\S+) import', content):
        parts = m.split('.')
        for i in range(1, len(parts)+1):
            imports.add('.'.join(parts[:i]))
    dep_graph[mod] = imports

# 检测循环
def find_cycles(graph):
    visited = set()
    rec_stack = set()
    cycles = []
    def dfs(node, path):
        visited.add(node)
        rec_stack.add(node)
        for neighbor in graph.get(node, set()):
            if neighbor not in visited:
                dfs(neighbor, path + [neighbor])
            elif neighbor in rec_stack:
                cycle = path[path.index(neighbor):] + [neighbor]
                cycles.append(cycle)
        rec_stack.discard(node)
    for node in graph:
        if node not in visited:
            dfs(node, [node])
    return cycles

cycles = find_cycles(dep_graph)
if cycles:
    print(f'  ⚠ 发现 {len(cycles)} 个循环:')
    for c in cycles:
        print(f'    → {" → ".join(c)}')
else:
    print('  ✅ 无循环依赖')

# ===== 5.2 async 审查 =====
print('\n[5.2] async/await 审查')
issues = []
for mod, content in all_modules.items():
    if 'async def' in content:
        # 检查是否有 await
        if ' await ' not in content and mod not in ('src.hypothalamus.meridian','src.hypothalamus.balance.meridian_rhythm'):
            pass  # 空 async 函数允许
    # 检查 time.sleep
    if 'time.sleep(' in content and 'import asyncio' in content:
        issues.append(f'{mod}: time.sleep 在 asyncio 上下文中使用')

# 检查全局变量
print('[5.3] 全局变量检查')
global_vars = []
for mod, content in all_modules.items():
    # 寻找模块级的可变状态
    top_level = content.split('\ndef ')[0] if 'def ' in content else content.split('\nclass ')[0]
    if re.search(r'^\w+\s*=\s*(list|dict|set|{})', top_level, re.MULTILINE):
        global_vars.append(mod)

if global_vars:
    print(f'  ⚠ 发现 {len(global_vars)} 个模块有全局可变状态:')
    for g in global_vars[:5]:
        print(f'    {g}')
else:
    print('  ✅ 无危险全局状态')

# ===== 5.4 ChromaDB 连接检查 =====
print('\n[5.4] ChromaDB 连接检查')
chroma_refs = []
for mod, content in all_modules.items():
    if 'chromadb' in content.lower():
        chroma_refs.append(mod)
print(f'  {len(chroma_refs)} 个模块引用 ChromaDB')
for c in chroma_refs:
    print(f'    {c}')

# ===== 5.5 统计 =====
print('\n[5.5] 代码统计')
total_lines = 0
total_funcs = 0
for mod, content in all_modules.items():
    lines = content.count('\n')
    total_lines += lines
    funcs = len(re.findall(r'def \w+\(', content))
    total_funcs += funcs

print(f'  总模块: {len(all_modules)}')
print(f'  总行数: {total_lines}')
print(f'  总函数: {total_funcs}')
print(f'  平均每模块: {total_lines//len(all_modules)} 行, {total_funcs//len(all_modules)} 函数')

print('\n✅ 阶段 5 完成')
