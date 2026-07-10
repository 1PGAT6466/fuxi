"""Fix remaining broken files by reverting patches that created nested functions."""
import os
os.chdir(r'E:\easyclaw\伏羲-v1.44\repo')

def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

# ===== online_eval.py =====
print('Fixing src/services/online_eval.py...')
content = read_file('src/services/online_eval.py')

# Revert the broken _read_metrics function
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
                        metrics = await asyncio.to_thread(_read_metrics)
                        except Exception as e:  # TODO: Narrow exception type
                        logger.warning("获取线上评测指标失败: %s", e, exc_info=True)'''
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
            metrics = await asyncio.to_thread(_read_metrics)
        except Exception as e:  # TODO: Narrow exception type
            logger.warning("获取线上评测指标失败: %s", e, exc_info=True)'''
if old in content:
    content = content.replace(old, new)
    print('  Fixed _read_metrics')
else:
    print('  SKIP: pattern not found')

# Also fix the second _read_metrics
old2 = '''            def _read_metrics():
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
new2 = '''            def _read_metrics():
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
if old2 in content:
    content = content.replace(old2, new2)
    print('  Fixed second _read_metrics')

write_file('src/services/online_eval.py', content)

# ===== memory.py =====
print('Fixing src/services/memory.py...')
content = read_file('src/services/memory.py')

# Fix the broken session read function
old = '''            def _read_session():
                result = []
                def _rd():
                    with open(session_file, "r", encoding="utf-8") as f:
                        for line in f:
                        try:
                            result.append(json.loads(line.strip()))
                        except Exception as e:
                            logger.warning("JSON解析会话记录失败: %s", e, exc_info=True)
                        return result
            result = await asyncio.to_thread(_read_session)'''
new = '''            def _read_session():
                result = []
                with open(session_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            result.append(json.loads(line.strip()))
                        except Exception as e:
                            logger.warning("JSON解析会话记录失败: %s", e, exc_info=True)
                return result
            result = await asyncio.to_thread(_read_session)'''
if old in content:
    content = content.replace(old, new)
    print('  Fixed _read_session')

write_file('src/services/memory.py', content)

# ===== knowledge_lifecycle.py =====
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
    print('  Fixed _read_events')
else:
    print('  SKIP: pattern not found')

write_file('src/services/knowledge_lifecycle.py', content)

print('\nDone!')
