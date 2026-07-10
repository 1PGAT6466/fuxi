"""Fix remaining indentation errors."""
import os
os.chdir(r'E:\easyclaw\伏羲-v1.44\repo')

def fix_for_block_indent(filepath):
    """Fix 'for line in f:' blocks where body is not indented."""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    fixed = False
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip()
        
        if 'for line in f:' in stripped:
            indent = len(line) - len(line.lstrip())
            expected_body_indent = indent + 4
            
            # Check if next line needs indentation fix
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if not next_line.strip():
                    j += 1
                    continue
                next_indent = len(next_line) - len(next_line.lstrip())
                if next_indent <= indent:
                    break  # We've exited the for block
                if next_indent < expected_body_indent:
                    # Need to add 4 spaces
                    lines[j] = '    ' + next_line
                    fixed = True
                    j += 1
                else:
                    j += 1
        i += 1
    
    if fixed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f'  Fixed indentation in {filepath}')
    else:
        print(f'  No fix needed in {filepath}')

files = [
    'src/services/online_eval.py',
    'src/services/memory.py',
    'src/services/knowledge_lifecycle.py',
]

for f in files:
    fix_for_block_indent(f)

# For growth files, check the with block issue
print('\nChecking growth files...')
for f in ['src/growth/adjustment_log.py', 'src/growth/growth_recorder.py']:
    with open(f, 'r', encoding='utf-8') as fh:
        lines = fh.readlines()
    for i, line in enumerate(lines):
        if 'with open(log_file, "a"' in line or 'with open(log_file, "r"' in line:
            indent = len(line) - len(line.lstrip())
            if i+1 < len(lines):
                next_line = lines[i+1]
                next_indent = len(next_line) - len(next_line.lstrip()) if next_line.strip() else 0
                if next_line.strip() and next_indent < indent + 4:
                    print(f'  {f} line {i+1}: needs indent fix')
                    # Fix: add indent to body of with block
                    j = i + 1
                    while j < len(lines) and lines[j].strip():
                        if len(lines[j]) - len(lines[j].lstrip()) < indent + 4:
                            lines[j] = '    ' + lines[j]
                        j += 1
                    with open(f, 'w', encoding='utf-8') as fh:
                        fh.writelines(lines)
                    print(f'  Fixed {f}')
                    break
