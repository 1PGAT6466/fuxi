"""Fix remaining N+1 queries."""
import os
os.chdir(r'E:\easyclaw\伏羲-v1.44\repo')

def fix_file(path, replacements):
    if not os.path.exists(path):
        print(f'  SKIP (file not found): {path}')
        return
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            print(f'  Fixed N+1: {old[:60]}...')
        else:
            print(f'  SKIP N+1: {old[:60]}...')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

# ===== db/vector_store.py - N+1 metadata update =====
print('Fixing N+1 in src/db/vector_store.py...')
fix_file('src/db/vector_store.py', [
    (
        '            # 针对每个匹配的向量，更新其 metadata\n            for i, chunk_id in enumerate(ids):\n                current_meta = metadatas[i] if i < len(metadatas) else {}\n                updated_meta = {**current_meta, **metadata_updates}\n                clean_meta = self._clean_metadata(updated_meta)\n\n                self._collection.update(\n                    ids=[chunk_id],\n                    metadatas=[clean_meta],\n                )',
        '            # Batch: 一次性更新所有 metadata\n            batch_ids = []\n            batch_metas = []\n            for i, chunk_id in enumerate(ids):\n                current_meta = metadatas[i] if i < len(metadatas) else {}\n                updated_meta = {**current_meta, **metadata_updates}\n                clean_meta = self._clean_metadata(updated_meta)\n                batch_ids.append(chunk_id)\n                batch_metas.append(clean_meta)\n            if batch_ids:\n                self._collection.update(ids=batch_ids, metadatas=batch_metas)'
    ),
])

