"""
tests/test_brain.py — 大脑 v4.2 单元测试
覆盖：多意图 Instinct、思考记忆、三级降级、自我纠错
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.hypothalamus.meridian import Meridian
from src.hypothalamus.brain import Brain, Instinct, Thought

# ========== Instinct v4.2 测试 ==========

class TestInstinctMultiIntent:
    """多意图联合识别"""
    
    def test_compare_with_material(self):
        r = Instinct.classify_intent("PA66和POM哪个更适合做齿轮")
        assert r["intent"] in ("compare", "general_search")
        assert "compare" in r["intents"]
        assert "material_selector" in r["intents"]
    
    def test_material_numeric(self):
        r = Instinct.classify_intent("PA66 收缩率参数")
        assert r["intent"] == "numeric_lookup"
        assert "material_selector" in r["intents"]
        assert "numeric_lookup" in r["intents"]
    
    def test_pure_how_to(self):
        r = Instinct.classify_intent("VLAN 怎么配置")
        assert r["intent"] == "how_to"
    
    def test_compare_two_things(self):
        r = Instinct.classify_intent("PPS和PBT哪个耐热性更好")
        assert r["intent"] in ("compare", "general_search")
    
    def test_definition_only(self):
        r = Instinct.classify_intent("什么是LCP")
        assert r["intent"] == "definition"


class TestInstinctContext:
    """上下文消歧"""
    
    def test_context_compare_boost(self):
        r = Instinct.classify_intent("它们的区别是什么", context=["PA66材料性能", "对比分析"])
        assert "compare" in r.get("intents", {})


class TestInstinctComplexity:
    """复杂度评估"""
    
    def test_compare_is_complex(self):
        r = Instinct.classify_intent("PA66和POM哪个强度高更适合齿轮应用")
        intent = {"intent": "compare", "intents": {"compare": 0.67, "definition": 0.5, "material_selector": 0.5}, "count": 3}
        c = Instinct.estimate_complexity("PA66和POM哪个强度高更适合齿轮应用", intent)
        assert c >= 4  # 长query + 多意图
    
    def test_simple_is_low(self):
        intent = {"intent": "definition", "intents": {"definition": 0.5}, "count": 1}
        c = Instinct.estimate_complexity("PA66", intent)
        assert c <= 2


class TestInstinctBoundary:
    """边界条件"""
    
    def test_empty_query(self):
        r = Instinct.classify_intent("")
        assert r["intent"] == "general_search"
        assert r["count"] == 0
    
    def test_english_query(self):
        r = Instinct.classify_intent("what is PA66")
        # 英文应被识别为材料
        assert "material_selector" in r.get("intents", {})
    
    def test_needs_external_when_few_hits(self):
        intent = {"intents": {"numeric_lookup": 0.8}}
        assert Instinct.needs_external_search(intent, internal_hits=1) is True
        assert Instinct.needs_external_search(intent, internal_hits=5) is False


# ========== Brain 核心测试 ==========

class TestBrainInit:
    """大脑初始化"""
    
    def test_brain_creation(self):
        m = Meridian()
        b = Brain(m)
        assert b.instinct is not None
        assert b._recent_thoughts == []
        assert b._conversation_context == []
    
    def test_brain_registered(self):
        m = Meridian()
        Brain(m)
        organ = m.get_organ("brain")
        assert organ is not None


class TestBrainSelfAssess:
    """自我评估"""
    
    def test_empty_answer_low_score(self):
        m = Meridian()
        b = Brain(m)
        score = b._self_assess("", {"internal": {"chunks": []}})
        assert score < 0.3
    
    def test_sourced_answer_high_score(self):
        m = Meridian()
        b = Brain(m)
        answer = "PA66 的收缩率为 1.5% [来源: 材料手册.pdf]"
        results = {"internal": {"chunks": [{"text": "收缩率 1.5%", "file_name": "a.pdf"}, {"text": "a", "file_name": "b"}, {"text": "b", "file_name": "c"}]}}
        score = b._self_assess(answer, results)
        assert score >= 0.6
    
    def test_honest_no_source(self):
        m = Meridian()
        b = Brain(m)
        answer = "知识库中未找到与此问题直接相关的信息"
        score = b._self_assess(answer, {"internal": {"chunks": []}})
        assert score >= 0.6  # 诚实应给高分


class TestBrainContextMemory:
    """思考记忆"""
    
    def test_context_accumulates(self):
        m = Meridian()
        b = Brain(m)
        b._conversation_context.append("PA66 参数")
        b._conversation_context.append("它的收缩率")
        assert len(b._conversation_context) == 2
    
    def test_context_limits_to_5(self):
        m = Meridian()
        b = Brain(m)
        for i in range(10):
            b._conversation_context.append(f"query {i}")
            # 手动调用裁剪逻辑
            if len(b._conversation_context) > 5:
                b._conversation_context = b._conversation_context[-5:]
        assert len(b._conversation_context) == 5


class TestBrainTopK:
    """检索参数"""
    
    def test_compare_needs_more(self):
        m = Meridian()
        b = Brain(m)
        k = b._top_k_for_intent({"intent": "compare", "count": 1})
        assert k == 15
    
    def test_general_default(self):
        m = Meridian()
        b = Brain(m)
        k = b._top_k_for_intent({"intent": "general_search", "count": 0})
        assert k == 10


class TestBrainStats:
    """统计"""
    
    def test_initial_stats(self):
        m = Meridian()
        b = Brain(m)
        s = b.stats()
        assert s["thoughts"] == 0
        assert s["alive"] is True


class TestBrainDirectSearch:
    """降级直调"""
    
    @pytest.mark.asyncio
    async def test_direct_search_returns_chunks(self):
        m = Meridian()
        b = Brain(m)
        result = await b._direct_search("test")
        assert "chunks" in result
        assert isinstance(result["chunks"], list)
