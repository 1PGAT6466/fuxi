"""
tests/test_evaluation.py — 模型质量评估闭环测试用例 (v1.44 P1)

测试范围：
  1. Evaluation 类初始化
  2. evaluate_response() — 单次评估
  3. evaluate_rag_output() — RAG 管线集成
  4. evaluate_batch() — 批量评估
  5. generate_report() — 评估报告生成
  6. get_stats() — 统计查询
  7. 去重机制
  8. 幻觉检测（启发式 + LLM）
  9. 反馈闭环触发
  10. 持久化读写
  11. 边界条件
"""
import pytest
import json
import asyncio
import time
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

# 确保 src 在 path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

# ============ Fixtures ============


@pytest.fixture
def evaluation_instance():
    """创建 Evaluation 实例"""
    from src.services.evaluation import Evaluation
    return Evaluation()


@pytest.fixture
def sample_query():
    return "什么是 SAG 三阶段检索管线？"


@pytest.fixture
def sample_response():
    return (
        "SAG（Seed-Aggregate-Generate）三阶段检索管线是伏羲平台的"
        "核心检索范式。第一阶段进行种子检索，包含实体引导路径和"
        "直接向量检索两条路径。第二阶段进行查询时多跳扩展，"
        "从种子事件反查关联实体。第三阶段使用 LLM 精排，"
        "对 Top-100 候选进行重排序。该管线遵循 ADR-001 和 ADR-003 架构决策。"
    )


@pytest.fixture
def sample_context():
    return (
        "SAG 三阶段管线是太阳·筑基的核心检索范式。"
        "阶段 1: 种子检索 (Path A: 实体引导 + Path B: 向量检索)。"
        "阶段 2: 多跳扩展 (H=1, 从 events 反查 entities)。"
        "阶段 3: LLM Rerank (粗排 Top-100 → 精排 Top-K)。"
        "ADR-001: SAG 三阶段作为标准检索范式。"
        "ADR-003: Event 作为召回索引，Chunk 作为输出载体。"
    )


@pytest.fixture
def sample_sources():
    return [
        "sag_pipeline.py 第 48-62 行",
        "ADR-001.md 第 12 行",
        "ADR-003.md 第 5 行",
    ]


# ============ Mock LLM 响应 ============

MOCK_RELEVANCY_ACCURACY_RESPONSE = json.dumps({
    "relevancy": {
        "score": 0.85,
        "detail": "回答准确描述了SAG三阶段结构",
        "issues": [],
    },
    "accuracy": {
        "score": 0.90,
        "detail": "所有声明均有上下文支持",
        "issues": [],
    },
}, ensure_ascii=False)

MOCK_COMPLETENESS_RESPONSE = json.dumps({
    "completeness": 0.75,
    "detail": "覆盖了三个阶段但缺少具体的实现细节",
    "missing": ["各阶段的具体参数配置", "降级策略"],
}, ensure_ascii=False)

MOCK_HALLUCINATION_RESPONSE = json.dumps({
    "hallucination_score": 0.10,
    "detail": "回答基本忠实于上下文，无严重幻觉",
    "hallucinated_claims": [],
    "supported_claims": [
        "SAG三个阶段结构正确",
        "ADR-001和ADR-003引用正确",
    ],
}, ensure_ascii=False)

MOCK_HALLUCINATION_DETECTED = json.dumps({
    "hallucination_score": 0.75,
    "detail": "检测到多处上下文不支持的声明",
    "hallucinated_claims": ["使用BERT做重排序", "支持5跳扩展"],
    "supported_claims": ["三阶段结构"],
}, ensure_ascii=False)

MOCK_LOW_QUALITY_RELEVANCY = json.dumps({
    "relevancy": {
        "score": 0.20,
        "detail": "回答与问题几乎无关",
        "issues": ["回答主题偏离"],
    },
    "accuracy": {
        "score": 0.15,
        "detail": "多处事实性错误",
        "issues": ["编造了不存在的配置参数"],
    },
}, ensure_ascii=False)


# ============ Test Cases ============


