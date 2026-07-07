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
            lines = f.readlines()
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            if re.match(r'^\s*except\s+.*:\s*$', stripped):
                j = i + 1
                while j < len(lines) and lines[j].strip() == '':
                    j += 1
                if j < len(lines) and lines[j].strip() == 'pass':
                    relpath = os.path.relpath(fpath, root)
                    results.append(f'{relpath}:{i+1}: {stripped.strip()}')
for r in results:
    print(r)
print(f'\nTotal: {len(results)}')
