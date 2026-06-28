"""
tests/test_kidney.py — 肾数据精炼单元测试 v4.1
"""
import pytest
import asyncio
import sys, os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.hypothalamus.meridian import Meridian, Signal
from src.hypothalamus.organs.kidney import KidneyAgent


@pytest.fixture
def kidney():
    m = Meridian()
    return KidneyAgent(m)


class TestKidneyScoring:
    def test_high_access_score(self, kidney):
        chunk = {
            "text": "PA66 拉伸强度 80MPa",
            "access_count": 15,
            "created_at": "2026-06-01T00:00:00Z",
        }
        score = kidney._score_chunk(chunk)
        assert score >= 0.8

    def test_zero_access_penalty(self, kidney):
        chunk = {
            "text": "旧数据",
            "access_count": 0,
            "created_at": "2025-01-01T00:00:00Z",
        }
        score = kidney._score_chunk(chunk)
        assert score < 0.5

    def test_empty_text_penalty(self, kidney):
        chunk = {
            "text": "",
            "access_count": 5,
            "created_at": "2026-06-01T00:00:00Z",
        }
        score = kidney._score_chunk(chunk)
        assert score <= 0.4

    def test_normal_chunk(self, kidney):
        chunk = {
            "text": "正常测试",
            "access_count": 5,
            "created_at": "2026-05-01T00:00:00Z",
        }
        score = kidney._score_chunk(chunk)
        assert 0.4 <= score <= 1.0


class TestKidneyFilter:
    def test_filter_empty(self, kidney):
        with patch("src.db.data_store.load_chunks", return_value=[]):
            result = asyncio.run(kidney._filter_blood())
            assert result["chunks"] == 0
            assert result["essence"] == 0

    def test_filter_with_chunks(self, kidney):
        fake = [
            {"file_hash": "abc", "text": "精华", "access_count": 20, "created_at": "2026-06-01T00:00:00Z"},
            {"file_hash": "def", "text": "废物", "access_count": 0, "created_at": "2025-01-01T00:00:00Z"},
        ]
        # _load_access_counts 从空磁盘返回 {}，会覆写 access_count 为 0
        # 但 created_at + 文本完整性仍能给出合理分
        with patch("src.db.data_store.load_chunks", return_value=fake):
            with patch.object(kidney, "_load_access_counts", return_value={"abc": 20, "def": 0}):
                result = asyncio.run(kidney._filter_blood())
                assert result["total_chunks"] == 2
                assert result["essence"] >= 1

    def test_filter_triggers_purge_on_overflow(self, kidney):
        fake = [{"file_hash": f"h{i}", "text": "x", "access_count": 0, "created_at": "2025-01-01T00:00:00Z"} for i in range(9000)]
        with patch("src.db.data_store.load_chunks", return_value=fake):
            with patch.object(kidney, "_purge_waste", return_value={"purged": 100}) as mock_purge:
                asyncio.run(kidney._filter_blood())
                mock_purge.assert_called_once()


class TestKidneyPurge:
    def test_purge_marked_as_waste(self, kidney):
        import time
        old_ts = time.time() - 40 * 86400  # 40 days ago
        fake = [{
            "file_hash": "old1",
            "text": "旧数据",
            "last_accessed": old_ts,
        }]
        with patch("src.db.data_store.load_chunks", return_value=fake):
            with patch("src.db.data_store.save_chunks") as mock_save:
                result = asyncio.run(kidney._purge_waste())
                assert result["purged"] >= 1
                mock_save.assert_called_once()  # 确实保存了（删除了废物）


class TestKidneyDeficiency:
    def test_deficiency_with_category(self, kidney):
        fake = [{"category": "材料", "text": "x"}] * 10 + [{"category": "电气", "text": "x"}] * 2
        with patch("src.db.data_store.load_chunks", return_value=fake):
            result = asyncio.run(kidney._detect_deficiency())
            assert isinstance(result, dict)
            assert "weak_areas" in result

    def test_deficiency_empty_chunks(self, kidney):
        with patch("src.db.data_store.load_chunks", return_value=[]):
            result = asyncio.run(kidney._detect_deficiency())


class TestKidneyStats:
    def test_initial_stats(self, kidney):
        s = kidney.stats()
        assert s["filter_count"] == 0
        assert s["purged_total"] == 0

    def test_running_flag(self, kidney):
        assert kidney._running is False