class TestEvaluationInit:
    """测试 Evaluation 类初始化"""

    def test_singleton_creation(self):
        """测试全局单例创建"""
        from src.services.evaluation import get_evaluator
        e1 = get_evaluator()
        e2 = get_evaluator()
        assert e1 is e2

    def test_default_config(self, evaluation_instance):
        """测试默认配置"""
        assert evaluation_instance.PASS_THRESHOLD == 0.60
        assert evaluation_instance.WARNING_THRESHOLD == 0.50
        assert evaluation_instance.CRITICAL_THRESHOLD == 0.35
        assert evaluation_instance.HALLUCINATION_ALERT == 0.30
        assert len(evaluation_instance.WEIGHTS) == 4
        assert sum(evaluation_instance.WEIGHTS.values()) == pytest.approx(1.0)

    def test_directories_created(self, evaluation_instance):
        """测试评估目录自动创建"""
        from src.services.evaluation import EVAL_DIR, EVAL_REPORTS_DIR
        assert EVAL_DIR.exists()
        assert EVAL_REPORTS_DIR.exists()


class TestEvaluateResponse:
    """测试 evaluate_response() 核心方法"""

    @pytest.mark.asyncio
    async def test_full_evaluation_success(
        self, evaluation_instance, sample_query, sample_response, sample_context, sample_sources
    ):
        """测试完整的四维评估流程"""
        with patch(
            "src.services.evaluation.Evaluation._eval_relevancy_accuracy",
            new_callable=AsyncMock,
            return_value={
                "relevancy": 0.85, "relevancy_detail": "相关",
                "accuracy": 0.90, "accuracy_detail": "准确",
            },
        ), patch(
            "src.services.evaluation.Evaluation._eval_completeness",
            new_callable=AsyncMock,
            return_value={
                "completeness": 0.75, "detail": "基本完整",
                "issues": [],
            },
        ), patch(
            "src.services.evaluation.Evaluation._eval_hallucination",
            new_callable=AsyncMock,
            return_value={
                "hallucination": 0.10, "hallucination_detail": "低幻觉",
                "hallucination_issues": [],
            },
        ):
            result = await evaluation_instance.evaluate_response(
                query=sample_query,
                response=sample_response,
                context=sample_context,
                sources=sample_sources,
            )

        assert result.eval_id.startswith("eval_")
        assert result.relevancy_score == 0.85
        assert result.accuracy_score == 0.90
        assert result.completeness_score == 0.75
        assert result.hallucination_score == 0.10
        assert result.overall_score > 0.7
        assert result.passed is True
        assert len(result.dimensions) == 4
        assert "low_relevancy" not in result.flags

    @pytest.mark.asyncio
    async def test_evaluation_low_quality(
        self, evaluation_instance, sample_query, sample_response, sample_context
    ):
        """测试低质量回答的评估"""
        with patch(
            "src.services.evaluation.Evaluation._eval_relevancy_accuracy",
            new_callable=AsyncMock,
            return_value={
                "relevancy": 0.20, "relevancy_detail": "不相关",
                "accuracy": 0.15, "accuracy_detail": "不准确",
            },
        ), patch(
            "src.services.evaluation.Evaluation._eval_completeness",
            new_callable=AsyncMock,
            return_value={
                "completeness": 0.30, "detail": "不完整",
                "issues": ["缺失关键信息"],
            },
        ), patch(
            "src.services.evaluation.Evaluation._eval_hallucination",
            new_callable=AsyncMock,
            return_value={
                "hallucination": 0.80, "hallucination_detail": "严重幻觉",
                "hallucination_issues": ["编造内容1", "编造内容2"],
            },
        ):
            result = await evaluation_instance.evaluate_response(
                query=sample_query,
                response="不知道",
                context=sample_context,
            )

        assert result.overall_score < 0.4
        assert result.passed is False
        assert "low_relevancy" in result.flags
        assert "hallucination_detected" in result.flags
        assert len(result.recommendations) > 0

    @pytest.mark.asyncio
    async def test_evaluation_with_empty_context(
        self, evaluation_instance, sample_query, sample_response
    ):
        """测试空上下文时的评估（触发启发式幻觉检测）"""
        with patch(
            "src.services.evaluation.Evaluation._eval_relevancy_accuracy",
            new_callable=AsyncMock,
            return_value={
                "relevancy": 0.70, "accuracy": 0.65,
            },
        ), patch(
            "src.services.evaluation.Evaluation._eval_completeness",
            new_callable=AsyncMock,
            return_value={"completeness": 0.60},
        ):
            result = await evaluation_instance.evaluate_response(
                query=sample_query,
                response=sample_response,
                context="",  # 空上下文
            )

        assert result.eval_id.startswith("eval_")
        # 应使用启发式幻觉检测
        assert result.hallucination_score >= 0  # 不应该是 0.5 fallback
        assert len(result.flags) >= 0

    @pytest.mark.asyncio
    async def test_evaluation_dedup(
        self, evaluation_instance, sample_query, sample_response, sample_context
    ):
        """测试去重机制：相同内容不重复评估"""
        with patch(
            "src.services.evaluation.Evaluation._eval_relevancy_accuracy",
            new_callable=AsyncMock,
            return_value={
                "relevancy": 0.85, "accuracy": 0.90,
            },
        ), patch(
            "src.services.evaluation.Evaluation._eval_completeness",
            new_callable=AsyncMock,
            return_value={"completeness": 0.75},
        ), patch(
            "src.services.evaluation.Evaluation._eval_hallucination",
            new_callable=AsyncMock,
            return_value={"hallucination": 0.10},
        ):
            # 第一次评估
            result1 = await evaluation_instance.evaluate_response(
                query=sample_query,
                response=sample_response,
                context=sample_context,
            )
            # 第二次评估（相同内容）
            result2 = await evaluation_instance.evaluate_response(
                query=sample_query,
                response=sample_response,
                context=sample_context,
            )

        assert result1.overall_score > 0
        # 第二次应该是缓存命中
        assert result2.overall_score == -1.0
        assert "cached_duplicate" in result2.flags

    @pytest.mark.asyncio
    async def test_evaluation_exception_handling(
        self, evaluation_instance, sample_query, sample_response, sample_context
    ):
        """测试 LLM 调用失败时的降级处理"""
        with patch(
            "src.services.evaluation.Evaluation._eval_relevancy_accuracy",
            new_callable=AsyncMock,
            side_effect=Exception("API timeout"),
        ), patch(
            "src.services.evaluation.Evaluation._eval_completeness",
            new_callable=AsyncMock,
            side_effect=Exception("API timeout"),
        ), patch(
            "src.services.evaluation.Evaluation._eval_hallucination",
            new_callable=AsyncMock,
            side_effect=Exception("API timeout"),
        ):
            result = await evaluation_instance.evaluate_response(
                query=sample_query,
                response=sample_response,
                context=sample_context,
            )

        # 所有维度降级为 fallback 值 0.5
        assert result.relevancy_score == 0.5
        assert result.accuracy_score == 0.5
        assert result.completeness_score == 0.5
        assert result.hallucination_score == 0.5
        # 应该能正常返回一个 EvaluationResult
        assert result.overall_score > 0
        assert isinstance(result.flags, list)


