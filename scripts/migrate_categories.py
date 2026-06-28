#!/usr/bin/env python3
"""
v4.3 分类迁移脚本 v4
从 uploads/ 读取 .docx 原始文件 → 提取文本 → match_category → 更新 SQLite + ChromaDB
"""
import sys, os, sqlite3, time, json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import chromadb
from chromadb.config import Settings as ChromaSettings
from category_registry import match_category

DB_PATH = PROJECT_ROOT / "data" / "chunks.db"
CHROMA_PATH = PROJECT_ROOT / "data" / "chroma"
UPLOADS_PATH = PROJECT_ROOT / "uploads"

def extract_docx_text(filepath):
    """从 .docx 提取文本"""
    try:
        import docx
        doc = docx.Document(str(filepath))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        return ""

def migrate():
    execute = "--execute" in sys.argv
    if not execute:
        print("=== DRY RUN (加 --execute 执行) ===\n")

    # 连接 SQLite
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # 连接 ChromaDB
    client = chromadb.PersistentClient(
        path=str(CHROMA_PATH),
        settings=ChromaSettings(anonymized_telemetry=False)
    )
    # 注意：集合名是 kb_chunks，不是 documents
    collection = client.get_collection("kb_chunks")

    # 扫描 uploads 目录
    docx_files = list(UPLOADS_PATH.glob("*.docx"))
    print(f"找到 {len(docx_files)} 个 .docx 源文件\n")

    # 逐文件处理
    stats = {}
    changes = []
    skipped = 0

    for filepath in docx_files:
        fname = filepath.name
        text = extract_docx_text(filepath)
        if not text:
            print(f"  跳过 (无文本): {fname}")
            skipped += 1
            continue

        new_cat = match_category(text, file_ext='.docx')
        stats[new_cat] = stats.get(new_cat, 0) + 1

        # 查 SQLite 中该文件的所有 chunks
        rows = conn.execute("SELECT id, category FROM chunks WHERE file_name=?", (fname,)).fetchall()
        for row in rows:
            old_cat = row["category"]
            if old_cat != new_cat:
                changes.append((row["id"], fname, old_cat, new_cat))

        print(f"  {fname[:45]:45s} → {new_cat} ({len(rows)} chunks)")

    print(f"\n=== 分类结果统计 ===")
    for cat, cnt in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {cnt} 个文件")
    print(f"\n需要变更: {len(changes)} 条 chunk")
    print(f"跳过: {skipped} 个文件")

    if not execute:
        print("\n=== DRY RUN 完成，加 --execute 执行迁移 ===")
        conn.close()
        return

    # === 执行迁移 ===
    print("\n=== 执行迁移 ===")
    updated_sqlite = 0
    updated_chroma = 0
    errors = 0

    for doc_id, fname, old_cat, new_cat in changes:
        # 1. SQLite
        cur = conn.execute("UPDATE chunks SET category=? WHERE id=?", (new_cat, doc_id))
        if cur.rowcount > 0:
            updated_sqlite += 1

        # 2. ChromaDB metadata
        try:
            existing = collection.get(ids=[doc_id], include=["metadatas"])
            if existing["metadatas"]:
                meta = dict(existing["metadatas"][0])
                meta["category"] = new_cat
                collection.update(ids=[doc_id], metadatas=[meta])
                updated_chroma += 1
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  ChromaDB 错误 {doc_id[:20]}: {e}")

    conn.commit()

    print(f"\nSQLite 更新: {updated_sqlite} 条")
    print(f"ChromaDB 更新: {updated_chroma} 条")
    print(f"错误: {errors} 条")

    # 最终验证
    print("\n=== 迁移后分布 ===")
    for row in conn.execute("SELECT category, COUNT(*) c FROM chunks GROUP BY category ORDER BY c DESC"):
        print(f"  {row[0]}: {row[1]} 条")

    conn.close()
    print("\n=== 迁移完成 ===")

if __name__ == "__main__":
    migrate()
