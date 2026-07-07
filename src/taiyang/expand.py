"""
expand.py — 太阳·查询扩展
同义词扩展 + 意图识别
"""
import logging
from typing import List, Dict

logger = logging.getLogger("taiyang.expand")


class QueryExpander:
    """查询扩展器"""

    def expand(self, query: str) -> List[str]:
        """扩展查询"""
        expanded = [query]

        synonyms = self._get_synonyms(query)
        expanded.extend(synonyms)

        return list(set(expanded))

    def _get_synonyms(self, query: str) -> List[str]:
        """获取同义词"""
        try:
            from src.taiyang.synonym_loader import load_synonyms
            synonyms_map = load_synonyms()
            result = []
            for word, syns in synonyms_map.items():
                if word in query:
                    for syn in syns:
                        result.append(query.replace(word, syn))
            return result[:5]
        except Exception as e:
            logger.warning("Exception 失败: %s", e, exc_info=True)
            return []
