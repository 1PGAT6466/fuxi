"""Fix N+1 queries - batch script."""
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

# ===== taiyang/graph_router.py - N+1 wiki page lookup =====
print('Fixing N+1 in src/taiyang/graph_router.py...')

# Fix the first N+1 block (Phase 2)
fix_file('src/taiyang/graph_router.py', [
    (
        '''            conn = _sqlite.connect(wiki_db)
            for e in top:
                entity_name = e["entity"]
                cur = conn.execute(
                    "SELECT id, title FROM wiki_pages WHERE title LIKE ? OR content LIKE ? LIMIT 3",
                    ("%" + entity_name + "%", "%" + entity_name + "%")
                )
                rows = cur.fetchall()
                for row in rows:
                    wiki_links.append({
                        "entity": entity_name,
                        "wiki_id": row[0],
                        "wiki_title": row[1],
                        "auto_linked": True
                    })
            conn.close()''',
        '''            conn = _sqlite.connect(wiki_db)
            # Batch: 用单条 SQL 替代 N+1 循环查询
            entity_names = [e["entity"] for e in top]
            if entity_names:
                conditions = []
                params = []
                for name in entity_names:
                    conditions.append("(title LIKE ? OR content LIKE ?)")
                    params.extend([f"%{name}%", f"%{name}%"])
                sql = f"SELECT id, title FROM wiki_pages WHERE {' OR '.join(conditions)} LIMIT {len(entity_names) * 3}"
                cur = conn.execute(sql, params)
                # 建立 title -> entity_name 映射
                title_to_entity = {}
                for row in cur.fetchall():
                    row_title = (row[1] or "").lower()
                    for name in entity_names:
                        if name.lower() in row_title:
                            wiki_links.append({
                                "entity": name,
                                "wiki_id": row[0],
                                "wiki_title": row[1],
                                "auto_linked": True
                            })
                            break
            conn.close()'''
    ),
])

# Fix the second N+1 block (Wiki links query)
fix_file('src/taiyang/graph_router.py', [
    (
        '''        conn = sqlite3.connect(str(WORLDTREE_DB_PATH), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        for e in top:
            entity_name = e["entity"]
            cur = conn.execute(
                "SELECT id, title FROM wiki_pages WHERE title LIKE ? OR content LIKE ? LIMIT 3",
                (f"%{entity_name}%", f"%{entity_name}%")
            )
            for row in cur.fetchall():
                wiki_links.append({"entity": entity_name, "wiki_id": row[0], "wiki_title": row[1]})
        conn.close()''',
        '''        conn = sqlite3.connect(str(WORLDTREE_DB_PATH), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        # Batch: 用单条 SQL 替代 N+1 循环查询
        entity_names = [e["entity"] for e in top]
        if entity_names:
            conditions = []
            params = []
            for name in entity_names:
                conditions.append("(title LIKE ? OR content LIKE ?)")
                params.extend([f"%{name}%", f"%{name}%"])
            sql = f"SELECT id, title FROM wiki_pages WHERE {' OR '.join(conditions)} LIMIT {len(entity_names) * 3}"
            cur = conn.execute(sql, params)
            for row in cur.fetchall():
                row_title = (row[1] or "").lower()
                for name in entity_names:
                    if name.lower() in row_title:
                        wiki_links.append({"entity": name, "wiki_id": row[0], "wiki_title": row[1]})
                        break
        conn.close()'''
    ),
])

# ===== storage/write_proxy.py - N+1 inserts =====
print('Fixing N+1 in src/storage/write_proxy.py...')
# write_proxy uses PostgreSQL executemany-style patterns
# The current code does individual INSERT in loops - convert to executemany
fix_file('src/storage/write_proxy.py', [
    # Chunks - batch insert
    (
        '''            for c in chunks:
                emb_str = self._embedding_to_str(c.embedding) if c.embedding else None
                cur.execute(
                    """INSERT INTO chunks (chunk_id, document_id, document_name, content,
                        chunk_index, token_count, metadata, embedding)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (chunk_id) DO UPDATE SET content=EXCLUDED.content, updated_at=now()""",
                    (c.chunk_id, c.document_id, c.document_name, c.content,
                     c.chunk_index, c.token_count, json.dumps(c.metadata), emb_str),''',
        '''            # Batch: executemany 替代循环 INSERT
            chunk_rows = []
            for c in chunks:
                emb_str = self._embedding_to_str(c.embedding) if c.embedding else None
                chunk_rows.append((c.chunk_id, c.document_id, c.document_name, c.content,
                     c.chunk_index, c.token_count, json.dumps(c.metadata), emb_str))
            cur.executemany(
                """INSERT INTO chunks (chunk_id, document_id, document_name, content,
                    chunk_index, token_count, metadata, embedding)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (chunk_id) DO UPDATE SET content=EXCLUDED.content, updated_at=now()""",
                chunk_rows)'''
    ),
])

