"""
tools.py — 少阴·FC工具定义
"""
import json
import logging
from typing import Dict, List, Any

logger = logging.getLogger("shaoyin.tools")

MAX_STEPS = 5
TOKEN_BUDGET = 15000

YANG_SYSTEM_PROMPT = """你是伏羲知识库的执行智能体。

## 工作原则
1. 先搜索，再回答。绝不凭空编造。
2. 搜索结果不足时，主动扩大搜索范围。
3. 涉及数字、规格、价格时，必须引用来源。
4. 不确定时说"根据现有资料无法确定"。

## 工具使用策略
- 简单问题 → 1次 search_knowledge + done
- 比较问题 → 分别搜索 A 和 B，再比较
- 分析问题 → 搜索 + 读取相关文档 + 综合分析

## 输出格式
调用 done 工具时，answer 字段必须是完整的中文回答，包含：
- 直接回答用户问题
- 引用来源（[Ref 1] 格式）
"""

YANG_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "搜索企业知识库",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "top_k": {"type": "integer", "default": 5, "description": "返回结果数"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": "完成任务并返回答案",
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string", "description": "完整回答"}
                },
                "required": ["answer"]
            }
        }
    }
]


class YangAgent:
    """阳·执行层"""

    def __init__(self):
        pass
