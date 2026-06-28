"""
tests/test_skeleton.py — 🦴 骨骼单元测试 v4.1
"""
import asyncio
from unittest.mock import patch

import pytest

from src.hypothalamus.meridian import Meridian, Signal
from src.hypothalamus.organs.skeleton import SkeletonAgent


@pytest.fixture
def skeleton():
    m = Meridian()
    return SkeletonAgent(m)


class TestSkeletonInit:
    def test_creation(self, skeleton):
        assert skeleton.organ_id == "skeleton"

    def test_registered(self, skeleton):
        organ = skeleton.meridian.get_organ("skeleton")
        assert organ is not None
        assert "骨" in organ.name

    def test_initial_stats(self, skeleton):
        s = skeleton.stats()
        assert isinstance(s, dict)
        assert "entities" in s


class TestSkeletonQuery:
    @pytest.mark.asyncio
    async def test_query_success(self, skeleton):
        fake_result = {
            "entities": [{"name": "PA66", "type": "材料"}],
            "paths": [["PA66", "used_in", "连接器"]],
        }
        with patch(
            "src.services.graph_router.route_entity_with_neighbors",
            return_value=fake_result,
        ):
            result = await skeleton._query("PA66")
            assert result["entities"] == fake_result["entities"]
            assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_query_failure_graceful(self, skeleton):
        with patch(
            "src.services.graph_router.route_entity_with_neighbors",
            side_effect=Exception("graph broken"),
        ):
            result = await skeleton._query("PA66")
            assert result["error"]
            assert result["entities"] == []


class TestSkeletonBuild:
    @pytest.mark.asyncio
    async def test_extract_with_relations(self, skeleton):
        fake_relations = [{"entity_a": "A", "entity_b": "B", "relation": "test", "confidence": 0.8}]
        with patch(
            "src.services.relation_builder.extract_relations_cooccurrence",
            return_value=fake_relations,
        ):
            with patch.object(skeleton, "_save_relations", return_value=True):
                result = await skeleton._extract_relations([{"text": "test"}])
                assert result["ok"] is True
                assert result["relations"] == 1

    @pytest.mark.asyncio
    async def test_extract_empty(self, skeleton):
        with patch(
            "src.services.relation_builder.extract_relations_cooccurrence",
            return_value=[],
        ):
            result = await skeleton._extract_relations([{"text": "test"}])
            assert result["ok"] is True
            assert result["relations"] == 0


class TestSkeletonSaveRelations:
    def test_save_new_relations(self, skeleton):
        fake_graph = {"entities": {}, "edges": []}
        fake_rels = [{"entity_a": "X", "entity_b": "Y", "relation": "uses", "confidence": 0.9}]
        with patch("src.db.data_store.load_graph", return_value=fake_graph):
            with patch("src.db.data_store.save_graph") as mock_save:
                ok = skeleton._save_relations(fake_rels)
                assert ok is True
                mock_save.assert_called_once()
                saved_graph = mock_save.call_args[0][0]
                assert "X" in saved_graph["entities"]
                assert len(saved_graph["edges"]) == 1

    def test_save_duplicate_skipped(self, skeleton):
        fake_graph = {
            "entities": {"X": {}, "Y": {}},
            "edges": [{"source": "X", "target": "Y", "relation": "uses"}],
        }
        fake_rels = [{"entity_a": "X", "entity_b": "Y", "relation": "uses", "confidence": 0.9}]
        with patch("src.db.data_store.load_graph", return_value=fake_graph):
            with patch("src.db.data_store.save_graph") as mock_save:
                ok = skeleton._save_relations(fake_rels)
                assert ok is True
                mock_save.assert_not_called()  # 重复不保存


class TestSkeletonStats:
    def test_stats_with_graph(self, skeleton):
        fake_graph = {"entities": {"A": {}, "B": {}, "C": {}}, "edges": [{"source": "A", "target": "B", "relation": "test"}]}
        with patch("src.db.data_store.load_graph", return_value=fake_graph):
            s = skeleton.stats()
            assert s["entities"] == 3
            assert s["edges"] == 1


class TestSkeletonScanning:
    def test_scan_interval(self, skeleton):
        assert skeleton.SCAN_INTERVAL == 3600
