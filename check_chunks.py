import sqlite3

db_path = 'E:/easyclaw/伏羲-v1.44/repo/data/chunks.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 检查表结构
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('Tables:', [t[0] for t in tables])

# 检查 chunks 表
if ('chunks',) in tables:
    cursor.execute('SELECT COUNT(*) FROM chunks')
    count = cursor.fetchone()[0]
    print(f'Total chunks: {count}')
    
    cursor.execute('SELECT file_name, COUNT(*) FROM chunks GROUP BY file_name')
    for row in cursor.fetchall():
        print(f'  {row[0]}: {row[1]} chunks')
    
    # 检查是否有嵌入向量
    cursor.execute('PRAGMA table_info(chunks)')
    columns = cursor.fetchall()
    print(f'Columns: {[c[1] for c in columns]}')
    
    # 检查一条记录
    cursor.execute('SELECT * FROM chunks LIMIT 1')
    row = cursor.fetchone()
    if row:
        print(f'Sample row (first 5 fields): {row[:5]}')

conn.close()
