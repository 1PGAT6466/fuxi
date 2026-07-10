"""Byte-level fix for broken string literal in llm.py"""
path = 'src/services/llm.py'
with open(path, 'rb') as f:
    data = f.read()

# Find the broken string: system_prompt="...garbled...?, max_tokens
# The issue: the closing " was eaten by PUA cleanup
# Pattern: system_prompt="<garbled_bytes>?, max_tokens
import re

# Find: system_prompt=" + any bytes + ?, max_tokens
# Replace: system_prompt="你是伏羲知识库助手", max_tokens
pattern = b'system_prompt="[\x80-\xff]+\?, max_tokens'
replacement = b'system_prompt="\xe4\xbd\xa0\xe6\x98\xaf\xe4\xbc\x8f\xe7\xbe\xb9\xe7\x9f\xa5\xe8\xaf\x86\xe5\xba\x93\xe5\x8a\xa9\xe6\x89\x8b", max_tokens'

matches = list(re.finditer(pattern, data))
print(f"Found {len(matches)} matches")

if matches:
    for m in matches:
        print(f"  At offset {m.start()}: {data[m.start():m.end()][:60]}")
    data = re.sub(pattern, replacement, data)
    print("Replaced")

# Also fix any other broken string literals (pattern: "=<garbled>?,)
# Find: =" + non-ASCII + ?,  or =" + non-ASCII + ?)
pattern2 = b'="[\x80-\xff]+\?[,)]'
def fix_str(m):
    return b'="(fixed)",' if m.group(0).endswith(b',') else b'="(fixed)")'

count2 = len(re.findall(pattern2, data))
if count2:
    data = re.sub(pattern2, fix_str, data)
    print(f"Fixed {count2} additional broken strings")

with open(path, 'wb') as f:
    f.write(data)

import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("OK: syntax valid!")
except py_compile.PyCompileError as e:
    print(f"Error: {e}")
