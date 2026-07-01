"""
tests/test_yang_agent.py — 太极·阳 Agent 单元测试
覆盖：初始化、工具定义、token 预算
"""
import pytest
from src.agents.yang_agent import YangAgent, YANG_SYSTEM_PROMPT, YANG_TOOLS, MAX_STEPS, TOKEN_BUDGET


@pytest.fixture
def agent():
    return YangAgent()


class TestYangAgentInit:
    """初始化测试"""

    def test_agent_id(self, agent):
        assert agent.agent_id == "yang"

    def test_description(self, agent):
        assert "阳" in agent.description


class TestConstants:
    """常量测试"""

    def test_max_steps(self):
        assert MAX_STEPS == 5

    def test_token_budget(self):
        assert TOKEN_BUDGET == 15000

    def test_system_prompt_not_empty(self):
        assert len(YANG_SYSTEM_PROMPT) > 100
        assert "搜索" in YANG_SYSTEM_PROMPT
        assert "引用" in YANG_SYSTEM_PROMPT


class TestToolDefinitions:
    """工具定义测试"""

    def test_tools_is_list(self):
        assert isinstance(YANG_TOOLS, list)
        assert len(YANG_TOOLS) >= 2

    def test_search_knowledge_tool(self):
        search_tool = next((t for t in YANG_TOOLS if t["function"]["name"] == "search_knowledge"), None)
        assert search_tool is not None
        assert "query" in search_tool["function"]["parameters"]["properties"]

    def test_done_tool(self):
        done_tool = next((t for t in YANG_TOOLS if t["function"]["name"] == "done"), None)
        assert done_tool is not None
        assert "answer" in done_tool["function"]["parameters"]["properties"]

    def test_tool_format(self):
        for tool in YANG_TOOLS:
            assert "type" in tool
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "parameters" in tool["function"]
