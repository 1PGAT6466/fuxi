"""Fix sync I/O in async functions - services and infra."""
import os
os.chdir(r'E:\easyclaw\伏羲-v1.44\repo')

def fix_file(path, replacements):
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

# ===== services/eval_pipeline.py =====
print('Fixing src/services/eval_pipeline.py...')
fix_file('src/services/eval_pipeline.py', [
    (
        '            with open(eval_file, "a", encoding="utf-8") as f:\n                f.write(json.dumps(result, ensure_ascii=False) + "\\n")',
        '            await asyncio.to_thread(lambda: open(eval_file, "a", encoding="utf-8").write(json.dumps(result, ensure_ascii=False) + "\\n"))'
    ),
    (
        '                with open(eval_file, "r", encoding="utf-8") as f:',
        '                def _rd():\n                    with open(eval_file, "r", encoding="utf-8") as f:'
    ),
])

# ===== services/online_eval.py =====
print('Fixing src/services/online_eval.py...')
fix_file('src/services/online_eval.py', [
    (
        '                with open(metrics_file, "a", encoding="utf-8") as f:\n                        f.write(json.dumps(metric, ensure_ascii=False) + "\\n")',
        '                await asyncio.to_thread(lambda: open(metrics_file, "a", encoding="utf-8").write(json.dumps(metric, ensure_ascii=False) + "\\n"))'
    ),
    (
        '                with open(metrics_file, "r", encoding="utf-8") as f:',
        '                def _rd():\n                    with open(metrics_file, "r", encoding="utf-8") as f:'
    ),
])

# ===== services/memory.py =====
print('Fixing src/services/memory.py...')
fix_file('src/services/memory.py', [
    (
        '                with open(session_file, "w", encoding="utf-8") as f:',
        '                def _wr():\n                    with open(session_file, "w", encoding="utf-8") as f:'
    ),
    (
        '                with open(session_file, "r", encoding="utf-8") as f:',
        '                def _rd():\n                    with open(session_file, "r", encoding="utf-8") as f:'
    ),
    (
        '                with open(memory_file, "a", encoding="utf-8") as f:',
        '                def _app():\n                    with open(memory_file, "a", encoding="utf-8") as f:'
    ),
    (
        '                with open(memory_file, "r", encoding="utf-8") as f:',
        '                def _rd2():\n                    with open(memory_file, "r", encoding="utf-8") as f:'
    ),
])

# ===== infra/adjustment_log.py =====
print('Fixing src/infra/adjustment_log.py...')
fix_file('src/infra/adjustment_log.py', [
    (
        '                with open(log_file, "a", encoding="utf-8") as f:\n                    f.write(json.dumps(entry, ensure_ascii=False) + "\\n")',
        '                await asyncio.to_thread(lambda: open(log_file, "a", encoding="utf-8").write(json.dumps(entry, ensure_ascii=False) + "\\n"))'
    ),
    (
        '                with open(log_file, "r", encoding="utf-8") as f:',
        '                def _rd():\n                    with open(log_file, "r", encoding="utf-8") as f:'
    ),
])

# ===== infra/engine.py =====
print('Fixing src/infra/engine.py...')
fix_file('src/infra/engine.py', [
    (
        '                with open(log_file, "a", encoding="utf-8") as f:\n                    f.write(json.dumps(record, ensure_ascii=False) + "\\n")',
        '                await asyncio.to_thread(lambda: open(log_file, "a", encoding="utf-8").write(json.dumps(record, ensure_ascii=False) + "\\n"))'
    ),
    (
        '                with open(log_file, "r", encoding="utf-8") as f:',
        '                def _rd():\n                    with open(log_file, "r", encoding="utf-8") as f:'
    ),
])

# ===== infra/growth_recorder.py =====
print('Fixing src/infra/growth_recorder.py...')
fix_file('src/infra/growth_recorder.py', [
    (
        '                with open(log_file, "a", encoding="utf-8") as f:\n                    f.write(json.dumps(record, ensure_ascii=False) + "\\n")',
        '                await asyncio.to_thread(lambda: open(log_file, "a", encoding="utf-8").write(json.dumps(record, ensure_ascii=False) + "\\n"))'
    ),
    (
        '            with open(log_file, "r", encoding="utf-8") as f:',
        '            def _rd():\n                with open(log_file, "r", encoding="utf-8") as f:'
    ),
])

# ===== infra/audit_log.py =====
print('Fixing src/infra/audit_log.py...')
# audit_log uses open() but in sync functions called from various contexts.
# The get_audit_stats function is sync and reads files. Skip for now.

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

# ===== services/feature_flags.py =====
print('Fixing src/services/feature_flags.py...')
fix_file('src/services/feature_flags.py', [
    (
        '    FLAG_FILE.write_text(json.dumps(flags, indent=2, ensure_ascii=False), encoding="utf-8")',
        '    import asyncio as _aio\n    await _aio.to_thread(lambda: FLAG_FILE.write_text(json.dumps(flags, indent=2, ensure_ascii=False), encoding="utf-8"))'
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

print('\nDone with services/infra fixes!')
