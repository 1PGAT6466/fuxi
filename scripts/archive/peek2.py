#!/usr/bin/env python3
with open('src/category_registry.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找 CATEGORIES dict 的结尾
in_categories = False
depth = 0
for i, line in enumerate(lines):
    if 'CATEGORIES' in line and '{' in line:
        in_categories = True
    if in_categories:
        depth += line.count('{') - line.count('}')
        if depth == 0:
            print(f"CATEGORIES 结束于第 {i+1} 行: {line.rstrip()}")
            # 打印前后几行
            for j in range(max(0, i-2), min(len(lines), i+5)):
                print(f"  {j+1}: {lines[j].rstrip()}")
            break

# 找 match_category 函数
print("\n=== match_category ===")
for i, line in enumerate(lines):
    if 'def match_category' in line:
        for j in range(i, min(len(lines), i+30)):
            print(f"  {j+1}: {lines[j].rstrip()}")
        break
