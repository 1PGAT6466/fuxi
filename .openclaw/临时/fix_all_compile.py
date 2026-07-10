"""Comprehensive fix for all compilation errors.
Strategy: For files where patches broke things, revert to original and apply correct fixes.
"""
import os
os.chdir(r'E:\easyclaw\伏羲-v1.44\repo')

def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

# ===== notifications.py =====
print('Fixing src/api/notifications.py...')
content = read_file('src/api/notifications.py')

# Fix the broken with block (extra indentation)
old = '''        try:
                with open(_NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
                notifications = json.load(f)'''
new = '''        try:
            with open(_NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
                notifications = json.load(f)'''
if old in content:
    content = content.replace(old, new)
    print('  Fixed indentation')

write_file('src/api/notifications.py', content)

# ===== learner.py =====
print('Fixing src/services/learner.py...')
content = read_file('src/services/learner.py')

# Revert: remove the broken await, use sync write (this function is sync)
old = '''    import asyncio as _aio
    await _aio.to_thread(lambda: open(FEEDBACK_LOG, "a", encoding="utf-8").write(json.dumps(entry, ensure_ascii=False) + "\\n"))'''
new = '''    with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\\n")'''
if old in content:
    content = content.replace(old, new)
    print('  Reverted to sync (function is not async)')

write_file('src/services/learner.py', content)

# ===== feedback_store.py =====
print('Fixing src/services/feedback_store.py...')
content = read_file('src/services/feedback_store.py')

old = '''    import asyncio as _aio
    await _aio.to_thread(lambda: open(log_path, 'a', encoding='utf-8').write(json.dumps(entry, ensure_ascii=False) + '\\n'))'''
new = '''    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\\n')'''
if old in content:
    content = content.replace(old, new)
    print('  Reverted to sync (function is not async)')

write_file('src/services/feedback_store.py', content)

# ===== evolver.py =====
print('Fixing src/services/evolver.py...')
content = read_file('src/services/evolver.py')

old = '''            import asyncio as _aio
            graph = await _aio.to_thread(lambda: json.loads(GRAPH_FILE.read_text(encoding='utf-8')))'''
new = '''            graph = json.loads(GRAPH_FILE.read_text(encoding='utf-8'))'''
if old in content:
    content = content.replace(old, new)
    print('  Reverted to sync (function is not async)')

write_file('src/services/evolver.py', content)

# ===== trace_logger.py =====
print('Fixing src/infra/trace_logger.py...')
content = read_file('src/infra/trace_logger.py')

old = '            await asyncio.to_thread(lambda: open(trace_file, "a", encoding="utf-8").write(log_line + "\\n"))'
new = '''            with open(trace_file, "a", encoding="utf-8") as f:
                f.write(log_line + "\\n")'''
if old in content:
    content = content.replace(old, new)
    print('  Reverted to sync (method is not async)')

write_file('src/infra/trace_logger.py', content)

# ===== eval_pipeline.py - broken nested function =====
print('Fixing src/services/eval_pipeline.py...')
content = read_file('src/services/eval_pipeline.py')

# The patch created a nested _rd inside _read_eval, breaking indentation
# Fix: remove the extra nesting
old = '''            def _read_eval():
                result = []
                def _rd():
                    with open(eval_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            result.append(json.loads(line.strip()))
                        except Exception as e:
                            logger.warning("JSON解析评测结果失败: %s", e, exc_info=True)
                return result
            results = await asyncio.to_thread(_read_eval)'''
new = '''            def _read_eval():
                result = []
                with open(eval_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            result.append(json.loads(line.strip()))
                        except Exception as e:
                            logger.warning("JSON解析评测结果失败: %s", e, exc_info=True)
                return result
            results = await asyncio.to_thread(_read_eval)'''
if old in content:
    content = content.replace(old, new)
    print('  Fixed nested function indentation')
else:
    print('  SKIP: pattern not found')

write_file('src/services/eval_pipeline.py', content)

# ===== online_eval.py - broken nested function =====
print('Fixing src/services/online_eval.py...')
content = read_file('src/services/online_eval.py')

old = '''            def _read_metrics():
                result = []
                def _rd():
                    with open(metrics_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            metric = json.loads(line.strip())
                            if metric.get("timestamp", 0) > cutoff:
                                result.append(metric)
                        except Exception as e:
                            logger.warning("JSON解析线上评测指标失败: %s", e, exc_info=True)
                return result
            stats = await asyncio.to_thread(_read_metrics)'''
