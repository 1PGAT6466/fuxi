"""
tests/test_coreference_resolver.py — 指代消解单元测试
=====================================================
覆盖 CoreferenceResolver 所有消解路径：
  - 代词替换（它、他、她、这个、那个、其、此）
  - 省略补全（短追问模式）
  - 边界情况（空历史、无指代、长查询）
  - 实体提取
  - 统计与缓存
"""
import pytest
from src.services.coreference_resolver import (
    CoreferenceResolver,
    resolve_coreference,
    get_resolver,
)


# ============================================================================
# 测试夹具
# ============================================================================

@pytest.fixture
def resolver():
    """创建不带 LLM 回退的 resolver"""
    return CoreferenceResolver(enable_llm=False)


@pytest.fixture
def resolver_with_llm():
    """创建带 LLM 回退的 resolver"""
    return CoreferenceResolver(enable_llm=True)


@pytest.fixture
def history_plc():
    """PLC 产品对话历史"""
    return [
        {"role": "user", "content": "PLC-200 是什么？"},
        {"role": "assistant", "content": "PLC-200 是一款高性能可编程逻辑控制器。"},
        {"role": "user", "content": "它的主要参数有哪些？"},
        {"role": "assistant", "content": "PLC-200 支持 32 路 IO，工作温度 -20~70°C。"},
    ]


@pytest.fixture
def history_material():
    """材料对话历史"""
    return [
        {"role": "user", "content": "PA66 和 POM 哪个更适合做齿轮？"},
        {"role": "assistant", "content": "PA66 的耐磨性更好，但 POM 精度更高。"},
    ]


@pytest.fixture
def history_person():
    """人物对话历史"""
    return [
        {"role": "user", "content": "张三是谁？"},
        {"role": "assistant", "content": "张三是公司的首席工程师，擅长嵌入式开发。"},
    ]


# ============================================================================
# 快速路径：无操作
# ============================================================================

class TestNoOp:
    """无需消解的查询直接返回"""

    @pytest.mark.asyncio
    async def test_empty_history(self, resolver):
        result = await resolver.resolve("它多少钱？", [])
        assert result == "它多少钱？"

    @pytest.mark.asyncio
    async def test_no_pronouns(self, resolver, history_plc):
        result = await resolver.resolve("PLC-200 支持多少路 IO？", history_plc)
        assert result == "PLC-200 支持多少路 IO？"

    @pytest.mark.asyncio
    async def test_none_history(self, resolver):
        result = await resolver.resolve("查询内容", None)
        assert result == "查询内容"

    @pytest.mark.asyncio
    async def test_independent_query(self, resolver, history_material):
        result = await resolver.resolve("什么是尼龙？", history_material)
        assert result == "什么是尼龙？"


# ============================================================================
# 代词替换：第三人称
# ============================================================================

class TestPronounReplacement:
    """显式代词替换"""

    @pytest.mark.asyncio
    async def test_ta_thing(self, resolver, history_plc):
        """「它」→ 产品名称"""
        result = await resolver.resolve("它多少钱？", history_plc)
        assert "PLC-200" in result

    @pytest.mark.asyncio
    async def test_ta_person(self, resolver, history_person):
        """「他」→ 人名"""
        result = await resolver.resolve("他在哪个部门？", history_person)
        assert "张三" in result

    @pytest.mark.asyncio
    async def test_zhege(self, resolver, history_plc):
        """「这个」→ 产品名称"""
        result = await resolver.resolve("这个支持 Wi-Fi 吗？", history_plc)
        assert "PLC-200" in result

    @pytest.mark.asyncio
    async def test_nage(self, resolver, history_material):
        """「那个」→ 材料名称"""
        result = await resolver.resolve("那个更便宜？", history_material)
        assert "PA66" in result or "POM" in result

    @pytest.mark.asyncio
    async def test_qi(self, resolver, history_plc):
        """「其」→ 产品名称"""
        result = await resolver.resolve("其价格是多少？", history_plc)
        assert "PLC-200" in result

    @pytest.mark.asyncio
    async def test_ci(self, resolver, history_plc):
        """「此」→ 产品名称"""
        result = await resolver.resolve("此产品的功耗如何？", history_plc)
        assert "PLC-200" in result

    @pytest.mark.asyncio
    async def test_gai(self, resolver, history_plc):
        """「该」→ 产品名称"""
        result = await resolver.resolve("该型号是否支持 5G？", history_plc)
        assert "PLC-200" in result

    @pytest.mark.asyncio
    async def test_zhexie(self, resolver, history_material):
        """「这些」→ 材料名称"""
        result = await resolver.resolve("这些材料的区别是什么？", history_material)
        assert "PA66" in result or "POM" in result


