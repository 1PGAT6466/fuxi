import os, re
root = r'E:\easyclaw\伏羲-v1.44\repo\src'

# Part B detailed
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
            lines = content.split('\n')
        
        for m in re.finditer(r'^\s*async\s+def\s+(\w+)\s*\(', content, re.MULTILINE):
            func_name = m.group(1)
            start_line_idx = content[:m.start()].count('\n')
            
            func_start = m.start()
            nl = content.find('\n', func_start)
            if nl == -1:
                continue
            body_start = nl + 1
            if body_start >= len(content):
                continue
            
            indent_match = re.match(r'^(\s*)', m.group(0))
            func_indent = indent_match.group(1)
            
            # Find function end
            func_body_end = len(content)
            for line_i in range(start_line_idx + 1, len(lines)):
                line = lines[line_i]
                stripped = line.strip()
                if stripped == '' or stripped.startswith('#'):
                    continue
                line_indent = len(line) - len(line.lstrip())
                async_indent = len(func_indent)
                if line_indent <= async_indent:
                    func_body_end = sum(len(l) + 1 for l in lines[:line_i])
                    break
            
            func_body = content[func_start:func_body_end]
            
            if 'await ' not in func_body and 'await\t' not in func_body:
                relpath = os.path.relpath(fpath, root)
                results.append((relpath, start_line_idx + 1, func_name))

results.sort()
prev_file = None
for r in results:
    if r[0] != prev_file:
        print(f'\n--- {r[0]} ---')
        prev_file = r[0]
    print(f'  Line {r[1]}: async def {r[2]}')
    
print(f'\nTotal fake async functions: {len(results)}')
