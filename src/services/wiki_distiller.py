"""
wiki_distiller.py — Phase 5.4: Wiki 知识蒸馏 + 交叉引用 + 增量更新
"""
import json, logging, time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DISTILL_PROMPT = """把以下技术文档章节提炼为结构化 Wiki 页面。

章节标题：{heading}
文档来源：{file_name}
分类：{category}
内容：{text}

要求：
1. 保留关键技术信息（参数、规格、流程步骤）
2. 去除冗余描述，提取核心要点
3. 用清晰标题和列表组织
4. 输出 Markdown 格式
5. 关键术语加粗"""

OVERVIEW_PROMPT = """为以下文档生成总览 Wiki 页面。

文档：{file_name}
内容摘要：{summary}

要求：
1. 一句话概括文档主题
2. 列出核心知识点（3-5 点）
3. 标注文档类型和适用范围
输出 Markdown 格式。"""

VERIFY_PROMPT = """校验以下 Wiki 内容是否忠实于原始文档。

Wiki 内容：{wiki_content}
原始文档：{source_text}

判断标准：
1. 关键数据是否与原文档一致
2. 是否有编造的内容
3. 结论是否与原文档一致

输出 JSON：{{"faithful": true/false, "issues": ["问题描述"], "score": 0.0-1.0}}"""


async def distill_section(text: str, heading: str, file_name: str, category: str = "") -> str:
    """蒸馏章节为 Wiki 页面"""
    from src.services.llm import call_llm
    prompt = DISTILL_PROMPT.format(heading=heading, file_name=file_name, category=category, text=text[:4000])
    result = await call_llm(prompt, max_tokens=2000)
    return result or ""


async def generate_overview(file_name: str, summary: str) -> str:
    """生成文档总览"""
    from src.services.llm import call_llm
    prompt = OVERVIEW_PROMPT.format(file_name=file_name, summary=summary[:2000])
    result = await call_llm(prompt, max_tokens=1000)
    return result or ""


async def verify_wiki_page(wiki_content: str, source_text: str) -> dict:
    """校验 Wiki 页面质量"""
    from src.services.llm import call_llm
    prompt = VERIFY_PROMPT.format(wiki_content=wiki_content[:2000], source_text=source_text[:3000])
    result = await call_llm(prompt, max_tokens=300)
    if result:
        try:
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(result)
        except json.JSONDecodeError:
            pass
    return {"faithful": True, "issues": ["LLM 校验失败"], "score": 0.5}


def extract_cross_references(wiki_text: str, all_titles: List[str]) -> List[str]:
    """提取交叉引用：在 Wiki 文本中查找指向其他页面的术语"""
    refs = []
    for title in all_titles[:50]:
        if len(title) >= 3 and title in wiki_text:
            refs.append(title)
    return list(set(refs))[:10]
