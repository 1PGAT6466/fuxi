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
from functools import lru_cache
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
            except Exception:
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
                    except Exception:
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

    def _ensure_db(self):
        """确保数据库和表存在"""
        self._db_conn = sqlite3.connect(self._db_path, check_same_thread=False)
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
        self._db_conn.commit()
        # Migrate from JSON if needed
        self._maybe_migrate_json()

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
        except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
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

    # ===== QA Pairs (unchanged) =====
    def add_qa_pair(self, question: str, source_chunk_id: str, qa_index: int = 0):
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
        except Exception as e:
            logger.error(f"[MemoryStore] add_qa_pair failed: {e}")

    def search_qa_pairs(self, query: str, top_k: int = 3) -> list:
        """搜索 QA 对（简单 LIKE 匹配）"""
        try:
            rows = self._db_conn.execute(
                "SELECT question, source_chunk_id FROM qa_pairs WHERE question LIKE ? LIMIT ?",
                (f'%{query}%', top_k)
            ).fetchall()
            return [{"question": r[0], "source_chunk_id": r[1]} for r in rows]
        except Exception:
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
    def _inverted(self):
        """Compatibility: return empty dict (inverted index not needed for compat)"""
        return {}

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

    @property
    def _db_conn_public(self):
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
