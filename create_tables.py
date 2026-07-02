"""
create_tables.py — 创建方案要求的数据库表
events/entities/relations
"""
import sys
sys.path.insert(0, '.')

from src.db.memory_store import get_store

store = get_store()

# 创建events表
store._db_conn.execute("""
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    title TEXT,
    summary TEXT,
    content TEXT,
    category TEXT,
    keywords TEXT,
    priority TEXT DEFAULT 'UNKNOWN',
    parent_event_id TEXT,
    level INTEGER DEFAULT 0,
    children TEXT,
    chunk_ids TEXT,
    entity_names TEXT,
    ref_list TEXT,
    file_hash TEXT,
    file_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# 创建entities表
store._db_conn.execute("""
CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY,
    name TEXT,
    entity_type TEXT,
    description TEXT,
    aliases TEXT,
    canonical_name TEXT,
    event_ids TEXT,
    chunk_ids TEXT,
    mentions INTEGER DEFAULT 1,
    file_hash TEXT,
    file_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# 创建relations表
store._db_conn.execute("""
CREATE TABLE IF NOT EXISTS relations (
    relation_id TEXT PRIMARY KEY,
    source_type TEXT,
    source_id TEXT,
    target_type TEXT,
    target_id TEXT,
    relation_type TEXT,
    weight REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

store._db_conn.commit()

print('数据库表创建完成')

# 验证表结构
for tbl in ['events', 'entities', 'relations']:
    columns = store._db_conn.execute('PRAGMA table_info(' + tbl + ')').fetchall()
    print(tbl + '表列: ' + str([c[1] for c in columns]))