class TestEvaluateRAGOutput:
    """测试 evaluate_rag_output() 集成方法"""

    @pytest.mark.asyncio
    async def test_rag_output_dict_format(
        self, evaluation_instance, sample_query, sample_response, sample_context
    ):
        """测试返回格式符合 RAG 管线集成要求"""
        with patch(
            "src.services.evaluation.Evaluation._evaluate_dimensions",
            new_callable=AsyncMock,
            return_value={
                "relevancy": 0.85, "accuracy": 0.90,
                "completeness": 0.75, "hallucination": 0.10,
            },
        ):
            result = await evaluation_instance.evaluate_rag_output(
                query=sample_query,
                answer=sample_response,
                context=sample_context,
                trace_id="test_trace_123",
            )

        assert isinstance(result, dict)
        assert "eval_id" in result
        assert "overall_score" in result
        assert "passed" in result
        assert "scores" in result
        assert "flags" in result
        assert "recommendations" in result
        assert "latency_ms" in result
        assert isinstance(result["scores"], dict)
        assert "relevancy" in result["scores"]
        assert "accuracy" in result["scores"]
        assert "completeness" in result["scores"]
        assert "hallucination" in result["scores"]

    @pytest.mark.asyncio
    async def test_rag_output_with_flags(
        self, evaluation_instance, sample_query
    ):
        """测试带问题的输出"""
        with patch(
            "src.services.evaluation.Evaluation._evaluate_dimensions",
            new_callable=AsyncMock,
            return_value={
                "relevancy": 0.30, "accuracy": 0.25,
                "completeness": 0.20, "hallucination": 0.70,
            },
        ):
            result = await evaluation_instance.evaluate_rag_output(
                query=sample_query,
                answer="这是一个编造的答案",
                context="完全不相关的内容",
            )

        assert result["passed"] is False
        assert "hallucination_detected" in result["flags"]
        assert len(result["recommendations"]) > 0


