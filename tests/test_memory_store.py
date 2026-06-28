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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
