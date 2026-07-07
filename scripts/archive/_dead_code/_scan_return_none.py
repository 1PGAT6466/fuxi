import os, re

ROOT = r'E:\easyclaw\伏羲-v1.44\repo\src'

# Find all except...return None/[]/"" patterns
results = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    if '__pycache__' in dirpath:
        continue
    for fn in filenames:
        if not fn.endswith('.py'):
            continue
        fp = os.path.join(dirpath, fn)
        with open(fp, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern: except ...:\n\s*return None/[]/{}/""
        for m in re.finditer(r'(except\s+[^:]*:)\s*\n(\s*return\s+(None|\[\]|\{\}|""))\b', content):
            line_num = content[:m.start()].count('\n') + 1
            rel = os.path.relpath(fp, ROOT)
            results.append((rel, line_num, m.group(1).strip(), m.group(2).strip()))
        
        # Also: except ...: return None (same line)
        for m in re.finditer(r'(except\s+[^:]*:)\s*return\s+(None|\[\]|\{\}|"")', content):
            line_num = content[:m.start()].count('\n') + 1
            rel = os.path.relpath(fp, ROOT)
            results.append((rel, line_num, m.group(1).strip(), f'return {m.group(2).strip()}'))

for r in sorted(results):
    print(f'{r[0]}:{r[1]}: {r[2]} -> {r[3]}')
print(f'\nTotal: {len(results)}')