# ============================================================================
# 省略补全
# ============================================================================

class TestEllipsisCompletion:
    """省略追问补全"""

    @pytest.mark.asyncio
    async def test_price_followup(self, resolver, history_plc):
        """「多少钱？」→ 补全主语"""
        result = await resolver.resolve("多少钱？", history_plc)
        assert "PLC-200" in result and "钱" in result

    @pytest.mark.asyncio
    async def test_how_to_followup(self, resolver, history_material):
        """「怎么用？」→ 补全主语"""
        result = await resolver.resolve("怎么处理？", history_material)
        assert "PA66" in result or "POM" in result

    @pytest.mark.asyncio
    async def test_why_followup(self, resolver, history_plc):
        """「为什么？」→ 补全上下文"""
        result = await resolver.resolve("为什么？", history_plc)
        assert "PLC-200" in result

    @pytest.mark.asyncio
    async def test_example_followup(self, resolver, history_plc):
        """「举个例子」→ 补全上下文"""
        result = await resolver.resolve("举个例子", history_plc)
        assert "PLC-200" in result

    @pytest.mark.asyncio
    async def test_detail_followup(self, resolver, history_plc):
        """「能详细说明一下」→ 补全上下文"""
        result = await resolver.resolve("能详细讲一下吗？", history_plc)
        assert "PLC-200" in result

    @pytest.mark.asyncio
    async def test_then_followup(self, resolver, history_plc):
        """「然后呢？」→ 补全上下文"""
        result = await resolver.resolve("然后呢？", history_plc)
        assert "PLC-200" in result

    @pytest.mark.asyncio
    async def test_features_followup(self, resolver, history_plc):
        """「特点是什么？」→ 补全主语"""
        result = await resolver.resolve("特点是什么？", history_plc)
        assert "PLC-200" in result

    @pytest.mark.asyncio
    async def test_short_followup_with_context(self, resolver, history_plc):
        """短追问自动补全"""
        result = await resolver.resolve("功耗？", history_plc)
        assert "PLC-200" in result


# ============================================================================
# 边界情况
# ============================================================================

class TestEdgeCases:
    """边界和异常"""

    @pytest.mark.asyncio
    async def test_single_message_history(self, resolver):
        """只有一条用户消息的历史"""
        history = [{"role": "user", "content": "你好"}]
        result = await resolver.resolve("它是什么？", history)
        assert result == "它是什么？"  # 无法消解时保持原样

    @pytest.mark.asyncio
    async def test_very_long_query(self, resolver, history_plc):
        """长查询 + 代词"""
        long_q = "我想详细了解一下这个产品的具体技术参数、应用场景和价格信息"
        result = await resolver.resolve(long_q, history_plc)
        assert "PLC-200" in result

    @pytest.mark.asyncio
    async def test_no_entities_in_history(self, resolver):
        """历史中无有效实体"""
        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！请问有什么可以帮你的？"},
        ]
        result = await resolver.resolve("这个怎么做？", history)
        # 无法找到具体实体，应保持原样或降级
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_multiple_pronouns(self, resolver, history_plc):
        """同一查询中有多个代词"""
        result = await resolver.resolve("这个和那个有什么区别？", history_plc)
        assert "PLC-200" in result

    @pytest.mark.asyncio
    async def test_quoted_entity_in_history(self, resolver):
        """引号中的实体优先提取"""
        history = [
            {"role": "user", "content": "「深蓝计划」是什么？"},
            {"role": "assistant", "content": "「深蓝计划」是公司的 AI 战略项目。"},
        ]
        result = await resolver.resolve("它的目标是什么？", history)
        assert "深蓝计划" in result

    @pytest.mark.asyncio
    async def test_model_number_in_history(self, resolver):
        """产品型号识别"""
        history = [
            {"role": "user", "content": "ABS-V0 的阻燃等级？"},
            {"role": "assistant", "content": "ABS-V0 达到 UL94 V-0 阻燃等级。"},
        ]
        result = await resolver.resolve("这个材料的价格？", history)
        assert "ABS-V0" in result