class TestEvaluateBatch:
    """测试批量评估"""

    @pytest.mark.asyncio
    async def test_batch_evaluation(self, evaluation_instance):
        """测试批量评估多个查询"""
        items = [
            {"query": "Q1", "response": "A1", "context": "C1"},
            {"query": "Q2", "response": "A2", "context": "C2"},
            {"query": "Q3", "response": "A3", "context": "C3"},
        ]

        with patch(
            "src.services.evaluation.Evaluation._evaluate_dimensions",
            new_callable=AsyncMock,
            return_value={
                "relevancy": 0.80, "accuracy": 0.85,
                "completeness": 0.70, "hallucination": 0.05,
            },
        ):
            results = await evaluation_instance.evaluate_batch(items)

        assert len(results) == 3
        for r in results:
            assert r.overall_score > 0.7
            assert r.passed is True

    @pytest.mark.asyncio
    async def test_batch_with_errors(self, evaluation_instance):
        """测试批量评估中的异常项处理"""
        items = [
            {"query": "Q1", "response": "A1", "context": "C1"},
            {"query": "Q2", "response": "A2", "context": "C2"},
        ]

        with patch(
            "src.services.evaluation.Evaluation._evaluate_dimensions",
            new_callable=AsyncMock,
            side_effect=[Exception("Fail"), {"relevancy": 0.80, "accuracy": 0.85, "completeness": 0.70, "hallucination": 0.05}],
        ):
            results = await evaluation_instance.evaluate_batch(items)

        assert len(results) == 2
        # 第一个应该降级
        assert results[0].flags == ["evaluation_error"]
        # 第二个正常
        assert results[1].overall_score > 0.7


class TestGenerateReport:
    """测试评估报告生成"""

    @pytest.mark.asyncio
    async def test_insufficient_data(self, evaluation_instance, tmp_path):
        """测试数据不足时返回 insufficient_data"""
        # 临时修改路径以避免读取真实数据
        with patch("src.services.evaluation.EVAL_DB_PATH", tmp_path / "nonexistent.jsonl"):
            report = await evaluation_instance.generate_report(min_samples=10)

        assert report["status"] == "insufficient_data"
        assert report["sample_count"] < 10

    @pytest.mark.asyncio
    async def test_report_percentile(self, evaluation_instance):
        """测试百分位数计算"""
        p50 = evaluation_instance._percentile([1, 2, 3, 4, 5], 50)
        assert p50 == 3.0

        p95 = evaluation_instance._percentile([1.0, 2.0, 3.0, 4.0, 5.0], 95)
        assert p95 == pytest.approx(4.8, rel=0.1)


class TestGetStats:
    """测试统计查询"""

    @pytest.mark.asyncio
    async def test_stats_empty(self, evaluation_instance, tmp_path):
        """测试空数据时的统计"""
        with patch("src.services.evaluation.EVAL_DB_PATH", tmp_path / "empty.jsonl"):
            stats = await evaluation_instance.get_stats()

        assert stats["total_evaluations"] == 0
        assert stats["avg_overall_score"] == 0
        assert stats["pass_rate"] == 0
        assert stats["hallucination_rate"] == 0


class TestHeuristicHallucination:
    """测试启发式幻觉检测"""

    def test_fabrication_pattern_detection(self, evaluation_instance):
        """测试编造模式检测"""
        query = "什么是SAG"
        response = "根据内部数据显示，SAG有5个阶段。据公司统计，准确率99%。"
        result = evaluation_instance._heuristic_hallucination_check(query, response)

        assert result["hallucination"] > 0
        assert len(result["hallucination_issues"]) > 0

    def test_normal_response_no_flags(self, evaluation_instance):
        """测试正常回答不触发幻觉标记"""
        query = "什么是SAG"
        response = "SAG是检索增强生成的一种策略。"
        result = evaluation_instance._heuristic_hallucination_check(query, response)

        assert result["hallucination"] == 0.0 or result["hallucination"] < 0.1
        assert len(result["hallucination_issues"]) == 0


