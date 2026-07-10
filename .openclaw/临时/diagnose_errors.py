"""Fix all compilation errors from previous patches."""
import os
os.chdir(r'E:\easyclaw\伏羲-v1.44\repo')

def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def fix_indentation_broken_by_with_block(content, line_num):
    """Fix the common pattern where we replaced 'with open(...) as f:' 
    with 'def _rd():\n    with open(...)' but broke the indentation."""
    lines = content.split('\n')
    # Find the problematic line and fix it
    # The issue is usually that we have:
    #   def _rd():
    #       with open(...) as f:
    # but the original code after 'with' was at the wrong indent level
    return content

# ===== Fix notifications.py =====
print('Fixing src/api/notifications.py...')
content = read_file('src/api/notifications.py')

# The _load_notifications function has a broken with block
# Let's see what's there
lines = content.split('\n')
for i, line in enumerate(lines[30:45], start=31):
    print(f'  Line {i}: {repr(line)}')

write_file('src/api/notifications.py', content)
print()

# ===== Fix services/learner.py =====
print('Fixing src/services/learner.py...')
content = read_file('src/services/learner.py')
lines = content.split('\n')
for i, line in enumerate(lines[45:55], start=46):
    print(f'  Line {i}: {repr(line)}')

# ===== Fix services/feedback_store.py =====
print('\nFixing src/services/feedback_store.py...')
content = read_file('src/services/feedback_store.py')
lines = content.split('\n')
for i, line in enumerate(lines[125:135], start=126):
    print(f'  Line {i}: {repr(line)}')

# ===== Fix services/evolver.py =====
print('\nFixing src/services/evolver.py...')
content = read_file('src/services/evolver.py')
lines = content.split('\n')
for i, line in enumerate(lines[130:142], start=131):
    print(f'  Line {i}: {repr(line)}')

# ===== Fix infra/trace_logger.py =====
print('\nFixing src/infra/trace_logger.py...')
content = read_file('src/infra/trace_logger.py')
lines = content.split('\n')
for i, line in enumerate(lines[38:50], start=39):
    print(f'  Line {i}: {repr(line)}')

# ===== Fix services/eval_pipeline.py =====
print('\nFixing src/services/eval_pipeline.py...')
content = read_file('src/services/eval_pipeline.py')
lines = content.split('\n')
for i, line in enumerate(lines[118:130], start=119):
    print(f'  Line {i}: {repr(line)}')

# ===== Fix services/online_eval.py =====
print('\nFixing src/services/online_eval.py...')
content = read_file('src/services/online_eval.py')
lines = content.split('\n')
for i, line in enumerate(lines[90:105], start=91):
    print(f'  Line {i}: {repr(line)}')

# ===== Fix services/memory.py =====
print('\nFixing src/services/memory.py...')
content = read_file('src/services/memory.py')
lines = content.split('\n')
for i, line in enumerate(lines[58:72], start=59):
    print(f'  Line {i}: {repr(line)}')

# ===== Fix services/knowledge_lifecycle.py =====
print('\nFixing src/services/knowledge_lifecycle.py...')
content = read_file('src/services/knowledge_lifecycle.py')
lines = content.split('\n')
for i, line in enumerate(lines[82:95], start=83):
    print(f'  Line {i}: {repr(line)}')

# ===== Fix growth/adjustment_log.py =====
print('\nFixing src/growth/adjustment_log.py...')
content = read_file('src/growth/adjustment_log.py')
lines = content.split('\n')
for i, line in enumerate(lines[67:80], start=68):
    print(f'  Line {i}: {repr(line)}')

# ===== Fix growth/engine.py =====
print('\nFixing src/growth/engine.py...')
content = read_file('src/growth/engine.py')
lines = content.split('\n')
for i, line in enumerate(lines[124:140], start=125):
    print(f'  Line {i}: {repr(line)}')

# ===== Fix growth/growth_recorder.py =====
print('\nFixing src/growth/growth_recorder.py...')
content = read_file('src/growth/growth_recorder.py')
lines = content.split('\n')
for i, line in enumerate(lines[52:65], start=53):
    print(f'  Line {i}: {repr(line)}')
