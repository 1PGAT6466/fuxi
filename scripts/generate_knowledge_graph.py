"""
批量生成知识图谱脚本
从 chunks.db 中读取文档，使用 AutoGraphBuilder 生成知识图谱
"""
import json
import sqlite3
import sys
import os
from pathlib import Path

# 添加项目路径
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))

from src.bagua.auto_graph import AutoGraphBuilder
from src.config import DATA_DIR

def main():
    print("=" * 60)
    print("伏羲知识图谱批量生成")
    print("=" * 60)
    
    # 1. 连接数据库
    # 使用 .env 中配置的 FUXI_DATA_DIR
    from dotenv import load_dotenv
    load_dotenv("E:/fuxi-system/.env")
    
    # 优先使用环境变量，否则使用默认路径
    data_dir = os.getenv("FUXI_DATA_DIR", "E:/fuxi-system/data")
    db_path = Path(data_dir) / "chunks.db"
    
    # 验证数据库路径
    print(f"数据库路径: {db_path}")
    print(f"数据库存在: {db_path.exists()}")
    
    if not db_path.exists():
        print(f"错误：数据库不存在 {db_path}")
        print("请检查 FUXI_DATA_DIR 环境变量配置")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # 2. 检查 chunks 表
    cursor.execute("SELECT COUNT(*) FROM chunks")
    chunk_count = cursor.fetchone()[0]
    print(f"chunks 表记录数: {chunk_count}")
    
    if chunk_count == 0:
        print("错误：chunks 表为空")
        conn.close()
        return
    
    # 3. 初始化 AutoGraphBuilder
    builder = AutoGraphBuilder()
    print(f"初始化 AutoGraphBuilder 完成")
    
    # 4. 读取所有 chunks
    cursor.execute("SELECT id, doc, file_name FROM chunks")
    chunks = cursor.fetchall()
    print(f"读取 {len(chunks)} 个 chunks")
    
    # 5. 批量生成知识图谱
    all_entities = []
    all_edges = []
    
    for i, (chunk_id, chunk_text, file_name) in enumerate(chunks, 1):
        if i % 100 == 0:
            print(f"处理进度: {i}/{len(chunks)}")
        
        if not chunk_text:
            continue
        
        # 提取实体
        entities = builder.extract_entities(chunk_text)
        for entity in entities:
            entity["chunk_id"] = chunk_id
            entity["file_name"] = file_name
            all_entities.append(entity)
        
        # 构建边
        edges = builder.build_from_text(chunk_text, doc_id=chunk_id)
        for edge in edges:
            edge["chunk_id"] = chunk_id
            edge["file_name"] = file_name
            all_edges.append(edge)
    
    print(f"提取实体数: {len(all_entities)}")
    print(f"构建边数: {len(all_edges)}")
    
    # 6. 去重实体
    unique_entities = {}
    for entity in all_entities:
        name = entity.get("name", "")
        if name and name not in unique_entities:
            unique_entities[name] = entity
    
    print(f"去重后实体数: {len(unique_entities)}")
    
    # 7. 去重边
    unique_edges = {}
    for edge in all_edges:
        key = (edge.get("source", ""), edge.get("target", ""), edge.get("relation", ""))
        if key not in unique_edges:
            unique_edges[key] = edge
    
    print(f"去重后边数: {len(unique_edges)}")
    
    # 8. 生成 knowledge_graph.json
    graph = {
        "nodes": list(unique_entities.values()),
        "edges": list(unique_edges.values()),
        "metadata": {
            "chunk_count": chunk_count,
            "entity_count": len(unique_entities),
            "edge_count": len(unique_edges),
        }
    }
    
    graph_path = DATA_DIR / "knowledge_graph.json"
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    
    print(f"知识图谱已保存到: {graph_path}")
    
    # 9. 写入 events 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            title TEXT,
            summary TEXT,
            content TEXT,
            chunk_ids_json TEXT,
            entity_names_json TEXT,
            event_type TEXT,
            level TEXT,
            file_hash TEXT,
            file_name TEXT,
            status TEXT DEFAULT 'active'
        )
    """)
    
    # 清空 events 表
    cursor.execute("DELETE FROM events")
    
    # 写入事件
    for i, (entity_name, entity) in enumerate(unique_entities.items(), 1):
        event_id = f"event_{i:06d}"
        cursor.execute("""
            INSERT INTO events (event_id, title, summary, content, chunk_ids_json, entity_names_json, event_type, level, file_hash, file_name, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_id,
            entity_name,
            f"实体: {entity_name}",
            json.dumps(entity, ensure_ascii=False),
            json.dumps([entity.get("chunk_id", "")]),
            json.dumps([entity_name]),
            entity.get("type", "unknown"),
            "entity",
            "",
            entity.get("file_name", ""),
            "active"
        ))
    
    conn.commit()
    print(f"写入 events 表: {len(unique_entities)} 条记录")
    
    # 10. 写入 entities 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY,
            entity_id TEXT,
            name TEXT,
            entity_type TEXT,
            description TEXT,
            aliases_json TEXT,
            chunk_ids_json TEXT,
            event_ids_json TEXT,
            source TEXT,
            file_hash TEXT,
            file_name TEXT,
            embedding BLOB,
            mentions INTEGER,
            status TEXT,
            timestamp DATETIME,
            tenant_id TEXT
        )
    """)
    
    # 清空 entities 表
    cursor.execute("DELETE FROM entities")
    
    # 写入实体
    for i, (entity_name, entity) in enumerate(unique_entities.items(), 1):
        entity_id = f"entity_{i:06d}"
        cursor.execute("""
            INSERT INTO entities (entity_id, name, entity_type, description, aliases_json, chunk_ids_json, event_ids_json, source, file_hash, file_name, mentions, status, tenant_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entity_id,
            entity_name,
            entity.get("type", "unknown"),
            f"实体: {entity_name}",
            json.dumps([], ensure_ascii=False),
            json.dumps([entity.get("chunk_id", "")], ensure_ascii=False),
            json.dumps([], ensure_ascii=False),
            "auto_graph",
            "",
            entity.get("file_name", ""),
            1,
            "active",
            "default"
        ))
    
    conn.commit()
    print(f"写入 entities 表: {len(unique_entities)} 条记录")
    
    # 11. 验证结果
    cursor.execute("SELECT COUNT(*) FROM events")
    event_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM entities")
    entity_count = cursor.fetchone()[0]
    
    print("\n" + "=" * 60)
    print("生成结果")
    print("=" * 60)
    print(f"chunks 表: {chunk_count} 条")
    print(f"events 表: {event_count} 条")
    print(f"entities 表: {entity_count} 条")
    print(f"knowledge_graph.json: {len(unique_entities)} 个节点, {len(unique_edges)} 条边")
    
    conn.close()
    print("\n知识图谱生成完成！")

if __name__ == "__main__":
    main()
