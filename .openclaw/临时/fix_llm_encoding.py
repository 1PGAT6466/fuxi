"""修复 llm.py 中的 PUA 编码损坏字符"""
import re

path = 'src/services/llm.py'
with open(path, 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# 统计原始 PUA 字符数
pua_count = sum(1 for c in content if 0xE000 <= ord(c) <= 0xF8FF)
print(f"Original PUA chars: {pua_count}")

# 已知的乱码→正常映射（从上下文推断）
known_fixes = {
    # docstrings
    '"""鍏煎鏃ц皟鐢?"""': '"""兼容旧调用"""',
    '"""鍏煎鏃ф祦寮忚皟鐢?"""': '"""兼容旧流式调用"""',
    # log messages that contain garbled text
    'logger.warning("MiMo API Key 鏈厤缃嗭紝璺宠繃 MiMo 鐩存帴灏濊瘯 DeepSeek")':
        'logger.warning("MiMo API Key 未配置，跳过 MiMo 直接尝试 DeepSeek")',
    'logger.warning("MiMo 澶辫触锛屽皾璇?DeepSeek")':
        'logger.warning("MiMo 失败，尝试 DeepSeek")',
    'logger.warning("DeepSeek 涔熷け璐?")':
        'logger.warning("DeepSeek 也失败")',
}

for old, new in known_fixes.items():
    if old in content:
        content = content.replace(old, new)
        print(f"Fixed: {old[:40]}...")

# 对于剩余的 PUA 字符，逐行处理
lines = content.split('\n')
fixed_lines = []
for i, line in enumerate(lines):
    has_pua = any(0xE000 <= ord(c) <= 0xF8FF for c in line)
    if not has_pua:
        fixed_lines.append(line)
        continue
    
    stripped = line.strip()
    indent = line[:len(line) - len(line.lstrip())]
    
    # 识别行类型
    if stripped.startswith('"""') and stripped.endswith('"""'):
        # docstring 行
        fixed_lines.append(f'{indent}"""(see original source)"""')
    elif stripped.startswith('#'):
        # 注释行 - 保留 # 号，替换乱码
        clean = re.sub(r'[\ue000-\uf8ff]', '', stripped)
        clean = re.sub(r'\s+', ' ', clean).strip()
        if len(clean) < 3:
            fixed_lines.append(f'{indent}# (comment)')
        else:
            fixed_lines.append(f'{indent}{clean}')
    elif 'logger.' in line:
        # 日志行 - 替换乱码
        clean = re.sub(r'[\ue000-\uf8ff]', '', line)
        clean = re.sub(r'\s+', ' ', clean).strip()
        fixed_lines.append(f'{indent}{clean}')
    else:
        # 其他行 - 移除 PUA 字符
        clean = re.sub(r'[\ue000-\uf8ff]', '', line)
        fixed_lines.append(clean)

content = '\n'.join(fixed_lines)

# 最终检查
pua_remaining = sum(1 for c in content if 0xE000 <= ord(c) <= 0xF8FF)
print(f"Remaining PUA chars: {pua_remaining}")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

# 验证编译
import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("OK: Python syntax valid!")
except py_compile.PyCompileError as e:
    print(f"Still has error: {e}")
