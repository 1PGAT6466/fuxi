import os, re
root = r'E:\easyclaw\伏羲-v1.44\repo\src'

# Part A2: except ... followed by return None / return []
print("===== TASK A2: except ... return None / return [] =====")
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
        for m in re.finditer(r'(except\s+[^:]*:)\s*\n(\s*return\s+(None|\[\]|""|{}\s*))\b', content, re.MULTILINE):
            line_num = content[:m.start()].count('\n') + 1
            relpath = os.path.relpath(fpath, root)
            results.append(f'{relpath}:{line_num}: {m.group(1).strip()} -> {m.group(2).strip()}')
for r in sorted(results):
    print(r)
print(f'\nTotal: {len(results)}')

# Part B: fake async
print("\n===== TASK B: finding fake async functions =====")
# Find async def with no await inside
async_count = 0
for dirpath, dirnames, filenames in os.walk(root):
    if '__pycache__' in dirpath:
        continue
    for fn in filenames:
        if not fn.endswith('.py'):
            continue
        fpath = os.path.join(dirpath, fn)
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
        
        # Find async def patterns
        for m in re.finditer(r'^\s*async\s+def\s+(\w+)\s*\(', content, re.MULTILINE):
            func_name = m.group(1)
            start_line = content[:m.start()].count('\n')
            
            # Find the function body - find the indentation level
            func_start = m.start()
            # Find next line
            nl = content.find('\n', func_start)
            if nl == -1:
                continue
            # Get indentation of first line after def
            body_start = nl + 1
            if body_start >= len(content):
                continue
            
            # Find function end (next line at same or lower indent as 'async')
            indent_match = re.match(r'^(\s*)', m.group(0))
            func_indent = indent_match.group(1)
            
            # Find matching } or dedent
            # Simple heuristic: find } at same indent level or EOF
            func_body_end = len(content)
            for line_i, line in enumerate(lines[start_line+1:], start_line+1):
                stripped = line.strip()
                if stripped == '' or stripped.startswith('#'):
                    continue
                # Check if line is at the same or lower indent level as async def
                if not line.startswith(' ') and not line.startswith('\t'):
                    func_body_end = sum(len(l) + 1 for l in lines[:line_i])
                    break
                if line.startswith(func_indent) and not line.startswith(func_indent + ' ') and not line.startswith(func_indent + '\t'):
                    if stripped.startswith('def ') or stripped.startswith('async def ') or stripped.startswith('class '):
                        func_body_end = sum(len(l) + 1 for l in lines[:line_i])
                        break
            
            func_body = content[func_start:func_body_end]
            
            # Check if there's an 'await' in the body
            if 'await ' not in func_body and 'await\t' not in func_body:
                relpath = os.path.relpath(fpath, root)
                async_count += 1

print(f"Total fake async functions found: {async_count}")
