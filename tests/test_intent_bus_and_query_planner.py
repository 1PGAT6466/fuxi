"""
test_intent_bus_and_query_planner.py — 统一5层路由 & 乾卦意图循环 单元测试

测试范围:
  - IntentBus: 意图分类、路由派发、意图循环、循环守卫、预加载缓存
  - QueryPlanner: 复杂度分析、查询规划、5层路由执行、结果融合、升级判定

运行方式:
  cd E:\easyclaw\伏羲-v1.44\repo
  python -m pytest tests/test_intent_bus_and_query_planner.py -v --tb=short
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

# Test Data
SIMPLE_QUERY = "什么是 VLAN"
MEDIUM_QUERY = "VLAN 和 VPN 的区别是什么"
COMPLEX_QUERY = "分析 VLAN 10 的配置对网络性能的影响"
GREETING_QUERY = "你好"
UPLOAD_QUERY = "上传这份文档"

# ============================================================================
# IntentBus Tests
# ============================================================================


class TestIntentBusClassify:
    """意图分类测试"""

    def test_preload_cache_greeting(self):
        """预加载缓存：问候语 → PRESENT"""
        from src.services.intent_bus import IntentBus, RAGIntent
        bus = IntentBus()

        async def _test():
            decision = await bus.classify_intent(GREETING_QUERY, use_llm=False)
            assert decision.intent == RAGIntent.PRESENT
            assert decision.confidence > 0.8
            assert "缓存" in decision.reasoning

        asyncio.run(_test())

    def test_preload_cache_search_prefix(self):
        """预加载缓存：前缀通配 '搜索*' → SEARCH"""
        from src.services.intent_bus import IntentBus, RAGIntent
        bus = IntentBus()

        async def _test():
            decision = await bus.classify_intent("搜索VLAN配置", use_llm=False)
            assert decision.intent == RAGIntent.SEARCH
            assert decision.confidence > 0.8

        asyncio.run(_test())

    def test_rule_based_upload(self):
        """正则规则：上传模式 → DIGEST"""
        from src.services.intent_bus import _rule_based_classify, RAGIntent
        decision = _rule_based_classify(UPLOAD_QUERY)
        assert decision is not None
        assert decision.intent == RAGIntent.DIGEST
        assert decision.confidence >= 0.8

    def test_rule_based_refine(self):
        """正则规则：对比模式 → REFINE"""
        from src.services.intent_bus import _rule_based_classify, RAGIntent
        decision = _rule_based_classify("VLAN 和 VPN 的区别")
        assert decision is not None
        assert decision.intent == RAGIntent.REFINE

    def test_default_fallback_to_search(self):
        """默认降级：未知查询 → SEARCH"""
        from src.services.intent_bus import IntentBus, RAGIntent
        bus = IntentBus()

        async def _test():
            decision = await bus.classify_intent("某种复杂的专业知识查询", use_llm=False)
            assert decision.intent == RAGIntent.SEARCH
            assert decision.confidence > 0.5

        asyncio.run(_test())

    def test_cache_hit(self):
        """缓存命中：相同查询第二次从缓存返回"""
        from src.services.intent_bus import IntentBus
        bus = IntentBus()

        async def _test():
            d1 = await bus.classify_intent("某种复杂的专业知识查询", use_llm=False)
            d2 = await bus.classify_intent("某种复杂的专业知识查询", use_llm=False)
            assert d1.intent == d2.intent
            assert bus._cache_hits >= 1

        asyncio.run(_test())


class TestIntentBusCycleGuard:
    """循环守卫测试"""

    def test_no_search_no_done(self):
        """未检索前禁止 DONE"""
        from src.services.intent_bus import IntentBus, IntentDecision, RAGIntent
        bus = IntentBus()
        bus._reset_cycle("测试问题")
        decision = IntentDecision(intent=RAGIntent.DONE, confidence=0.9, reasoning="测试")
        guard_result = bus._cycle_guard(decision)
        assert guard_result is not None
        assert guard_result.intent == RAGIntent.SEARCH
        assert "未检索" in guard_result.reasoning

    def test_consecutive_limit(self):
        """同意图连续超限 → 降级"""
        from src.services.intent_bus import IntentBus, IntentDecision, RAGIntent
        bus = IntentBus()
        bus._reset_cycle("测试")
        bus._last_intent = RAGIntent.SEARCH
        bus._consecutive_count = 3
        bus._searched = True
        decision = IntentDecision(intent=RAGIntent.SEARCH, confidence=0.8)
        guard_result = bus._cycle_guard(decision)
        assert guard_result is not None
        assert guard_result.intent != RAGIntent.SEARCH
        assert "连续超限" in guard_result.reasoning

    def test_round_limit_force_present(self):
        """接近轮数上限 → 强制 PRESENT"""
        from src.services.intent_bus import IntentBus, IntentDecision, RAGIntent
        bus = IntentBus()
        bus._reset_cycle("测试")
        bus._round_count = 7
        bus._searched = True
        decision = IntentDecision(intent=RAGIntent.SEARCH, confidence=0.9)
        guard_result = bus._cycle_guard(decision)
        assert guard_result is not None
        assert guard_result.intent == RAGIntent.PRESENT
        assert "收束" in guard_result.reasoning

    def test_done_low_confidence_downgrade(self):
        """DONE 置信度不足 → 降级 PRESENT"""
        from src.services.intent_bus import IntentBus, IntentDecision, RAGIntent
        bus = IntentBus()
        bus._reset_cycle("测试")
        bus._searched = True
        decision = IntentDecision(intent=RAGIntent.DONE, confidence=0.5)
        guard_result = bus._cycle_guard(decision)
        assert guard_result is not None
        assert guard_result.intent == RAGIntent.PRESENT
        assert "置信度不足" in guard_result.reasoning


class TestIntentBusDispatch:
    """意图路由派发测试"""

    def test_register_and_dispatch(self):
        """注册处理器并派发意图"""
        from src.services.intent_bus import IntentBus, IntentDecision, RAGIntent
        bus = IntentBus()
        mock_handler = AsyncMock(return_value={"result": "ok", "summary": "搜索完成"})
        bus.register_handler(RAGIntent.SEARCH, mock_handler)

        async def _test():
            decision = IntentDecision(intent=RAGIntent.SEARCH, confidence=0.9)
            result = await bus.dispatch(decision, SIMPLE_QUERY)
            assert result["intent"] == "SEARCH"
            assert result.get("summary") == "搜索完成"
            mock_handler.assert_called_once()

        asyncio.run(_test())

    def test_dispatch_no_handler(self):
        """无注册处理器 → 跳过"""
        from src.services.intent_bus import IntentBus, IntentDecision, RAGIntent
        bus = IntentBus()

        async def _test():
            decision = IntentDecision(intent=RAGIntent.DONE, confidence=0.9)
            result = await bus.dispatch(decision, SIMPLE_QUERY)
            assert result["intent"] == "DONE"
            assert result.get("skipped") is True

        asyncio.run(_test())

    def test_handler_error_isolation(self):
        """处理器异常不影响其他处理器"""
        from src.services.intent_bus import IntentBus, IntentDecision, RAGIntent
        bus = IntentBus()
        bad_handler = AsyncMock(side_effect=RuntimeError("模拟错误"))
        good_handler = AsyncMock(return_value={"summary": "成功"})
        bus.register_handler(RAGIntent.SEARCH, bad_handler)
        bus.register_handler(RAGIntent.SEARCH, good_handler)

        async def _test():
            decision = IntentDecision(intent=RAGIntent.SEARCH, confidence=0.9)
            result = await bus.dispatch(decision, SIMPLE_QUERY)
            assert result.get("summary") == "成功"
            assert "_error" in result

        asyncio.run(_test())


class TestIntentBusLoop:
    """完整意图循环测试"""

    def test_run_intent_loop(self):
        """执行完整意图循环"""
        from src.services.intent_bus import IntentBus, RAGIntent
        bus = IntentBus()
        search_handler = AsyncMock(return_value={"results": [{"text": "VLAN是..."}], "summary": "检索到1条"})
        refine_handler = AsyncMock(return_value={"results": [{"text": "VLAN是..."}], "summary": "精炼后1条"})
        present_handler = AsyncMock(return_value={"answer": "VLAN是虚拟局域网", "summary": "回答已生成"})
        bus.register_handler(RAGIntent.SEARCH, search_handler)
        bus.register_handler(RAGIntent.REFINE, refine_handler)
        bus.register_handler(RAGIntent.PRESENT, present_handler)

        async def _test():
            result = await bus.run_intent_loop(SIMPLE_QUERY)
            assert "intent_trace" in result
            assert len(result["intent_trace"]) > 0
            assert result["rounds"] > 0
            assert result["session_id"] == bus.session_id

        asyncio.run(_test())

    def test_intent_trace_records(self):
        """意图历史记录正确"""
        from src.services.intent_bus import IntentBus
        bus = IntentBus()

        async def _test():
            result = await bus.run_intent_loop(SIMPLE_QUERY)
            trace = result["intent_trace"]
            for record in trace:
                assert "step" in record
                assert "intent" in record
                assert "confidence" in record
                assert "reasoning" in record
                assert "latency_ms" in record
            assert trace[-1]["intent"] in ("PRESENT", "DONE")

        asyncio.run(_test())


class TestIntentBusFactory:
    """工厂函数测试"""

    def test_create_default_intent_bus(self):
        """create_default_intent_bus 正确注册默认处理器"""
        from src.services.intent_bus import create_default_intent_bus, RAGIntent
        bus = create_default_intent_bus("test-session")
        assert bus.session_id == "test-session"
        assert RAGIntent.SEARCH in bus._handlers
        assert RAGIntent.REFINE in bus._handlers
        assert RAGIntent.PRESENT in bus._handlers
        assert RAGIntent.DIGEST not in bus._handlers

    def test_stats(self):
        """统计信息正确"""
        from src.services.intent_bus import IntentBus
        bus = IntentBus()

        async def _test():
            await bus.classify_intent("查询A", use_llm=False)
            await bus.classify_intent("查询B", use_llm=False)
            stats = bus.stats
            assert "cache_hits" in stats
            assert "cache_misses" in stats
            assert "cache_size" in stats

        asyncio.run(_test())


# ============================================================================
# QueryPlanner Tests
# ============================================================================


class TestQueryComplexity:
    """查询复杂度分析测试"""

    def test_simple_query(self):
        from src.services.query_planner import analyze_query_complexity, QueryComplexity
        complexity, confidence = analyze_query_complexity(SIMPLE_QUERY)
        assert complexity == QueryComplexity.SIMPLE
        assert confidence > 0.8

    def test_medium_query_comparison(self):
        from src.services.query_planner import analyze_query_complexity, QueryComplexity
        complexity, confidence = analyze_query_complexity(MEDIUM_QUERY)
        assert complexity == QueryComplexity.MEDIUM
        assert confidence > 0.7

    def test_medium_query_how_to(self):
        from src.services.query_planner import analyze_query_complexity, QueryComplexity
        complexity, _ = analyze_query_complexity("如何配置交换机端口")
        assert complexity == QueryComplexity.MEDIUM

    def test_complex_query_analysis(self):
        from src.services.query_planner import analyze_query_complexity, QueryComplexity
        complexity, confidence = analyze_query_complexity(COMPLEX_QUERY)
        assert complexity == QueryComplexity.COMPLEX
        assert confidence > 0.8

    def test_complex_query_causal(self):
        from src.services.query_planner import analyze_query_complexity, QueryComplexity
        complexity, _ = analyze_query_complexity("为什么 VLAN 10 的网络延迟这么高")
        assert complexity == QueryComplexity.COMPLEX

    def test_complex_query_hypothetical(self):
        from src.services.query_planner import analyze_query_complexity, QueryComplexity
        complexity, _ = analyze_query_complexity("如果增加带宽，对网络性能有什么影响")
        assert complexity == QueryComplexity.COMPLEX

    def test_empty_query(self):
        from src.services.query_planner import analyze_query_complexity, QueryComplexity
        complexity, _ = analyze_query_complexity("  ")
        assert complexity == QueryComplexity.SIMPLE

    def test_long_query_at_least_medium(self):
        from src.services.query_planner import analyze_query_complexity, QueryComplexity
        long_query = "这是一个非常长的查询" * 10
        complexity, _ = analyze_query_complexity(long_query)
        assert complexity != QueryComplexity.SIMPLE


class TestQueryPlan:
    """查询规划测试"""

    def test_simple_plan_strategy(self):
        from src.services.query_planner import QueryPlanner, QueryComplexity
        planner = QueryPlanner()

        async def _test():
            plan = await planner.plan(SIMPLE_QUERY, force_complexity=QueryComplexity.SIMPLE)
            assert plan.complexity == QueryComplexity.SIMPLE
            assert plan.strategy.value == "direct"
            assert len(plan.steps) == 2
            assert plan.steps[0].level.value == 1
            assert plan.steps[1].level.value == 2

        asyncio.run(_test())

    def test_medium_plan_strategy(self):
        from src.services.query_planner import QueryPlanner, QueryComplexity
        planner = QueryPlanner()

        async def _test():
            plan = await planner.plan(MEDIUM_QUERY, force_complexity=QueryComplexity.MEDIUM)
            assert plan.complexity == QueryComplexity.MEDIUM
            assert plan.strategy.value == "cascade"
            assert len(plan.steps) == 4
            levels = [s.level.value for s in plan.steps]
            assert 3 in levels

        asyncio.run(_test())

    def test_complex_plan_strategy(self):
        from src.services.query_planner import QueryPlanner, QueryComplexity
        planner = QueryPlanner()

        async def _test():
            plan = await planner.plan(COMPLEX_QUERY, force_complexity=QueryComplexity.COMPLEX)
            assert plan.complexity == QueryComplexity.COMPLEX
            assert plan.strategy.value == "full"
            assert len(plan.steps) == 5
            levels = [s.level.value for s in plan.steps]
            assert 4 in levels

        asyncio.run(_test())

    def test_fusion_strategy_selection(self):
        from src.services.query_planner import QueryPlanner, QueryComplexity
        planner = QueryPlanner()

        async def _test():
            s_plan = await planner.plan(SIMPLE_QUERY, force_complexity=QueryComplexity.SIMPLE)
            assert s_plan.fusion_strategy == "none"
            m_plan = await planner.plan(MEDIUM_QUERY, force_complexity=QueryComplexity.MEDIUM)
            assert m_plan.fusion_strategy == "rrf"
            c_plan = await planner.plan(COMPLEX_QUERY, force_complexity=QueryComplexity.COMPLEX)
            assert c_plan.fusion_strategy == "weighted"

        asyncio.run(_test())

    def test_step_dependencies(self):
        from src.services.query_planner import QueryPlanner, QueryComplexity
        planner = QueryPlanner()

        async def _test():
            plan = await planner.plan(COMPLEX_QUERY, force_complexity=QueryComplexity.COMPLEX)
            for step in plan.steps:
                for dep_id in step.dependencies:
                    assert dep_id < step.step_id

        asyncio.run(_test())

    def test_auto_complexity_detection(self):
        """自动复杂度检测（不强制指定）"""
        from src.services.query_planner import QueryPlanner, QueryComplexity
        planner = QueryPlanner()

        async def _test():
            plan = await planner.plan(SIMPLE_QUERY)
            assert plan.complexity == QueryComplexity.SIMPLE
            assert plan.strategy.value == "direct"

        asyncio.run(_test())


class TestQueryPlannerExecute:
    """查询执行测试"""

    @patch("src.services.query_planner.QueryPlanner._execute_l1_cache")
    @patch("src.services.query_planner.QueryPlanner._execute_l2_vector")
    @patch("src.services.query_planner.QueryPlanner._execute_l5_generate")
    def test_execute_simple_plan(self, mock_l5, mock_l2, mock_l1):
        from src.services.query_planner import QueryPlanner, QueryComplexity, LayerResult, RouteLevel

        mock_l1.return_value = LayerResult(level=RouteLevel.L1_CACHE, source="cache", results=[], confidence=0.0)
        mock_l2.return_value = LayerResult(
            level=RouteLevel.L2_VECTOR, source="vector",
            results=[{"text": "VLAN 是...", "score": 8.0, "file_hash": "abc"}],
            confidence=0.8,
        )
        mock_l5.return_value = LayerResult(
            level=RouteLevel.L5_GENERATE, source="generate",
            results=[{"answer": "VLAN 是虚拟局域网"}],
            confidence=0.85,
        )

        planner = QueryPlanner()

        async def _test():
            plan = await planner.plan(SIMPLE_QUERY, force_complexity=QueryComplexity.SIMPLE)
            result = await planner.execute(plan)
            assert "results" in result
            assert "layer_results" in result
            assert "meta" in result
            assert result["meta"]["complexity"] == "simple"
            assert result["meta"]["strategy"] == "direct"

        asyncio.run(_test())

    @patch("src.services.query_planner.QueryPlanner._execute_l1_cache")
    @patch("src.services.query_planner.QueryPlanner._execute_l2_vector")
    @patch("src.services.query_planner.QueryPlanner._execute_l3_graph")
    @patch("src.services.query_planner.QueryPlanner._execute_l5_generate")
    def test_execute_medium_plan(self, mock_l5, mock_l3, mock_l2, mock_l1):
        from src.services.query_planner import QueryPlanner, QueryComplexity, LayerResult, RouteLevel

        mock_l1.return_value = LayerResult(level=RouteLevel.L1_CACHE, source="cache", results=[], confidence=0.0)
        mock_l2.return_value = LayerResult(
            level=RouteLevel.L2_VECTOR, source="vector",
            results=[{"text": "VLAN...", "score": 7.0, "file_hash": "x"}],
            confidence=0.7,
        )
        mock_l3.return_value = LayerResult(
            level=RouteLevel.L3_GRAPH, source="graph",
            results=[{"text": "VLAN...", "score": 7.0, "file_hash": "x", "_source": "graph"}],
            confidence=0.6,
        )
        mock_l5.return_value = LayerResult(
            level=RouteLevel.L5_GENERATE, source="generate",
            results=[{"answer": "VLAN 是..."}],
            confidence=0.85,
        )

        planner = QueryPlanner()

        async def _test():
            plan = await planner.plan(MEDIUM_QUERY, force_complexity=QueryComplexity.MEDIUM)
            result = await planner.execute(plan)
            assert result["meta"]["complexity"] == "medium"
            layer_levels = [lr["level"] for lr in result["layer_results"]]
            assert 3 in layer_levels

        asyncio.run(_test())

    @patch("src.services.query_planner.QueryPlanner._execute_l1_cache")
    @patch("src.services.query_planner.QueryPlanner._execute_l2_vector")
    @patch("src.services.query_planner.QueryPlanner._execute_l3_graph")
    @patch("src.services.query_planner.QueryPlanner._execute_l4_reason")
    @patch("src.services.query_planner.QueryPlanner._execute_l5_generate")
    def test_execute_complex_plan_all_layers(self, mock_l5, mock_l4, mock_l3, mock_l2, mock_l1):
        from src.services.query_planner import QueryPlanner, QueryComplexity, LayerResult, RouteLevel

        mock_l1.return_value = LayerResult(level=RouteLevel.L1_CACHE, source="cache", results=[], confidence=0.0)
        mock_l2.return_value = LayerResult(
            level=RouteLevel.L2_VECTOR, source="vector",
            results=[{"text": "chunk", "score": 5.0, "file_hash": "h"}],
            confidence=0.5,
        )
        mock_l3.return_value = LayerResult(
            level=RouteLevel.L3_GRAPH, source="graph",
            results=[{"text": "chunk", "score": 5.0, "file_hash": "h"}],
            confidence=0.6,
        )
        mock_l4.return_value = LayerResult(
            level=RouteLevel.L4_REASON, source="reason",
            results=[{"text": "chunk", "score": 5.0, "file_hash": "h"}],
            confidence=0.7,
        )
        mock_l5.return_value = LayerResult(
            level=RouteLevel.L5_GENERATE, source="generate",
            results=[{"answer": "分析结果"}],
            confidence=0.85,
        )

        planner = QueryPlanner()

        async def _test():
            plan = await planner.plan(COMPLEX_QUERY, force_complexity=QueryComplexity.COMPLEX)
            result = await planner.execute(plan)
            assert result["meta"]["complexity"] == "complex"
            assert result["meta"]["strategy"] == "full"
            layer_levels = [lr["level"] for lr in result["layer_results"]]
            assert 4 in layer_levels
            assert 5 in layer_levels

        asyncio.run(_test())


class TestUpgradeLogic:
    """升级判定逻辑测试"""

    def test_cache_hit_no_upgrade(self):
        from src.services.query_planner import (
            QueryPlanner, QueryComplexity, LayerResult, RouteLevel, QueryPlan,
            PlanStep, RouteStrategy,
        )
        planner = QueryPlanner()
        plan = QueryPlan(query=SIMPLE_QUERY, complexity=QueryComplexity.SIMPLE, strategy=RouteStrategy.DIRECT, steps=[])
        l1_result = LayerResult(level=RouteLevel.L1_CACHE, source="cache", results=[{"text": "缓存结果"}], confidence=0.95)
        l2_step = PlanStep(2, RouteLevel.L2_VECTOR, SIMPLE_QUERY, "vector_retrieve", "向量检索")
        should_upgrade = planner._should_upgrade(l2_step, [l1_result], plan)
        assert should_upgrade is False

    def test_cache_miss_upgrade(self):
        from src.services.query_planner import (
            QueryPlanner, QueryComplexity, LayerResult, RouteLevel, QueryPlan,
            PlanStep, RouteStrategy,
        )
        planner = QueryPlanner()
        plan = QueryPlan(query=SIMPLE_QUERY, complexity=QueryComplexity.SIMPLE, strategy=RouteStrategy.DIRECT, steps=[])
        l1_result = LayerResult(level=RouteLevel.L1_CACHE, source="cache", results=[], confidence=0.0)
        l2_step = PlanStep(2, RouteLevel.L2_VECTOR, SIMPLE_QUERY, "vector_retrieve", "向量检索")
        should_upgrade = planner._should_upgrade(l2_step, [l1_result], plan)
        assert should_upgrade is True

    def test_low_confidence_upgrade(self):
        from src.services.query_planner import (
            QueryPlanner, QueryComplexity, LayerResult, RouteLevel, QueryPlan,
            PlanStep, RouteStrategy,
        )
        planner = QueryPlanner()
        plan = QueryPlan(query=SIMPLE_QUERY, complexity=QueryComplexity.SIMPLE, strategy=RouteStrategy.DIRECT, steps=[])
        l2_result = LayerResult(level=RouteLevel.L2_VECTOR, source="vector", results=[{"text": "t"}], confidence=0.3)
        l3_step = PlanStep(3, RouteLevel.L3_GRAPH, SIMPLE_QUERY, "graph_traverse", "图谱")
        should_upgrade = planner._should_upgrade(l3_step, [l2_result], plan)
        assert should_upgrade is True

    def test_complex_always_upgrade_to_l4(self):
        from src.services.query_planner import (
            QueryPlanner, QueryComplexity, LayerResult, RouteLevel, QueryPlan,
            PlanStep, RouteStrategy,
        )
        planner = QueryPlanner()
        plan = QueryPlan(query=COMPLEX_QUERY, complexity=QueryComplexity.COMPLEX, strategy=RouteStrategy.FULL_PIPELINE, steps=[])
        l3_result = LayerResult(
            level=RouteLevel.L3_GRAPH, source="graph",
            results=[{"text": "t"} for _ in range(10)], confidence=0.9,
        )
        l4_step = PlanStep(4, RouteLevel.L4_REASON, COMPLEX_QUERY, "multi_step_reason", "推理")
        should_upgrade = planner._should_upgrade(l4_step, [l3_result], plan)
        assert should_upgrade is True


class TestResultFusion:
    """结果融合测试"""

    def test_rrf_fusion_multiple_sources(self):
        from src.services.query_planner import QueryPlanner, RouteLevel, LayerResult
        planner = QueryPlanner()
        l2 = LayerResult(
            level=RouteLevel.L2_VECTOR, source="vector",
            results=[
                {"file_hash": "a1", "chunk_index": 0, "score": 8.0, "text": "v1"},
                {"file_hash": "b1", "chunk_index": 0, "score": 5.0, "text": "v2"},
            ],
            confidence=0.7,
        )
        l3 = LayerResult(
            level=RouteLevel.L3_GRAPH, source="graph",
            results=[
                {"file_hash": "a1", "chunk_index": 0, "score": 9.0, "text": "g1"},
                {"file_hash": "c1", "chunk_index": 0, "score": 6.0, "text": "g2"},
            ],
            confidence=0.6,
        )

        async def _test():
            merged = await planner._rrf_fuse([l2, l3])
            assert len(merged) >= 2

        asyncio.run(_test())

    def test_weighted_fusion(self):
        from src.services.query_planner import QueryPlanner, RouteLevel, LayerResult
        planner = QueryPlanner()
        l2 = LayerResult(
            level=RouteLevel.L2_VECTOR, source="vector",
            results=[{"file_hash": "a", "chunk_index": 0, "score": 8.0, "text": "v"}],
            confidence=0.7,
        )
        l3 = LayerResult(
            level=RouteLevel.L3_GRAPH, source="graph",
            results=[{"file_hash": "a", "chunk_index": 0, "score": 8.0, "text": "g"}],
            confidence=0.6,
        )

        async def _test():
            merged = await planner._weighted_fuse([l2, l3])
            assert len(merged) >= 1
            assert merged[0]["_sources"] is not None
            assert len(merged[0]["_sources"]) <= 2

        asyncio.run(_test())

    def test_none_fusion_returns_last_layer(self):
        from src.services.query_planner import (
            QueryPlanner, QueryComplexity, LayerResult, RouteLevel, QueryPlan, RouteStrategy,
        )
        planner = QueryPlanner()
        plan = QueryPlan(
            query=SIMPLE_QUERY, complexity=QueryComplexity.SIMPLE,
            strategy=RouteStrategy.DIRECT, steps=[], fusion_strategy="none",
        )
        l1 = LayerResult(level=RouteLevel.L1_CACHE, source="cache", results=[], confidence=0.0)
        l2 = LayerResult(
            level=RouteLevel.L2_VECTOR, source="vector",
            results=[{"text": "final", "score": 9.0, "file_hash": "x"}],
            confidence=0.9,
        )

        async def _test():
            fused = await planner._fuse_results([l1, l2], plan)
            assert fused["results"] == l2.results

        asyncio.run(_test())


class TestQueryPlannerStats:
    """统计信息测试"""

    def test_stats_update(self):
        from src.services.query_planner import QueryPlanner
        planner = QueryPlanner()

        async def _test():
            await planner._execute_l1_cache("query1", {}, None)
            await planner._execute_l1_cache("query2", {}, None)
            stats = planner.stats
            assert stats["cache_misses"] >= 2

        asyncio.run(_test())

    def test_clear_cache(self):
        from src.services.query_planner import QueryPlanner
        planner = QueryPlanner()

        async def _test():
            await planner._execute_l1_cache("query1", {}, None)
            planner.clear_cache()
            stats = planner.stats
            assert stats["cache_hits"] == 0
            assert stats["cache_misses"] == 0

        asyncio.run(_test())


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegrationIntentBusAndPlanner:
    """IntentBus + QueryPlanner 集成测试"""

    def test_intent_bus_with_planner_as_handler(self):
        from src.services.intent_bus import IntentBus, RAGIntent
        bus = IntentBus()

        async def search_with_planner(query, context, decision):
            from src.services.query_planner import QueryPlanner, QueryComplexity
            planner = QueryPlanner()
            plan = await planner.plan(query, force_complexity=QueryComplexity.SIMPLE)
            l2 = await planner._execute_l2_vector(query, {}, None)
            return {"results": l2.results[:5], "summary": f"5层路由检索到 {len(l2.results)} 条"}

        bus.register_handler(RAGIntent.SEARCH, search_with_planner)

        async def _test():
            result = await bus.run_intent_loop(SIMPLE_QUERY)
            trace = result["intent_trace"]
            assert any(r["intent"] == "SEARCH" for r in trace)

        asyncio.run(_test())


class TestAugmentWithGraph:
    """图谱增强测试"""

    def test_augment_adds_categories_and_relations(self):
        from src.services.query_planner import _augment_with_graph
        results = [{"file_hash": "abc", "text": "VLAN 数据", "score": 8.0, "file_name": "test.pdf"}]
        categories = ["网络建设", "交换机配置"]
        relations = [{"subject": "VLAN", "object": "交换机", "relation": "配置于"}]
        augmented = _augment_with_graph(results, categories, relations)
        assert len(augmented) == 4
        assert any("graph_category" == r.get("_source") for r in augmented)
        assert any("graph_relation" == r.get("_source") for r in augmented)


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """边界情况测试"""

    def test_empty_query_intent_bus(self):
        from src.services.intent_bus import IntentBus, RAGIntent
        bus = IntentBus()

        async def _test():
            decision = await bus.classify_intent("", use_llm=False)
            assert decision.intent == RAGIntent.PRESENT
            assert decision.confidence == 1.0

        asyncio.run(_test())

    def test_whitespace_query(self):
        from src.services.intent_bus import IntentBus, RAGIntent
        bus = IntentBus()

        async def _test():
            decision = await bus.classify_intent("   \n  ", use_llm=False)
            assert decision.intent == RAGIntent.PRESENT

        asyncio.run(_test())

    def test_fallback_intent_chain(self):
        """意图降级链完整"""
        from src.services.intent_bus import IntentBus, RAGIntent
        bus = IntentBus()
        assert bus._fallback_intent(RAGIntent.SEARCH) == RAGIntent.REFINE
        assert bus._fallback_intent(RAGIntent.REFINE) == RAGIntent.PRESENT
        assert bus._fallback_intent(RAGIntent.PRESENT) == RAGIntent.DONE
        assert bus._fallback_intent(RAGIntent.DONE) == RAGIntent.DONE

    def test_unknown_query_caches(self):
        """未知查询会缓存"""
        from src.services.intent_bus import IntentBus
        bus = IntentBus()

        async def _test():
            await bus.classify_intent("一个未知的专业技术查询", use_llm=False)
            assert len(bus._cache) >= 1  # 至少缓存了默认决策

        asyncio.run(_test())

    def test_planner_stats_reset_on_execute(self):
        """执行查询计划后统计正确更新"""
        from src.services.query_planner import QueryPlanner, QueryComplexity, LayerResult, RouteLevel
        planner = QueryPlanner()
        # 统计初始化
        assert planner.stats["total_queries"] == 0
        assert planner.stats["cache_hits"] == 0

    def test_preload_cache_contains_required_entries(self):
        """预加载缓存包含所有必需的意图条目"""
        from src.services.intent_bus import _PRELOAD_INTENT_CACHE
        required = ["你好", "谢谢", "再见", "帮助", "搜*", "查找*", "上传*", "消化*"]
        for key in required:
            assert key in _PRELOAD_INTENT_CACHE, f"缺少预加载缓存条目: {key}"
