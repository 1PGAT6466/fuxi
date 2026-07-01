"""
tests/test_yin_agent.py — 太极·阴 Agent 单元测试
覆盖：规则校验、数字一致性、幻觉检测、答非所问检测
"""
import pytest
from src.shaoyin.validator import YinAgent


@pytest.fixture
def agent():
    return YinAgent()


class TestRuleCheckBasic:
    """基础规则校验"""

    def test_good_answer_passes(self, agent):
        result = agent._rule_check(
            answer="PA66 的拉伸强度为 80 MPa，收缩率约 1.5%。根据材料手册 [Ref 1] 记载...",
            sources=[{"text": "PA66 拉伸强度 ≥ 80MPa，收缩率 1.5%"}],
            query="PA66 拉伸强度"
        )
        assert result["passed"] is True
        assert result["score"] >= 60

    def test_short_answer_fails(self, agent):
        result = agent._rule_check(
            answer="不知道",
            sources=[],
            query="PA66 拉伸强度"
        )
        assert result["score"] < 100
        assert any("过短" in i for i in result["issues"])

    def test_empty_answer_low_score(self, agent):
        result = agent._rule_check(
            answer="",
            sources=[],
            query="test"
        )
        assert result["score"] < 100
        assert any("过短" in i for i in result["issues"])


class TestMaterialNumberFilter:
    """材料名数字过滤"""

    def test_pa66_not_phantom(self, agent):
        """PA66 中的 66 不应被判为幻觉数字"""
        result = agent._rule_check(
            answer="PA66 的拉伸强度是 80 MPa",
            sources=[{"text": "PA66 拉伸强度 ≥ 80MPa"}],
            query="PA66 拉伸强度"
        )
        # 66 不应该出现在 issues 中
        issues_str = " ".join(result.get("issues", []))
        assert "66" not in issues_str or "幻觉" not in issues_str

    def test_pom_not_phantom(self, agent):
        """POM 材料测试"""
        result = agent._rule_check(
            answer="POM 的硬度为 HRC 80",
            sources=[{"text": "POM 硬度 HRC 80"}],
            query="POM 硬度"
        )
        issues_str = " ".join(result.get("issues", []))
        assert "80" not in issues_str or "幻觉" not in issues_str

    def test_real_phantom_detected(self, agent):
        """真正的幻觉数字应该被检测到"""
        result = agent._rule_check(
            answer="PA66 的拉伸强度是 80 MPa，密度 1.14，熔点 260，收缩率 1.5，硬度 120，模量 3.5，冲击强度 45，弯曲强度 110",
            sources=[{"text": "PA66 拉伸强度 80MPa"}],
            query="PA66 参数"
        )
        # 应该有幻觉数字的警告
        assert len(result["issues"]) > 0


class TestHallucinationDetection:
    """幻觉关键词检测"""

    def test_hallucination_without_source(self, agent):
        result = agent._rule_check(
            answer="据统计，PA66 的市场占有率达到 60%",
            sources=[],
            query="PA66 市场"
        )
        assert any("据统计" in i for i in result["issues"])

    def test_hallucination_with_source_ok(self, agent):
        result = agent._rule_check(
            answer="据统计，PA66 的市场占有率达到 60%",
            sources=[{"text": "PA66 市场占有率 60%"}],
            query="PA66 市场"
        )
        # 有来源支持，不应扣分
        issues_str = " ".join(result.get("issues", []))
        assert "据统计" not in issues_str


class TestRelevanceCheck:
    """答非所问检测"""

    def test_relevant_answer_passes(self, agent):
        result = agent._rule_check(
            answer="PA66 的拉伸强度为 80 MPa，是一种常用的工程塑料",
            sources=[{"text": "PA66 拉伸强度 80MPa"}],
            query="PA66 拉伸强度"
        )
        issues_str = " ".join(result.get("issues", []))
        assert "答非所问" not in issues_str

    def test_irrelevant_answer_detected(self, agent):
        result = agent._rule_check(
            answer="今天天气很好，适合出门散步，公园里有很多人在跑步",
            sources=[{"text": "PA66 拉伸强度 80MPa"}],
            query="PA66 拉伸强度"
        )
        # 应该检测到答非所问
        assert result["score"] < 100


class TestSecurityCheck:
    """安全性检查"""

    def test_password_leak_detected(self, agent):
        result = agent._rule_check(
            answer="数据库密码: abc123",
            sources=[],
            query="数据库配置"
        )
        assert any("敏感" in i for i in result["issues"])
