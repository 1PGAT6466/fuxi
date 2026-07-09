"""
long_doc_handler.py — Phase 6.6: 长文档处理
文档级摘要索引 + 层级分块 + 跨 chunk 上下文
"""
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


async def generate_doc_summary(text: str, file_name: str, max_length: int = 500) -> str:
    """生成文档级摘要"""
    from src.services.llm import call_deepseek
    prompt = f"用 3-5 句话概括以下文档的核心内容：\n\n文件：{file_name}\n内容：{text[:3000]}\n\n摘要："
    result = await call_deepseek(prompt, max_tokens=300)
    return result or text[:max_length]


class HierarchicalIndex:
    """三级索引：章节 → 段落 → 句子"""
    
    def __init__(self):
        self._sections: Dict[str, dict] = {}  # section_id → {title, summary, paragraphs}
        self._paragraphs: Dict[str, list] = {}  # paragraph_id → [sentence_ids]
    
    def add_section(self, section_id: str, title: str, summary: str):
        self._sections[section_id] = {"title": title, "summary": summary, "paragraphs": []}
    
    def add_paragraph(self, section_id: str, para_id: str, sentences: List[str]):
        self._paragraphs[para_id] = sentences
        if section_id in self._sections:
            self._sections[section_id]["paragraphs"].append(para_id)
    
    def search_coarse(self, query: str) -> List[str]:
        """粗筛：匹配章节标题/摘要"""
        matched = []
        q_lower = query.lower()
        for sid, sec in self._sections.items():
            if any(kw in sec["title"].lower() or kw in sec["summary"].lower() for kw in q_lower.split()):
                matched.append(sid)
        return matched
    
    def search_fine(self, section_id: str, query: str) -> List[str]:
        """精筛：匹配段落/句子"""
        para_ids = self._sections.get(section_id, {}).get("paragraphs", [])
        results = []
        for pid in para_ids:
            sentences = self._paragraphs.get(pid, [])
            for sent in sentences:
                if any(kw in sent.lower() for kw in query.lower().split()):
                    results.append(sent)
        return results[:5]
    
    def expand_context(self, para_id: str, window: int = 2) -> List[str]:
        """跨 chunk 上下文扩展"""
        # 获取前后 paragraph 的句子
        all_paras = list(self._paragraphs.keys())
        idx = all_paras.index(para_id) if para_id in all_paras else -1
        if idx < 0:
            return []
        start = max(0, idx - window)
        end = min(len(all_paras), idx + window + 1)
        result = []
        for i in range(start, end):
            result.extend(self._paragraphs.get(all_paras[i], []))
        return result


_hier_index = None

def get_hierarchical_index() -> HierarchicalIndex:
    global _hier_index
    if _hier_index is None:
        _hier_index = HierarchicalIndex()
    return _hier_index
