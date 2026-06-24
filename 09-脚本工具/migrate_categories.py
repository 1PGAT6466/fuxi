"""
migrate_categories.py — 分类数据迁移脚本
==========================================
将数据库中已有的旧分类名批量替换为统一名称

运行方式：
    cd /home/feng-shaoxuan/kb-server
    python scripts/migrate_categories.py [--dry-run]
"""

import os
import sys
import json
import sqlite3
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import DATA_DIR, CHUNKS_DB_PATH, GRAPH_PATH

# 旧名 → 新名 映射
ALIAS_MAP = {
    "网络建设": "IT网络",
    "品质管理": "品质测量",
    "公司制度": "操作手册",
}


def migrate_chunks_db(dry_run=False):
    """迁移 chunks.db 中的分类字段"""
    if not CHUNKS_DB_PATH.exists():
        print(f"chunks.db not found at {CHUNKS_DB_PATH}")
        return
    
    conn = sqlite3.connect(str(CHUNKS_DB_PATH))
    
    # 查看当前分类分布
    rows = conn.execute(
        "SELECT category, COUNT(*) as cnt FROM chunks GROUP BY category ORDER BY cnt DESC"
    ).fetchall()
    
    print("\n当前 chunks.db 分类分布:")
    for cat, cnt in rows:
        new_cat = ALIAS_MAP.get(cat, cat)
        marker = f" → {new_cat}" if cat != new_cat else ""
        print(f"  {cat}: {cnt}{marker}")
    
    # 需要迁移的记录
    need_migrate = []
    for old_name, new_name in ALIAS_MAP.items():
        count = conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE category = ?", (old_name,)
        ).fetchone()[0]
        if count > 0:
            need_migrate.append((old_name, new_name, count))
    
    if not need_migrate:
        print("\n无需迁移，所有分类已是最新名称")
        conn.close()
        return
    
    print(f"\n需要迁移:")
    for old_name, new_name, count in need_migrate:
        print(f"  {old_name} → {new_name}: {count} 条")
    
    if dry_run:
        print("\n[DRY RUN] 未实际修改")
        conn.close()
        return
    
    # 执行迁移
    for old_name, new_name, count in need_migrate:
        conn.execute(
            "UPDATE chunks SET category = ? WHERE category = ?",
            (new_name, old_name)
        )
        print(f"  ✅ {old_name} → {new_name}: {count} 条已更新")
    
    conn.commit()
    conn.close()
    print("\nchunks.db 迁移完成")


def migrate_chroma(dry_run=False):
    """迁移 ChromaDB 中的分类元数据"""
    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        
        chroma_dir = str(DATA_DIR / "chroma")
        if not os.path.exists(chroma_dir):
            print(f"\nChromaDB 目录不存在: {chroma_dir}")
            return
        
        client = chromadb.PersistentClient(
            path=chroma_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        collection = client.get_collection("kb_chunks")
        
        # 查询需要迁移的记录
        for old_name, new_name in ALIAS_MAP.items():
            results = collection.get(
                where={"category": old_name},
                include=["metadatas"]
            )
            count = len(results["ids"]) if results and results["ids"] else 0
            
            if count == 0:
                continue
            
            print(f"\n  ChromaDB: {old_name} → {new_name}: {count} 条")
            
            if dry_run:
                continue
            
            # 批量更新 metadata
            for i, chunk_id in enumerate(results["ids"]):
                meta = results["metadatas"][i]
                meta["category"] = new_name
                collection.update(
                    ids=[chunk_id],
                    metadatas=[meta]
                )
            print(f"    ✅ 已更新 {count} 条")
        
        if not dry_run:
            print("\nChromaDB 迁移完成")
        
    except Exception as e:
        print(f"\nChromaDB 迁移失败: {e}")


def migrate_graph(dry_run=False):
    """迁移 knowledge_graph.json 中的分类"""
    if not GRAPH_PATH.exists():
        print(f"\nknowledge_graph.json not found")
        return
    
    graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    nodes = graph.get("nodes", {})
    
    migrated = 0
    for name, info in nodes.items():
        cat = info.get("category", "")
        if cat in ALIAS_MAP:
            if not dry_run:
                info["category"] = ALIAS_MAP[cat]
            migrated += 1
    
    if migrated == 0:
        print("\n图谱无需迁移")
        return
    
    print(f"\n图谱: {migrated} 个实体分类需更新")
    
    if dry_run:
        print("[DRY RUN] 未实际修改")
        return
    
    tmp_path = str(GRAPH_PATH) + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, str(GRAPH_PATH))
    print("✅ 图谱迁移完成")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate category names to unified format")
    parser.add_argument("--dry-run", action="store_true", help="只分析不修改")
    args = parser.parse_args()
    
    print("=" * 50)
    print("分类数据迁移工具")
    print("=" * 50)
    print(f"映射关系: {json.dumps(ALIAS_MAP, ensure_ascii=False)}")
    
    migrate_chunks_db(dry_run=args.dry_run)
    migrate_chroma(dry_run=args.dry_run)
    migrate_graph(dry_run=args.dry_run)
    
    print("\n" + "=" * 50)
    if args.dry_run:
        print("[DRY RUN] 完成，未修改任何数据")
    else:
        print("迁移完成！建议重启 kb-server")
    print("=" * 50)
