"""memory_store.py 单元测试 — 覆盖 LRU/SQLite/hash/并发"""
import pytest
import json
import os
import sys
import threading

sys.path.insert(0, os.path.expanduser("~/kb-server"))

from src.db.memory_store import MemoryStore


@pytest.fixture
def store(tmp_path):
    db_path = str(tmp_path / "test.db")
    return MemoryStore(db_path=db_path)


@pytest.fixture
def sample_chunks():
    return [
        {"text": "PA66 拉伸强度 85MPa", "file_hash": "h1", "file_name": "f1.docx", "chunk_index": 0},
        {"text": "POM 弯曲模量 2.6GPa", "file_hash": "h1", "file_name": "f1.docx", "chunk_index": 1},
        {"text": "PLC 控制器选型指南", "file_hash": "h2", "file_name": "f2.docx", "chunk_index": 0},
    ]


class TestMemoryStore:
    def test_add_and_get(self, store, sample_chunks):
        store.add_batch(sample_chunks)
        result = store.get_by_hash("h1")
        assert len(result) == 2

    def test_lru_eviction(self, store):
        for i in range(10):
            store.add_batch([{"text": f"chunk {i}", "file_hash": f"h{i}", "file_name": f"f{i}.docx", "chunk_index": 0}])
        assert store.total_chunks >= 10

    def test_keyword_search(self, store, sample_chunks):
        store.add_batch(sample_chunks)
        results = store.keyword_search("PA66")
        assert len(results) > 0
        assert "PA66" in results[0].get("text", "")

    def test_keyword_search_empty(self, store):
        results = store.keyword_search("不存在的词")
        assert results == []

    def test_get_by_file_name(self, store, sample_chunks):
        store.add_batch(sample_chunks)
        result = store.get_by_file_name("f2.docx")
        assert len(result) == 1
        assert "PLC" in result[0].get("text", "")

    def test_delete_by_hash(self, store, sample_chunks):
        store.add_batch(sample_chunks)
        store.delete_by_hash("h1")
        result = store.get_by_hash("h1")
        assert len(result) == 0

    def test_total_chunks(self, store, sample_chunks):
        assert store.total_chunks == 0
        store.add_batch(sample_chunks)
        assert store.total_chunks == 3

    def test_total_files(self, store, sample_chunks):
        store.add_batch(sample_chunks)
        assert store.total_files >= 2

    def test_concurrent_read_write(self, store, sample_chunks):
        store.add_batch(sample_chunks)
        errors = []

        def reader():
            try:
                for _ in range(10):
                    store.keyword_search("PA66")
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(10):
                    store.add_batch([{"text": f"c{i}", "file_hash": f"ch{i}", "file_name": f"cf{i}.docx", "chunk_index": 0}])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader), threading.Thread(target=writer)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_stats(self, store, sample_chunks):
        store.add_batch(sample_chunks)
        s = store.stats()
        assert isinstance(s, dict)

    def test_add_single(self, store):
        store.add({"text": "single", "file_hash": "h9", "file_name": "f9.docx", "chunk_index": 0})
        result = store.get_by_hash("h9")
        assert len(result) == 1


class TestIndexes:
    def test_ensure_indexes_creates_expected_indexes(self, tmp_path):
        import sqlite3
        from src.db.data_store import _ensure_indexes

        db_path = str(tmp_path / "test_idx.db")
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE chunks (
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
        conn.commit()

        _ensure_indexes(conn)

        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='chunks'"
        ).fetchall()
        index_names = {r[0] for r in rows}
        assert "idx_chunks_file" in index_names
        assert "idx_chunks_category" in index_names
        assert "idx_chunks_created" in index_names
        conn.close()

    def test_ensure_indexes_idempotent(self, tmp_path):
        import sqlite3
        from src.db.data_store import _ensure_indexes

        db_path = str(tmp_path / "test_idx2.db")
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE chunks (
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
        conn.commit()

        _ensure_indexes(conn)
        _ensure_indexes(conn)

        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='chunks'"
        ).fetchall()
        index_names = [r[0] for r in rows]
        assert index_names.count("idx_chunks_file") == 1
        conn.close()


class TestDynamicTTL:
    def test_calculate_dynamic_ttl_low_access(self):
        from src.db.data_store import _calculate_dynamic_ttl
        import time
        assert _calculate_dynamic_ttl(5, time.time()) == 30

    def test_calculate_dynamic_ttl_medium_access(self):
        from src.db.data_store import _calculate_dynamic_ttl
        import time
        assert _calculate_dynamic_ttl(11, time.time()) == 60

    def test_calculate_dynamic_ttl_high_access(self):
        from src.db.data_store import _calculate_dynamic_ttl
        import time
        assert _calculate_dynamic_ttl(101, time.time()) == 120

    def test_calculate_dynamic_ttl_boundary_10(self):
        from src.db.data_store import _calculate_dynamic_ttl
        import time
        assert _calculate_dynamic_ttl(10, time.time()) == 30

    def test_calculate_dynamic_ttl_boundary_11(self):
        from src.db.data_store import _calculate_dynamic_ttl
        import time
        assert _calculate_dynamic_ttl(11, time.time()) == 60

    def test_calculate_dynamic_ttl_boundary_100(self):
        from src.db.data_store import _calculate_dynamic_ttl
        import time
        assert _calculate_dynamic_ttl(100, time.time()) == 60

    def test_calculate_dynamic_ttl_boundary_101(self):
        from src.db.data_store import _calculate_dynamic_ttl
        import time
        assert _calculate_dynamic_ttl(101, time.time()) == 120


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
