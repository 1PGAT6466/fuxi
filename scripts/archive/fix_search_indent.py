#!/usr/bin/env python3
"""修复 search.py 缩进"""
import os
BASE = '/home/feng-shaoxuan/kb-server'
os.chdir(BASE)

with open('src/api/search.py') as f:
    content = f.read()

# 问题：第 75 行 "try:" 后面没有对应的缩进块
# 把 "    try:\n    # D5: metrics" 改成 "#  try: ..."（注释掉重复的 try）
old = '''    try:
    # D5: metrics'''
new = '''    # V4.2 P0: 在信号量保护下执行检索'''
if old in content:
    content = content.replace(old, new)
    with open('src/api/search.py', 'w') as f:
        f.write(content)
    print("FIXED: removed duplicate try:")
else:
    print("PATTERN NOT FOUND")
    # 显示实际问题行
    for i, line in enumerate(content.split('\n')[74:82], 75):
        print(f'{i}: {repr(line[:60])}')
