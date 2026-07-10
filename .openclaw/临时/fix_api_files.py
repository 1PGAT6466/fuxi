"""Fix remaining compilation errors in API files."""
import os
os.chdir(r'E:\easyclaw\伏羲-v1.44\repo')

def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

# ===== documents.py - missing asyncio import =====
print('Fixing src/api/documents.py...')
content = read_file('src/api/documents.py')
# Add asyncio import if missing
if 'import asyncio' not in content:
    content = 'import asyncio\n' + content
    print('  Added asyncio import')
# Revert the broken lambda (file handle leak)
old = '                            content = await asyncio.to_thread(lambda: open(fpath, "rb").read())'
new = '''                            with open(fpath, "rb") as f:
                                content = f.read()'''
if old in content:
    content = content.replace(old, new)
    print('  Reverted to sync (inside sync iteration)')
write_file('src/api/documents.py', content)

# ===== feedback.py =====
print('Fixing src/api/feedback.py...')
content = read_file('src/api/feedback.py')
lines = content.split('\n')
# Find the broken with block
for i, line in enumerate(lines):
    if 'with open(fpath, "r"' in line:
        indent = len(line) - len(line.lstrip())
        if i+1 < len(lines) and lines[i+1].strip() and not lines[i+1].startswith(' ' * (indent + 4)):
            lines[i+1] = ' ' * (indent + 4) + lines[i+1].lstrip()
            print(f'  Fixed indentation at line {i+1}')
content = '\n'.join(lines)
write_file('src/api/feedback.py', content)

# ===== files_alias.py =====
print('Fixing src/api/files_alias.py...')
content = read_file('src/api/files_alias.py')
old = '                            content = await asyncio.to_thread(lambda: open(fpath, "rb").read())'
new = '''                            with open(fpath, "rb") as f:
                                content = f.read()'''
if old in content:
    content = content.replace(old, new)
    print('  Reverted to sync')
write_file('src/api/files_alias.py', content)

# ===== files_view.py =====
print('Fixing src/api/files_view.py...')
content = read_file('src/api/files_view.py')
# Fix multiple occurrences
for _ in range(3):
    old = '                        content = await asyncio.to_thread(lambda: open(fpath, "rb").read())'
    new = '''                        with open(fpath, "rb") as f:
                            content = f.read()'''
    if old in content:
        content = content.replace(old, new, 1)
        print('  Reverted one occurrence to sync')
write_file('src/api/files_view.py', content)

# ===== llm.py =====
print('Fixing src/services/llm.py...')
content = read_file('src/services/llm.py')
lines = content.split('\n')
for i, line in enumerate(lines[282:295], start=283):
    print(f'  Line {i}: {repr(line)}')
write_file('src/services/llm.py', content)

print('\nDone!')
