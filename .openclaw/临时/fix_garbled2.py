"""Fix garbled docstrings in llm.py line by line"""

path = 'src/services/llm.py'
with open(path, 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

fixed_count = 0
for i, line in enumerate(lines):
    original = line
    # Check for non-printable characters (U+E190 and similar)
    has_bad = False
    for c in line:
        cp = ord(c)
        if cp > 0xFFFF or (0xE000 <= cp <= 0xF8FF) or (0xFFF0 <= cp <= 0xFFFF):
            has_bad = True
            break
    
    if has_bad or '鍏煎' in line or '鏃ц' in line or '皟鐢' in line:
        # Replace entire docstring lines
        stripped = line.strip()
        if stripped.startswith('"""') and stripped.endswith('"""'):
            lines[i] = line[:len(line) - len(line.lstrip())] + '"""兼容旧调用"""\n'
            fixed_count += 1
        elif 'logger.warning' in line:
            # Fix garbled log messages
            if 'MiMo' in line and 'DeepSeek' in line:
                indent = line[:len(line) - len(line.lstrip())]
                lines[i] = indent + 'logger.warning("MiMo 失败，尝试 DeepSeek")\n'
                fixed_count += 1
            elif 'DeepSeek' in line:
                indent = line[:len(line) - len(line.lstrip())]
                lines[i] = indent + 'logger.warning("DeepSeek 也失败")\n'
                fixed_count += 1

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"Fixed {fixed_count} lines")
