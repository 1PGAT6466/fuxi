#!/usr/bin/env python3
"""修复：从备份恢复 + 正确插入新分类"""
import py_compile

# 从备份恢复原始文件
import shutil
shutil.copy('src_backup_20260624_044330/category_registry.py', 'src/category_registry.py')
print("已从备份恢复原始文件")

# 读取
with open('src/category_registry.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 在 CATEGORIES dict 末尾插入新分类
# 找 CATEGORIES = { ... } 的最后一个 }
# 用正则找 "CATEGORIES" 开始的字典块
import re

# 找到 CATEGORIES dict 的结束位置
# 策略：找到所有只含 } 的行，取最后一个
lines = content.split('\n')
last_brace_line = None
for i, line in enumerate(lines):
    if line.strip() == '}':
        last_brace_line = i

if last_brace_line is None:
    print("ERROR: 找不到字典结尾")
    exit(1)

new_entry = '''    # ── 操作手册类 ──
    "操作手册_泛微OA": {
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

lines.insert(last_brace_line, new_entry)
content = '\n'.join(lines)

# 2. match_category 签名加 file_name
content = content.replace(
    'def match_category(text: str, file_ext: str = "", max_len: int = 5000) -> Optional[str]:',
    'def match_category(text: str, file_ext: str = "", max_len: int = 5000, file_name: str = "") -> Optional[str]:'
)

# 3. 在 match_category 开头加文件名模式匹配
old_start = '    if not text or len(text) < 5:'
pattern_code = '''    # 文件名模式匹配：操作手册类直接命中
    if file_name:
        _fn_lower = file_name.lower()
        if '泛微' in _fn_lower or 'e-cology' in _fn_lower or 'ecology' in _fn_lower:
            return '操作手册_泛微OA'

'''
content = content.replace(old_start, pattern_code + old_start)

# 写回
with open('src/category_registry.py', 'w', encoding='utf-8') as f:
    f.write(content)

# 验证
try:
    py_compile.compile('src/category_registry.py', doraise=True)
    print("OK: 语法检查通过")
except py_compile.PyCompileError as e:
    print(f"ERROR: {e}")

# 验证新分类存在
exec(open('src/category_registry.py').read())
if '操作手册_泛微OA' in CATEGORIES:
    print("OK: 操作手册_泛微OA 已注册")
else:
    print("ERROR: 分类未注册")
