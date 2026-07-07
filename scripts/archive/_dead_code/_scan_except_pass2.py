import os, re
root = r'E:\easyclaw\伏羲-v1.44\repo\src'
results = []
for dirpath, dirnames, filenames in os.walk(root):
    if '__pycache__' in dirpath:
        continue
    for fn in filenames:
        if not fn.endswith('.py'):
            continue
        fpath = os.path.join(dirpath, fn)
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        # Pattern: except ... : \n (maybe blank) pass
        for m in re.finditer(r'^(\s*)(except\s+[^:]*:)\s*\n(\s*pass\s*\n)', content, re.MULTILINE):
            line_num = content[:m.start()].count('\n') + 1
            relpath = os.path.relpath(fpath, root)
            results.append(f'{relpath}:{line_num}: {m.group(2).strip()}')
        # Also direct same-line: except ... : pass
        for m in re.finditer(r'(except\s+[^:]*:\s*)pass\b', content):
            line_num = content[:m.start()].count('\n') + 1
            relpath = os.path.relpath(fpath, root)
            results.append(f'{relpath}:{line_num}: {m.group(1).strip()} pass (same line)')
for r in sorted(results):
    print(r)
print(f'\nTotal: {len(results)}')
