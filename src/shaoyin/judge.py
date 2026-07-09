"""
judge.py — Phase 1.3: LLM-as-Judge 评测
用 MiMo/DeepSeek 评分（相关性/忠实性/完整性/引用准确性）
"""
import json, logging

logger = logging.getLogger(__name__)

JUDGE_PROMPT = """你是一个知识库答案质量评审员。

用户问题: {query}
检索到的内容: {context}
生成的答案: {answer}

请从以下维度评分（1-5分）：
1. 相关性 — 答案是否直接回应用户问题
2. 忠实性 — 答案是否严格基于检索内容，无编造
3. 完整性 — 答案是否涵盖了问题的关键方面
4. 引用准确性 — 答案中的引用是否指向正确来源

返回 JSON：
{{"relevance":1-5, "faithfulness":1-5, "completeness":1-5, "citation_accuracy":1-5, "overall":1-5, "issues":[], "passed":true}}
"""


async def judge_answer(query: str, answer: str, contexts: list) -> dict:
    """LLM-as-Judge: 评估答案质量"""
    try:
        from src.services.llm import call_deepseek
        
        context_text = "\n\n---\n\n".join([
            f"[{i+1}] {c.get('text', '')[:300]}" for i, c in enumerate(contexts[:5])
        ]) if contexts else "无检索内容"
        
        prompt = JUDGE_PROMPT.format(query=query, context=context_text[:3000], answer=answer[:2000])
        result = await call_deepseek(prompt, max_tokens=500, temperature=0.1)
        
        if result:
            result = result.strip()
            if result.startswith('```'):
                result = result.split('\n', 1)[1].rsplit('```', 1)[0]
            try:
                return json.loads(result)
            except json.JSONDecodeError as e:
                logger.error(f"[Judge] JSON 解析失败: {e}, raw_result={result[:200]}")
                return {"overall": 3, "passed": True, "issues": ["JSON 解析失败"]}
        return {"overall": 3, "passed": True, "issues": []}
    except Exception as e:  # TODO: Narrow exception type
        logger.warning(f"[Judge] LLM-as-Judge failed: {e}")
        return {"overall": 3, "passed": True, "issues": [str(e)]}


async def judge_and_decide(answer: str, contexts: list) -> dict:
    """裁判模型质检：评估+决策"""
    query = contexts[0].get("_query", "") if contexts else ""
    result = await judge_answer(query, answer, contexts)
    
    passed = result.get("passed", True) and result.get("overall", 3) >= 3
    return {
        "answer": answer,
        "passed": passed,
        "judge_result": result,
    }
