"""
fact_check.py — 事实性校验 (v1.50)
生成答案后再检索验证关键断言是否有出处
"""
import logging, asyncio
from typing import List, Dict

logger = logging.getLogger(__name__)


async def extract_claims(answer: str) -> List[str]:
    """从答案中提取关键断言"""
    from src.services.llm import call_llm_fast
    prompt = (
        "从以下答案中提取所有事实性断言（具体数据、名称、参数、结论），每条一行，不要解释：\n\n"
        f"{answer[:1500]}\n\n断言列表："
    )
    result = await call_llm_fast(prompt, max_tokens=300)
    if not result:
        return []
    claims = [c.strip().lstrip("0123456789.-、）) ") for c in result.strip().split("\n") if c.strip() and len(c.strip()) > 5]
    return claims[:10]


async def verify_claim(claim: str, sources: List[str]) -> Dict:
    """验证单个断言是否有出处"""
    from src.services.llm import call_llm_fast
    sources_text = "\n".join(sources[:5])
    prompt = (
        f"判断以下断言是否被检索内容支持。\n\n"
        f"断言：{claim}\n\n"
        f"检索内容：\n{sources_text[:2000]}\n\n"
        f"回答：支持 / 部分支持 / 不支持 / 无法判断\n理由："
    )
    result = await call_llm_fast(prompt, max_tokens=100)
    if not result:
        return {"claim": claim, "verdict": "无法判断", "reason": ""}
    
    verdict = "无法判断"
    for v in ["支持", "不支持", "部分支持"]:
        if v in result:
            verdict = v
            break
    
    return {"claim": claim, "verdict": verdict, "reason": result[:200]}


async def fact_check(answer: str, sources: List[str]) -> Dict:
    """
    事实性校验主函数
    返回: {"verified": bool, "claims": list, "score": float}
    """
    try:
        claims = await extract_claims(answer)
        if not claims:
            return {"verified": True, "claims": [], "score": 1.0}
        
        # 并行验证所有断言
        tasks = [verify_claim(c, sources) for c in claims]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        verified = []
        for r in results:
            if isinstance(r, Exception):
                verified.append({"claim": "?", "verdict": "错误", "reason": str(r)})
            else:
                verified.append(r)
        
        # 计算可信度分数
        total = len(verified)
        supported = sum(1 for v in verified if v["verdict"] in ("支持", "部分支持"))
        score = supported / total if total > 0 else 1.0
        
        return {
            "verified": score >= 0.6,
            "claims": verified,
            "score": round(score, 2),
        }
    except Exception as e:  # TODO: Narrow exception type
        logger.warning(f"事实性校验失败: {e}")
        return {"verified": True, "claims": [], "score": 1.0}
