"""
kun/wiki_manager.py — 坤卦 Wiki 管理
====================================

管理 Wiki 统一知识库接口。
"""

import logging
import time
from typing import Any, Dict, List, Optional

from src.bagua.kun.utils import compute_content_hash, extract_keywords

logger = logging.getLogger("bagua.kun")


class WikiManager:
    """Wiki 管理器

    管理 Wiki 统一知识库接口。

    Attributes:
        wiki_pages: Wiki 页面字典
        keyword_index: 关键词倒排索引
    """

    def __init__(self):
        """初始化 Wiki 管理器"""
        self.wiki_pages: Dict[str, Dict[str, Any]] = {}
        self.keyword_index: Dict[str, List[str]] = {}

    def push_to_wiki(
        self,
        doc_id: str,
        content: str,
        title: Optional[str] = None,
        category: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """推送 Wiki 页面

        Args:
            doc_id: 文档 ID
            content: 内容
            title: 标题
            category: 分类
            metadata: 元数据

        Returns:
            是否成功
        """
        try:
            # 内容去重
            content_hash = compute_content_hash(content)
            if content_hash in [page.get("content_hash") for page in self.wiki_pages.values()]:
                logger.info(f"Wiki 页面已存在: {doc_id}")
                return False

            # 自动分类
            if not category:
                category = self._classify_content(content)

            # 创建 Wiki 页面
            wiki_page = {
                "doc_id": doc_id,
                "content": content,
                "content_hash": content_hash,
                "title": title or doc_id,
                "category": category,
                "metadata": metadata or {},
                "created_at": time.time(),
                "updated_at": time.time(),
            }

            self.wiki_pages[doc_id] = wiki_page

            # 建立关键词倒排索引
            self._index_keywords(doc_id, content)

            logger.info(f"推送 Wiki 页面成功: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"推送 Wiki 页面失败: {e}")
            return False

    def recall_wiki(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """召回 Wiki 页面

        Args:
            query: 查询
            limit: 数量限制

        Returns:
            Wiki 页面列表
        """
        try:
            # 关键词搜索
            doc_ids = self._keyword_search(query)

            # 获取 Wiki 页面
            wiki_pages = []
            for doc_id in doc_ids[:limit]:
                if doc_id in self.wiki_pages:
                    wiki_pages.append(self.wiki_pages[doc_id])

            return wiki_pages
        except Exception as e:
            logger.error(f"召回 Wiki 页面失败: {e}")
            return []

    def _classify_content(self, content: str) -> str:
        """分类内容

        Args:
            content: 内容

        Returns:
            分类
        """
        # 简单实现：根据关键词分类
        keywords = extract_keywords(content)

        if any(keyword in ["Python", "Java", "JavaScript", "C++"] for keyword in keywords):
            return "编程"
        elif any(keyword in ["机器学习", "深度学习", "AI", "人工智能"] for keyword in keywords):
            return "AI"
        elif any(keyword in ["数据库", "SQL", "MySQL", "PostgreSQL"] for keyword in keywords):
            return "数据库"
        else:
            return "其他"

    def _index_keywords(self, doc_id: str, content: str) -> None:
        """建立关键词倒排索引

        Args:
            doc_id: 文档 ID
            content: 内容
        """
        try:
            keywords = extract_keywords(content)

            for keyword in keywords:
                if keyword not in self.keyword_index:
                    self.keyword_index[keyword] = []
                if doc_id not in self.keyword_index[keyword]:
                    self.keyword_index[keyword].append(doc_id)
        except Exception as e:
            logger.error(f"建立关键词倒排索引失败: {e}")

    def _keyword_search(self, query: str) -> List[str]:
        """关键词搜索

        Args:
            query: 查询

        Returns:
            文档 ID 列表
        """
        try:
            keywords = extract_keywords(query)

            # 收集所有匹配的文档 ID
            doc_ids = []
            for keyword in keywords:
                if keyword in self.keyword_index:
                    doc_ids.extend(self.keyword_index[keyword])

            # 去重
            doc_ids = list(set(doc_ids))

            return doc_ids
        except Exception as e:
            logger.error(f"关键词搜索失败: {e}")
            return []

    def get_wiki_stats(self) -> Dict[str, Any]:
        """获取 Wiki 统计

        Returns:
            Wiki 统计
        """
        try:
            total_pages = len(self.wiki_pages)
            total_keywords = len(self.keyword_index)

            # 按分类统计
            categories = {}
            for page in self.wiki_pages.values():
                category = page.get("category", "其他")
                categories[category] = categories.get(category, 0) + 1

            return {
                "total_pages": total_pages,
                "total_keywords": total_keywords,
                "categories": categories,
            }
        except Exception as e:
            logger.error(f"获取 Wiki 统计失败: {e}")
            return {}

    def get_page(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """获取 Wiki 页面

        Args:
            doc_id: 文档 ID

        Returns:
            Wiki 页面
        """
        return self.wiki_pages.get(doc_id)

    def clear_wiki(self) -> bool:
        """清空 Wiki

        Returns:
            是否成功
        """
        try:
            self.wiki_pages.clear()
            self.keyword_index.clear()
            return True
        except Exception as e:
            logger.error(f"清空 Wiki 失败: {e}")
            return False