# ===== bagua/distiller.py - N+1 inserts =====
print('Fixing N+1 in src/bagua/distiller.py...')
fix_file('src/bagua/distiller.py', [
    # entities batch insert
    (
        '''        for e in result.get("entities",[]):
            name = e["name"].strip()
            if not name: continue
            eid = make_id("ent", name)
            conn.execute("INSERT OR IGNORE INTO entities (id,name,type,category_path,created_at) VALUES (?,?,?,?,?)",
                        (nid,name,e.get("type","concept"),path,now))''',
        '''        # Batch: executemany 替代循环 INSERT
        entity_rows = []
        for e in result.get("entities",[]):
            name = e["name"].strip()
            if not name: continue
            eid = make_id("ent", name)
            entity_rows.append((eid, name, e.get("type","concept"), path, now))
            emap[name] = eid
            stats["ent"] += 1
        if entity_rows:
            conn.executemany("INSERT OR IGNORE INTO entities (id,name,type,category_path,created_at) VALUES (?,?,?,?,?)", entity_rows)'''
    ),
])

# ===== services/distiller.py - N+1 inserts =====
print('Fixing N+1 in src/services/distiller.py...')
fix_file('src/services/distiller.py', [
    # terms batch insert
    (
        '''        for t in result.get("terms",[]):
            tn, td = t["term"].strip(), t.get("definition","").strip()
            if not tn or len(td)<8: continue
            tid = make_id("term", tn)
            conn.execute("INSERT OR IGNORE INTO terms (id,term,definition,category,created_at) VALUES (?,?,?,?,?)",
                        (tid,tn,td,path,now))''',
        '''        # Batch: executemany 替代循环 INSERT
        term_rows = []
        for t in result.get("terms",[]):
            tn, td = t["term"].strip(), t.get("definition","").strip()
            if not tn or len(td)<8: continue
            tid = make_id("term", tn)
            term_rows.append((tid, tn, td, path, now))
            tmap[tn] = tid
            stats["term"] += 1
        if term_rows:
            conn.executemany("INSERT OR IGNORE INTO terms (id,term,definition,category,created_at) VALUES (?,?,?,?,?)", term_rows)'''
    ),
])

# ===== taiyang/graph_traversal.py - N+1 inserts =====
print('Fixing N+1 in src/taiyang/graph_traversal.py...')
fix_file('src/taiyang/graph_traversal.py', [
    (
        '''    for e in edges:
        src = e.get("source", "")
        tgt = e.get("target", "")
        rel = e.get("relation", "related_to")
        if src and tgt:
            conn.execute(
                "INSERT OR IGNORE INTO graph_adjacency VALUES (?,?,?,?,1.0)",
                (src, tgt, rel, "out")
            )''',
        '''    # Batch: executemany 替代循环 INSERT
    adj_rows = []
    for e in edges:
        src = e.get("source", "")
        tgt = e.get("target", "")
        rel = e.get("relation", "related_to")
        if src and tgt:
            adj_rows.append((src, tgt, rel, "out", 1.0))
    if adj_rows:
        conn.executemany("INSERT OR IGNORE INTO graph_adjacency VALUES (?,?,?,?,1.0)", adj_rows)'''
    ),
])

# ===== services/relation_builder.py - N+1 inserts =====
print('Fixing N+1 in src/services/relation_builder.py...')
fix_file('src/services/relation_builder.py', [
    (
        '''                for r in relations:
                    try:
                        db.execute(
                            "INSERT OR IGNORE INTO entity_relations (from_id, to_id, relation_type) VALUES (?, ?, ?)",
                            (r["from_id"], r["to_id"], r["relation_type"])
                        )
                        count += 1
                    except Exception as e:
                        logger.warning(f"插入关系失败: {e}")''',
        '''                # Batch: executemany 替代循环 INSERT
                rel_rows = [(r["from_id"], r["to_id"], r["relation_type"]) for r in relations]
                if rel_rows:
                    db.executemany(
                        "INSERT OR IGNORE INTO entity_relations (from_id, to_id, relation_type) VALUES (?, ?, ?)",
                        rel_rows
                    )
                    count = len(rel_rows)'''
    ),
])

# ===== services/vector_store.py - N+1 metadata update =====
print('Fixing N+1 in src/services/vector_store.py...')
fix_file('src/services/vector_store.py', [
    (
        '''            for i, chunk_id in enumerate(ids):
                current_meta = metadatas[i] if i < len(metas) else {}
                updated_meta = {**current_meta, **metadata_updates}
                clean_meta = self._clean_metadata(updated_meta)

                self._collection.update(
                    ids=[chunk_id],
                    metadatas=[clean_meta],
                )''',
        '''            # Batch: 一次性更新所有 metadata
            batch_ids = []
            batch_metas = []
            for i, chunk_id in enumerate(ids):
                current_meta = metadatas[i] if i < len(metadatas) else {}
                updated_meta = {**current_meta, **metadata_updates}
                clean_meta = self._clean_metadata(updated_meta)
                batch_ids.append(chunk_id)
                batch_metas.append(clean_meta)
            if batch_ids:
                self._collection.update(ids=batch_ids, metadatas=batch_metas)'''
    ),
])

print('\nDone with N+1 fixes!')
