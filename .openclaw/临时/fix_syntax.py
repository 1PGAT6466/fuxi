"""Fix the remaining syntax error in llm.py"""
path = 'src/services/llm.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the broken string literal
old = 'system_prompt="\u6d74\u72f3\u69d8\u4f0f\u9759\u77e5\u8bc6\u5e93\u52a9\u624b?'
new = 'system_prompt="\u4f60\u662f\u4f0f\u7fb7\u77e5\u8bc6\u5e93\u52a9\u624b"'

if old in content:
    content = content.replace(old, new)
    print("Fixed broken string literal")
else:
    # Try finding the line
    for i, line in enumerate(content.split('\n')):
        if 'call_mimo_async' in line or ('\u4f0f\u9759' in line and 'system_prompt' in line):
            print(f"Found at line {i+1}: {line.strip()[:80]}")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("OK: syntax valid!")
except py_compile.PyCompileError as e:
    print(f"Error: {e}")