new = '''            def _read_metrics():
                result = []
                with open(metrics_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            metric = json.loads(line.strip())
                            if metric.get("timestamp", 0) > cutoff:
                                result.append(metric)
                        except Exception as e:
                            logger.warning("JSON解析线上评测指标失败: %s", e, exc_info=True)
                return result
            stats = await asyncio.to_thread(_read_metrics)'''
if old in content:
    content = content.replace(old, new)
    print('  Fixed nested function indentation')
else:
    print('  SKIP: pattern not found')

write_file('src/services/online_eval.py', content)

# ===== memory.py - broken nested function =====
print('Fixing src/services/memory.py...')
content = read_file('src/services/memory.py')

old = '''            def _write_session():
                def _wr():
                    with open(session_file, "w", encoding="utf-8") as f:
                    json.dump(messages, f, ensure_ascii=False, indent=2)
            await asyncio.to_thread(_write_session)'''
new = '''            def _write_session():
                with open(session_file, "w", encoding="utf-8") as f:
                    json.dump(messages, f, ensure_ascii=False, indent=2)
            await asyncio.to_thread(_write_session)'''
if old in content:
    content = content.replace(old, new)
    print('  Fixed nested function indentation')
else:
    print('  SKIP: pattern not found')

write_file('src/services/memory.py', content)

# ===== knowledge_lifecycle.py - broken nested function =====
print('Fixing src/services/knowledge_lifecycle.py...')
content = read_file('src/services/knowledge_lifecycle.py')

old = '''            def _read_events():
                result = []
                def _rd():
                    with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            event = json.loads(line.strip())
                            result.append(event.get("data", {}))
                        except Exception as e:
                            logger.warning("JSON解析生命周期事件失败: %s", e, exc_info=True)
                return result'''
new = '''            def _read_events():
                result = []
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            event = json.loads(line.strip())
                            result.append(event.get("data", {}))
                        except Exception as e:
                            logger.warning("JSON解析生命周期事件失败: %s", e, exc_info=True)
                return result'''
if old in content:
    content = content.replace(old, new)
    print('  Fixed nested function indentation')
else:
    print('  SKIP: pattern not found')

write_file('src/services/knowledge_lifecycle.py', content)

# ===== growth/adjustment_log.py - broken nested function =====
print('Fixing src/growth/adjustment_log.py...')
content = read_file('src/growth/adjustment_log.py')

old = '''            def _read_log():
                result = []
                def _rd():
                    with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            result.append(json.loads(line.strip()))
                        except Exception as e:  # TODO: Narrow exception type
                            logger.warning("JSON解析调整记录失败: %s", e, exc_info=True)
                return result
            records = await asyncio.to_thread(_read_log)'''
new = '''            def _read_log():
                result = []
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            result.append(json.loads(line.strip()))
                        except Exception as e:  # TODO: Narrow exception type
                            logger.warning("JSON解析调整记录失败: %s", e, exc_info=True)
                return result
            records = await asyncio.to_thread(_read_log)'''
if old in content:
    content = content.replace(old, new)
    print('  Fixed nested function indentation')
else:
    print('  SKIP: pattern not found')

write_file('src/growth/adjustment_log.py', content)

# ===== growth/engine.py - broken nested function =====
print('Fixing src/growth/engine.py...')
content = read_file('src/growth/engine.py')

old = '''            def _read_log():
                result = []
                def _rd():
                    with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            result.append(json.loads(line.strip()))
                        except Exception as e:
                            logger.warning("JSON解析成长事件失败: %s", e, exc_info=True)
                return result
            events = await asyncio.to_thread(_read_log)'''
new = '''            def _read_log():
                result = []
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            result.append(json.loads(line.strip()))
                        except Exception as e:
                            logger.warning("JSON解析成长事件失败: %s", e, exc_info=True)
                return result
            events = await asyncio.to_thread(_read_log)'''
if old in content:
    content = content.replace(old, new)
    print('  Fixed nested function indentation')
else:
    print('  SKIP: pattern not found')

write_file('src/growth/engine.py', content)

# ===== growth/growth_recorder.py - broken nested function =====
print('Fixing src/growth/growth_recorder.py...')
content = read_file('src/growth/growth_recorder.py')

old = '''        def _read_log():
            result = []
            def _rd():
                with open(log_file, "r", encoding="utf-8") as f:
                for line in f:'''
new = '''        def _read_log():
            result = []
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:'''
if old in content:
    content = content.replace(old, new)
    print('  Fixed nested function indentation')
else:
    print('  SKIP: pattern not found')

write_file('src/growth/growth_recorder.py', content)

print('\nDone fixing all compilation errors!')
