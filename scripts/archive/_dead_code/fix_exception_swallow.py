#!/usr/bin/env python3
"""
修复裸 except 和异常吞噬 — 伏羲 v1.50 代码层质量修复
- 将 except Exception (无 logger) 添加 logger.warning/logging.getLogger().warning
- 优先修复核心路径文件
"""
import os, re, sys

BASE = r'E:\easyclaw\伏羲-v1.44\repo\src'

# Maps file path relative to BASE -> logger name pattern to use
# We'll auto-detect logger from imports or use logging.getLogger(__name__)

def detect_logger_name(filepath):
    """Detect the logger variable name or pattern used in the file."""
    with open(filepath, encoding='utf-8') as f:
        content = f.read()
    
    # Check for explicit logger = logging.getLogger(...)
    m = re.search(r'logger\s*=\s*logging\.getLogger\(["\'](.+?)["\']\)', content)
    if m:
        return 'logger', m.group(1)
    
    # Check for inline: import logging; logger = logging.getLogger(__name__)
    m = re.search(r'import logging;\s*logger\s*=\s*logging\.getLogger', content)
    if m:
        return 'logger', '__name__'
    
    # Check for logging.getLogger("...") calls
    m = re.search(r'logging\.getLogger\(["\'](.+?)["\']\)', content)
    if m:
        return 'logging.getLogger("' + m.group(1) + '")', m.group(1)
    
    return 'logging.getLogger(__name__)', '__name__'

def fix_file(filepath):
    """Fix exception swallowing in a single file."""
    with open(filepath, encoding='utf-8') as f:
        lines = f.readlines()
    
    var_name, _ = detect_logger_name(filepath)
    
    # Find all except Exception blocks that lack logger/traceback follow-up
    modified = False
    i = 0
    result_lines = list(lines)
    
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Match except Exception... lines
        m = re.match(r'^(\s*except\s+Exception)(.*?)(:)\s*$', stripped)
        if not m:
            i += 1
            continue
        
        indent = m.group(1)[:len(m.group(1)) - len('except Exception')]  # leading whitespace
        body_indent = indent + '    '
        
        # Check if already has logger call in the except body
        has_logger = False
        j = i + 1
        next_line = ''
        while j < len(lines) and j < i + 15:
            nl = lines[j]
            if nl.strip() == '':
                j += 1
                continue
            if re.match(r'^\s*$', nl):
                j += 1
                continue
            if re.search(r'logger\.(error|warning|exception|critical|info|debug)', nl):
                has_logger = True
                break
            if 'logging.getLogger' in nl and not nl.strip().startswith('import') and re.search(r'\.(error|warning|exception)', nl):
                has_logger = True
                break
            if 'traceback' in nl.lower() and 'print_traceback' in nl.lower():
                has_logger = True
                break
            # If immediately followed by return, raise, pass — need to add logger before
            if re.match(r'^\s*(return|raise|pass|continue)\s*', nl):
                next_line = nl
                break
            break
        
        if has_logger:
            i += 1
            continue
        
        # Skip if the next meaningful line is a try/except
        if next_line.strip() in ('return', 'raise', 'pass', 'continue'):
            # Build the logger line
            exc_var = 'e' if ' as e' in stripped else ''
            msg = f"Operation failed"
            if exc_var:
                log_line = f'{body_indent}{var_name}.warning(f"{msg}: {{e}}", exc_info=True)\n'
            else:
                log_line = f'{body_indent}{var_name}.warning("{msg}", exc_info=True)\n'
            
            # Find the index in result_lines
            # Find where this line is in result_lines
            for ri, rl in enumerate(result_lines):
                if rl == line and ri >= i - 10:
                    # Ensure the next line is indeed the pass/return/raise/continue
                    next_ri = ri + 1
                    while next_ri < len(result_lines) and result_lines[next_ri].strip() == '':
                        next_ri += 1
                    if next_ri < len(result_lines) and result_lines[next_ri].strip() in ('return', 'raise', 'pass', 'continue'):
                        result_lines.insert(next_ri, log_line)
                        modified = True
                    break
        
        i += 1
    
    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(result_lines)
        print(f'  FIXED: {os.path.relpath(filepath, BASE)}')
        return True
    return False

# List of files to process (core + secondary)
files_to_fix = []

for root, dirs, filenames in os.walk(BASE):
    dirs[:] = [d for d in dirs if d not in ('__pycache__', 'logs')]
    for fn in filenames:
        if fn.endswith('.py'):
            files_to_fix.append(os.path.join(root, fn))

# Process all files
fixed_count = 0
for fpath in sorted(files_to_fix):
    rel = os.path.relpath(fpath, BASE)
    try:
        if fix_file(fpath):
            fixed_count += 1
    except Exception as e:
        print(f'  ERROR {rel}: {e}')

print(f'\nTotal files modified: {fixed_count}')
