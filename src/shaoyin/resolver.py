"""
resolver.py — 少阴·指代消解
resolve_query + compress_history
"""
import logging
from typing import List, Dict

logger = logging.getLogger("shaoyin.resolver")


class QueryResolver:
    """指代消解器"""

    PRONOUNS = ["它", "他", "她", "这个", "那个", "上述", "前面提到的"]

    def resolve(self, query: str, history: List[Dict] = None) -> str:
        """消解指代"""
        if not history:
            return query

        needs_resolution = any(p in query for p in self.PRONOUNS)
        if not needs_resolution:
            return query

        context = self._extract_context(history)
        if context:
            resolved = query
            for pronoun in self.PRONOUNS:
                if pronoun in resolved:
                    resolved = resolved.replace(pronoun, context)
            return resolved

        return query

    def _extract_context(self, history: List[Dict]) -> str:
        for msg in reversed(history[-5:]):
            content = msg.get("content", "")
            if content and len(content) > 10:
                return content[:50]
        return ""


def compress_history(history: List[Dict], max_messages: int = 10) -> List[Dict]:
    """压缩历史"""
    if len(history) <= max_messages:
        return history

    recent = history[-max_messages:]
    summary_msg = {"role": "system", "content": f"（省略了{len(history) - max_messages}条历史消息）"}
    return [summary_msg] + recent
