#!/usr/bin/env python3
"""修复 v2_routes.py 中的 fuxi 实例获取方式"""
import os

BASE = '/home/feng-shaoxuan/kb-server'
os.chdir(BASE)

fp = 'src/api/v2_routes.py'
with open(fp) as f:
    content = f.read()

old = '''    try:
        from src.server import _fuxi_instance as _fuxi
        if _fuxi is None:
            return {"ok": False, "error": "伏羲生命体尚未苏醒"}
        meridian = _fuxi.meridian'''

new = '''    try:
        from src.server import app
        _fuxi = getattr(app.state, "fuxi", None)
        if _fuxi is None:
            from src.server import _fuxi_instance
            _fuxi = _fuxi_instance
        if _fuxi is None:
            return {"ok": False, "error": "伏羲生命体尚未苏醒"}
        meridian = _fuxi.meridian'''

if old in content:
    content = content.replace(old, new)
    with open(fp, 'w') as f:
        f.write(content)
    print("v2_routes.py: fuxi 实例获取已修复（app.state.fuxi → 模块级 fallback）")
else:
    print("PATTERN NOT FOUND")
    # Debug
    for i, line in enumerate(content.split('\n')[44:56], start=45):
        print(f"{i}: {line}")
