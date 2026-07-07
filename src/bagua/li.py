#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
li.py — 离卦 ☲ · 伏羲 v2.1

离为火，主知识蒸馏与推理。
对应能力：LLM 推理、知识蒸馏、内容生成、结果后处理。

Phase 2 实现：
  - 核心检索逻辑 execute()：基于关键词匹配的本地知识检索
  - 降级规则：LLM 不可用时使用纯关键词匹配
  - 支持多轮查询和结果截断
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.bagua.base_gua import (
    GuaBase,
    DegradationRule,
    FallbackAction,
)

logger = logging.getLogger("bagua.li")


class LiGua(GuaBase):
    """离卦 — 知识蒸馏与推理

    离卦代表光明与智慧，负责：
      - 本地知识检索（关键词匹配 + 排序）
      - 内容蒸馏（从长文本提取精华）
      - 推理链生成

    Usage::

        li = LiGua()
        li.start()

        result = li.execute({
            "action": "search",
            "query": "Python 性能优化",
            "documents": [...],
            "top_k": 5,
        })

        # 或蒸馏已有内容
        result = li.execute({
            "action": "distill",
            "content": "大量文本...",
            "max_length": 200,
        })

        li.stop()
    """

    GUA_NAME: str = "li"
    GUA_EMOJI: str = "☲"
    GUA_DESCRIPTION: str = "知识蒸馏与推理 — LLM、蒸馏、生成、后处理"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        # 注册外部依赖
        self.register_dependency("llm", failure_threshold=3)
        self.register_dependency("vectordb", failure_threshold=5)

    # ========================================================================
    # GuaBase 抽象方法实现
    # ========================================================================

    def _setup_degradation_rules(self) -> None:
        """注册离卦降级规则

        1. LLM 不可用时降级为纯关键词匹配（priority=10）
        2. 向量数据库不可用时降级为内存搜索（priority=5）
        """
        llm_cb = self._circuits.get("llm")
        vectordb_cb = self._circuits.get("vectordb")

        # 规则 10: LLM 不可用 → 纯关键词模式
        self.add_rule(DegradationRule(
            name="llm_unavailable",
            condition_fn=lambda: (
                llm_cb is not None and not llm_cb.is_healthy
            ),
            fallback=FallbackAction(
                name="keyword_only_fallback",
                handler=self._fallback_keyword_only,
                description="LLM 不可用时使用纯关键词匹配",
            ),
            priority=10,
        ))

        # 规则 5: 向量数据库不可用 → 内存搜索
        self.add_rule(DegradationRule(
            name="vectordb_unavailable",
            condition_fn=lambda: (
                vectordb_cb is not None and not vectordb_cb.is_healthy
            ),
            fallback=FallbackAction(
                name="memory_search_fallback",
                handler=self._fallback_memory_search,
                description="向量数据库不可用时使用内存关键词搜索",
            ),
            priority=5,
        ))

    def _execute_core(self, params: Dict[str, Any]) -> Any:
        """核心执行 — 按 action 字段分发

        Supported actions:
            - "search":    关键词检索给定文档列表
            - "distill":   蒸馏/截断长文本
            - "compare":   对比两个结果集选出最佳
            - "summarize": 摘要生成

        Args:
            params: {
                "action": "search" | "distill" | "compare" | "summarize",
                ... (各 action 特有参数)
            }

        Returns:
            各 action 的返回值

        Raises:
            ValueError: 未知 action
        """
        action = params.get("action", "search")

        if action == "search":
            return self._search(
                query=params.get("query", ""),
                documents=params.get("documents", []),
                top_k=params.get("top_k", 5),
            )

        if action == "distill":
            return self._distill(
                content=params.get("content", ""),
                query=params.get("query", ""),
                max_length=params.get("max_length", 200),
            )

        if action == "compare":
            return self._compare(
                candidates=params.get("candidates", []),
                query=params.get("query", ""),
                top_k=params.get("top_k", 3),
            )

        if action == "summarize":
            return self._summarize(
                content=params.get("content", ""),
                max_length=params.get("max_length", 100),
            )

        raise ValueError(
            f"[{self.GUA_NAME}] 未知 action: {action}。"
            f"支持: search, distill, compare, summarize"
        )

    # ========================================================================
    # 核心能力
    # ========================================================================

    def _search(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """关键词检索给定文档列表

        使用简单 TF（词频）计分匹配 query 与 documents 中的 content。

        Args:
            query:     检索查询
            documents: 文档列表 [{"doc_id": str, "content": str, ...}]
            top_k:     返回结果数

        Returns:
            {
                "results": [...],
                "total_matched": int,
                "query": str,
                "mode": str,
            }
        """
        if not query or not documents:
            return {
                "results": [],
                "total_matched": 0,
                "query": query,
                "mode": "keyword_tf",
            }

        # 分词
        query_terms = _tokenize(query)

        if not query_terms:
            return {
                "results": [],
                "total_matched": 0,
                "query": query,
                "mode": "keyword_tf",
            }

        # 计算每个文档的 TF 分数
        scored: List[tuple] = []
        for doc in documents:
            content = doc.get("content", "")
            if not content:
                continue

            content_tokens = _tokenize(content)
            if not content_tokens:
                continue

            # TF 计分：query 中每个 term 在文档中出现的次数 / 文档词数
            score = 0.0
            for term in query_terms:
                tf = content_tokens.count(term) / max(len(content_tokens), 1)
                score += tf

            if score > 0:
                scored.append((doc, score))

        # 按分数降序排列
        scored.sort(key=lambda x: x[1], reverse=True)

        top_results = scored[:top_k]

        results = []
        for doc, score in top_results:
            content = doc.get("content", "")
            preview = content[:300] if len(content) > 300 else content
            results.append({
                "doc_id": doc.get("doc_id", ""),
                "content": content,
                "preview": preview,
                "score": round(score, 4),
                "source": doc.get("source", ""),
                "category": doc.get("category", ""),
            })

        return {
            "results": results,
            "total_matched": len(scored),
            "query": query,
            "mode": "keyword_tf",
        }

    def _distill(
        self,
        content: str,
        query: str = "",
        max_length: int = 200,
    ) -> Dict[str, Any]:
        """蒸馏/截断长文本，提取与查询最相关的部分

        Args:
            content:    原始长文本
            query:      查询（用于相关度评分）
            max_length: 最大输出长度（字符数）

        Returns:
            {"distilled": str, "original_length": int, "truncated": bool}
        """
        if not content:
            return {"distilled": "", "original_length": 0, "truncated": False}

        original_length = len(content)

        # 如果原文本已经较短，不需要蒸馏
        if original_length <= max_length:
            return {"distilled": content, "original_length": original_length, "truncated": False}

        # 有 query → 提取最相关的片段
        if query and len(content) > max_length:
            # 找到 query 相关度最高的段落
            distilled = _extract_relevant_paragraph(content, query, max_length)
        else:
            # 无 query → 取开头 + 结尾摘录
            half = max_length // 2
            distilled = content[:half] + "\n...(省略)...\n" + content[-half:]

        return {
            "distilled": distilled,
            "original_length": original_length,
            "truncated": True,
        }

    def _compare(
        self,
        candidates: List[Dict[str, Any]],
        query: str = "",
        top_k: int = 3,
    ) -> Dict[str, Any]:
        """对比多个候选结果，选出最佳

        Args:
            candidates: 候选列表 [{"id": str, "content": str, "score": float}]
            query:      原始查询
            top_k:      保留结果数

        Returns:
            {"ranked": [...], "best": {...}, "total": int}
        """
        if not candidates:
            return {"ranked": [], "best": None, "total": 0}

        # 按已有 score 排序，没有 score 的重新计算
        ranked = []
        for c in candidates:
            score = c.get("score", 0)
            if score == 0 and query:
                content = c.get("content", "")
                if content:
                    query_terms = _tokenize(query)
                    content_tokens = _tokenize(content)
                    for term in query_terms:
                        score += content_tokens.count(term) / max(len(content_tokens), 1)
            ranked.append((c, score))

        ranked.sort(key=lambda x: x[1], reverse=True)

        top = [{"item": item, "score": round(score, 4)} for item, score in ranked[:top_k]]

        return {
            "ranked": top,
            "best": top[0] if top else None,
            "total": len(candidates),
        }

    def _summarize(
        self,
        content: str,
        max_length: int = 100,
    ) -> Dict[str, Any]:
        """简单摘要：截取开头 + 统计信息

        Args:
            content:    原始文本
            max_length: 最大摘要长度

        Returns:
            {"summary": str, "stats": {...}}
        """
        if not content:
            return {"summary": "", "stats": {"chars": 0, "lines": 0}}

        lines = content.strip().split("\n")
        words = content.split()

        # 简单摘要：第一句或截断
        summary = content[:max_length].rsplit("。", 1)[0] + "。"
        if len(summary) > max_length:
            summary = content[:max_length] + "..."

        return {
            "summary": summary,
            "stats": {
                "chars": len(content),
                "lines": len(lines),
                "words": len(words),
            },
        }

    # ========================================================================
    # 降级处理
    # ========================================================================

    def _fallback_keyword_only(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """LLM 不可用 → 纯关键词模式降级"""
        action = params.get("action", "search")
        if action == "search":
            return self._search(
                query=params.get("query", ""),
                documents=params.get("documents", []),
                top_k=params.get("top_k", 5),
            )
        if action == "distill":
            content = params.get("content", "")
            return self._distill(
                content=content,
                query=params.get("query", ""),
                max_length=params.get("max_length", 200),
            )
        if action == "summarize":
            content = params.get("content", "")
            return self._summarize(
                content=content,
                max_length=params.get("max_length", 100),
            )
        return {"results": [], "mode": "fallback_keyword_only", "degraded": True}

    def _fallback_memory_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """向量数据库不可用 → 内存搜索降级"""
        action = params.get("action", "search")
        if action == "search":
            return self._search(
                query=params.get("query", ""),
                documents=params.get("documents", []),
                top_k=params.get("top_k", 5),
            )
        return {"results": [], "mode": "fallback_memory_search", "degraded": True}


# ============================================================================
# 辅助函数
# ============================================================================


def _tokenize(text: str) -> List[str]:
    """简易中文+英文混合分词

    Args:
        text: 输入文本

    Returns:
        词元列表（已转小写）
    """
    import re
    # 匹配中文连续 1+ 字 或 英文连续 2+ 字母
    tokens = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]{2,}', text.lower())
    return tokens


def _extract_relevant_paragraph(text: str, query: str, max_length: int) -> str:
    """从长文本中提取与 query 最相关的段落

    Args:
        text:       原始长文本
        query:      查询词
        max_length: 最大长度

    Returns:
        蒸馏后的文本
    """
    # 按段落分割
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    if not paragraphs:
        return text[:max_length]

    query_terms = _tokenize(query)

    if not query_terms:
        half = max_length // 2
        return text[:half] + "\n...(省略)...\n" + text[-half:]

    # 对每个段落打分
    scored_paragraphs = []
    for p in paragraphs:
        p_tokens = _tokenize(p)
        score = 0.0
        for term in query_terms:
            if term in p_tokens:
                score += 1.0
        scored_paragraphs.append((p, score))

    # 按分数排序，取最好的段落
    scored_paragraphs.sort(key=lambda x: x[1], reverse=True)

    result = ""
    for p, _ in scored_paragraphs:
        if len(result) + len(p) + 2 > max_length:
            # 还能拼一些，截断
            remaining = max_length - len(result) - 2
            if remaining > 20:
                result += p[:remaining] + "..."
            break
        result += p + "\n"

    return result.strip() or text[:max_length]


__all__ = ["LiGua", "_tokenize"]
