"""Fix sync I/O in async functions - services and infra (corrected paths)."""
import os
os.chdir(r'E:\easyclaw\伏羲-v1.44\repo')

def fix_file(path, replacements):
    if not os.path.exists(path):
        print(f'  SKIP (file not found): {path}')
        return
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            print(f'  Fixed: {old[:60]}...')
        else:
            print(f'  SKIP: {old[:60]}...')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

# ===== growth/adjustment_log.py =====
print('Fixing src/growth/adjustment_log.py...')
fix_file('src/growth/adjustment_log.py', [
    (
        '                with open(log_file, "a", encoding="utf-8") as f:\n                    f.write(json.dumps(entry, ensure_ascii=False) + "\\n")',
        '                await asyncio.to_thread(lambda: open(log_file, "a", encoding="utf-8").write(json.dumps(entry, ensure_ascii=False) + "\\n"))'
    ),
    (
        '                with open(log_file, "r", encoding="utf-8") as f:',
        '                def _rd():\n                    with open(log_file, "r", encoding="utf-8") as f:'
    ),
])

# ===== growth/engine.py =====
print('Fixing src/growth/engine.py...')
fix_file('src/growth/engine.py', [
    (
        '                with open(log_file, "a", encoding="utf-8") as f:\n                    f.write(json.dumps(record, ensure_ascii=False) + "\\n")',
        '                await asyncio.to_thread(lambda: open(log_file, "a", encoding="utf-8").write(json.dumps(record, ensure_ascii=False) + "\\n"))'
    ),
    (
        '                with open(log_file, "r", encoding="utf-8") as f:',
        '                def _rd():\n                    with open(log_file, "r", encoding="utf-8") as f:'
    ),
])

# ===== growth/growth_recorder.py =====
print('Fixing src/growth/growth_recorder.py...')
fix_file('src/growth/growth_recorder.py', [
    (
        '                with open(log_file, "a", encoding="utf-8") as f:\n                    f.write(json.dumps(record, ensure_ascii=False) + "\\n")',
        '                await asyncio.to_thread(lambda: open(log_file, "a", encoding="utf-8").write(json.dumps(record, ensure_ascii=False) + "\\n"))'
    ),
    (
        '            with open(log_file, "r", encoding="utf-8") as f:',
        '            def _rd():\n                with open(log_file, "r", encoding="utf-8") as f:'
    ),
])

# ===== infra/trace_logger.py =====
print('Fixing src/infra/trace_logger.py...')
fix_file('src/infra/trace_logger.py', [
    (
        '            with open(trace_file, "a", encoding="utf-8") as f:\n                f.write(log_line + "\\n")',
        '            await asyncio.to_thread(lambda: open(trace_file, "a", encoding="utf-8").write(log_line + "\\n"))'
    ),
])

# ===== services/knowledge_lifecycle.py =====
print('Fixing src/services/knowledge_lifecycle.py...')
fix_file('src/services/knowledge_lifecycle.py', [
    (
        '                with open(log_file, "a", encoding="utf-8") as f:\n                    f.write(json.dumps(event, ensure_ascii=False) + "\\n")',
        '                await asyncio.to_thread(lambda: open(log_file, "a", encoding="utf-8").write(json.dumps(event, ensure_ascii=False) + "\\n"))'
    ),
    (
        '                with open(log_file, "r", encoding="utf-8") as f:',
        '                def _rd():\n                    with open(log_file, "r", encoding="utf-8") as f:'
    ),
])

# ===== services/online_eval.py - fix the metrics_file write =====
print('Fixing src/services/online_eval.py (remaining)...')
fix_file('src/services/online_eval.py', [
    (
        '                        f.write(json.dumps(metric, ensure_ascii=False) + "\\n")',
        '                        f.write(json.dumps(metric, ensure_ascii=False) + "\\n")\n                    await asyncio.to_thread(_wr)'
    ),
])

# ===== services/learner.py =====
print('Fixing src/services/learner.py...')
fix_file('src/services/learner.py', [
    (
        '    with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:\n        f.write(json.dumps(entry, ensure_ascii=False) + "\\n")',
        '    import asyncio as _aio\n    await _aio.to_thread(lambda: open(FEEDBACK_LOG, "a", encoding="utf-8").write(json.dumps(entry, ensure_ascii=False) + "\\n"))'
    ),
])

# ===== services/feedback_store.py =====
print('Fixing src/services/feedback_store.py...')
fix_file('src/services/feedback_store.py', [
    (
        "    with open(log_path, 'a', encoding='utf-8') as f:\n        f.write(json.dumps(entry, ensure_ascii=False) + '\\n')",
        "    import asyncio as _aio\n    await _aio.to_thread(lambda: open(log_path, 'a', encoding='utf-8').write(json.dumps(entry, ensure_ascii=False) + '\\n'))"
    ),
])

# ===== services/evolver.py =====
print('Fixing src/services/evolver.py...')
fix_file('src/services/evolver.py', [
    (
        "            graph = json.loads(GRAPH_FILE.read_text(encoding='utf-8'))",
        "            import asyncio as _aio\n            graph = await _aio.to_thread(lambda: json.loads(GRAPH_FILE.read_text(encoding='utf-8')))"
    ),
])

print('\nDone with batch 2 fixes!')
