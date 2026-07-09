"""
evaluator.py — Phase 1.3.2: RAG 自动化评测器（LLM-as-Judge）
"""
import json, logging, time, requests
from typing import List, Dict

logger = logging.getLogger(__name__)

import os
MIMO_API_KEY = os.getenv("MIMO_API_KEY", "")
MIMO_BASE_URL = os.getenv("MIMO_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")


def _llm_judge(prompt: str, max_tokens: int = 500) -> str:
    """调用 LLM 做评判"""
    try:
        r = requests.post(
            f"{MIMO_BASE_URL}/chat/completions",
            json={
                "model": "mimo-v2.5",
                "messages": [
                    {"role": "system", "content": "你是 RAG 质量评测专家。只输出 JSON，不要多余文字。"},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": 0.1
            },
            headers={"Authorization": f"Bearer {MIMO_API_KEY}", "Content-Type": "application/json"},
            timeout=30
        )
        return r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        logger.warning(f"LLM judge failed: {e}")
        return ""


def eval_relevancy(query: str, results: List[Dict]) -> Dict:
    """评估检索结果的相关性（Context Relevancy）"""
    if not results:
        return {"score": 0, "detail": "无检索结果"}
    
    docs_text = "\n".join([f"[{i+1}] {(r.get('text','') or '')[:200]}" for i, r in enumerate(results[:5])])
    prompt = f"""判断以下检索结果与用户问题的相关性。

用户问题：{query}
检索结果：
{docs_text}

对每个结果判断：relevant / partially / irrelevant
输出 JSON：{{"scores": ["relevant", "relevant", ...], "avg_score": 0.0-1.0}}"""
    
    resp = _llm_judge(prompt)
    try:
        s = resp.find("{")
        e = resp.rfind("}") + 1
        if s >= 0 and e > s:
            return json.loads(resp[s:e])
    except json.JSONDecodeError as e:
        logger.error(f"eval_relevancy JSON 解析失败: {e}, resp={resp[:200]}")
    except Exception:
        pass
    return {"score": 0.5, "detail": "LLM 评判解析失败"}


def eval_faithfulness(query: str, answer: str, context: str) -> Dict:
    """评估回答的忠实度（Faithfulness）"""
    prompt = f"""检查以下回答是否忠实于提供的上下文。
对回答中的每个事实性声明，判断是否有上下文支持。

用户问题：{query}
上下文：{context[:2000]}
回答：{answer[:1000]}

输出 JSON：{{"faithfulness_score": 0.0-1.0, "unsupported_claims": ["声明1"], "supported_claims": ["声明2"]}}"""
    
    resp = _llm_judge(prompt)
    try:
        s = resp.find("{")
        e = resp.rfind("}") + 1
        if s >= 0 and e > s:
            return json.loads(resp[s:e])
    except json.JSONDecodeError as e:
        logger.error(f"eval_faithfulness JSON 解析失败: {e}, resp={resp[:200]}")
    except Exception:
        pass
    return {"faithfulness_score": 0.5, "detail": "LLM 评判解析失败"}


def eval_answer_relevancy(query: str, answer: str) -> float:
    """评估回答与问题的相关性（Answer Relevancy）"""
    prompt = f"""判断以下回答是否回答了用户的问题。
用户问题：{query}
回答：{answer[:500]}

评分 0-1（0=完全不相关，1=完全回答了问题）
只输出数字，不要其他文字。"""
    
    resp = _llm_judge(prompt, max_tokens=10)
    try:
        return float(resp.strip())
    except Exception as e:
        logger.warning("回答相关性评分解析失败: %s", e, exc_info=True)
        return 0.5
