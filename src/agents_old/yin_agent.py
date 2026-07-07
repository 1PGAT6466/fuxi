"""
yin_agent.py — 太极·阴 Agent v4.0
校验层：MiMo 2.5 Turbo + 规则校验 + 幻觉检测
"""
import json
import re
import logging
import time
from typing import Dict, List

from src.agents import BaseAgent, AgentContext

logger = logging.getLogger(__name__)

YIN_SYSTEM_PROMPT = """你是伏羲知识库的校验智能体。你的任务是判断回答是否合格。

## 校验规则（按优先级）
1. **事实性**：回答中的数字、型号、规格是否在来源中出现？编造的数字=不合格。
2. **来源引用**：有来源时是否引用？无来源时是否使用了"据/根据/研究表明"等词？
3. **完整性**：是否直接回答了用户问题？答非所问=不合格。
4. **安全性**：是否泄露内部信息？是否包含不当内容？

## 输出格式（严格 JSON）
{
  "passed": true/false,
  "score": 0-100,
  "issues": ["问题1", "问题2"],
  "suggestion": "改进建议",
  "need_redo": true/false,
  "reason": "判断理由"
}

## 重要
- 不要吹毛求疵。格式小问题不算不合格。
- 只有严重问题（编造数字、答非所问、泄露信息）才 need_redo=true。
- 保持客观，不要过度严格也不要放水。"""


class YinAgent(BaseAgent):
    """太极·阴 Agent：校验层"""

    def __init__(self):
        super().__init__(agent_id="yin", description="太极·阴 校验层")

    async def run(self, ctx: AgentContext) -> Dict:
        """阴·校验主逻辑"""
        start = time.time()
        answer = ctx.metadata.get("answer", "")
        sources = ctx.metadata.get("sources", [])
        query = ctx.query

        # Phase 1: 规则校验（快，零成本）
        rule_result = self._rule_check(answer, sources, query)

        # Phase 2: LLM 校验（慢，有成本，仅在规则发现问题时调用）
        if rule_result["issues"]:
            try:
                llm_result = await self._llm_verify(answer, sources, query, rule_result["issues"])
                duration = (time.time() - start) * 1000
                self._record_run(duration)
                return {
                    "success": True,
                    "passed": llm_result.get("passed", False),
                    "score": llm_result.get("score", 0),
                    "issues": llm_result.get("issues", rule_result["issues"]),
                    "suggestion": llm_result.get("suggestion", ""),
                    "need_redo": llm_result.get("need_redo", False),
                    "reason": llm_result.get("reason", ""),
                    "duration_ms": round(duration, 1),
                }
            except Exception as e:
                logger.warning(f"[Yin] LLM verify failed: {e}")

        duration = (time.time() - start) * 1000
        self._record_run(duration)
        return {
            "success": True,
            "passed": rule_result["passed"],
            "score": rule_result["score"],
            "issues": rule_result["issues"],
            "suggestion": rule_result["suggestion"],
            "need_redo": rule_result["need_redo"],
            "reason": rule_result["reason"],
            "duration_ms": round(duration, 1),
        }

    def _rule_check(self, answer: str, sources: List[Dict], query: str) -> Dict:
        """规则校验：快、零成本"""
        issues = []
        score = 100

        # 1. 答案长度检查
        if len(answer.strip()) < 20:
            issues.append("答案过短，可能信息不足")
            score -= 30

        # 2. 来源引用检查
        if sources and "[Ref" not in answer and "来源" not in answer[-300:]:
            issues.append("有来源但未在答案中引用")
            score -= 15

        # 3. 数字一致性检查（过滤材料名中的数字：PA66、POM、PC+ABS 等）
        numbers_in_answer = set(re.findall(r'\d+\.?\d*', answer))
        if numbers_in_answer and sources:
            source_text = " ".join(s.get("text", "") for s in sources[:5])
            numbers_in_source = set(re.findall(r'\d+\.?\d*', source_text))
            material_numbers = set()
            for match in re.findall(r'[A-Za-z]{2,}\d+', answer):
                material_numbers.update(re.findall(r'\d+\.?\d*', match))
            phantom_numbers = numbers_in_answer - numbers_in_source - material_numbers
            if len(phantom_numbers) > 3:
                issues.append(f"答案包含 {len(phantom_numbers)} 个来源中未出现的数字")
                score -= 25

        # 4. 幻觉关键词检测
        hallucination_phrases = ["据统计", "研究表明", "数据显示", "一般来说", "通常认为"]
        for phrase in hallucination_phrases:
            if phrase in answer and not sources:
                issues.append(f"答案使用了'{phrase}'但无来源支持")
                score -= 10

        # 5. 答非所问检测（简单关键词匹配）
        query_keywords = set(re.findall(r'[\u4e00-\u9fff]{2,}', query))
        if query_keywords and len(answer) > 50:
            answer_text = answer[:500]
            overlap = sum(1 for kw in query_keywords if kw in answer_text)
            if overlap == 0 and len(query_keywords) >= 2:
                issues.append("答案可能答非所问（与问题关键词无重叠）")
                score -= 20

        # 6. 安全性检查
        sensitive_patterns = [r'密码\s*[:：]\s*\S+', r'key\s*[:：]\s*\S+', r'token\s*[:：]\s*\S+']
        for pat in sensitive_patterns:
            if re.search(pat, answer, re.IGNORECASE):
                issues.append("答案可能泄露敏感信息")
                score -= 30

        score = max(score, 0)
        need_redo = score < 60
        passed = score >= 60

        return {
            "passed": passed,
            "score": score,
            "issues": issues,
            "suggestion": "请修正上述问题" if issues else "",
            "need_redo": need_redo,
            "reason": f"规则校验得分 {score}/100" if not issues else f"发现 {len(issues)} 个问题",
        }
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

    async def _llm_verify(self, answer: str, sources: List[Dict], query: str, rule_issues: List[str]) -> Dict:
        """LLM 校验：慢、有成本，仅在规则发现问题时调用"""
        from src.services.llm import call_deepseek

        source_texts = [s.get("text", "")[:200] for s in sources[:3]]
        judge_prompt = f"""请判断以下回答是否存在问题：

问题：{query}
回答：{answer[:500]}
来源：{json.dumps(source_texts, ensure_ascii=False)}
规则检测到的问题：{', '.join(rule_issues)}

请判断：
1. 这些问题是否真实存在（不是误报）
2. 回答是否需要重做

输出 JSON：{{"confirmed_issues": [...], "need_redo": true/false, "reason": "...", "score": 0-100}}"""

        result = await call_deepseek(judge_prompt, max_tokens=300, temperature=0.1)
        if result:
            try:
                judge = json.loads(result)
                return {
                    "passed": not judge.get("need_redo", False),
                    "score": judge.get("score", 60),
                    "issues": judge.get("confirmed_issues", rule_issues),
                    "suggestion": judge.get("reason", ""),
                    "need_redo": judge.get("need_redo", False),
                    "reason": judge.get("reason", ""),
                }
            except json.JSONDecodeError as e:
                logger.warning("json.JSONDecodeError 失败: %s", e, exc_info=True)

        return {
            "passed": False,
            "score": 50,
            "issues": rule_issues,
            "need_redo": True,
            "reason": "LLM 校验失败，信任规则校验结果",
        }