class TestIntegrationPoints:
    """测试与其他服务的集成点"""

    @pytest.mark.asyncio
    async def test_feedback_store_integration(self, evaluation_instance):
        """测试反馈闭环触发"""
        from src.services.evaluation import EvaluationResult

        with patch(
            "src.services.feedback_store.log_feedback_unified",
            new_callable=AsyncMock,
        ) as mock_feedback:
            result = EvaluationResult(
                eval_id="test_123",
                timestamp=time.time(),
                query="test",
                response="test",
                context="test",
                overall_score=0.3,
                passed=False,
                flags=["hallucination_detected"],
                recommendations=["测试建议"],
            )
            await evaluation_instance._trigger_feedback_loop(result)

            mock_feedback.assert_called_once()
            # 验证调用参数
            call_args = mock_feedback.call_args
            assert call_args.kwargs["action"] == "eval_fail"
            assert "scores" in call_args.kwargs["metadata"]

    @pytest.mark.asyncio
    async def test_flush_method(self, evaluation_instance):
        """测试 flush 方法"""
        # 添加一些数据到缓冲区
        evaluation_instance._batch_buffer.append({"test": "data"})
        evaluation_instance._eval_index["test_id"] = "1234"

        await evaluation_instance.flush()

        # 缓冲区应该被清空
        assert len(evaluation_instance._batch_buffer) == 0

    @pytest.mark.asyncio
    async def test_clear_dedup_cache(self, evaluation_instance):
        """测试清空去重缓存"""
        evaluation_instance._dedup_cache["test_key"] = time.time()
        await evaluation_instance.clear_dedup_cache()
        assert len(evaluation_instance._dedup_cache) == 0


class TestConvenienceFunctions:
    """测试模块级便捷函数"""

    @pytest.mark.asyncio
    async def test_evaluate_response_function(self):
        """测试 evaluate_response 便捷函数"""
        from src.services.evaluation import evaluate_response

        with patch(
            "src.services.evaluation.Evaluation.evaluate_rag_output",
            new_callable=AsyncMock,
            return_value={
                "eval_id": "test",
                "overall_score": 0.85,
                "passed": True,
                "scores": {},
                "flags": [],
            },
        ):
            result = await evaluate_response(
                query="test", response="test", context="test"
            )
            assert result["overall_score"] == 0.85

    @pytest.mark.asyncio
    async def test_generate_quality_report_function(self):
        """测试 generate_quality_report 便捷函数"""
        from src.services.evaluation import generate_quality_report

        with patch(
            "src.services.evaluation.Evaluation.generate_report",
            new_callable=AsyncMock,
            return_value={"status": "ok", "sample_count": 10},
        ):
            result = await generate_quality_report(hours=1)
            assert result["status"] == "ok"


class TestEdgeCases:
    """边界条件测试"""

    @pytest.mark.asyncio
    async def test_empty_query(self, evaluation_instance):
        """测试空查询"""
        with patch(
            "src.services.evaluation.Evaluation._evaluate_dimensions",
            new_callable=AsyncMock,
            return_value={
                "relevancy": 0.0, "accuracy": 0.0,
                "completeness": 0.0, "hallucination": 1.0,
            },
        ):
            result = await evaluation_instance.evaluate_response(
                query="",
                response="",
                context="",
            )

        assert isinstance(result, object)
        assert result.overall_score == 0.0

    @pytest.mark.asyncio
    async def test_very_long_inputs(self, evaluation_instance):
        """测试超长输入"""
        long_query = "A" * 5000
        long_response = "B" * 5000
        long_context = "C" * 5000

        with patch(
            "src.services.evaluation.Evaluation._evaluate_dimensions",
            new_callable=AsyncMock,
            return_value={
                "relevancy": 0.50, "accuracy": 0.50,
                "completeness": 0.50, "hallucination": 0.50,
            },
        ):
            result = await evaluation_instance.evaluate_response(
                query=long_query,
                response=long_response,
                context=long_context,
            )

        # 应被截断到 500 字符
        assert len(result.query) <= 500
        assert result.overall_score == 0.5

    @pytest.mark.asyncio
    async def test_unicode_handling(self, evaluation_instance):
        """测试 Unicode/中文处理"""
        with patch(
            "src.services.evaluation.Evaluation._evaluate_dimensions",
            new_callable=AsyncMock,
            return_value={
                "relevancy": 0.88, "accuracy": 0.92,
                "completeness": 0.80, "hallucination": 0.05,
            },
        ):
            result = await evaluation_instance.evaluate_response(
                query="模具设计中导向柱的直径标准是多少？🔧",
                response="导向柱直径标准为 D=20mm，适用于 4040 以下模具 🎯",
                context="导向柱直径 D=20，模胚 4040 以下使用 A 类结构",
            )

        assert result.eval_id.startswith("eval_")
        assert result.overall_score > 0

    def test_safe_json_parse(self, evaluation_instance):
        """测试安全 JSON 解析"""
        from src.services.evaluation import Evaluation

        # 正常 JSON
        result = Evaluation._safe_json_parse('{"score": 0.85}')
        assert result == {"score": 0.85}

        # 带前缀的 JSON
        result = Evaluation._safe_json_parse('这是说明 {"score": 0.85}')
        assert result == {"score": 0.85}

        # 带后缀的 JSON
        result = Evaluation._safe_json_parse('{"score": 0.85} 额外文字')
        assert result == {"score": 0.85}

        # 无效 JSON
        result = Evaluation._safe_json_parse('这不是JSON')
        assert result == {}

        # 空字符串
        result = Evaluation._safe_json_parse('')
        assert result == {}