# ============================================================================
# 实体提取
# ============================================================================

class TestEntityExtraction:
    """实体提取逻辑"""

    def test_extract_quoted_entity(self, resolver):
        entities = resolver._extract_key_entities('请分析「伏羲平台」的架构')
        assert entities.get("thing") == "伏羲平台"

    def test_extract_model_number(self, resolver):
        entities = resolver._extract_key_entities("PLC-200 支持多少路 IO？")
        assert entities.get("thing") == "PLC-200"

    def test_extract_chinese_company(self, resolver):
        entities = resolver._extract_key_entities("华为公司的最新财报如何？")
        assert entities.get("thing") == "华为公司"

    def test_extract_subject_from_start(self, resolver):
        entities = resolver._extract_key_entities("RAG技术是如何提升检索质量的")
        assert len(entities) > 0

    def test_extract_empty_text(self, resolver):
        entities = resolver._extract_key_entities("")
        assert entities == {}


# ============================================================================
# 统计与缓存
# ============================================================================

class TestStatsAndCache:
    """统计和缓存功能"""

    @pytest.mark.asyncio
    async def test_stats_increments(self, resolver, history_plc):
        resolver.reset_stats()
        await resolver.resolve("它多少钱？", history_plc)
        stats = resolver.get_stats()
        assert stats["rule_hits"] >= 1

    @pytest.mark.asyncio
    async def test_stats_no_op(self, resolver):
        resolver.reset_stats()
        await resolver.resolve("独立查询", None)
        stats = resolver.get_stats()
        assert stats["no_op"] >= 1

    def test_reset_stats(self, resolver):
        resolver.reset_stats()
        stats = resolver.get_stats()
        assert stats["rule_hits"] == 0
        assert stats["no_op"] == 0

    def test_get_stats_returns_dict(self, resolver):
        stats = resolver.get_stats()
        assert isinstance(stats, dict)
        assert "rule_hits" in stats
        assert "llm_hits" in stats
        assert "no_op" in stats

    @pytest.mark.asyncio
    async def test_session_id_no_effect(self, resolver, history_plc):
        """session_id 参数应正常工作"""
        result1 = await resolver.resolve("它多少钱？", history_plc, session_id="sess1")
        result2 = await resolver.resolve("它多少钱？", history_plc, session_id="sess2")
        assert "PLC-200" in result1
        assert "PLC-200" in result2


# ============================================================================
# 工厂函数
# ============================================================================

class TestFactoryFunction:
    """便捷函数测试"""

    @pytest.mark.asyncio
    async def test_resolve_coreference(self, history_plc):
        result = await resolve_coreference("它多少钱？", history_plc)
        assert "PLC-200" in result

    def test_get_resolver_singleton(self):
        r1 = get_resolver()
        r2 = get_resolver()
        assert r1 is r2  # 默认单例

    def test_get_resolver_with_llm(self):
        r = get_resolver(enable_llm=True)
        assert r.ENABLE_LLM_FALLBACK is True


# ============================================================================
# 集成场景
# ============================================================================

