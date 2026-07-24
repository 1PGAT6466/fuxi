"""
test_integration_deep.py — 深度集成测试
测试端到端链路
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDeepIntegration:
    """深度集成测试"""

    def test_taiyin_init(self):
        """测试太阴初始化"""
        from src.hypothalamus import Meridian
        from src.taiyin.server import TaiyinServer

        m = Meridian()
        taiyin = TaiyinServer(m)
        assert taiyin is not None
        assert taiyin.symbol_id == "taiyin"

    def test_degradation_chain_config(self):
        """测试降级链配置"""
        from src.taiyang.degradation_chain import DegradationChain

        chain = DegradationChain()
        assert len(chain.DEGRADATION_CONFIG) == 5
        assert "L1_FAST" in chain.DEGRADATION_CONFIG
        assert "L5_CRAG" in chain.DEGRADATION_CONFIG

    def test_self_rag_config(self):
        """测试Self-RAG配置"""
        from src.shaoyin.smart_self_rag import SmartSelfRAG, NUMERIC_PATTERNS

        rag = SmartSelfRAG()
        assert len(NUMERIC_PATTERNS) > 10

    def test_crag_init(self):
        """测试CRAG初始化"""
        from src.shaoyin.crag_corrector import CRAGCorrector

        crag = CRAGCorrector()
        assert crag is not None

    def test_growth_recorder_init(self):
        """测试成长记录器初始化"""
        from src.growth.growth_recorder import GrowthRecordPoints

        recorder = GrowthRecordPoints()
        assert recorder is not None

    def test_mcp_protocol(self):
        """测试MCP协议"""
        from src.taiyin.mcp_protocol import get_mcp_server

        server = get_mcp_server()
        assert len(server.tools) >= 20  # v1.50 R4: tools expanded to 24
        assert len(server.resources) == 3

    def test_eval_automation_init(self):
        """测试评测自动化初始化"""
        from src.services.eval_automation import get_eval_automation

        automation = get_eval_automation()
        assert automation is not None

    def test_query_router_integration(self):
        """测试查询分类器集成"""
        from src.shaoyin.query_router import classify_query

        test_cases = [
            ("PA66拉伸强度", "numeric_lookup"),
            ("PA66和POM的区别", "compare"),
            ("什么是注塑", "definition"),
            ("怎么调试模具", "how_to"),
        ]

        for query, expected_type in test_cases:
            qtype, complexity, mode, top_k = classify_query(query)
            assert qtype == expected_type, f"查询'{query}'应分类为{expected_type}，实际为{qtype}"

    def test_signal_protocol_integration(self):
        """测试信号协议集成"""
        from src.infra.protocol import Signal, SignalType, SIGNAL_TIMEOUT

        signal = Signal(
            source="taiyin",
            target="shaoyin",
            signal_type="query",
            payload={"query": "test"},
        )
        assert signal.source == "taiyin"
        assert signal.target == "shaoyin"
        assert signal.signal_type == "query"

        assert "query" in SIGNAL_TIMEOUT
        assert "search" in SIGNAL_TIMEOUT

    def test_trace_logger(self):
        """测试TraceLogger"""
        from src.infra.trace_logger import TraceLogger

        logger = TraceLogger("test_trace", "test_symbol")
        assert logger.trace_id == "test_trace"
        assert logger.symbol_id == "test_symbol"

    def test_meridian_monitor(self):
        """测试MeridianMonitor"""
        from src.infra.meridian_monitor import MeridianMonitor

        monitor = MeridianMonitor()
        monitor.record_signal("sig1", "taiyin", "shaoyin", "query", 100.0, True)
        assert monitor.metrics["signals_sent"] == 1

    def test_feature_flags(self):
        """测试Feature Flags"""
        from src.services.feature_flags import load_flags

        flags = load_flags()
        assert len(flags) >= 9

    def test_data_models(self):
        """测试数据模型"""
        from src.models import Chunk, Event, Entity, Relation

        chunk = Chunk(text="test", file_hash="abc")
        d = chunk.to_dict()
        chunk2 = Chunk.from_dict(d)
        assert chunk2.text == "test"

    def test_unified_pipeline(self):
        """测试统一管线"""
        from src.pipeline.unified import UnifiedPipeline

        pipeline = UnifiedPipeline()
        assert pipeline is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
