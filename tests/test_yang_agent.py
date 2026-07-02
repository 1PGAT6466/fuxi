"""tests/test_yang_agent.py — YangAgent 测试"""
import pytest
from src.shaoyin.tools import YangAgent, YANG_SYSTEM_PROMPT, YANG_TOOLS, MAX_STEPS, TOKEN_BUDGET

@pytest.fixture
def agent():
    return YangAgent()

def test_constants():
    assert MAX_STEPS == 5
    assert TOKEN_BUDGET == 15000
    assert len(YANG_SYSTEM_PROMPT) > 100

def test_tools_is_list():
    assert isinstance(YANG_TOOLS, list)
    assert len(YANG_TOOLS) >= 2

def test_tool_format():
    for tool in YANG_TOOLS:
        assert 'type' in tool
        assert tool['type'] == 'function'
        assert 'function' in tool
        assert 'name' in tool['function']
