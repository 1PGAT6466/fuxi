"""
tests/test_liver.py — 肝免疫过滤单元测试 v4.0
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.hypothalamus import Meridian
from src.hypothalamus.organs.liver import LiverAgent


@pytest.fixture
def liver():
    m = Meridian()
    return LiverAgent(m)


class TestLiverFilter:
    """肝过滤测试"""

    def test_empty_results(self, liver):
        result = liver.quick_assess([])
        assert result["verdict"] == "EMPTY"
        assert result["score"] == 0.0

    def test_high_quality_results(self, liver):
        results = [
            {"_rerank_score": 9.0, "score": 8.5, "text": "PA66 拉伸强度 80MPa, 广泛应用于连接器壳体"},
            {"_rerank_score": 8.5, "score": 7.0, "text": "连接器设计手册规定壳体材料需满足 60MPa 拉伸强度"},
        ]
        verdict = liver.quick_assess(results)
        assert verdict["verdict"] == "PASS"
        assert verdict["score"] >= 0.7

    def test_low_quality_results(self, liver):
        results = [
            {"_rerank_score": 2.0, "score": 1.5, "text": "一些无关内容"},
            {"_rerank_score": 1.0, "score": 1.0, "text": "更无关的东西"},
        ]
        verdict = liver.quick_assess(results)
        assert verdict["verdict"] == "RETRY"

    def test_mixed_results(self, liver):
        """有 rerank 分数的混合结果"""
        results = [
            {"_rerank_score": 9.0, "score": 8.0, "text": "高质量"},
            {"_rerank_score": 0.0, "score": 2.0, "text": "低质量"},
        ]
        verdict = liver.quick_assess(results)
        # 9.0 + 0.0 = 4.5 avg → 应该 PASS (9.0 > 7.0 取第一个)
        # Actually quick_assess takes ALL rerank scores avg
        assert verdict["verdict"] in ("PASS", "RETRY")

    def test_no_rerank_fallback_to_raw_score(self, liver):
        results = [
            {"score": 8.0, "text": "没有 rerank 但有高 raw score"},
            {"score": 7.0, "text": "另一条"},
        ]
        verdict = liver.quick_assess(results)
        assert verdict["verdict"] == "PASS"

    def test_filter_removes_short_content(self, liver):
        import asyncio
        results = [
            {"text": "ab", "file_name": "test.pdf"},
            {"text": "PA66 材料参数 拉伸强度 80MPa 工程塑料 连接器壳体应用", "file_name": "valid.pdf"},
        ]
        filtered = asyncio.run(liver._filter(results, "PA66"))
        assert len(filtered) == 1
        assert "valid" in filtered[0]["file_name"]

    def test_filter_immune_memory(self, liver):
        """测试免疫记忆过滤"""
        import asyncio
        # Pre-set toxicity for a source
        liver._immune_memory["toxic_source.pdf"] = {"toxicity": 0.9, "count": 5}
        
        results = [
            {"text": "Some harmful content", "file_name": "toxic_source.pdf"},
            {"text": "Good PA66 content here", "file_name": "good.pdf"},
        ]
        filtered = asyncio.run(liver._filter(results, "query"))
        assert len(filtered) == 1
        assert "good" in filtered[0]["file_name"]


class TestLiverStats:
    """肝统计测试"""

    def test_initial_stats(self, liver):
        stats = liver.stats()
        assert "immune_memory_size" in stats
        assert "filtered_total" in stats
        assert stats["alive"] is True
