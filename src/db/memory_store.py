"""
memory_store.py — Phase 0 重构：SQLite 游标 + LRU 缓存
改动原则：
1. 不再全量加载到内存，查询直接走 SQLite
2. LRU 缓存热门查询结果，避免重复 SQL
3. 保持所有公开 API 接口不变，对调用方透明
"""
import sqlite3, json, os, logging
from pathlib import Path
from typing import List, Dict, Optional
from collections import OrderedDict
import threading

logger = logging.getLogger(__name__)

# 从 config 读取路径
from src.config import DATA_DIR

class MemoryStore:
    """v2.0: SQLite-backed store with LRU cache (no full memory load)"""

    def __init__(self, db_path: str = None):
        self._db_path = db_path or str(DATA_DIR / "chunks.db")
        # Auto-repair: if DB is malformed, recreate from backup
        from pathlib import Path
        db_file = Path(self._db_path)
        if db_file.exists():
            try:
                import sqlite3 as _sq
                _t = _sq.connect(self._db_path)
                _t.execute("SELECT COUNT(*) FROM chunks")
                _t.close()
            except Exception:  # TODO: Narrow exception type
                # DB corrupted, try to restore from .bak
                bak = db_file.with_suffix('.db.bak')
                if bak.exists():
                    try:
                        # Export from .bak to fresh DB
                        src = _sq.connect(str(bak))
                        rows = src.execute("SELECT * FROM chunks").fetchall()
                        schema = src.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='chunks'").fetchone()[0]
                        src.close()
                        new_path = str(db_file) + '.new'
                        dst = _sq.connect(new_path)
                        dst.execute(schema)
                        dst.executemany("INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?)", rows)
                        dst.commit()
                        dst.close()
                        os.replace(new_path, self._db_path)
                    except Exception:  # TODO: Narrow exception type
                        logger.debug("[suppressed] os.replace(new_path, self._db_")
                        pass
        self._db_conn = None
        self._ensure_db()
        # LRU cache for hash lookups (key=file_hash, value=list of chunks)
        self._cache_hash = OrderedDict()
        self._cache_name = OrderedDict()
        self._cache_max = 500  # max cached entries per cache
        self._lock = threading.Lock()
        # File metadata cache
        self._files_cache = None
        self._files_cache_time = 0
        # JSON parse cache: chunk_id → parsed dict
        self._json_cache: OrderedDict[str, tuple] = OrderedDict()
        self._json_cache_max = 500

    def _ensure_db(self):
        """确保数据库和表存在"""
        self._db_conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=10)
        self._db_conn.row_factory = sqlite3.Row  # L-11: 启用按名称访问
        self._db_conn.execute("PRAGMA journal_mode=WAL")
        self._db_conn.execute("PRAGMA synchronous=NORMAL")
        self._db_conn.execute("PRAGMA cache_size=-64000")  # 64MB SQLite cache
        self._db_conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc TEXT NOT NULL,
                file_hash TEXT,
                file_name TEXT,
                category TEXT,
                chunk_index INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                loader_path TEXT
            )
        """)
        self._db_conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(file_hash)")
        self._db_conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_name ON chunks(file_name)")
        self._db_conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_status ON chunks(status)")
        self._db_conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_category ON chunks(category)")
        self._db_conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_index ON chunks(file_hash, chunk_index)")

        # Phase A: 迁移旧 events/entities 表（若存在不兼容 schema 则重建）
        self._migrate_events_entities()

        # Phase A: events 表（SAG 事件索引）
        self._db_conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                chunk_id TEXT,
                title TEXT,
                summary TEXT,
                content TEXT,
                entities_json TEXT DEFAULT '[]',
                event_type TEXT DEFAULT '',
                keywords_json TEXT DEFAULT '[]',
                priority TEXT DEFAULT 'UNKNOWN',
                level INTEGER DEFAULT 1,
                chunk_ids_json TEXT DEFAULT '[]',
                entity_names_json TEXT DEFAULT '[]',
                parent_event_id TEXT DEFAULT '',
                file_hash TEXT DEFAULT '',
                file_name TEXT DEFAULT '',
                embedding BLOB,
                status TEXT DEFAULT 'active',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._db_conn.execute("CREATE INDEX IF NOT EXISTS idx_events_event_id ON events(event_id)")
        self._db_conn.execute("CREATE INDEX IF NOT EXISTS idx_events_chunk_id ON events(chunk_id)")
        self._db_conn.execute("CREATE INDEX IF NOT EXISTS idx_events_status ON events(status)")
        self._db_conn.execute("CREATE INDEX IF NOT EXISTS idx_events_file_hash ON events(file_hash)")
        self._db_conn.execute("CREATE INDEX IF NOT EXISTS idx_events_entity_names ON events(entity_names_json)")
        self._db_conn.execute("CREATE INDEX IF NOT EXISTS idx_events_title_search ON events(title)")

        # Phase A: entities 表（SAG 实体索引）
        self._db_conn.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                entity_type TEXT DEFAULT '',
                description TEXT DEFAULT '',
                aliases_json TEXT DEFAULT '[]',
                chunk_ids_json TEXT DEFAULT '[]',
                event_ids_json TEXT DEFAULT '[]',
                source TEXT DEFAULT 'sag_extractor',
                file_hash TEXT DEFAULT '',
                file_name TEXT DEFAULT '',
                embedding BLOB,
                mentions INTEGER DEFAULT 1,
                status TEXT DEFAULT 'active',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._db_conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_entity_id ON entities(entity_id)")
        self._db_conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name)")
        self._db_conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type)")
        self._db_conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_status ON entities(status)")

        self._db_conn.commit()
        # Migrate from JSON if needed
        self._maybe_migrate_json()

    def _migrate_events_entities(self):
        """Phase A: 检测旧 events/entities 表 schema 并迁移

        旧 schema 缺少 id, chunk_id, entity_type, status, embedding, timestamp 等列。
        若列不匹配则 DROP 旧表并重建。
        """
        try:
            existing = self._db_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('events', 'entities')"
            ).fetchall()
            existing_names = [r[0] for r in existing]
            if not existing_names:
                return  # 无旧表，无需迁移

            # 安全修复 (CWE-89): 白名单验证表名（防止SQL注入）
            ALLOWED_TABLES = {'events', 'entities'}
            for table_name in existing_names:
                if table_name not in ALLOWED_TABLES:
                    logger.warning(f"[MemoryStore] 跳过未知表: {table_name}")
                    continue
                cols = self._db_conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
                col_names = [c[1] for c in cols]

                # 检查是否需要迁移（缺少新字段）
                if table_name == 'events':
                    needed = {'id', 'chunk_id', 'embedding', 'status', 'timestamp'}
                    missing = needed - set(col_names)
                    if missing:
                        logger.info(f"[MemoryStore] 检测到旧 events 表 schema，缺少: {missing}，准备迁移...")
                        self._db_conn.execute("DROP TABLE IF EXISTS events")
                        # 也要删旧索引
                        self._db_conn.execute("DROP INDEX IF EXISTS idx_events_event_id")
                        self._db_conn.execute("DROP INDEX IF EXISTS idx_events_chunk_id")
                        self._db_conn.execute("DROP INDEX IF EXISTS idx_events_status")
                        self._db_conn.execute("DROP INDEX IF EXISTS idx_events_file_hash")

                elif table_name == 'entities':
                    needed = {'id', 'entity_type', 'aliases_json', 'chunk_ids_json', 'source', 'embedding', 'status', 'timestamp'}
                    missing = needed - set(col_names)
                    if missing:
                        logger.info(f"[MemoryStore] 检测到旧 entities 表 schema，缺少: {missing}，准备迁移...")
                        self._db_conn.execute("DROP TABLE IF EXISTS entities")
                        self._db_conn.execute("DROP INDEX IF EXISTS idx_entities_entity_id")
                        self._db_conn.execute("DROP INDEX IF EXISTS idx_entities_name")
                        self._db_conn.execute("DROP INDEX IF EXISTS idx_entities_type")
                        self._db_conn.execute("DROP INDEX IF EXISTS idx_entities_status")

            self._db_conn.commit()
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[MemoryStore] 迁移 events/entities 表失败: {e}")

    def _maybe_migrate_json(self):
        """从旧 JSON 文件迁移数据"""
        json_path = DATA_DIR / "chunks.json"
        if not json_path.exists():
            return
        if self._count_rows() > 0:
            return
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                chunks = json.load(f)
            if not chunks:
                return
            rows = []
            for c in chunks:
                rows.append((
                    json.dumps(c, ensure_ascii=False),
                    c.get("file_hash", ""),
                    c.get("file_name", ""),
                    c.get("category", ""),
                    c.get("chunk_index", 0),
                    "active",
                    c.get("created_at", ""),
                    "",
                ))
            with self._db_conn:
                self._db_conn.executemany(
                    "INSERT INTO chunks (doc, file_hash, file_name, category, chunk_index, status, created_at, loader_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    rows
                )
            self._db_conn.commit()
            logger.info(f"[MemoryStore] Migrated {len(rows)} chunks from JSON")
        except Exception as e:  # TODO: Narrow exception type
            logger.error(f"[MemoryStore] JSON migration failed: {e}")

    def _count_rows(self) -> int:
        return self._db_conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    def _row_to_chunk(self, row) -> dict:
        """Convert a DB row (id, doc_json) to chunk dict"""
        row_id, doc_json = row
        c = json.loads(doc_json) if isinstance(doc_json, str) else doc_json
        c["_db_id"] = row_id
        return c

    # ===== Cache helpers =====
    def _cache_get(self, cache: OrderedDict, key: str) -> Optional[list]:
        with self._lock:
            if key in cache:
                cache.move_to_end(key)
                return cache[key]
        return None

    def _cache_put(self, cache: OrderedDict, key: str, value: list):
        with self._lock:
            cache[key] = value
            cache.move_to_end(key)
            while len(cache) > self._cache_max:
                cache.popitem(last=False)

    def _invalidate_cache(self, key: str = None, file_hash: str = None):
        """Invalidate cache entries"""
        with self._lock:
            if file_hash:
                self._cache_hash.pop(file_hash, None)
            if key:
                self._cache_name.pop(key, None)

    # ===== Public API (unchanged interface) =====

    def hierarchical_search(self, query: str, category: str = "", file_type: str = "",
                            date_from: str = "", date_to: str = "",
                            summary_top_k: int = 5, chunk_top_k: int = 15) -> list:
        """Hierarchical search: SQLite-based keyword search with category filtering"""
        import re, json as _json
        terms = [t.strip() for t in re.split(r'[\s,，。、]+', query.lower()) if len(t.strip()) >= 1]
        if not terms:
            terms = [query.lower()]
        conditions = ["status = 'active'"]
        params = []
        if category:
            conditions.append("category = ?")
            params.append(category)
        like_conditions = []
        for term in terms[:5]:
            like_conditions.append("LOWER(doc) LIKE ?")
            params.append(f"%{term}%")
        if like_conditions:
            conditions.append("(" + " OR ".join(like_conditions) + ")")
        where = " AND ".join(conditions)
        sql = f"SELECT id, doc FROM chunks WHERE {where} LIMIT ?"
        params.append(chunk_top_k)
        try:
            rows = self._db_conn.execute(sql, params).fetchall()
            results = []
            for row_id, doc_json in rows:
                c = _json.loads(doc_json) if isinstance(doc_json, str) else doc_json
                c["_db_id"] = row_id
                text = (c.get("text", "") or "").lower()
                score = sum(1.0 for t in terms if t in text)
                c["score"] = round(score, 2)
                results.append(c)
            return results
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[MemoryStore] hierarchical_search failed: {e}")
            return []


    def keyword_search(self, query: str, top_k: int = 20) -> list:
        """Simple keyword search via SQLite LIKE on chunk text"""
        import re
        terms = [t.strip() for t in re.split(r'[\s,，。、]+', query.lower()) if len(t.strip()) >= 1]
        if not terms:
            return []
        conditions = ["status = 'active'"]
        params = []
        like_parts = []
        for term in terms[:5]:
            like_parts.append("LOWER(doc) LIKE ?")
            params.append(f"%{term}%")
        conditions.append("(" + " OR ".join(like_parts) + ")")
        where = " AND ".join(conditions)
        sql = f"SELECT id, doc FROM chunks WHERE {where} LIMIT ?"
        params.append(top_k * 3)
        try:
            rows = self._db_conn.execute(sql, params).fetchall()
            results = []
            for row_id, doc_json in rows:
                c = json.loads(doc_json) if isinstance(doc_json, str) else doc_json
                c["_db_id"] = row_id
                text = (c.get("text", "") or "").lower()
                score = sum(1.0 for t in terms if t in text)
                c["score"] = round(score, 2)
                if score > 0:
                    results.append(c)
            results.sort(key=lambda x: x.get("score", 0), reverse=True)
            return results[:top_k]
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[MemoryStore] keyword_search failed: {e}")
            return []

    def get_all(self, limit: int = None, offset: int = 0) -> List[Dict]:
        """返回 chunk 列表（直接走 SQLite，不加载到内存）"""
        if limit is not None:
            rows = self._db_conn.execute(
                "SELECT id, doc FROM chunks WHERE status='active' ORDER BY id LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
        else:
            rows = self._db_conn.execute(
                "SELECT id, doc FROM chunks WHERE status='active' ORDER BY id"
            ).fetchall()
        return [self._row_to_chunk(r) for r in rows]

    @property
    def total_chunks(self) -> int:
        return self._db_conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE status='active'"
        ).fetchone()[0]

    @property
    def total_files(self) -> int:
        return self._db_conn.execute(
            "SELECT COUNT(DISTINCT file_hash) FROM chunks WHERE status='active'"
        ).fetchone()[0]

    def get_by_hash(self, file_hash: str) -> List[Dict]:
        """按 hash 查询 chunks（带 LRU 缓存）"""
        cached = self._cache_get(self._cache_hash, file_hash)
        if cached is not None:
            return cached

        # Try exact match first
        rows = self._db_conn.execute(
            "SELECT id, doc FROM chunks WHERE file_hash=? AND status='active' ORDER BY chunk_index",
            (file_hash,)
        ).fetchall()

        # Try short hash prefix if no exact match
        if not rows and len(file_hash) > 16:
            short = file_hash[:16]
            rows = self._db_conn.execute(
                "SELECT id, doc FROM chunks WHERE file_hash LIKE ? AND status='active' ORDER BY chunk_index",
                (short + '%',)
            ).fetchall()

        result = [self._row_to_chunk(r) for r in rows]
        self._cache_put(self._cache_hash, file_hash, result)
        return result

    def get_by_file_name(self, file_name: str) -> List[Dict]:
        """按文件名查询 chunks（带 LRU 缓存）"""
        cached = self._cache_get(self._cache_name, file_name)
        if cached is not None:
            return cached

        rows = self._db_conn.execute(
            "SELECT id, doc FROM chunks WHERE file_name=? AND status='active' ORDER BY chunk_index",
            (file_name,)
        ).fetchall()

        result = [self._row_to_chunk(r) for r in rows]
        self._cache_put(self._cache_name, file_name, result)
        return result

    def delete_by_hash(self, file_hash: str) -> int:
        """删除指定 file_hash 的所有 chunk"""
        with self._db_conn:
            cur = self._db_conn.execute(
                "UPDATE chunks SET status='deleted' WHERE file_hash=? AND status='active'",
                (file_hash,)
            )
            deleted = cur.rowcount
        self._invalidate_cache(file_hash=file_hash)
        self._files_cache = None
        return deleted

    def invalidate_by_name(self, file_name: str) -> int:
        """按文件名标记删除"""
        with self._db_conn:
            cur = self._db_conn.execute(
                "UPDATE chunks SET status='deleted' WHERE file_name=? AND status='active'",
                (file_name,)
            )
            invalidated = cur.rowcount
        self._invalidate_cache(key=file_name)
        self._files_cache = None
        return invalidated

    def add(self, chunk: dict) -> int:
        """添加单个 chunk"""
        with self._db_conn:
            cur = self._db_conn.execute(
                "INSERT INTO chunks (doc, file_hash, file_name, category, chunk_index, status, created_at, loader_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    json.dumps(chunk, ensure_ascii=False),
                    chunk.get("file_hash", ""),
                    chunk.get("file_name", ""),
                    chunk.get("category", ""),
                    chunk.get("chunk_index", 0),
                    "active",
                    chunk.get("created_at", ""),
                    chunk.get("loader_path", ""),
                )
            )
            return cur.lastrowid

    def add_batch(self, chunks: list) -> int:
        """批量添加 chunks"""
        rows = []
        for c in chunks:
            rows.append((
                json.dumps(c, ensure_ascii=False),
                c.get("file_hash", ""),
                c.get("file_name", ""),
                c.get("category", ""),
                c.get("chunk_index", 0),
                "active",
                c.get("created_at", ""),
                c.get("loader_path", ""),
            ))
        with self._db_conn:
            self._db_conn.executemany(
                "INSERT INTO chunks (doc, file_hash, file_name, category, chunk_index, status, created_at, loader_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                rows
            )
        return len(rows)

    # ===== v1.50 兼容别名 =====
    def insert_many(self, chunks: list) -> int:
        """兼容别名 → add_batch()"""
        return self.add_batch(chunks)

    def add_document(self, doc: dict) -> int:
        """兼容别名 → add()"""
        return self.add(doc)

    def get_files_summary(self) -> List[Dict]:
        """获取文件摘要（带缓存）"""
        if self._files_cache is not None:
            return self._files_cache

        rows = self._db_conn.execute("""
            SELECT file_hash, file_name, category,
                   COUNT(*) as chunk_count,
                   MIN(created_at) as created_at
            FROM chunks WHERE status='active'
            GROUP BY file_hash
            ORDER BY created_at DESC
        """).fetchall()

        result = []
        for r in rows:
            result.append({
                "file_hash": r[0],
                "file_name": r[1],
                "category": r[2],
                "chunk_count": r[3],
                "created_at": r[4],
            })
        self._files_cache = result
        return result

    # ===== Phase A: Events & Entities CRUD =====

    def add_event(self, event_data: dict) -> int:
        """添加单个 event"""
        import json as _json
        # 将 embedding (List[float]) 序列化为 BLOB
        embedding_blob = None
        if event_data.get("embedding"):
            import struct
            emb = event_data["embedding"]
            if isinstance(emb, list) and len(emb) > 0:
                try:
                    embedding_blob = struct.pack(f'{len(emb)}f', *emb)
                except Exception:  # TODO: Narrow exception type
                    embedding_blob = _json.dumps(emb).encode('utf-8')

        with self._db_conn:
            cur = self._db_conn.execute(
                """INSERT OR REPLACE INTO events
                   (event_id, chunk_id, title, summary, content, entities_json, event_type,
                    keywords_json, priority, level, chunk_ids_json, entity_names_json,
                    parent_event_id, file_hash, file_name, embedding, status, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (
                    event_data.get("event_id", f"evt_{int(__import__('time').time()*1000)}_{id(event_data)}"),
                    event_data.get("chunk_id", ""),
                    event_data.get("title", ""),
                    event_data.get("summary", ""),
                    event_data.get("content", ""),
                    _json.dumps(event_data.get("entities", []), ensure_ascii=False),
                    event_data.get("event_type", ""),
                    _json.dumps(event_data.get("keywords", []), ensure_ascii=False),
                    event_data.get("priority", "UNKNOWN"),
                    event_data.get("level", 1),
                    _json.dumps(event_data.get("chunk_ids", []), ensure_ascii=False),
                    _json.dumps(event_data.get("entity_names", []), ensure_ascii=False),
                    event_data.get("parent_event_id", ""),
                    event_data.get("file_hash", ""),
                    event_data.get("file_name", ""),
                    embedding_blob,
                    event_data.get("status", "active"),
                )
            )
            return cur.lastrowid

    def add_entity(self, entity_data: dict) -> int:
        """添加单个 entity"""
        import json as _json
        with self._db_conn:
            cur = self._db_conn.execute(
                """INSERT OR REPLACE INTO entities
                   (entity_id, name, entity_type, description, aliases_json, chunk_ids_json,
                    event_ids_json, source, file_hash, file_name, embedding, mentions, status, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (
                    entity_data.get("entity_id", f"ent_{int(__import__('time').time()*1000)}_{id(entity_data)}"),
                    entity_data.get("name", ""),
                    entity_data.get("entity_type", "") or entity_data.get("type", ""),
                    entity_data.get("description", ""),
                    _json.dumps(entity_data.get("aliases", []), ensure_ascii=False),
                    _json.dumps(entity_data.get("chunk_ids", []), ensure_ascii=False),
                    _json.dumps(entity_data.get("event_ids", []), ensure_ascii=False),
                    entity_data.get("source", "sag_extractor"),
                    entity_data.get("file_hash", ""),
                    entity_data.get("file_name", ""),
                    None,  # embedding placeholder for Phase A task 3
                    entity_data.get("mentions", 1),
                    entity_data.get("status", "active"),
                )
            )
            return cur.lastrowid

    def get_events_by_chunk_id(self, chunk_id: str) -> list:
        """按 chunk_id 查询 events"""
        try:
            rows = self._db_conn.execute(
                "SELECT * FROM events WHERE chunk_id=? AND status='active'",
                (chunk_id,)
            ).fetchall()
            cols = [desc[0] for desc in self._db_conn.execute(
                "SELECT * FROM events LIMIT 0"
            ).description]
            return [dict(zip(cols, row)) for row in rows]
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[MemoryStore] get_events_by_chunk_id failed: {e}")
            return []

    def get_entities_by_name(self, name: str) -> list:
        """按名称查询 entities"""
        try:
            rows = self._db_conn.execute(
                "SELECT * FROM entities WHERE name=? AND status='active'",
                (name,)
            ).fetchall()
            cols = [desc[0] for desc in self._db_conn.execute(
                "SELECT * FROM entities LIMIT 0"
            ).description]
            return [dict(zip(cols, row)) for row in rows]
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[MemoryStore] get_entities_by_name failed: {e}")
            return []

    def get_entity_count(self) -> int:
        """返回活跃 entity 总数"""
        try:
            return self._db_conn.execute(
                "SELECT COUNT(*) FROM entities WHERE status='active'"
            ).fetchone()[0]
        except Exception:  # TODO: Narrow exception type
            return 0

    def get_event_count(self) -> int:
        """返回活跃 event 总数"""
        try:
            return self._db_conn.execute(
                "SELECT COUNT(*) FROM events WHERE status='active'"
            ).fetchone()[0]
        except Exception:  # TODO: Narrow exception type
            return 0

    def get_chunks_batch(self, chunk_ids: List[str]) -> Dict[str, dict]:
        """批量获取 chunk（避免 N+1 查询）

        FIX-02, FIX-05: 一次 IN 查询 + JSON 解析缓存

        Returns:
            {chunk_id: parsed_chunk_dict, ...}
        """
        if not chunk_ids:
            return {}

        result = {}
        missing_ids = []

        # 先查 JSON 缓存
        for cid in chunk_ids:
            cached = self._json_cache.get(cid)
            if cached is not None:
                result[cid] = cached
            else:
                missing_ids.append(cid)

        if not missing_ids:
            return result

        # 批量查询缺失的 chunk
        try:
            placeholders = ",".join("?" * len(missing_ids))
            # 用 json_extract 匹配 chunk_id 和 id 字段
            conditions = []
            params = []
            for cid in missing_ids:
                conditions.append("(json_extract(doc, '$.chunk_id') = ? OR json_extract(doc, '$.id') = ?)")
                params.extend([cid, cid])

            sql = f"SELECT id, doc FROM chunks WHERE ({' OR '.join(conditions)}) AND status='active'"
            rows = self._db_conn.execute(sql, params).fetchall()

            for row_id, doc_json in rows:
                c = json.loads(doc_json) if isinstance(doc_json, str) else doc_json
                cid_from_doc = c.get("chunk_id") or c.get("id", "")
                result[cid_from_doc] = c
                # 也以传入的 cid 为 key 缓存
                for orig_cid in missing_ids:
                    if orig_cid and (orig_cid in str(cid_from_doc) or cid_from_doc in str(orig_cid)):
                        self._json_cache_put(orig_cid, c)
                        break
                # 缓存
                self._json_cache_put(str(cid_from_doc), c)
        except Exception as e:  # TODO: Narrow exception type
            logger.debug(f"[MemoryStore] get_chunks_batch failed: {e}")

        return result

    def _json_cache_put(self, key: str, value: dict):
        """写入 JSON 解析缓存"""
        if len(self._json_cache) >= self._json_cache_max:
            self._json_cache.popitem(last=False)
        self._json_cache[key] = value
        self._json_cache.move_to_end(key)

    def get_all_events(self, limit: int = None, offset: int = 0) -> list:
        """获取 event 列表"""
        try:
            cols = [desc[0] for desc in self._db_conn.execute(
                "SELECT * FROM events LIMIT 0"
            ).description]
            if limit is not None:
                rows = self._db_conn.execute(
                    "SELECT * FROM events WHERE status='active' ORDER BY id LIMIT ? OFFSET ?",
                    (limit, offset)
                ).fetchall()
            else:
                rows = self._db_conn.execute(
                    "SELECT * FROM events WHERE status='active' ORDER BY id"
                ).fetchall()
            return [dict(zip(cols, row)) for row in rows]
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[MemoryStore] get_all_events failed: {e}")
            return []

    def get_all_entities(self, limit: int = None, offset: int = 0) -> list:
        """获取 entity 列表"""
        try:
            cols = [desc[0] for desc in self._db_conn.execute(
                "SELECT * FROM entities LIMIT 0"
            ).description]
            if limit is not None:
                rows = self._db_conn.execute(
                    "SELECT * FROM entities WHERE status='active' ORDER BY id LIMIT ? OFFSET ?",
                    (limit, offset)
                ).fetchall()
            else:
                rows = self._db_conn.execute(
                    "SELECT * FROM entities WHERE status='active' ORDER BY id"
                ).fetchall()
            return [dict(zip(cols, row)) for row in rows]
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[MemoryStore] get_all_entities failed: {e}")
            return []

    # ===== QA Pairs (unchanged) =====
    def add_qa_pair(self, question: str, source_chunk_id: str, qa_index: int = 0) -> None:
        """添加 QA 对"""
        try:
            self._db_conn.execute("""
                CREATE TABLE IF NOT EXISTS qa_pairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    source_chunk_id TEXT,
                    qa_index INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self._db_conn.execute(
                "INSERT INTO qa_pairs (question, source_chunk_id, qa_index) VALUES (?, ?, ?)",
                (question, source_chunk_id, qa_index)
            )
            self._db_conn.commit()
        except Exception as e:  # TODO: Narrow exception type
            logger.error(f"[MemoryStore] add_qa_pair failed: {e}")

    def search_qa_pairs(self, query: str, top_k: int = 3) -> list:
        """搜索 QA 对（简单 LIKE 匹配）"""
        try:
            rows = self._db_conn.execute(
                "SELECT question, source_chunk_id FROM qa_pairs WHERE question LIKE ? LIMIT ?",
                (f'%{query}%', top_k)
            ).fetchall()
            return [{"question": r[0], "source_chunk_id": r[1]} for r in rows]
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[MemoryStore] search_qa_pairs failed: {e}")
            return []

    # ===== Compatibility aliases =====
    @property
    def _chunks(self):
        """Compatibility: return all chunks as list (USE SPARINGLY, loads all)"""
        logger.warning("[MemoryStore] _chunks property called - this loads all data! Use get_all(limit=) instead.")
        return self.get_all()

    @property
    def _by_hash(self):
        """Compatibility: return hash index (USE SPARINGLY)"""
        logger.warning("[MemoryStore] _by_hash property called - use get_by_hash() instead.")
        result = {}
        rows = self._db_conn.execute(
            "SELECT file_hash, id, doc FROM chunks WHERE status='active' ORDER BY file_hash, chunk_index"
        ).fetchall()
        for fh, row_id, doc_json in rows:
            c = json.loads(doc_json) if isinstance(doc_json, str) else doc_json
            c["_db_id"] = row_id
            result.setdefault(fh, []).append(c)
        return result

    @property
    def _files(self):
        """Compatibility: return files dict"""
        result = {}
        for f in self.get_files_summary():
            result[f["file_hash"]] = f
        return result

    @property
    # DEPRECATED: 未使用，v1.50 标记待删除
    def _inverted(self):
        """Compatibility: return empty dict (inverted index not needed for compat)"""
        return {}

    # DEPRECATED: 未使用，v1.50 标记待删除
    @property
    def _loaded(self):
        """Compatibility: always True (no loading phase needed)"""
        return True

    def _load(self):
        """Compatibility: no-op (data is in SQLite)"""
        pass

    def stats(self) -> dict:
        """Return store statistics"""
        return {
            "total_chunks": self.total_chunks,
            "total_files": self.total_files,
        }
# DEPRECATED: 未使用，v1.50 标记待删除

    @property
    def _db_conn_public(self):
        # DEPRECATED: 未使用，v1.50 标记待删除
        """Compatibility alias"""
        return self._db_conn

    def _save_to_db(self, row_id: int, c: dict):
        """Update a chunk in DB"""
        with self._db_conn:
            self._db_conn.execute(
                "UPDATE chunks SET doc=?, file_hash=?, file_name=?, category=?, chunk_index=?, status=?, loader_path=? WHERE id=?",
                (
                    json.dumps(c, ensure_ascii=False),
                    c.get("file_hash", ""),
                    c.get("file_name", ""),
                    c.get("category", ""),
                    c.get("chunk_index", 0),
                    c.get("status", "active"),
                    c.get("loader_path", ""),
                    row_id,
                )
            )

# Singleton
_store: Optional[MemoryStore] = None

def get_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store
