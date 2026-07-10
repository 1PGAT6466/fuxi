"""Fix N+1 in shaoyang/relation_builder.py"""
import os
os.chdir(r'E:\easyclaw\伏羲-v1.44\repo')

with open('src/shaoyang/relation_builder.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''                count = 0
                for r in relations:
                    try:
                        db.execute(
                            "INSERT OR IGNORE INTO entity_relations (from_id, to_id, relation_type) VALUES (?, ?, ?)",
                            (r["from_id"], r["to_id"], r["relation_type"])
                        )
                        count += 1
                    except Exception as e:
                        logger.warning(f"\u63d2\u5165\u5173\u7cfb\u5931\u8d25: {e}")'''

new = '''                # Batch: executemany \u66ff\u4ee3\u5faa\u73af INSERT
                rel_rows = [(r["from_id"], r["to_id"], r["relation_type"]) for r in relations]
                count = 0
                if rel_rows:
                    try:
                        db.executemany(
                            "INSERT OR IGNORE INTO entity_relations (from_id, to_id, relation_type) VALUES (?, ?, ?)",
                            rel_rows
                        )
                        count = len(rel_rows)
                    except Exception as e:
                        logger.warning(f"\u6279\u91cf\u63d2\u5165\u5173\u7cfb\u5931\u8d25: {e}")'''

if old in content:
    content = content.replace(old, new)
    print('Fixed N+1 in shaoyang/relation_builder.py')
else:
    print('SKIP: pattern not found')

with open('src/shaoyang/relation_builder.py', 'w', encoding='utf-8') as f:
    f.write(content)
