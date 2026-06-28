#!/usr/bin/env python3
"""最终修复：把 fuxi 和 meridian 引用存入 app.state，v2_routes 从 Request 访问"""
import os

BASE = '/home/feng-shaoxuan/kb-server'
os.chdir(BASE)

# 1. 修复 server.py startup — 存入 app.state.meridian
with open('src/server.py') as f:
    srv = f.read()

if 'app.state.meridian = _fuxi_instance.meridian' not in srv:
    srv = srv.replace(
        '        app.state.fuxi = _fuxi_instance',
        '''        app.state.fuxi = _fuxi_instance
        app.state.meridian = _fuxi_instance.meridian
        app.state.fuxi_version = "4.2"
        app.state.fuxi_born_at = __import__('time').time()'''
    )
    with open('src/server.py', 'w') as f:
        f.write(srv)
    print("server.py: meridian 已存入 app.state")

# 2. 修复 v2_routes.py 使用 Request 获取
with open('src/api/v2_routes.py') as f:
    content = f.read()

# 确保有 from fastapi import Request
if 'from fastapi import' in content and 'Request' not in content.split('from fastapi import')[1].split('\n')[0]:
    content = content.replace('from fastapi import APIRouter, Query, HTTPException',
                              'from fastapi import APIRouter, Query, HTTPException, Request')

# 修改 bagua_status 函数签名和获取方式
old_sig = 'async def bagua_status():'
new_sig = 'async def bagua_status(request: Request):'
if old_sig in content:
    content = content.replace(old_sig, new_sig)

# 替换 fuxi 获取逻辑
old_block = '''    try:
        from src.server import app
        _fuxi = getattr(app.state, "fuxi", None)
        if _fuxi is None:
            from src.server import _fuxi_instance
            _fuxi = _fuxi_instance
        if _fuxi is None:
            return {"ok": False, "error": "伏羲生命体尚未苏醒"}
        meridian = _fuxi.meridian'''

new_block = '''    try:
        meridian = request.app.state.meridian
        _fuxi = request.app.state.fuxi
    except AttributeError:
        try:
            from src.server import _fuxi_instance as _fuxi
            if _fuxi is None:
                return {"ok": False, "error": "伏羲生命体尚未苏醒"}
            meridian = _fuxi.meridian
        except:
            return {"ok": False, "error": "伏羲生命体尚未苏醒"}'''

if old_block in content:
    content = content.replace(old_block, new_block)
    with open('src/api/v2_routes.py', 'w') as f:
        f.write(content)
    print("v2_routes.py: 已使用 Request.app.state.meridian")
else:
    print("OLD PATTERN NOT FOUND, showing context around line 44:")
    for i, line in enumerate(content.split('\n')[43:58], start=44):
        print(f"{i}: {line}")

print("\n修复完成，请重启服务")
