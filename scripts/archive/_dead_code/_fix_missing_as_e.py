#!/usr/bin/env python3
"""
Fix: Ensure except clauses with 'e' in log message have 'as e'.
Also clean up generic Chinese log messages.
"""
import os, re

ROOT = r'E:\easyclaw\伏羲-v1.44\repo\src'

for dirpath, dirnames, filenames in os.walk(ROOT):
    if '__pycache__' in dirpath:
        continue
    for fn in filenames:
        if not fn.endswith('.py'):
            continue
        fp = os.path.join(dirpath, fn)
        with open(fp, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        modified = False
        new_lines = list(lines)
        
        i = 0
        while i < len(lines):
            line = lines[i]
            # Match: except X: (without 'as')
            m = re.match(r'^(\s*except\s+)([^:#]+)(:\s*)$', line)
            if m and ' as ' not in line:
                exc_type = m.group(2).strip()
                indent = m.group(1)
                colon = m.group(3)
                
                # Check next line for logger.warning with 'e' reference
                j = i + 1
                while j < len(lines) and lines[j].strip() == '':
                    j += 1
                if j < len(lines):
                    next_line = lines[j]
                    if 'logger.warning' in next_line and ('%s", e' in next_line or '"%s", e' in next_line):
                        # Need to add ' as e' to except
                        new_lines[i] = f'{indent}except {exc_type} as e:\n'
                        modified = True
                        print(f'  {os.path.relpath(fp, ROOT)}:{i+1}: added "as e"')
                        
                        # Also fix generic Chinese message
                        log_match = re.search(r'logger\.warning\("([^"]+)"\s*,\s*e\s*,\s*exc_info=True\)', next_line)
                        if log_match:
                            msg = log_match.group(1)
                            clean_msg = msg.replace('抓取 ', '').replace(' 异常', '')
                            new_lines[j] = f'{indent}    logger.warning("{clean_msg} 失败: %s", e, exc_info=True)'
                
                i = j + 1
                continue
            
            # Match: except X: \n logger.warning("...") (no e reference)
            m2 = re.match(r'^(\s*except\s+)([^:#]+)(:\s*)$', line)
            if m2:
                exc_type = m2.group(2).strip()
                j = i + 1
                while j < len(lines) and lines[j].strip() == '':
                    j += 1
                if j < len(lines):
                    next_line = lines[j]
                    if 'logger.warning' in next_line and '%s' not in next_line:
                        # Message is fine as-is
                        pass
                i = j + 1 if j < len(lines) else i + 1
                continue
            
            i += 1
        
        if modified:
            with open(fp, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

print('Done.')
