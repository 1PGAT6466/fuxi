"""
test_core_modules.py — 核心模块测试
测试四象核心功能
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestQueryRouter:
    """查询分类器测试"""

    def test_classify_numeric(self):
        from src.shaoyin.query_router import classify_query
        qtype, complexity, mode, top_k = classify_query("PA66拉伸强度是多少")
        assert qtype == "numeric_lookup"
        assert mode == "L1_FAST"

    def test_classify_compare(self):
        from src.shaoyin.query_router import classify_query
        qtype, complexity, mode, top_k = classify_query("PA66和POM的区别")
        assert qtype == "compare"
        assert mode == "L2_STANDARD"

    def test_classify_definition(self):
        from src.shaoyin.query_router import classify_query
        qtype, complexity, mode, top_k = classify_query("什么是注塑")
        assert qtype == "definition"
        assert mode == "L1_FAST"

    def test_classify_how_to(self):
        from src.shaoyin.query_router import classify_query
        qtype, complexity, mode, top_k = classify_query("怎么调试模具")
        assert qtype == "how_to"
        assert mode == "L2_STANDARD"


class TestSmartSelfRAG:
    """Self-RAG测试"""

    def test_should_skip_high_score(self):
        from src.shaoyin.smart_self_rag import SmartSelfRAG
        rag = SmartSelfRAG()
        results = [{"score": 0.9, "text": "test"}]
        assert rag._should_skip(results) == True

    def test_must_trigger_low_score(self):
        from src.shaoyin.smart_self_rag import SmartSelfRAG
        rag = SmartSelfRAG()
        results = [{"score": 0.3, "text": "test"}]
        assert rag._must_trigger(results) == True

    def test_numeric_query_detection(self):
        from src.shaoyin.smart_self_rag import SmartSelfRAG
        rag = SmartSelfRAG()
        assert rag._is_numeric_query("拉伸强度是多少") == True
        assert rag._is_numeric_query("今天天气怎么样") == False


class TestCRAGCorrector:
    """CRAG纠正器测试"""

    def test_evaluate_empty(self):
        from src.shaoyin.crag_corrector import RetrievalEvaluator
        evaluator = RetrievalEvaluator()
        assert evaluator.evaluate("test", []) == "NEED_REWRITE"

    def test_evaluate_low_score(self):
        from src.shaoyin.crag_corrector import RetrievalEvaluator
        evaluator = RetrievalEvaluator()
        results = [{"score": 0.1, "text": "test"}]
        assert evaluator.evaluate("test", results) == "NEED_REWRITE"


class TestDegradationChain:
    """降级链测试"""

    def test_five_layers(self):
        from src.taiyang.degradation_chain import DegradationChain
        chain = DegradationChain()
        assert len(chain.DEGRADATION_CONFIG) == 5
        assert "L1_FAST" in chain.DEGRADATION_CONFIG
        assert "L2_STANDARD" in chain.DEGRADATION_CONFIG
        assert "L3_DEEP" in chain.DEGRADATION_CONFIG
        assert "L4_AGENT" in chain.DEGRADATION_CONFIG
        assert "L5_CRAG" in chain.DEGRADATION_CONFIG


class TestL5CRAG:
    """L5 CRAG测试"""

    def test_config(self):
        from src.taiyang.l5_crag import L5_CRAG_CONFIG
        assert len(L5_CRAG_CONFIG["conditions"]) == 4
        assert L5_CRAG_CONFIG["execution"]["max_retries"] == 2


class TestTraceLogger:
    """TraceLogger测试"""

    def test_init(self):
        from src.infra.trace_logger import TraceLogger
        logger = TraceLogger("test_trace", "test_symbol")
        assert logger.trace_id == "test_trace"
        assert logger.symbol_id == "test_symbol"


class TestMeridianMonitor:
    """MeridianMonitor测试"""

    def test_record_signal(self):
        from src.infra.meridian_monitor import MeridianMonitor
        monitor = MeridianMonitor()
        monitor.record_signal("sig1", "taiyin", "shaoyin", "query", 100.0, True)
        assert monitor.metrics["signals_sent"] == 1
        assert monitor.metrics["signals_received"] == 1

    def test_health_report(self):
        from src.infra.meridian_monitor import MeridianMonitor
        monitor = MeridianMonitor()
        report = monitor.get_health_report()
        assert "status" in report
        assert "metrics" in report


class TestGrowthEngine:
    """成长引擎测试"""

    def test_init(self):
        from src.growth.engine import GrowthEngine
        engine = GrowthEngine()
        assert engine is not None


class TestSignalProtocol:
    """信号协议测试"""

    def test_signal_types(self):
        from src.infra.protocol import SignalType
        assert len(SignalType) > 10

    def test_signal_creation(self):
        from src.infra.protocol import Signal
        signal = Signal(source="taiyin", target="shaoyin", signal_type="query")
        assert signal.source == "taiyin"
        assert signal.target == "shaoyin"


class TestFeatureFlags:
    """Feature Flags测试"""

    def test_load_flags(self):
        from src.taiyin.flags import load_flags
        flags = load_flags()
        assert len(flags) >= 9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
