"""
judge_v2.py — LLM-as-Judge 答案质量评分 (v1.43)
用 MiMo 2.5 Pro 自动评估答案质量
"""
import json, logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

JUDGE_PROMPT = """你是一个知识库答案质量评审员。

用户问题: {query}
检索到的内容: {context}
生成的答案: {answer}

请从以下维度评分（1-5分）:
1. 相关性: 答案是否回答了问题
2. 忠实性: 答案是否基于检索内容，没有编造
3. 完整性: 答案是否充分完整
4. 引用准确性: 来源标注是否正确

返回 JSON:
{{"relevance": 1-5, "faithfulness": 1-5, "completeness": 1-5, "citation_accuracy": 1-5, "overall": 1-5, "reason": "一句话"}}"""


async def judge_answer(query: str, context: str, answer: str) -> Dict:
    """
    用 MiMo 2.5 Pro 作为 Judge 评分
    返回: {"relevance": int, "faithfulness": int, "completeness": int, "citation_accuracy": int, "overall": int, "reason": str}
    """
    try:
        from src.services.llm import call_llm_fast
        prompt = JUDGE_PROMPT.format(
            query=query[:500],
            context=context[:2000],
            answer=answer[:1500],
        )
        result = await call_llm_fast(prompt, max_tokens=200, temperature=0.1)
        if not result:
            return {"overall": 0, "reason": "Judge 调用失败"}
        
        # 解析 JSON
        try:
            # 尝试直接解析
            data = json.loads(result)
            return data
        except json.JSONDecodeError:
            # 尝试提取 JSON
            import re
            match = re.search(r'\{[^}]+\}', result)
            if match:
                return json.loads(match.group())
            return {"overall": 0, "reason": "解析失败"}
    except Exception as e:
        logger.warning(f"Judge 评分失败: {e}")
        return {"overall": 0, "reason": str(e)}


def get_quality_level(score: int) -> str:
    """分数转质量等级"""
    if score >= 4:
        return "优秀"
    elif score >= 3:
        return "良好"
    elif score >= 2:
        return "一般"
    else:
        return "差"