class TestIntegrationScenarios:
    """真实对话场景"""

    @pytest.mark.asyncio
    async def test_complete_conversation_flow(self, resolver):
        """模拟完整的多轮对话流程"""
        history = [
            {"role": "user", "content": "伏羲平台支持哪些文档格式？"},
            {"role": "assistant", "content": "伏羲平台支持 PDF、Word、Excel、PPT 等格式。"},
        ]

        # 第1轮追问：代词
        q1 = await resolver.resolve("它能处理扫描件吗？", history)
        assert "伏羲平台" in q1

        # 第2轮追问：省略
        history.append({"role": "user", "content": "它能处理扫描件吗？"})
        history.append({"role": "assistant", "content": "可以，伏羲平台内置 OCR 引擎。"})
        q2 = await resolver.resolve("准确率多少？", history)
        assert "伏羲平台" in q2 or "OCR" in q2

    @pytest.mark.asyncio
    async def test_engineering_context(self, resolver):
        """工程场景：多轮技术讨论"""
        history = [
            {"role": "user", "content": "M3 螺栓的强度等级？"},
            {"role": "assistant", "content": "M3 螺栓常见强度等级为 4.8、8.8、10.9、12.9。"},
            {"role": "user", "content": "8.8 级的抗拉强度？"},
            {"role": "assistant", "content": "8.8 级 M3 螺栓抗拉强度约 800MPa。"},
        ]

        result = await resolver.resolve("那 10.9 级呢？", history)
        assert "M3" in result or "螺栓" in result

    @pytest.mark.asyncio
    async def test_multi_entity_history(self, resolver):
        """多实体场景：正确选择最近的实体"""
        history = [
            {"role": "user", "content": "伺服电机和步进电机的区别？"},
            {"role": "assistant", "content": "伺服电机精度更高，步进电机成本更低。"},
            {"role": "user", "content": "伺服电机配套的驱动器推荐？"},
            {"role": "assistant", "content": "推荐 ACD-2000 系列驱动器，支持多种反馈。"},
        ]

        # 最近提及的是 ACD-2000
        result = await resolver.resolve("它的价格？", history)
        assert "ACD-2000" in result

    @pytest.mark.asyncio
    async def test_abs_material_followup(self, resolver):
        """材料场景：ABS-V0 追问，助手消息中同时出现多个型号"""
        history = [
            {"role": "user", "content": "ABS-V0 的阻燃等级？"},
            {"role": "assistant", "content": "ABS-V0 达到 UL94 V-0 阻燃等级。"},
        ]
        result = await resolver.resolve("它的密度呢？", history)
        assert "ABS-V0" in result

    @pytest.mark.asyncio
    async def test_short_single_word_followup(self, resolver):
        """极短追问：单个词 + 问号"""
        history = [
            {"role": "user", "content": "PLC-200 的工作温度范围？"},
            {"role": "assistant", "content": "PLC-200 工作温度 -20~70°C。"},
        ]
        result = await resolver.resolve("功耗？", history)
        assert "PLC-200" in result

    @pytest.mark.asyncio
    async def test_na_suffix_pattern(self, resolver):
        """「那 X 呢？」模式"""
        history = [
            {"role": "user", "content": "PA66 的性能如何？"},
            {"role": "assistant", "content": "PA66 具有高强度和良好的耐磨性。"},
        ]
        result = await resolver.resolve("那 POM 呢？", history)
        assert "PA66" in result


# ============================================================================
# 实体提取增强测试（P2 改进）
# ============================================================================

class TestEntityExtractionEnhanced:
    """增强实体提取：覆盖助手回复中的主题实体识别"""

    def test_assistant_response_topic_entity(self, resolver):
        """助手回复中提取主题实体（「X 达到...」模式）"""
        entities = resolver._extract_key_entities(
            "ABS-V0 达到 UL94 V-0 阻燃等级。"
        )
        assert entities.get("thing") == "ABS-V0"

    def test_assistant_response_support_entity(self, resolver):
        """助手回复中提取实体（「X 支持...」模式）"""
        entities = resolver._extract_key_entities(
            "PLC-200 支持 32 路 IO，工作温度 -20~70°C。"
        )
        assert entities.get("thing") == "PLC-200"

    def test_assistant_response_recommend_entity(self, resolver):
        """助手回复中提取实体（「推荐 X...」模式）"""
        entities = resolver._extract_key_entities(
            "推荐 ACD-2000 系列驱动器，支持多种反馈。"
        )
        assert entities.get("thing") == "ACD-2000"

    def test_assistant_response_is_entity(self, resolver):
        """助手回复中提取实体（「X 是一款...」模式）"""
        entities = resolver._extract_key_entities(
            "PLC-200 是一款高性能可编程逻辑控制器。"
        )
        assert entities.get("thing") == "PLC-200"

    def test_generic_terms_no_false_positive(self, resolver):
        """通用术语不应被当作实体"""
        entities = resolver._extract_key_entities(
            "伺服电机精度更高，步进电机成本更低。"
        )
        assert entities.get("thing") is None or entities["thing"] not in (
            "更高", "更低", "电机精度", "电机成本"
        )
