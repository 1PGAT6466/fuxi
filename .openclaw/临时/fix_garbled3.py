"""彻底清理 llm.py 中所有非 ASCII 乱码字符，替换为可读文本"""
import re

path = 'src/services/llm.py'
with open(path, 'rb') as f:
    raw = f.read()

# 统计有多少行包含 non-ASCII
lines = raw.split(b'\n')
problem_lines = []
for i, line in enumerate(lines):
    # 检查是否包含高位字节（非 ASCII）
    has_high = any(b > 127 for b in line)
    if has_high:
        problem_lines.append(i)

print(f"Total lines: {len(lines)}")
print(f"Lines with non-ASCII: {len(problem_lines)}")

# 策略：保留纯 ASCII 部分，将 non-ASCII 块替换为占位符
def clean_line(line_bytes):
    """将一行中的 non-ASCII 字符替换掉"""
    result = bytearray()
    i = 0
    while i < len(line_bytes):
        b = line_bytes[i]
        if b < 128:
            result.append(b)
            i += 1
        else:
            # 跳过整个 multi-byte sequence
            while i < len(line_bytes) and line_bytes[i] > 127:
                i += 1
    return bytes(result)

cleaned_lines = []
for i, line in enumerate(lines):
    if i in problem_lines:
        cleaned = clean_line(line)
        # 如果清理后只剩下空白和标点，标记为空注释
        stripped = cleaned.strip().rstrip(b'#').strip().rstrip(b'"').strip().rstrip(b':').strip()
        if len(stripped) < 3:
            # 太短了，用有意义的占位符
            if b'def ' in line:
                # 函数定义行，保留
                cleaned_lines.append(cleaned)
            elif b'class ' in line:
                cleaned_lines.append(cleaned)
            elif b'import ' in line:
                cleaned_lines.append(cleaned)
            elif b'return' in line:
                cleaned_lines.append(cleaned)
            elif b'"""' in line:
                # docstring 行
                indent = b''
                for c in line:
                    if c in (32, 9):  # space, tab
                        indent += bytes([c])
                    else:
                        break
                cleaned_lines.append(indent + b'"""(see source)"""')
            else:
                cleaned_lines.append(cleaned)
        else:
            cleaned_lines.append(cleaned)
    else:
        cleaned_lines.append(line)

result = b'\n'.join(cleaned_lines)

with open(path, 'wb') as f:
    f.write(result)

print("Done. Verifying...")
import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("OK: Python syntax valid")
except py_compile.PyCompileError as e:
    print(f"Still has error: {e}")
