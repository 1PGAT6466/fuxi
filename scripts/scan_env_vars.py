import re, os, glob, sys

repo = r'E:\easyclaw\伏羲-v1.44\repo'
vars_map = {}

for filepath in glob.glob(os.path.join(repo, 'src', '**', '*.py'), recursive=True):
    if '__pycache__' in filepath:
        continue
    try:
        with open(filepath, encoding='utf-8', errors='ignore') as fh:
            content = fh.read()
    except Exception:
        continue
    
    relpath = os.path.relpath(filepath, repo)
    
    # Pattern 1: os.getenv("VAR_NAME")
    for m in re.finditer(r'os\.getenv\(\"([^\"]+)\"\)', content):
        key = m.group(1)
        vars_map.setdefault(key, set()).add(relpath)
    
    # Pattern 2: os.getenv('VAR_NAME')
    for m in re.finditer(r"os\.getenv\('([^']+)'\)", content):
        key = m.group(1)
        vars_map.setdefault(key, set()).add(relpath)
    
    # Pattern 3: os.environ.get("VAR_NAME")
    for m in re.finditer(r'os\.environ\.get\(\"([^\"]+)\"\)', content):
        key = m.group(1)
        vars_map.setdefault(key, set()).add(relpath)
    
    # Pattern 4: os.environ.get('VAR_NAME')
    for m in re.finditer(r"os\.environ\.get\('([^']+)'\)", content):
        key = m.group(1)
        vars_map.setdefault(key, set()).add(relpath)
    
    # Pattern 5: os.getenv("VAR", ...) with other quote types
    for m in re.finditer(r'os\.getenv\([\"]([^\"]+)[\"]', content):
        key = m.group(1)
        vars_map.setdefault(key, set()).add(relpath)

# Print results
for k in sorted(vars_map.keys()):
    files = ', '.join(sorted(vars_map[k]))
    sys.stdout.write(f'  {k} -> {files}\n')

sys.stdout.write(f'\nTotal unique env vars: {len(vars_map)}\n')
