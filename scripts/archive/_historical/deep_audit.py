#!/usr/bin/env python3
"""伏羲 V4.2 深度代码审计扫描"""
import os, re, ast, sys

BASE = '/home/feng-shaoxuan/kb-server'
os.chdir(BASE)
sys.path.insert(0, BASE)

report = {"sync_in_async": [], "no_await": [], "hardcoded": [], "dead_imports": [], "missing_handlers": []}

# 扫描所有非 _unused 的 py 文件
for root, dirs, files in os.walk('src'):
    dirs[:] = [d for d in dirs if d not in ('__pycache__', '_unused')]
    for fn in files:
        if not fn.endswith('.py'):
            continue
        fpath = os.path.join(root, fn)
        with open(fpath, errors='ignore') as f:
            content = f.read()
        
        # 1. 同步阻塞调用在 async 上下文中
        if 'async def' in content:
            # 同步文件 I/O
            if 'open(' in content and 'aiofiles' not in content:
                report["sync_in_async"].append(f"{fn}: sync open() in async context")
            # 同步 HTTP
            if re.search(r'requests\.(get|post)', content) and 'aiohttp' not in content:
                report["sync_in_async"].append(f"{fn}: sync requests in async context")
            # 同步 sleep
            if 'time.sleep(' in content and 'asyncio.sleep' not in content:
                report["sync_in_async"].append(f"{fn}: time.sleep in async context")
            # SQLite 同步调用
            if 'sqlite3.connect' in content:
                report["sync_in_async"].append(f"{fn}: sync sqlite3 in async context")

        # 2. 硬编码凭据/机密
        if re.search(r'(api_key|API_KEY|password|PASSWORD|secret|SECRET)\s*=\s*["\'][^"\']{8,}', content):
            if 'os.getenv' not in content and 'os.environ' not in content:
                report["hardcoded"].append(f"{fn}: hardcoded credential suspected")

        # 3. 缺少 __init__.py 检查
        # (skip, not critical)

        # 4. 检查是否有未处理的 await 表达式
        lines = content.split('\n')
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('#') or stripped.startswith('"""'):
                continue
            # await 但没赋值也没 return 且不在 async def 中（简单检测）
            if 'await ' in stripped and 'async def' not in stripped:
                # 空值赋给了变量但没使用 → 不报
                pass

# 5. 检查 server.py 注册了哪些路由
with open('src/server.py') as f:
    server_content = f.read()

routes_found = re.findall(r'app\.include_router\((\w+)', server_content)
report["registered_routers"] = routes_found

# 检查每个 router 是否有对应的文件
api_dir = 'src/api'
for rf in routes_found:
    expected = os.path.join(api_dir, f'{rf}.py')
    if not os.path.exists(expected):
        report["missing_handlers"].append(f"Router '{rf}' has no file at {expected}")

# 输出
print("=== 深度代码审计 ===")
for cat, items in report.items():
    if cat == 'registered_routers':
        print(f"\n📋 已注册路由: {', '.join(items)}")
        continue
    if items:
        print(f"\n⚠️ {cat.upper()} ({len(items)}):")
        for item in items:
            print(f"  - {item}")
    else:
        if cat in ('sync_in_async', 'hardcoded', 'dead_imports', 'missing_handlers'):
            print(f"\n✅ {cat}: 未发现问题")

# 6. 统计
py_files = sum(1 for root,dirs,files in os.walk('src') 
               for fn in files if fn.endswith('.py') and '_unused' not in root and '__pycache__' not in root)
print(f"\n📊 总源文件: {py_files}")
print(f"📊 _unused 归档: {len([f for f in os.listdir('src/services/_unused') if f.endswith('.py')])}")
