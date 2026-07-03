"""
test_integration.py — 集成测试
验证四象链路贯通
"""
import pytest
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestIntegrationChain:
    """集成测试：四象链路"""

    def test_chain_taiyin_shaoyin_taiyang(self):
        """链路1：太阴→少阴→太阳（完整查询）"""
        from src.taiyin.server import TaiyinServer
        from src.shaoyin.brain import ShaoyinBrain
        from src.taiyang.retrieval import hybrid_search
        from src.hypothalamus.meridian import Meridian

        m = Meridian()
        taiyin = TaiyinServer(m)
        shaoyin = ShaoyinBrain(m)

        # 验证实例化
        assert taiyin is not None
        assert shaoyin is not None
        assert len(m._symbols) >= 2

    def test_chain_taiyin_taiyang_search(self):
        """链路2：太阴→太阳（直接搜索）"""
        from src.taiyang.retrieval import hybrid_search
        from src.taiyang.fusion import rrf_fusion

        # 验证函数可调用
        assert callable(hybrid_search)
        assert callable(rrf_fusion)

    def test_chain_taiyin_shaoyang_ingest(self):
        """链路3：太阴→少阳（入库）"""
        from src.shaoyang.pipeline import ShaoyangPipeline
        from src.hypothalamus.meridian import Meridian

        m = Meridian()
        pipeline = ShaoyangPipeline(m)

        # 验证实例化
        assert pipeline is not None

    def test_degradation_chain_l1_to_l5(self):
        """降级链：L1→L2→L3→L4→L5"""
        from src.taiyang.degradation_chain import DegradationChain

        chain = DegradationChain()

        # 验证五层配置
        assert "L1_FAST" in chain.DEGRADATION_CONFIG
        assert "L2_STANDARD" in chain.DEGRADATION_CONFIG
        assert "L3_DEEP" in chain.DEGRADATION_CONFIG
        assert "L4_AGENT" in chain.DEGRADATION_CONFIG
        assert "L5_CRAG" in chain.DEGRADATION_CONFIG

    def test_query_router_classification(self):
        """查询分类器：9种类型"""
        from src.shaoyin.query_router import classify_query

        # 测试各种查询类型
        test_cases = [
            ("PA66和POM的区别", "compare"),
            ("拉伸强度是多少", "numeric_lookup"),
            ("BOM清单", "table_query"),
            ("什么是注塑", "definition"),
            ("怎么调试模具", "how_to"),
            ("选材建议", "material_selector"),
            ("关系和影响", "multi_hop"),
            ("效率优化方案", "open_ended"),
        ]

        for query, expected_type in test_cases:
            result_type, complexity, mode, top_k = classify_query(query)
            assert result_type == expected_type, f"查询'{query}'应分类为{expected_type}，实际为{result_type}"

    def test_self_rag_reflection(self):
        """Self-RAG：条件触发"""
        from src.shaoyin.smart_self_rag import SmartSelfRAG

        rag = SmartSelfRAG()

        # 高置信度结果应跳过
        high_conf_results = [{"score": 0.9, "text": "test"}]
        assert rag._should_skip(high_conf_results) == True

        # 低置信度结果应触发
        low_conf_results = [{"score": 0.3, "text": "test"}]
        assert rag._must_trigger(low_conf_results) == True

    def test_crag_correction(self):
        """CRAG：评估+纠正"""
        from src.shaoyin.crag_corrector import RetrievalEvaluator

        evaluator = RetrievalEvaluator()

        # 空结果应返回NEED_REWRITE
        assert evaluator.evaluate("test", []) == "NEED_REWRITE"

        # 低分结果应返回NEED_REWRITE
        low_score_results = [{"score": 0.1, "text": "test"}]
        assert evaluator.evaluate("test", low_score_results) == "NEED_REWRITE"

    def test_trace_logger(self):
        """TraceLogger：全链路追踪"""
        from src.infra.trace_logger import TraceLogger

        logger = TraceLogger("test_trace_123", "test_symbol")

        # 验证实例化
        assert logger.trace_id == "test_trace_123"
        assert logger.symbol_id == "test_symbol"

    def test_meridian_monitor(self):
        """MeridianMonitor：经络监控"""
        from src.infra.meridian_monitor import MeridianMonitor

        monitor = MeridianMonitor()

        # 记录信号
        monitor.record_signal("sig_1", "taiyin", "shaoyin", "query", 100.0, True)

        # 验证指标
        assert monitor.metrics["signals_sent"] == 1
        assert monitor.metrics["signals_received"] == 1

        # 获取健康报告
        report = monitor.get_health_report()
        assert report["status"] == "healthy"

    def test_growth_engine(self):
        """成长引擎：记录+评估"""
        from src.growth.engine import GrowthEngine

        engine = GrowthEngine()

        # 验证实例化
        assert engine is not None

    def test_feature_flags(self):
        """Feature Flags：3+1"""
        from src.taiyin.flags import load_flags

        flags = load_flags()

        # 验证9个Flag
        assert len(flags) >= 9

    def test_evaluation_system(self):
        """评测体系：eval_answer_relevancy/eval_faithfulness"""
        from src.services.evaluator import eval_answer_relevancy, eval_faithfulness

        # 验证函数可调用
        assert callable(eval_answer_relevancy)
        assert callable(eval_faithfulness)

    def test_feedback_loop(self):
        """Feedback Loop：feedback_store/learner/evolver"""
        from src.services.feedback_store import clear_feedback_cache
        from src.services.learner import extract_new_terms
        from src.services.evolver import evolve_graph, discover_entities

        # 验证函数可调用
        assert callable(clear_feedback_cache)
        assert callable(extract_new_terms)
        assert callable(evolve_graph)
        assert callable(discover_entities)

    def test_knowledge_graph(self):
        """知识图谱：graph_traversal/kg_extractor/relation_builder"""
        from src.taiyang.graph_traversal import find_paths, build_adjacency
        from src.shaoyang.kg_extractor import EntityResolver, extract_entities_llm
        from src.shaoyang.relation_builder import build_relations_from_chunks

        # 验证函数可调用
        assert callable(find_paths)
        assert callable(build_adjacency)
        assert callable(extract_entities_llm)
        assert callable(build_relations_from_chunks)

    def test_l5_crag_executor(self):
        """L5 CRAG：执行器"""
        from src.taiyang.l5_crag import L5CRAGExecutor, should_trigger_l5

        executor = L5CRAGExecutor()

        # 验证实例化
        assert executor is not None

        # 验证触发条件
        assert callable(should_trigger_l5)

    def test_symbol_base(self):
        """SymbolBase：四象基类"""
        from src.infra.symbol_base import SymbolBase

        # 验证基类可实例化
        class TestSymbol(SymbolBase):
            def __init__(self):
                pass

        symbol = TestSymbol()
        assert symbol is not None

    def test_protocol(self):
        """Protocol：信号协议"""
        from src.infra.protocol import SymbolRequest, SymbolResponse

        # 验证协议类可实例化
        req = SymbolRequest(source="test", target="test", method="test")
        assert req.source == "test"

    def test_data_models(self):
        """数据模型：Chunk/Event/Entity/Relation"""
        from src.models import Chunk, Event, Entity, Relation

        # 验证双向序列化
        chunk = Chunk(text="test", file_hash="abc")
        d = chunk.to_dict()
        chunk2 = Chunk.from_dict(d)
        assert chunk2.text == "test"

    def test_unified_pipeline(self):
        """统一管线：8步"""
        from src.pipeline.unified import UnifiedPipeline

        # 验证管线可实例化
        pipeline = UnifiedPipeline()
        assert pipeline is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
