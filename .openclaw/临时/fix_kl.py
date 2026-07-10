"""Fix knowledge_lifecycle.py"""
import os
os.chdir(r'E:\easyclaw\伏羲-v1.44\repo')

with open('src/services/knowledge_lifecycle.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''            def _count():
                c = 0
                def _rd():
                    with open(log_file, "r", encoding="utf-8") as f:
                        for line in f:
                        try:
                            event = json.loads(line.strip())
                            if event.get("timestamp", 0) > cutoff:
                                c += 1
                        except Exception as e:
                            logger.warning("JSON\u89e3\u6790\u751f\u547d\u5468\u671f\u4e8b\u4ef6\u7edf\u8ba1\u5931\u8d25: %s", e, exc_info=True)
                return c'''

new = '''            def _count():
                c = 0
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            event = json.loads(line.strip())
                            if event.get("timestamp", 0) > cutoff:
                                c += 1
                        except Exception as e:
                            logger.warning("JSON\u89e3\u6790\u751f\u547d\u5468\u671f\u4e8b\u4ef6\u7edf\u8ba1\u5931\u8d25: %s", e, exc_info=True)
                return c'''

if old in content:
    content = content.replace(old, new)
    print('Fixed _count')
else:
    print('SKIP: _count')

with open('src/services/knowledge_lifecycle.py', 'w', encoding='utf-8') as f:
    f.write(content)
