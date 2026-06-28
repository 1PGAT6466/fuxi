#!/usr/bin/env python3
with open('src/category_registry.py', 'r', encoding='utf-8') as f:
    content = f.read()
# 打印文件的前50行和后30行
lines = content.split('\n')
print(f"总行数: {len(lines)}")
print("=== 前30行 ===")
for i, line in enumerate(lines[:30], 1):
    print(f"{i:3d}: {line}")
print("\n=== 后30行 ===")
for i, line in enumerate(lines[-30:], len(lines)-29):
    print(f"{i:3d}: {line}")
