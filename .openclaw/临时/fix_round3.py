"""Fix remaining compilation errors - round 3."""
import os
os.chdir(r'E:\easyclaw\伏羲-v1.44\repo')

def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

# ===== eval_pipeline.py - await in sync function =====
print('Fixing src/services/eval_pipeline.py...')
content = read_file('src/services/eval_pipeline.py')
# Revert the broken write patch
old = '            await asyncio.to_thread(lambda: open(eval_file, "a", encoding="utf-8").write(json.dumps(result, ensure_ascii=False) + "\\n"))'
new = '''            with open(eval_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\\n")'''
if old in content:
    content = content.replace(old, new)
    print('  Reverted write to sync')
write_file('src/services/eval_pipeline.py', content)

# ===== online_eval.py =====
print('Fixing src/services/online_eval.py...')
content = read_file('src/services/online_eval.py')
lines = content.split('\n')
# Find and fix the broken with block around line 97
for i, line in enumerate(lines):
    if 'with open(metrics_file, "r"' in line and i > 0:
        # Check if the next line is not properly indented
        if i+1 < len(lines) and lines[i+1].strip() and not lines[i+1].startswith(' ' * (len(line) - len(line.lstrip()) + 4)):
            # The with block body needs to be indented
            indent = len(line) - len(line.lstrip()) + 4
            # Find the end of the with block
            j = i + 1
            while j < len(lines) and lines[j].strip():
                if not lines[j].startswith(' ' * indent):
                    lines[j] = ' ' * indent + lines[j].lstrip()
                j += 1
            print(f'  Fixed indentation at line {i+1}')
content = '\n'.join(lines)
# Also revert the broken write
old = '                        f.write(json.dumps(metric, ensure_ascii=False) + "\\n")\n                    await asyncio.to_thread(_wr)'
new = '''                        f.write(json.dumps(metric, ensure_ascii=False) + "\\n")'''
if old in content:
    content = content.replace(old, new)
    print('  Reverted write to sync')
write_file('src/services/online_eval.py', content)

# ===== memory.py =====
print('Fixing src/services/memory.py...')
content = read_file('src/services/memory.py')
lines = content.split('\n')
# Fix the with block at line 80
for i, line in enumerate(lines):
    if 'with open(session_file, "r"' in line or 'with open(memory_file' in line:
        indent = len(line) - len(line.lstrip())
        # Check if next line is properly indented
        if i+1 < len(lines) and lines[i+1].strip() and not lines[i+1].startswith(' ' * (indent + 4)):
            lines[i+1] = ' ' * (indent + 4) + lines[i+1].lstrip()
            print(f'  Fixed indentation at line {i+1}')
content = '\n'.join(lines)
write_file('src/services/memory.py', content)

# ===== knowledge_lifecycle.py =====
print('Fixing src/services/knowledge_lifecycle.py...')
content = read_file('src/services/knowledge_lifecycle.py')
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'with open(log_file, "r"' in line:
        indent = len(line) - len(line.lstrip())
        if i+1 < len(lines) and lines[i+1].strip() and not lines[i+1].startswith(' ' * (indent + 4)):
            lines[i+1] = ' ' * (indent + 4) + lines[i+1].lstrip()
            print(f'  Fixed indentation at line {i+1}')
content = '\n'.join(lines)
write_file('src/services/knowledge_lifecycle.py', content)

# ===== growth/adjustment_log.py =====
print('Fixing src/growth/adjustment_log.py...')
content = read_file('src/growth/adjustment_log.py')
# Revert the broken write
old = '            await asyncio.to_thread(lambda: open(log_file, "a", encoding="utf-8").write(json.dumps(entry, ensure_ascii=False) + "\\n"))'
new = '''            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\\n")'''
if old in content:
    content = content.replace(old, new)
    print('  Reverted write to sync')
write_file('src/growth/adjustment_log.py', content)

# ===== growth/engine.py =====
print('Fixing src/growth/engine.py...')
content = read_file('src/growth/engine.py')
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'with open(log_file, "r"' in line:
        indent = len(line) - len(line.lstrip())
        if i+1 < len(lines) and lines[i+1].strip() and not lines[i+1].startswith(' ' * (indent + 4)):
            lines[i+1] = ' ' * (indent + 4) + lines[i+1].lstrip()
            print(f'  Fixed indentation at line {i+1}')
content = '\n'.join(lines)
# Also revert the broken write
old = '                await asyncio.to_thread(lambda: open(log_file, "a", encoding="utf-8").write(json.dumps(record, ensure_ascii=False) + "\\n"))'
new = '''                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\\n")'''
if old in content:
    content = content.replace(old, new)
    print('  Reverted write to sync')
write_file('src/growth/engine.py', content)

# ===== growth/growth_recorder.py =====
print('Fixing src/growth/growth_recorder.py...')
content = read_file('src/growth/growth_recorder.py')
# Revert the broken write
old = '            await asyncio.to_thread(lambda: open(log_file, "a", encoding="utf-8").write(json.dumps(record, ensure_ascii=False) + "\\n"))'
new = '''            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\\n")'''
if old in content:
    content = content.replace(old, new)
    print('  Reverted write to sync')
write_file('src/growth/growth_recorder.py', content)

print('\nDone!')