# ===== storage/write_proxy.py - N+1 PostgreSQL inserts =====
print('Fixing N+1 in src/storage/write_proxy.py...')
fix_file('src/storage/write_proxy.py', [
    # Chunks batch
    (
        '            for c in chunks:\n                emb_str = self._embedding_to_str(c.embedding) if c.embedding else None\n                cur.execute(\n                    """INSERT INTO chunks (chunk_id, document_id, document_name, content,\n                       chunk_index, token_count, metadata, embedding)\n                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)\n                       ON CONFLICT (chunk_id) DO UPDATE SET content=EXCLUDED.content, updated_at=now()""",\n                    (c.chunk_id, c.document_id, c.document_name, c.content,\n                     c.chunk_index, c.token_count, json.dumps(c.metadata), emb_str),\n                )',
        '            # Batch: executemany 替代循环 INSERT\n            chunk_rows = []\n            for c in chunks:\n                emb_str = self._embedding_to_str(c.embedding) if c.embedding else None\n                chunk_rows.append((c.chunk_id, c.document_id, c.document_name, c.content,\n                     c.chunk_index, c.token_count, json.dumps(c.metadata), emb_str))\n            if chunk_rows:\n                cur.executemany(\n                    """INSERT INTO chunks (chunk_id, document_id, document_name, content,\n                       chunk_index, token_count, metadata, embedding)\n                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)\n                       ON CONFLICT (chunk_id) DO UPDATE SET content=EXCLUDED.content, updated_at=now()""",\n                    chunk_rows)'
    ),
    # Events batch
    (
        '            for e in events:\n                emb_str = self._embedding_to_str(e.embedding) if e.embedding else None\n                cur.execute(\n                    """INSERT INTO events (event_id, chunk_id, content, event_type,\n                       entities_json, confidence, status, metadata, embedding)\n                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)\n                       ON CONFLICT (event_id) DO UPDATE SET content=EXCLUDED.content, updated_at=now()""",\n                    (e.event_id, e.chunk_id, e.content, e.event_type,\n                     json.dumps(e.entities_json), e.confidence, e.status,\n                     json.dumps(e.metadata), emb_str),\n                )',
        '            # Batch: executemany 替代循环 INSERT\n            event_rows = []\n            for e in events:\n                emb_str = self._embedding_to_str(e.embedding) if e.embedding else None\n                event_rows.append((e.event_id, e.chunk_id, e.content, e.event_type,\n                     json.dumps(e.entities_json), e.confidence, e.status,\n                     json.dumps(e.metadata), emb_str))\n            if event_rows:\n                cur.executemany(\n                    """INSERT INTO events (event_id, chunk_id, content, event_type,\n                       entities_json, confidence, status, metadata, embedding)\n                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)\n                       ON CONFLICT (event_id) DO UPDATE SET content=EXCLUDED.content, updated_at=now()""",\n                    event_rows)'
    ),
    # Entities batch
    (
        '            for ent in entities:\n                emb_str = self._embedding_to_str(ent.embedding) if ent.embedding else None\n                cur.execute(\n                    """INSERT INTO entities (entity_id, name, normalized_name, type,\n                       aliases_json, chunk_ids_json, metadata, embedding)\n                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)\n                       ON CONFLICT (entity_id) DO UPDATE\n                       SET aliases_json = entities.aliases_json || EXCLUDED.aliases_json,\n                           chunk_ids_json = entities.chunk_ids_json || EXCLUDED.chunk_ids_json,\n                           updated_at = now()""",\n                    (ent.entity_id, ent.name, ent.normalized_name, ent.type,\n                     json.dumps(ent.aliases), json.dumps(ent.chunk_ids),\n                     json.dumps(ent.metadata), emb_str),\n                )',
        '            # Batch: executemany 替代循环 INSERT\n            ent_rows = []\n            for ent in entities:\n                emb_str = self._embedding_to_str(ent.embedding) if ent.embedding else None\n                ent_rows.append((ent.entity_id, ent.name, ent.normalized_name, ent.type,\n                     json.dumps(ent.aliases), json.dumps(ent.chunk_ids),\n                     json.dumps(ent.metadata), emb_str))\n            if ent_rows:\n                cur.executemany(\n                    """INSERT INTO entities (entity_id, name, normalized_name, type,\n                       aliases_json, chunk_ids_json, metadata, embedding)\n                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)\n                       ON CONFLICT (entity_id) DO UPDATE\n                       SET aliases_json = entities.aliases_json || EXCLUDED.aliases_json,\n                           chunk_ids_json = entities.chunk_ids_json || EXCLUDED.chunk_ids_json,\n                           updated_at = now()""",\n                    ent_rows)'
    ),
    # Links batch
    (
        '            for link in links:\n                cur.execute(\n                    """INSERT INTO event_entities (event_id, entity_id, role, confidence)\n                       VALUES (%s,%s,%s,%s)\n                       ON CONFLICT (event_id, entity_id) DO NOTHING""",\n                    (link.event_id, link.entity_id, link.role, link.confidence),\n                )',
        '            # Batch: executemany 替代循环 INSERT\n            link_rows = [(link.event_id, link.entity_id, link.role, link.confidence) for link in links]\n            if link_rows:\n                cur.executemany(\n                    """INSERT INTO event_entities (event_id, entity_id, role, confidence)\n                       VALUES (%s,%s,%s,%s)\n                       ON CONFLICT (event_id, entity_id) DO NOTHING""",\n                    link_rows)'
    ),
])

# ===== services/relation_builder.py - N+1 inserts =====
print('Fixing N+1 in src/services/relation_builder.py...')
fix_file('src/services/relation_builder.py', [
    (
        '                for r in relations:\n                    try:\n                        db.execute(\n                            "INSERT OR IGNORE INTO entity_relations (from_id, to_id, relation_type) VALUES (?, ?, ?)",\n                            (r["from_id"], r["to_id"], r["relation_type"])\n                        )\n                        count += 1\n                    except Exception as e:\n                        logger.warning(f"插入关系失败: {e}")',
        '                # Batch: executemany 替代循环 INSERT\n                rel_rows = [(r["from_id"], r["to_id"], r["relation_type"]) for r in relations]\n                if rel_rows:\n                    try:\n                        db.executemany(\n                            "INSERT OR IGNORE INTO entity_relations (from_id, to_id, relation_type) VALUES (?, ?, ?)",\n                            rel_rows\n                        )\n                        count = len(rel_rows)\n                    except Exception as e:\n                        logger.warning(f"批量插入关系失败: {e}")'
    ),
])

print('\nDone with remaining N+1 fixes!')