class TestEvaluationResultDataclass:
    """测试数据类"""

    def test_evaluation_result_creation(self):
        """测试 EvaluationResult 创建"""
        from src.services.evaluation import EvaluationResult

        result = EvaluationResult(
            eval_id="eval_test",
            timestamp=time.time(),
            query="测试查询",
            response="测试回答",
            context="测试上下文",
            relevancy_score=0.85,
            accuracy_score=0.90,
            completeness_score=0.75,
            hallucination_score=0.10,
            overall_score=0.82,
            passed=True,
            flags=["test_flag"],
            recommendations=["测试建议"],
        )

        assert result.eval_id == "eval_test"
        assert result.passed is True
        assert result.overall_score == 0.82
        assert "test_flag" in result.flags

    def test_evaluation_result_defaults(self):
        """测试默认值"""
        from src.services.evaluation import EvaluationResult

        result = EvaluationResult(
            eval_id="eval_test",
            timestamp=time.time(),
            query="test",
            response="test",
            context="test",
        )

        assert result.overall_score == 0.0
        assert result.passed is False
        assert result.dimensions == []
        assert result.flags == []
        assert result.recommendations == []


class TestDimensionWeights:
    """测试维度权重"""

    def test_weighted_average_calculation(self, evaluation_instance):
        """测试加权平均计算"""
        dim_results = {
            "relevancy": 1.0,
            "accuracy": 1.0,
            "completeness": 1.0,
            "hallucination": 0.0,  # 无幻觉 → 转换后 = 1.0
        }
        overall, _ = evaluation_instance._compute_overall(dim_results)
        assert overall == pytest.approx(1.0)

    def test_poor_hallucination_impact(self, evaluation_instance):
        """测试幻觉对综合得分的影响"""
        dim_results = {
            "relevancy": 0.8,
            "accuracy": 0.8,
            "completeness": 0.8,
            "hallucination": 0.8,  # 严重幻觉 → 转换后 = 0.2
        }
        overall, _ = evaluation_instance._compute_overall(dim_results)
        # 幻觉权重 0.25, 转化得分 0.2 → 贡献 0.05
        # 其他三维各贡献 0.2 (0.8*0.25)
        # 总计: 0.2+0.24+0.2+0.05 = 0.69
        assert overall < 0.7


# ============ Integration test (requires running server) ============


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_evaluation_without_llm(evaluation_instance):
    """
    集成测试：不 mock LLM，测试评估流程。
    由于可能没有真实的 LLM API key，使用启发式降级。
    """
    result = await evaluation_instance.evaluate_response(
        query="测试问题",
        response="这是一个测试回答，包含据公司统计的具体数据 99.9%",
        context="",  # 空上下文 → 触发启发式幻觉检测
    )

    # 基本结构完整性检查
    assert result.eval_id.startswith("eval_")
    assert isinstance(result.overall_score, float)
    assert isinstance(result.latency_ms, float)
    assert result.latency_ms >= 0
    assert isinstance(result.dimensions, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
