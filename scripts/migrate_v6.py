#!/usr/bin/env python3
"""
Step 2: 分类迁移
从 uploads/ 读取 .docx → match_category(带 file_name) → 更新 SQLite + ChromaDB
"""
import sys, sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import chromadb
from chromadb.config import Settings as ChromaSettings
from category_registry import match_category

DB_PATH = PROJECT_ROOT / "data" / "chunks.db"
CHROMA_PATH = PROJECT_ROOT / "data" / "chroma"
UPLOADS_PATH = PROJECT_ROOT / "uploads"

execute = "--execute" in sys.argv
if not execute:
    print("=== DRY RUN (加 --execute 执行) ===\n")

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row
client = chromadb.PersistentClient(path=str(CHROMA_PATH), settings=ChromaSettings(anonymized_telemetry=False))
collection = client.get_collection("kb_chunks")

docx_files = list(UPLOADS_PATH.glob("*.docx"))
print(f"源文件: {len(docx_files)} 个\n")

import docx as docx_lib

stats = {}
changes = []

for filepath in docx_files:
    fname = filepath.name
    try:
        d = docx_lib.Document(str(filepath))
        text = "\n".join(p.text for p in d.paragraphs if p.text.strip())
    except:
        text = ""

    if not text:
        print(f"  跳过: {fname}")
        continue

    new_cat = match_category(text, file_ext=".docx", file_name=fname)
    stats[new_cat] = stats.get(new_cat, 0) + 1

    rows = conn.execute("SELECT id, category FROM chunks WHERE file_name=?", (fname,)).fetchall()
    for row in rows:
        if row["category"] != new_cat:
            changes.append((row["id"], fname, row["category"], new_cat))

    print(f"  {fname[:50]:50s} → {new_cat} ({len(rows)} chunks)")

print(f"\n=== 统计 ===")
for cat, cnt in sorted(stats.items(), key=lambda x: -x[1]):
    print(f"  {cat}: {cnt}")
print(f"变更: {len(changes)} 条")

if not execute:
    print("\nDRY RUN 完成")
    conn.close()
    sys.exit(0)

# 执行
ok_sql = ok_chroma = err = 0
for doc_id, fname, old, new in changes:
    if conn.execute("UPDATE chunks SET category=? WHERE id=?", (new, doc_id)).rowcount > 0:
        ok_sql += 1
    try:
        ex = collection.get(ids=[doc_id], include=["metadatas"])
        if ex["metadatas"]:
            m = dict(ex["metadatas"][0])
            m["category"] = new
            collection.update(ids=[doc_id], metadatas=[m])
            ok_chroma += 1
    except:
        err += 1

conn.commit()
print(f"\nSQLite: {ok_sql} | ChromaDB: {ok_chroma} | 错误: {err}")

print("\n=== 最终 ===")
for r in conn.execute("SELECT category, COUNT(*) c FROM chunks GROUP BY category ORDER BY c DESC"):
    print(f"  {r[0]}: {r[1]}")
conn.close()
