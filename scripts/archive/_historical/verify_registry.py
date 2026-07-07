#!/usr/bin/env python3
with open('src/category_registry.py', 'r', encoding='utf-8') as f:
    content = f.read()
if '操作手册_泛微OA' in content:
    print("OK: 字符串存在")
else:
    print("ERROR: 字符串不存在")

# 检查 CATEGORIES 里有没有
import ast
# 找 CATEGORIES = { ... } 块
start = content.find('CATEGORIES = {')
if start < 0:
    print("ERROR: 找不到 CATEGORIES")
else:
    # 找到匹配的 }
    depth = 0
    end = start
    for i, c in enumerate(content[start:]):
        if c == '{': depth += 1
        elif c == '}': depth -= 1
        if depth == 0:
            end = start + i + 1
            break
    cat_block = content[start:end]
    if '操作手册_泛微OA' in cat_block:
        print("OK: 在 CATEGORIES 字典内")
    else:
        print("ERROR: 不在 CATEGORIES 字典内")
        # 检查插入位置
        print(f"文件末尾200字符:\n{content[-200:]}")
