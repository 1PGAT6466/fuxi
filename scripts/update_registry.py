#!/usr/bin/env python3
"""
Step 1: 更新 category_registry.py
- 新增 "操作手册_泛微OA" 分类
- match_category 加 file_name 参数 + 文件名模式匹配
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
reg_path = PROJECT_ROOT / "src" / "category_registry.py"

with open(reg_path, 'r', encoding='utf-8') as f:
    content = f.read()

# === 1. 在 CATEGORIES dict 中新增分类 ===
# 在最后一个分类条目之后、字典结尾 } 之前插入
new_cat = '''    "操作手册_泛微OA": {
        "keywords": [
            "流程引擎", "审批", "表单", "门户", "公文", "人事管理",
            "后台维护", "前台使用", "功能模块", "E-cology", "泛微",
            "协同办公", "组织架构", "权限设置", "模块配置", "考勤",
            "合同", "招聘", "培训", "报表", "资产", "客户", "预算"
        ],
        "priority": 8,
        "domain": "泛微协同办公平台E-cology操作手册",
        "desc": "泛微OA系统各模块的后台维护和前端使用手册"
    },'''

# 在字典最后一个 } 前插入
last_brace = content.rfind('}')
content = content[:last_brace] + new_cat + '\n}'

# === 2. match_category 函数签名加 file_name 参数 ===
content = content.replace(
    'def match_category(text: str, file_ext: str = "", max_len: int = 5000) -> Optional[str]:',
    'def match_category(text: str, file_ext: str = "", max_len: int = 5000, file_name: str = "") -> Optional[str]:'
)

# === 3. 在 match_category 函数体开头加入文件名模式匹配 ===
old_body_start = '''    if not text or len(text) < 5:'''

pattern_block = '''    # 文件名模式匹配：操作手册类直接命中
    if file_name:
        _MANUAL_PATTERNS = {
            '操作手册_泛微OA': ['泛微', 'E-cology', 'ecology'],
        }
        for cat, patterns in _MANUAL_PATTERNS.items():
            for pat in patterns:
                if pat.lower() in file_name.lower():
                    return cat

'''

content = content.replace(old_body_start, pattern_block + old_body_start)

# 写回
with open(reg_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("OK: category_registry.py 已更新")
print("  - 新增 操作手册_泛微OA 分类")
print("  - match_category 支持 file_name 参数")
