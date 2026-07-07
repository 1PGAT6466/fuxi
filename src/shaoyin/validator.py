"""
validator.py — 少阴·校验模块
合并 yin_agent + judge 的校验逻辑
"""
import re
import logging
from typing import Dict, List, Any

logger = logging.getLogger("shaoyin.validator")


class YinAgent:
    """阴·校验层 — 规则 + LLM 双层校验"""

    def __init__(self):
        pass

    # DEPRECATED: 未使用，v1.50 标记待删除
    def _rule_check(self, answer: str, sources: List[Dict], query: str) -> Dict:
        """规则校验（零成本）"""
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

        # 3. 数字一致性检查（过滤材料名中的数字）
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

        # 5. 答非所问检测
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
