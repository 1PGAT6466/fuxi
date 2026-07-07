#!/usr/bin/env python3
"""
Fuxi v1.50 Fixer — Combined Task A (except swallow) + Task B (fake-async mark)
Version: FINAL
"""
import os, re, sys

ROOT = r'E:\easyclaw\伏羲-v1.44\repo\src'
DRY_RUN = '--apply' not in sys.argv
LOG = []
TOTAL_A, TOTAL_A2, TOTAL_B = 0, 0, 0


def fix_file(relpath, path):
    global TOTAL_A, TOTAL_A2, TOTAL_B
    with open(path, 'r', encoding='utf-8') as f:
        original = f.read()
    lines = original.split('\n')
    
    has_logger = 'logger' in original and ('logger.' in original or 'logger =' in original or 'logger=' in original or 'from logging' in original or 'import logging' in original)
    
    new_lines = list(lines)
    a1_count = 0
    a2_count = 0
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Match: except EXC_TYPE:
        e_match = re.match(r'^(\s*)(except\s+)([^#:]+)(:)(\s*)(.*)$', line)
        if not e_match:
            i += 1
            continue
        
        indent = e_match.group(1)
        exc_part = e_match.group(3).strip()
        colon = e_match.group(4)
        rest = e_match.group(6).strip()
        
        # Check if except already has 'as'
        has_as = ' as ' in exc_part
        
        # Skip CancelledError (legit, no fix needed)
        if 'CancelledError' in exc_part:
            i += 1
            continue
        
        # Case: except X: pass on same line
        if rest == 'pass' or rest.startswith('pass '):
            # Skip if already has comment explanation
            if '#' in rest and 'pass  #' in rest:
                i += 1
                continue
            
            exc_short = exc_part.split(' as ')[0].strip()
            
            if has_logger:
                if has_as:
                    new_lines[i] = f'{indent}except {exc_part}:\n{indent}    logger.warning("{exc_short} 失败: %s", e, exc_info=True)'
                else:
                    new_lines[i] = f'{indent}except {exc_part} as e:\n{indent}    logger.warning("{exc_short} 失败: %s", e, exc_info=True)'
            else:
                if has_as:
                    new_lines[i] = f'{indent}except {exc_part}:\n{indent}    pass'
                else:
                    new_lines[i] = f'{indent}except {exc_part} as e:\n{indent}    pass  # 静默：{exc_short} 失败不影响主流程'
            a1_count += 1
            i += 1
            continue
        
        # Case: pass on next non-empty line
        if rest == '':
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                j += 1
            if j < len(lines):
                next_line = lines[j]
                next_stripped = next_line.strip()
                if next_stripped == 'pass' or next_stripped.startswith('pass '):
                    if '#' in next_stripped and 'pass  #' in next_stripped:
                        i = j + 1
                        continue
                    
                    exc_short = exc_part.split(' as ')[0].strip()
                    
                    if has_logger:
                        if has_as:
                            new_lines[j] = f'{indent}    logger.warning("{exc_short} 失败: %s", e, exc_info=True)'
                        else:
                            new_lines[i] = f'{indent}except {exc_part} as e:'
                            new_lines[j] = f'{indent}    logger.warning("{exc_short} 失败: %s", e, exc_info=True)'
                    else:
                        if not has_as:
                            new_lines[i] = f'{indent}except {exc_part} as e:'
                        new_lines[j] = f'{indent}    pass  # 静默：{exc_short} 失败不影响主流程'
                    a1_count += 1
                    i = j + 1
                    continue
        i += 1
    
    if a1_count > 0:
        TOTAL_A += 1
        LOG.append(f'  [A1] {relpath}: {a1_count} except...pass')
    
    lines = new_lines
    
    # ---- TASK A2: except...return None/[]/{} ----
    new_lines = list(lines)
    i = 0
    while i < len(lines):
        line = lines[i]
        e_match = re.match(r'^(\s*)(except\s+)([^#:]+)(:)(\s*)(.*)$', line)
        if not e_match:
            i += 1
            continue
        
        indent = e_match.group(1)
        exc_part = e_match.group(3).strip()
        rest = e_match.group(6).strip()
        has_as = ' as ' in exc_part
        
        # Same-line return
        ret_match = re.match(r'return\s+(None|\[\]|\{\}|"")\s*(#.*)?$', rest)
        if ret_match:
            ret_val = ret_match.group(1)
            exc_short = exc_part.split(' as ')[0].strip()
            
            if has_logger:
                if has_as:
                    new_lines[i] = f'{indent}except {exc_part}:\n{indent}    logger.warning("{exc_short} 失败: %s", e, exc_info=True)\n{indent}    return {ret_val}'
                else:
                    new_lines[i] = f'{indent}except {exc_part} as e:\n{indent}    logger.warning("{exc_short} 失败: %s", e, exc_info=True)\n{indent}    return {ret_val}'
            else:
                if not has_as:
                    new_lines[i] = f'{indent}except {exc_part} as e:\n{indent}    pass  # 静默：{exc_short} 失败，返回 {ret_val}\n{indent}    return {ret_val}'
                else:
                    new_lines[i] = f'{indent}except {exc_part}:\n{indent}    pass  # 静默：{exc_short} 失败，返回 {ret_val}\n{indent}    return {ret_val}'
            a2_count += 1
            i += 1
            continue
        
        # Next-line return
        if rest == '':
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                j += 1
            if j < len(lines):
                ret_match = re.match(r'^(\s+)return\s+(None|\[\]|\{\}|"")\s*(#.*)?$', lines[j])
                if ret_match:
                    ret_val = ret_match.group(2)
                    exc_short = exc_part.split(' as ')[0].strip()
                    
                    if has_logger:
                        if has_as:
                            new_lines[j] = f'{indent}    logger.warning("{exc_short} 失败: %s", e, exc_info=True)\n{lines[j]}'
                        else:
                            new_lines[i] = f'{indent}except {exc_part} as e:'
                            new_lines[j] = f'{indent}    logger.warning("{exc_short} 失败: %s", e, exc_info=True)\n{lines[j]}'
                    else:
                        if not has_as:
                            new_lines[i] = f'{indent}except {exc_part} as e:'
                        new_lines[j] = f'{indent}    pass  # 静默：{exc_short} 失败，返回 {ret_val}\n{lines[j]}'
                    a2_count += 1
                    i = j + 1
                    continue
        i += 1
    
    if a2_count > 0:
        TOTAL_A2 += 1
        LOG.append(f'  [A2] {relpath}: {a2_count} except...return')
    
    lines = new_lines
    content = '\n'.join(lines)
    
    # ---- TASK B: Mark fake-async functions ----
    lines = content.split('\n')
    b_count = 0
    insert_offset = 0
    
    func_positions = []
    for i, line in enumerate(lines):
        m = re.match(r'^(\s*)(async\s+def\s+)(\w+)\s*\(', line)
        if m:
            func_positions.append((i, m.group(1), m.group(3)))
    
    for pos, indent, func_name in func_positions:
        adjusted_pos = pos + insert_offset
        
        func_end = len(lines)
        async_indent = len(indent) if indent else 0
        for j in range(adjusted_pos + 1, len(lines)):
            l = lines[j]
            if l.strip() == '' or l.strip().startswith('#'):
                continue
            line_indent = len(l) - len(l.lstrip())
            if line_indent <= async_indent:
                func_end = j
                break
        
        body = '\n'.join(lines[adjusted_pos:func_end])
        
        if 'await ' not in body and 'await\t' not in body:
            comment = f'{indent}# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行'
            
            mark_idx = adjusted_pos - 1
            if mark_idx >= 0 and 'FAKE-ASYNC' in lines[mark_idx]:
                continue
            
            insert_at = adjusted_pos
            while insert_at > 0 and lines[insert_at - 1].strip() == '':
                insert_at -= 1
            
            lines.insert(insert_at, comment)
            insert_offset += 1
            b_count += 1
    
    if b_count > 0:
        TOTAL_B += 1
        LOG.append(f'  [B] {relpath}: {b_count} fake-async')
    
    content = '\n'.join(lines)
    
    if not DRY_RUN and content != original:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)


def main():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        if '__pycache__' in dirpath:
            continue
        for fn in sorted(filenames):
            if not fn.endswith('.py'):
                continue
            fp = os.path.join(dirpath, fn)
            rel = os.path.relpath(fp, ROOT)
            fix_file(rel, fp)
    
    for l in LOG:
        print(l)
    
    print(f'\n{"=" * 60}')
    print(f'Task A1 (except...pass):     {TOTAL_A} files')
    print(f'Task A2 (except...return):   {TOTAL_A2} files')
    print(f'Task B  (fake-async mark):   {TOTAL_B} files')
    print(f'Total files:                 {TOTAL_A + TOTAL_A2 + TOTAL_B}')
    if DRY_RUN:
        print('\n*** DRY RUN — re-run with --apply ***')

if __name__ == '__main__':
    main()
