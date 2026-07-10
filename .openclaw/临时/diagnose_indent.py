"""Diagnose and fix remaining indentation errors."""
import os
os.chdir(r'E:\easyclaw\伏羲-v1.44\repo')

files = [
    'src/services/online_eval.py',
    'src/services/memory.py',
    'src/services/knowledge_lifecycle.py',
    'src/growth/adjustment_log.py',
    'src/growth/growth_recorder.py',
]

for f in files:
    with open(f, 'r', encoding='utf-8') as fh:
        lines = fh.readlines()
    print(f'=== {f} ===')
    for i, line in enumerate(lines):
        stripped = line.rstrip()
        if 'for line in f:' in stripped or ('with open' in stripped and 'r"' in stripped):
            indent = len(line) - len(line.lstrip())
            # Check if next line is properly indented
            if i+1 < len(lines):
                next_line = lines[i+1]
                next_indent = len(next_line) - len(next_line.lstrip()) if next_line.strip() else 0
                expected = indent + 4
                if next_line.strip() and next_indent < expected:
                    print(f'  Line {i+1}: indent={indent}, next indent={next_indent}, expected>={expected}')
                    print(f'    Current: {repr(lines[i])}')
                    print(f'    Next:    {repr(lines[i+1])}')
    print()
