#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kun.py — 坤卦 ☷ · 伏羲 v2.1 Phase 1

坤为地，厚德载物。
主记忆存储与管理：

Phase 1 器官迁移：
  - 心(HeartAgent) → 坤卦：短期对话记忆 + 用户偏好
  - 脾(SpleenAgent) → 坤卦：Wiki 统一知识库接口

能力清单：
  - 短期对话记忆（200 条上限，按 session_id 隔离）
  - 记忆召回（最近 N 条）
  - 用户偏好存取（键值）
  - Wiki 页面存储（push_to_wiki，含内容去重 + 自动分类）
  - Wiki 内容检索（recall_wiki，含关键词倒排索引）
  - Wiki 统计（get_wiki_stats）
  - [v2.2] 向量存储接口 store_vector()
  - [v2.2] 知识图谱接口 store_graph()
  - [v2.2] Wiki 持久化接口 store_wiki()
  - [v2.2] 知识图谱自动构建 build_knowledge_graph()

通过 GuaBase.execute() 统一入口：
  - action="store_conversation" → store_conversation()
  - action="recall_conversation" → recall_conversation()
  - action="set_preference"      → set_preference()
  - action="get_preference"      → get_preference()
  - action="push"                → push_to_wiki()
  - action="recall"              → recall_wiki()
  - action="stats"               → get_wiki_stats() + get_stats()
  - action="clear"               → clear_wiki()
  - action="store_vector"        → store_vector()
  - action="store_graph"         → store_graph()
  - action="store_wiki"          → store_wiki()
  - action="build_kg"            → build_knowledge_graph()
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.bagua.base_gua import (
    GuaBase,
    DegradationRule,
    FallbackAction,
)
from src.bagua.auto_graph import get_auto_graph_builder

logger = logging.getLogger("bagua.kun")

# 短期记忆上限
SHORT_TERM_MAX: int = 200

# Session TTL（秒）— 超过此时间未活动的 session 将被自动清理
SESSION_TTL: float = 3600.0

# 全局 session 数量上限
SESSION_MAX_COUNT: int = 1000


class KunGua(GuaBase):
    """坤卦 ☷ — 记忆存储与管理

    坤卦厚重、承载万物，负责系统的一切"记忆"相关功能：

    心迁移能力：
      - 短期对话记忆：保存最近 200 条对话
      - 记忆召回：按数量召回最近 N 条
      - 用户偏好：键值对形式的用户偏好存取

    脾迁移能力：
      - Wiki 统一知识库接口：push_to_wiki / recall_wiki / get_wiki_stats
      - 内容去重（按 content hash）
      - 关键词倒排索引

    Usage::

        kun = KunGua()
        kun.start()

        # 通过 execute() 统一入口
        kun.execute({"action": "store_conversation", "session_id": "s1",
                      "role": "user", "content": "你好"})
        kun.execute({"action": "push",
                      "doc_id": "page-001",
                      "content": "Python 是一种编程语言。"})
        kun.execute({"action": "recall", "query": "Python"})
        kun.execute({"action": "stats"})

        kun.stop()

    Attributes:
        GUA_NAME:              卦名 "kun"
        GUA_EMOJI:             "☷"
        GUA_DESCRIPTION:       卦述
        SHORT_TERM_MAX:        短期记忆上限（200）
    """

    GUA_NAME: str = "kun"
    GUA_EMOJI: str = "☷"
    GUA_DESCRIPTION: str = "记忆存储与管理 — 短期记忆/Wiki知识库/用户偏好"

    SHORT_TERM_MAX: int = SHORT_TERM_MAX
    SESSION_TTL: float = SESSION_TTL
    SESSION_MAX_COUNT: int = SESSION_MAX_COUNT

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        # ================================================================
        #  短期记忆（心/HeartAgent 迁移）
        # ================================================================
        # {session_id: [{"role": str, "content": str, "time": float}, ...]}
        self._short_term: Dict[str, List[Dict[str, Any]]] = {}

        # 用户偏好：{session_id: {key: value}}
        self._preferences: Dict[str, Dict[str, Any]] = {}

        # Session 最后活动时间戳：{session_id: last_activity_float}
        self._session_activity: Dict[str, float] = {}

        # 存储计数
        self._memories_stored: int = 0

        # ================================================================
        #  Wiki 统一知识库（脾/SpleenAgent 迁移）
        # ================================================================
        # {doc_id: {content, hash, category, tags, created_at, ...}}
        self._wiki_store: Dict[str, Dict[str, Any]] = {}

        # 内容 hash → doc_id 索引（用于去重）
        self._content_hash_index: Dict[str, str] = {}

        # 简单关键词倒排索引 {term: [doc_id, ...]}
        self._keyword_index: Dict[str, List[str]] = {}

        # Wiki 存储计数（从脾迁移的 _stored_total）
        self._stored_total: int = 0

        # 注册外部依赖
        self.register_dependency("wiki_engine", failure_threshold=3)

    # ========================================================================
    # GuaBase 抽象方法实现
    # ========================================================================

    def _setup_degradation_rules(self) -> None:
        """注册坤卦降级规则

        1. 记忆超载时自动精简（priority=10）
        2. Wiki 引擎不可用时空结果降级（priority=5）
        """
        # 规则 10: 记忆存储上限触发精简
        self.add_rule(DegradationRule(
            name="memory_overload",
            condition_fn=lambda: self._check_memory_overload(),
            fallback=FallbackAction(
                name="trim_memory",
                handler=self._fallback_trim_memory,
                description="记忆超载时自动精简",
            ),
            priority=10,
        ))

        def _empty_recall(params: Dict[str, Any]) -> list:
            return []

        def _empty_stats(params: Dict[str, Any]) -> dict:
            return {"total_pages": 0, "stored_total": self._stored_total, "degraded": True}

        wiki_cb = self._circuits.get("wiki_engine")

        # 规则 5: Wiki 引擎不可用时降级
        self.add_rule(DegradationRule(
            name="wiki_engine_unavailable",
            condition_fn=lambda: (
                wiki_cb is not None
                and not wiki_cb.is_healthy
            ),
            fallback=FallbackAction(
                name="empty_wiki_fallback",
                handler=_empty_recall,
                description="Wiki 引擎不可用时返回空结果",
            ),
            priority=5,
        ))

    def _execute_core(self, params: Dict[str, Any]) -> Any:
        """核心执行 — 按 action 字段分发

        Args:
            params: {
                "action": "store_conversation" | "recall_conversation"
                          | "set_preference" | "get_preference"
                          | "push" | "recall" | "stats" | "clear",
                ... (各 action 特有参数)
            }

        Returns:
            各 action 的返回值

        Raises:
            ValueError: 未知 action
        """
        action = params.get("action", "")

        # ---- 短期记忆（心迁移） ----
        if action == "store_conversation":
            return self.store_conversation(
                session_id=params.get("session_id", "default"),
                role=params.get("role", "user"),
                content=params.get("content", ""),
            )

        if action == "recall_conversation":
            return self.recall_conversation(
                session_id=params.get("session_id", "default"),
                n=params.get("n", 10),
            )

        if action == "set_preference":
            self.set_preference(
                session_id=params.get("session_id", "default"),
                key=params.get("key", ""),
                value=params.get("value", ""),
            )
            return {"ok": True, "key": params.get("key", "")}

        if action == "get_preference":
            value = self.get_preference(
                session_id=params.get("session_id", "default"),
                key=params.get("key", ""),
            )
            return {"key": params.get("key", ""), "value": value}

        # ---- Wiki 知识库（脾迁移） ----
        if action == "push":
            doc_id = params.get("doc_id", "")
            content = params.get("content", "")
            if not content:
                raise ValueError("push 需要 content 参数")
            return self.push_to_wiki(
                doc_id=doc_id,
                content=content,
                category=params.get("category", ""),
                tags=params.get("tags", []),
            )

        if action == "recall":
            query = params.get("query", "")
            top_k = params.get("top_k", 5)
            return self.recall_wiki(query=query, top_k=top_k)

        if action == "stats":
            # 合并两种统计
            mem_stats = self.get_stats()
            wiki_stats = self.get_wiki_stats()
            return {**mem_stats, **wiki_stats}

        if action == "clear":
            self.clear_wiki()
            return {"ok": True, "message": "Wiki 存储已清空"}

        # ---- v2.2 标准化存储接口 ----
        if action == "store_vector":
            return self.store_vector(
                doc_id=params.get("doc_id", ""),
                chunks=params.get("chunks", []),
                metadata=params.get("metadata", {}),
            )

        if action == "store_wiki":
            return self.store_wiki(
                doc_id=params.get("doc_id", ""),
                content=params.get("content", ""),
                title=params.get("title", ""),
                source=params.get("source", ""),
                category=params.get("category", ""),
            )

        if action == "store_graph":
            return self.store_graph(
                entities=params.get("entities", []),
                relations=params.get("relations", []),
                doc_id=params.get("doc_id", ""),
            )

        if action == "build_kg":
            return self.build_knowledge_graph(
                doc_id=params.get("doc_id", ""),
            )

        # ---- v1.50 Phase B: 自动知识图谱构建 - 零 LLM - ---
        if action == "auto_graph":
            return self.auto_graph_from_doc(
                doc_id=params.get("doc_id", ""),
                content=params.get("content", ""),
                doc_name=params.get("doc_name", ""),
            )

        if action == "get_graph_stats":
            return self.get_auto_graph_stats()

        raise ValueError(
            f"[{self.GUA_NAME}] 未知 action: {action}。"
            f"支持: store_conversation, recall_conversation, "
            f"set_preference, get_preference, push, recall, stats, clear, "
            f"store_vector, store_wiki, store_graph, build_kg, auto_graph, get_graph_stats"
        )

    # ========================================================================
    # 短期记忆（心/HeartAgent 迁移）
    # ========================================================================

    def store_conversation(
        self,
        session_id: str = "default",
        role: str = "user",
        content: str = "",
    ) -> Dict[str, Any]:
        """存储一条对话到短期记忆

        迁移自 HeartAgent._handle_store_memory。
        每个 session_id 独立存储，全局上限 SHORT_TERM_MAX 条。

        Args:
            session_id: 会话标识
            role:       角色（"user" / "assistant" / "system"）
            content:    对话内容文本

        Returns:
            {"ok": True, "stored": int} — 当前存储条数
        """
        if not content:
            return {"ok": False, "stored": 0, "error": "空内容"}

        # ---- 每次写入前清理过期 session ----
        self._cleanup_expired_sessions()

        if session_id not in self._short_term:
            self._short_term[session_id] = []

        # 更新活动时间戳
        self._session_activity[session_id] = time.time()

        entry: Dict[str, Any] = {
            "role": role,
            "content": content,
            "time": time.time(),
        }
        self._short_term[session_id].append(entry)

        # 超过上限 → 截断保留最新 N 条
        if len(self._short_term[session_id]) > self.SHORT_TERM_MAX:
            self._short_term[session_id] = self._short_term[session_id][
                -self.SHORT_TERM_MAX:
            ]
            logger.debug(
                "☷ [坤] Session %s 记忆超 %d 条，已截断",
                session_id, self.SHORT_TERM_MAX,
            )

        self._memories_stored += 1
        return {"ok": True, "stored": len(self._short_term[session_id])}

    # ========================================================================
    # Session 生命周期管理
    # ========================================================================

    def _cleanup_expired_sessions(self) -> None:
        """清理过期 session 和超量的 session

        清理策略：
          1. 移除超过 SESSION_TTL 未活动的 session
          2. 如果 session 总数超过 SESSION_MAX_COUNT，
             按 last_activity 排序，清理最久未活动的最多 20% session
        """
        now = time.time()

        # ---- 步骤 1: 按 TTL 清理 ----
        expired_ids = [
            sid for sid, last_act in self._session_activity.items()
            if now - last_act > self.SESSION_TTL
        ]
        for sid in expired_ids:
            self._remove_session(sid)

        if expired_ids:
            logger.debug(
                "☷ [坤] TTL 清理: 移除 %d 个过期 session",
                len(expired_ids),
            )

        # ---- 步骤 2: 按数量上限清理 ----
        current_count = len(self._session_activity)
        if current_count > self.SESSION_MAX_COUNT:
            # 按 last_activity 升序，最久未活动的排前面
            sorted_sessions = sorted(
                self._session_activity.items(),
                key=lambda item: item[1],
            )
            # 清理超出上限的 20%（至少清理 1 个）
            overflow = current_count - self.SESSION_MAX_COUNT
            remove_count = max(overflow, int(current_count * 0.2), 1)
            to_remove = sorted_sessions[:remove_count]
            for sid, _ in to_remove:
                self._remove_session(sid)
            logger.warning(
                "☷ [坤] 容量清理: session %d/%d，移除 %d 个最久未活动 session",
                current_count, self.SESSION_MAX_COUNT, remove_count,
            )

    def _remove_session(self, session_id: str) -> None:
        """移除指定 session 的所有数据

        Args:
            session_id: 要移除的会话标识
        """
        self._short_term.pop(session_id, None)
        self._preferences.pop(session_id, None)
        self._session_activity.pop(session_id, None)

    def recall_conversation(
        self,
        session_id: str = "default",
        n: int = 10,
    ) -> Dict[str, Any]:
        """召回最近 N 条对话记录

        迁移自 HeartAgent._handle_recall。

        Args:
            session_id: 会话标识
            n:          召回条数（默认 10）

        Returns:
            {"history": [{"role": ..., "content": ..., "time": ...}, ...]}
        """
        memories = self._short_term.get(session_id, [])
        return {"history": list(memories[-n:])}

    # ========================================================================
    # 用户偏好（心/HeartAgent 迁移）
    # ========================================================================

    def set_preference(
        self,
        session_id: str = "default",
        key: str = "",
        value: str = "",
    ) -> None:
        """设置用户偏好

        迁移自 HeartAgent._handle_user_preference 的写入路径。
        偏好按 session_id 隔离。

        Args:
            session_id: 会话标识
            key:        偏好键名
            value:      偏好值
        """
        if not key:
            logger.debug("☷ [坤] set_preference: key 为空，忽略")
            return

        if session_id not in self._preferences:
            self._preferences[session_id] = {}

        self._preferences[session_id][key] = value
        logger.debug(
            "☷ [坤] Session %s 偏好设置: %s = %s",
            session_id, key, str(value)[:60],
        )

    def get_preference(
        self,
        session_id: str = "default",
        key: str = "",
    ) -> Optional[str]:
        """读取用户偏好

        迁移自 HeartAgent._handle_user_preference 的读取路径。

        Args:
            session_id: 会话标识
            key:        偏好键名

        Returns:
            偏好值（字符串），未找到时返回 None
        """
        if not key:
            return None

        session_prefs = self._preferences.get(session_id, {})
        value = session_prefs.get(key, None)
        return value if value is not None else None

    # ========================================================================
    # Wiki 统一知识库接口（脾/SpleenAgent 迁移）
    # ========================================================================

    def push_to_wiki(
        self,
        doc_id: str = "",
        content: str = "",
        category: str = "",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """存储 Wiki 页面

        功能对齐脾的 _handle_nutrition：
          - 计算 content 的 hash 用于去重
          - 相同内容的页面不重复存储
          - 自动更新关键词倒排索引
          - 递增 _stored_total

        Args:
            doc_id: 页面 ID，为空时自动生成（MD5 前 16 位）
            content: 页面内容
            category: 分类标签（为空时自动分类）
            tags:   标签列表

        Returns:
            {"ok": True/False, "doc_id": str, "is_new": bool,
             "stored_total": int, "error": str (仅失败时)}
        """
        if not content:
            return {"ok": False, "doc_id": "", "is_new": False, "error": "content 为空"}

        try:
            # 生成/确认 doc_id
            if not doc_id:
                doc_id = hashlib.md5(content.encode("utf-8")).hexdigest()[:16]

            content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()

            # 去重：同 content hash 的页面不重复存储
            existing_doc_id = self._content_hash_index.get(content_hash)
            is_new = existing_doc_id is None

            if is_new:
                self._stored_total += 1
            else:
                # 内容完全相同，更新元数据
                if existing_doc_id in self._wiki_store:
                    self._wiki_store[existing_doc_id]["accessed_at"] = time.time()
                    self._wiki_store[existing_doc_id]["access_count"] = (
                        self._wiki_store[existing_doc_id].get("access_count", 0) + 1
                    )
                    logger.debug(
                        "[%s] Wiki 页面已存在，更新访问: %s", self.GUA_NAME, existing_doc_id,
                    )
                    return {
                        "ok": True,
                        "doc_id": existing_doc_id,
                        "is_new": False,
                        "stored_total": self._stored_total,
                    }

            # 存储页面
            doc = {
                "doc_id": doc_id,
                "content": content,
                "content_hash": content_hash,
                "content_len": len(content),
                "category": category or self._classify_content(content),
                "tags": tags or [],
                "created_at": time.time(),
                "accessed_at": time.time(),
                "access_count": 0,
            }
            self._wiki_store[doc_id] = doc
            self._content_hash_index[content_hash] = doc_id

            # 更新关键词倒排索引
            self._index_keywords(doc_id, content)

            # 记录断路器成功
            wiki_cb = self._circuits.get("wiki_engine")
            if wiki_cb:
                wiki_cb.record_success()

            # v1.50 Phase B: 自动建图 — 零 LLM 抽取实体+边
            auto_graph_result = self._try_auto_graph(content, doc_id)

            logger.info(
                "[%s] Wiki 页面已存储: %s (len=%d, cat=%s) | auto_graph=%s",
                self.GUA_NAME, doc_id, len(content), doc["category"],
                "ok" if auto_graph_result and auto_graph_result.get("ok") else "skip",
            )
            return {
                "ok": True,
                "doc_id": doc_id,
                "is_new": True,
                "stored_total": self._stored_total,
                "auto_graph": auto_graph_result,
            }

        except Exception as e:
            logger.error(
                "[%s] push_to_wiki 失败: %s", self.GUA_NAME, e, exc_info=True,
            )
            wiki_cb = self._circuits.get("wiki_engine")
            if wiki_cb:
                wiki_cb.record_failure()
            return {"ok": False, "doc_id": "", "is_new": False, "error": str(e)}

    def recall_wiki(self, query: str = "", top_k: int = 5) -> List[Dict[str, Any]]:
        """检索 Wiki 内容

        功能对齐脾的 _search_wiki / _handle_pump：
          1. 尝试向量搜索（如果外部嵌入服务可用）
          2. Fallback: 关键词倒排索引搜索
          3. 结果按匹配分数排序

        Args:
            query: 检索查询词
            top_k: 返回结果数（默认 5）

        Returns:
            结果列表，每项包含 {doc_id, content, preview, score, category, tags, ...}
        """
        if not query or not self._wiki_store:
            return []

        try:
            # 关键词检索
            results = self._keyword_search(query, top_k)

            # 更新访问计数
            for r in results:
                doc_id = r.get("doc_id", "")
                if doc_id in self._wiki_store:
                    self._wiki_store[doc_id]["accessed_at"] = time.time()
                    self._wiki_store[doc_id]["access_count"] = (
                        self._wiki_store[doc_id].get("access_count", 0) + 1
                    )

            # 记录断路器成功
            wiki_cb = self._circuits.get("wiki_engine")
            if wiki_cb:
                wiki_cb.record_success()

            return results

        except Exception as e:
            logger.error(
                "[%s] recall_wiki 失败: %s", self.GUA_NAME, e, exc_info=True,
            )
            wiki_cb = self._circuits.get("wiki_engine")
            if wiki_cb:
                wiki_cb.record_failure()
            return []

    def get_wiki_stats(self) -> Dict[str, Any]:
        """获取 Wiki 统计信息

        对齐脾的 stats() 方法。

        Returns:
            {"total_pages": int, "stored_total": int,
             "total_content_len": int, "avg_content_len": float,
             "categories": {category: count},
             "keyword_index_terms": int}
        """
        try:
            total_pages = len(self._wiki_store)
            total_content_len = sum(
                d.get("content_len", 0) for d in self._wiki_store.values()
            )

            # 分类统计
            categories: Dict[str, int] = {}
            for doc in self._wiki_store.values():
                cat = doc.get("category", "未分类")
                categories[cat] = categories.get(cat, 0) + 1

            return {
                "total_pages": total_pages,
                "stored_total": self._stored_total,
                "total_content_len": total_content_len,
                "avg_content_len": round(total_content_len / max(total_pages, 1), 1),
                "categories": categories,
                "keyword_index_terms": len(self._keyword_index),
                "health": self._health.value,
                "uptime_sec": round(self.uptime_sec, 1),
            }

        except Exception as e:
            logger.error(
                "[%s] get_wiki_stats 失败: %s", self.GUA_NAME, e, exc_info=True,
            )
            return {
                "total_pages": 0,
                "stored_total": self._stored_total,
                "error": str(e),
            }

    def clear_wiki(self) -> None:
        """清空 Wiki 存储"""
        self._wiki_store.clear()
        self._content_hash_index.clear()
        self._keyword_index.clear()
        self._stored_total = 0
        logger.info("[%s] Wiki 存储已清空", self.GUA_NAME)

    def get_page(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """获取指定 Wiki 页面

        Args:
            doc_id: 页面 ID

        Returns:
            页面数据 dict，不存在时返回 None
        """
        return self._wiki_store.get(doc_id)

    # ========================================================================
    # 综合统计
    # ========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """获取坤卦综合统计信息（短期记忆侧）

        Returns:
            {"total_sessions": int, "total_memories": int,
             "total_preferences": int, "memories_stored": int,
             "session_ttl": float, "session_max": int}
        """
        total_memories = sum(len(v) for v in self._short_term.values())
        total_preferences = sum(len(v) for v in self._preferences.values())
        return {
            "total_sessions": len(self._short_term),
            "total_memories": total_memories,
            "total_preferences": total_preferences,
            "memories_stored": self._memories_stored,
            "session_ttl": self.SESSION_TTL,
            "session_max": self.SESSION_MAX_COUNT,
        }

    # ========================================================================
    # 降级处理
    # ========================================================================

    def _check_memory_overload(self) -> bool:
        """检查是否记忆过载（降级条件）

        Returns:
            True 如果任何 session 记忆超过 90% 上限
        """
        for memories in self._short_term.values():
            if len(memories) >= int(self.SHORT_TERM_MAX * 0.9):
                return True
        return False

    def _fallback_trim_memory(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """记忆超载降级处理：精简最早记忆

        Args:
            params: 原始参数（透传）

        Returns:
            精简后的结果
        """
        for session_id, memories in self._short_term.items():
            if len(memories) > int(self.SHORT_TERM_MAX * 0.8):
                keep = int(self.SHORT_TERM_MAX * 0.8)
                self._short_term[session_id] = memories[-keep:]
                logger.warning(
                    "☷ [坤] Session %s 记忆精简完成，保留 %d 条",
                    session_id, keep,
                )

        return self._execute_core(params)

    # ========================================================================
    # 内部方法
    # ========================================================================

    @staticmethod
    def _classify_content(text: str) -> str:
        """简单内容分类

        对齐脾的 _classify_text 方法。

        Args:
            text: 文本内容

        Returns:
            分类标签
        """
        t = text.lower()
        if any(kw in t for kw in ["api", "接口", "部署", "运维", "服务器", "docker", "kubernetes"]):
            return "技术文档"
        if any(kw in t for kw in ["财报", "财务", "收入", "利润", "成本"]):
            return "财务"
        if any(kw in t for kw in ["产品", "需求", "设计", "上线"]):
            return "产品"
        if any(kw in t for kw in ["会议", "周报", "日报", "计划"]):
            return "办公"
        return "通用办公"

    def _index_keywords(self, doc_id: str, content: str) -> None:
        """为页面构建简单关键词倒排索引

        Args:
            doc_id: 页面 ID
            content: 页面内容
        """
        # 简单分词：中文 ≥2 字 或 英文 ≥2 字母
        tokens = re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{2,}', content.lower())
        seen: set = set()
        for token in tokens:
            if token not in seen:
                seen.add(token)
                if token not in self._keyword_index:
                    self._keyword_index[token] = []
                self._keyword_index[token].append(doc_id)

    def _keyword_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """关键词搜索

        对 query 分词后，按关键词匹配 doc 数计分。

        Args:
            query: 检索查询
            top_k: 返回结果数

        Returns:
            结果列表
        """
        query_tokens = re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{2,}', query.lower())

        if not query_tokens:
            return []

        # 计算每个 doc 的分数
        scores: Dict[str, float] = {}
        for token in query_tokens:
            matched_docs = self._keyword_index.get(token, [])
            for doc_id in matched_docs:
                scores[doc_id] = scores.get(doc_id, 0) + 1

        # 按分数排序
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_docs = sorted_docs[:top_k]

        results: List[Dict[str, Any]] = []
        for doc_id, score in top_docs:
            doc = self._wiki_store.get(doc_id)
            if doc:
                preview = doc["content"][:500]
                results.append({
                    "doc_id": doc_id,
                    "content": doc["content"],
                    "preview": preview,
                    "score": score,
                    "category": doc.get("category", ""),
                    "tags": doc.get("tags", []),
                    "content_len": doc.get("content_len", 0),
                    "created_at": doc.get("created_at", 0),
                })

        return results

    # ========================================================================
    # v2.2 标准化存储接口
    # ========================================================================

    def store_vector(
        self,
        doc_id: str,
        chunks: List[Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """统一向量存储接口

        数据校验 → 写入 ChromaDB → 返回确认。
        将带有 embedding 的 chunk 写入 ChromaDB 向量数据库。

        Args:
            doc_id: 文档唯一标识
            chunks: Chunk 对象列表（必须包含 embedding 属性）
            metadata: 附加元数据

        Returns:
            {
                "ok": True/False,
                "doc_id": str,
                "vectors_stored": int,
                "collection": str,
                "error": str (仅失败时),
            }
        """
        result: Dict[str, Any] = {
            "ok": False,
            "doc_id": doc_id,
            "vectors_stored": 0,
            "collection": "kb_chunks",
        }

        # === 数据校验 ===
        if not doc_id:
            result["error"] = "doc_id 为空"
            return result

        if not chunks:
            result["error"] = "chunks 为空"
            return result

        # 筛选有 embedding 的 chunk
        vectorized = []
        for c in chunks:
            emb = getattr(c, "embedding", None)
            if emb is not None:
                vectorized.append(c)

        if not vectorized:
            result["ok"] = True
            result["vectors_stored"] = 0
            result["message"] = "无向量化数据，跳过"
            return result

        meta = metadata or {}

        try:
            from src.db.vector_store import get_vector_store
            vs = get_vector_store()
            if vs is None:
                result["error"] = "VectorStore 不可用"
                return result

            ids = []
            embeddings = []
            metadatas = []
            documents = []

            for i, c in enumerate(vectorized):
                chunk_id = f"{doc_id}_{i}"
                ids.append(chunk_id)
                embeddings.append(c.embedding)
                doc_text = getattr(c, "text", "")
                documents.append(doc_text)
                m = {
                    "doc_id": doc_id,
                    "chunk_index": str(getattr(c, "chunk_index", i)),
                    "file_name": str(getattr(c, "file_name", "")),
                    "category": str(getattr(c, "category", "")),
                    "source_file": str(getattr(c, "source_file", "")),
                }
                m.update({k: str(v)[:512] for k, v in meta.items()})
                metadatas.append(m)

            success = vs.add(
                ids=ids,
                embeddings=embeddings,
                metadata=metadatas,
                documents=documents,
            )

            if success:
                result["ok"] = True
                result["vectors_stored"] = len(ids)
                logger.info(
                    "[%s] store_vector: %d 条向量写入 ChromaDB (doc_id=%s)",
                    self.GUA_NAME, len(ids), doc_id,
                )
            else:
                result["error"] = "ChromaDB 写入失败"

        except Exception as e:
            logger.error("[%s] store_vector 异常: %s", self.GUA_NAME, e, exc_info=True)
            result["error"] = str(e)

        return result

    def store_wiki(
        self,
        doc_id: str,
        content: str,
        title: str = "",
        source: str = "",
        category: str = "",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """统一 Wiki 持久化接口

        数据校验 → 写入 worldtree.db/wiki_pages → 同步向量 → 返回确认。
        不同于 push_to_wiki（仅内存），此方法真正持久化到 SQLite。

        Args:
            doc_id: 文档唯一标识
            content: 页面内容
            title: 页面标题
            source: 来源文件路径
            category: 分类标签
            tags: 标签列表

        Returns:
            {
                "ok": True/False,
                "doc_id": str,
                "page_id": str,
                "is_new": bool,
                "error": str (仅失败时),
            }
        """
        result: Dict[str, Any] = {
            "ok": False,
            "doc_id": doc_id,
            "page_id": "",
            "is_new": False,
        }

        # === 数据校验 ===
        if not content or not content.strip():
            result["error"] = "content 为空"
            return result

        if not doc_id:
            doc_id = hashlib.md5(content.encode("utf-8")).hexdigest()[:16]
            result["doc_id"] = doc_id

        title = title or f"Document_{doc_id[:8]}"
        category = category or self._classify_content(content)
        tags = tags or []

        try:
            import sqlite3
            from src.config import WORLDTREE_DB_PATH

            db_path = str(WORLDTREE_DB_PATH)
            os.makedirs(os.path.dirname(db_path), exist_ok=True)

            conn = sqlite3.connect(db_path, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")

            # 确保表存在
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wiki_pages (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    category TEXT DEFAULT '',
                    tags TEXT DEFAULT '[]',
                    summary TEXT DEFAULT '',
                    content TEXT NOT NULL,
                    sources TEXT DEFAULT '[]',
                    version INTEGER DEFAULT 1,
                    quality_score REAL DEFAULT 0.5,
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                )
            """)
            conn.commit()

            # 生成 page_id
            page_id = f"wiki_{doc_id}"
            now = time.strftime("%Y-%m-%d %H:%M")

            # 生成摘要
            summary = content[:200].strip()
            if len(content) > 200:
                last_period = max(
                    summary.rfind("。"),
                    summary.rfind("."),
                    summary.rfind("\n"),
                )
                if last_period > 100:
                    summary = summary[:last_period + 1]
                else:
                    summary = summary[:197] + "..."

            sources_json = json.dumps([source] if source else [], ensure_ascii=False)
            tags_json = json.dumps(tags, ensure_ascii=False)

            # 检查是否已存在
            existing = conn.execute(
                "SELECT id FROM wiki_pages WHERE id = ?", (page_id,)
            ).fetchone()
            is_new = existing is None

            conn.execute(
                """INSERT OR REPLACE INTO wiki_pages
                   (id, title, category, tags, summary, content, sources, version, quality_score, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (page_id, title, category, tags_json, summary, content,
                 sources_json, 1, 0.7, now, now),
            )
            conn.commit()
            conn.close()

            result["ok"] = True
            result["page_id"] = page_id
            result["is_new"] = is_new

            # 同时更新内存缓存
            self.push_to_wiki(doc_id=doc_id, content=content,
                             category=category, tags=tags)

            logger.info(
                "[%s] store_wiki: page_id=%s, title=%s, len=%d, is_new=%s",
                self.GUA_NAME, page_id, title, len(content), is_new,
            )

        except Exception as e:
            logger.error("[%s] store_wiki 异常: %s", self.GUA_NAME, e, exc_info=True)
            result["error"] = str(e)

        return result

    def store_graph(
        self,
        entities: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
        doc_id: str = "",
    ) -> Dict[str, Any]:
        """统一知识图谱存储接口

        数据校验 → 写入 knowledge_graph.json + chunks.db (entities/relations 表) → 返回确认。

        Args:
            entities: 实体列表 [{"name": str, "type": str, "description": str, ...}]
            relations: 关系列表 [{"source": str, "target": str, "relation": str, ...}]
            doc_id: 关联文档 ID

        Returns:
            {
                "ok": True/False,
                "entities_count": int,
                "relations_count": int,
                "graph_file": str,
                "error": str (仅失败时),
            }
        """
        result: Dict[str, Any] = {
            "ok": False,
            "entities_count": 0,
            "relations_count": 0,
            "graph_file": "",
        }

        # === 数据校验 ===
        if not entities and not relations:
            result["error"] = "entities 和 relations 均为空"
            return result

        try:
            from src.config import GRAPH_PATH, DATA_DIR
            import sqlite3

            graph_file = str(GRAPH_PATH)
            result["graph_file"] = graph_file

            # 1. 写入 knowledge_graph.json（合并已有数据）
            existing_graph: Dict[str, Any] = {"nodes": {}, "edges": []}
            if os.path.exists(graph_file):
                try:
                    with open(graph_file, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content and content != "{}":
                            existing_graph = json.loads(content)
                except (json.JSONDecodeError, IOError):
                    logger.warning("[%s] knowledge_graph.json 读取失败，使用空图", self.GUA_NAME)

            # 合并节点
            nodes = existing_graph.get("nodes", existing_graph.get("entities", {}))
            if not isinstance(nodes, dict):
                nodes = {}

            for entity in entities:
                name = entity.get("name", "")
                if not name:
                    continue
                if name not in nodes:
                    nodes[name] = {
                        "type": entity.get("type", entity.get("entity_type", "")),
                        "description": entity.get("description", ""),
                        "aliases": entity.get("aliases", []),
                        "source_doc": doc_id,
                        "created_at": time.strftime("%Y-%m-%d %H:%M"),
                    }
                else:
                    # 更新已有节点信息
                    existing_node = nodes[name]
                    if isinstance(existing_node, dict):
                        if entity.get("description") and not existing_node.get("description"):
                            existing_node["description"] = entity["description"]

            # 合并边
            edges = list(existing_graph.get("edges", []))
            seen_edges = set()
            for edge in edges:
                key = (edge.get("from", ""), edge.get("to", ""), edge.get("relation", ""))
                seen_edges.add(key)

            for rel in relations:
                source = rel.get("source", rel.get("from", ""))
                target = rel.get("target", rel.get("to", ""))
                relation_type = rel.get("relation", rel.get("relation_type", "related_to"))
                if not source or not target:
                    continue
                key = (source, target, relation_type)
                if key not in seen_edges:
                    edges.append({
                        "from": source,
                        "to": target,
                        "relation": relation_type,
                        "description": rel.get("description", ""),
                        "source_doc": doc_id,
                    })
                    seen_edges.add(key)

            new_graph = {"nodes": nodes, "edges": edges}

            # 原子写入
            tmp_path = graph_file + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(new_graph, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, graph_file)

            # 2. 写入 chunks.db 的 entities 和 relations 表
            chunks_db_path = str(DATA_DIR / "chunks.db")
            conn = sqlite3.connect(chunks_db_path, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")

            # 确保表存在
            conn.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    entity_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    entity_type TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    aliases TEXT DEFAULT '[]',
                    mentions INTEGER DEFAULT 1,
                    file_hash TEXT DEFAULT '',
                    file_name TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS relations (
                    relation_id TEXT PRIMARY KEY,
                    source_type TEXT DEFAULT '',
                    source_id TEXT DEFAULT '',
                    target_type TEXT DEFAULT '',
                    target_id TEXT DEFAULT '',
                    relation_type TEXT DEFAULT '',
                    weight REAL DEFAULT 1.0,
                    created_at TEXT DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type)")
            conn.commit()

            now = time.strftime("%Y-%m-%d %H:%M")

            # 写入实体
            for entity in entities:
                name = entity.get("name", "")
                if not name:
                    continue
                entity_id = entity.get("entity_id", f"ent_{hashlib.md5(name.encode()).hexdigest()[:12]}")
                entity_type = entity.get("type", entity.get("entity_type", ""))
                description = entity.get("description", "")
                aliases = json.dumps(entity.get("aliases", []), ensure_ascii=False)
                conn.execute(
                    """INSERT OR REPLACE INTO entities
                       (entity_id, name, entity_type, description, aliases, file_hash, file_name, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (entity_id, name, entity_type, description, aliases,
                     doc_id, entity.get("file_name", ""), now),
                )

            # 写入关系
            for rel in relations:
                source = rel.get("source", rel.get("from", ""))
                target = rel.get("target", rel.get("to", ""))
                if not source or not target:
                    continue
                relation_id = rel.get("relation_id",
                    f"rel_{hashlib.md5(f'{source}_{target}'.encode()).hexdigest()[:12]}")
                relation_type = rel.get("relation", rel.get("relation_type", "related_to"))
                conn.execute(
                    """INSERT OR REPLACE INTO relations
                       (relation_id, source_type, source_id, target_type, target_id, relation_type, weight, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (relation_id, "entity", source, "entity", target, relation_type,
                     rel.get("weight", 1.0), now),
                )

            conn.commit()
            conn.close()

            result["ok"] = True
            result["entities_count"] = len(entities)
            result["relations_count"] = len(relations)

            logger.info(
                "[%s] store_graph: %d 实体, %d 关系 → %s + %s/entities,relations",
                self.GUA_NAME, len(entities), len(relations),
                graph_file, chunks_db_path,
            )

        except Exception as e:
            logger.error("[%s] store_graph 异常: %s", self.GUA_NAME, e, exc_info=True)
            result["error"] = str(e)

        return result

    # ========================================================================
    # 知识图谱自动构建
    # ========================================================================

    def build_knowledge_graph(self, doc_id: str = "") -> Dict[str, Any]:
        """从文档自动构建知识图谱

        从 chunks.db 中按 doc_id 检索该文档的所有 chunk，
        调用 SAG 提取器获取实体和关系，
        然后写入 knowledge_graph.json 和 entities/relations 表。

        实现方案要求的"坤卦负责知识图谱自动构建"。

        Args:
            doc_id: 文档 file_hash 或标识符

        Returns:
            {
                "ok": True/False,
                "doc_id": str,
                "chunks_processed": int,
                "entities_extracted": int,
                "relations_extracted": int,
                "graph_stored": bool,
                "error": str (仅失败时),
            }
        """
        result: Dict[str, Any] = {
            "ok": False,
            "doc_id": doc_id,
            "chunks_processed": 0,
            "entities_extracted": 0,
            "relations_extracted": 0,
            "graph_stored": False,
        }

        if not doc_id:
            # 无 doc_id 时，尝试从 wiki_store 获取内容
            result["error"] = "doc_id 为空，无法检索 chunk 数据"
            return result

        try:
            # === 步骤 1: 从 chunks.db 读取文档的所有 chunk ===
            from src.db.memory_store import get_store
            store = get_store()

            # 按 file_hash 或模糊匹配检索
            chunks = store.get_by_hash(doc_id)

            # 如果精确匹配失败，尝试短 hash 前缀匹配（兼容 16 位短 hash）
            if not chunks:
                short = doc_id[:16] if len(doc_id) > 16 else doc_id
                chunks = store.get_by_hash(short)

            # 最后尝试模糊：通过所有 chunk 的 file_hash 做 LIKE 搜索
            if not chunks:
                try:
                    raw_rows = store._db_conn.execute(
                        "SELECT id, doc FROM chunks WHERE file_hash LIKE ? AND status='active' LIMIT 100",
                        (doc_id[:8] + '%',)
                    ).fetchall()
                    if raw_rows:
                        import json as _json
                        chunks = []
                        for row_id, doc_json in raw_rows:
                            c = _json.loads(doc_json) if isinstance(doc_json, str) else doc_json
                            c["_db_id"] = row_id
                            chunks.append(c)
                except Exception:
                    pass

            if not chunks:
                logger.warning(
                    "[%s] build_knowledge_graph: 未找到 doc_id=%s 的 chunk 数据",
                    self.GUA_NAME, doc_id,
                )
                result["error"] = f"未找到 doc_id={doc_id} 的 chunk 数据"
                return result

            result["chunks_processed"] = len(chunks)

            # === 步骤 2: 调用 SAG 提取器获取实体和关系 ===
            all_entities: List[Dict[str, Any]] = []
            all_relations: List[Dict[str, Any]] = []

            try:
                # E-1 (Round 2 审计): 八卦层延迟导入四象模块（shaoyang/kg_extractor）。
                # 风险已评估：此 import 仅在 build_knowledge_graph() 方法体内、try/except 中延迟执行，
                # 不阻塞模块加载，不构成启动时循环依赖。shaoyang 不反向导入 bagua，依赖图为 DAG。
                # 长期方向 (Phase 3)：将实体提取能力下移至 src/infra/ 共享层。
                from src.shaoyang.kg_extractor import (
                    extract_entities_llm,
                    extract_relations_llm,
                )
                import asyncio

                # 合并所有 chunk 文本（最多 10000 字符）
                combined_text = ""
                for c in chunks:
                    text = c.get("text", "")
                    if len(combined_text) + len(text) > 10000:
                        combined_text += text[:10000 - len(combined_text)]
                        break
                    combined_text += text + "\n\n"

                if combined_text.strip():
                    file_name = chunks[0].get("file_name", doc_id)

                    # 尝试 LLM 提取
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # 尝试用同步方式
                            from src.services.llm import call_llm
                            import json as _json

                            # 实体提取
                            entity_prompt = f"""从以下文档中抽取实体。只输出 JSON 数组。
实体类型：person / organization / product / material / device / concept / location

文档：{file_name}
内容：{combined_text[:3000]}

输出：[{{"name":"实体名","type":"类型","description":"一句话描述"}}]"""

                            entity_raw = loop.run_until_complete(
                                call_llm(entity_prompt, max_tokens=2000)
                            ) if not loop.is_running() else None

                            if entity_raw:
                                entity_raw = entity_raw.strip()
                                if entity_raw.startswith("```"):
                                    entity_raw = entity_raw.split("\n", 1)[1].rsplit("```", 1)[0]
                                all_entities = _json.loads(entity_raw)

                            # 关系提取
                            if all_entities:
                                entity_names = [e["name"] for e in all_entities[:15]]
                                relation_prompt = f"""从以下文档中抽取实体间关系。只输出 JSON 数组。
实体列表：{_json.dumps(entity_names, ensure_ascii=False)}
内容：{combined_text[:3000]}

关系类型：uses, contains, manufactured_by, supplied_by, part_of, related_to

输出：[{{"source":"实体A","target":"实体B","relation":"关系类型"}}]"""

                                relation_raw = loop.run_until_complete(
                                    call_llm(relation_prompt, max_tokens=1500)
                                ) if not loop.is_running() else None

                                if relation_raw:
                                    relation_raw = relation_raw.strip()
                                    if relation_raw.startswith("```"):
                                        relation_raw = relation_raw.split("\n", 1)[1].rsplit("```", 1)[0]
                                    all_relations = _json.loads(relation_raw)

                    except Exception as e:
                        logger.warning(
                            "[%s] LLM 实体/关系提取失败，使用关键词提取: %s",
                            self.GUA_NAME, e,
                        )

            except ImportError:
                logger.warning("[%s] kg_extractor 模块不可用", self.GUA_NAME)

            # === 步骤 3: 关键词规则提取（LLM 不可用时的 fallback） ===
            if not all_entities:
                all_entities, all_relations = self._rule_based_kg_extraction(chunks)

            result["entities_extracted"] = len(all_entities)
            result["relations_extracted"] = len(all_relations)

            # === 步骤 4: 写入知识图谱 ===
            if all_entities or all_relations:
                store_result = self.store_graph(
                    entities=all_entities,
                    relations=all_relations,
                    doc_id=doc_id,
                )
                result["graph_stored"] = store_result.get("ok", False)
                result["ok"] = store_result.get("ok", False)
            else:
                result["ok"] = True
                result["message"] = "未提取到实体或关系，跳过硬是存储"

            logger.info(
                "[%s] build_knowledge_graph: doc_id=%s, chunks=%d, entities=%d, relations=%d",
                self.GUA_NAME, doc_id, len(chunks),
                result["entities_extracted"], result["relations_extracted"],
            )

        except Exception as e:
            logger.error(
                "[%s] build_knowledge_graph 异常: %s",
                self.GUA_NAME, e, exc_info=True,
            )
            result["error"] = str(e)

        return result

    def _rule_based_kg_extraction(
        self,
        chunks: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """基于规则的关键词实体/关系提取（LLM 不可用时的 fallback）

        使用正则匹配和共现分析从 chunk 文本中提取实体和关系。

        Args:
            chunks: chunk 字典列表

        Returns:
            (entities, relations) 元组
        """
        entities: List[Dict[str, Any]] = []
        relations: List[Dict[str, Any]] = []
        entity_set: Dict[str, Dict[str, Any]] = {}

        # 定义常见实体模式
        patterns = [
            # 中文组织机构
            (r'(?:公司|集团|企业|工厂|研究院|实验室|部门|团队|委员会)', "organization"),
            # 技术/产品术语
            (r'(?:系统|平台|框架|引擎|算法|模型|协议|接口|组件|模块|服务)', "concept"),
            # 材料
            (r'(?:PA\d{2}|PC|ABS|PP|PE|PVC|POM|PMMA|PBT|PET|TPE|TPU|不锈钢|铝合金|钛合金|碳纤维)', "material"),
            # 设备
            (r'(?:注塑机|挤出机|CNC|加工中心|铣床|车床|磨床|检测仪|传感器|控制器|PLC)', "device"),
            # 人员
            (r'(?:工程师|设计师|经理|总监|主任|操作员|技术员)', "person"),
        ]

        all_text = ""
        for c in chunks:
            text = c.get("text", "")
            if text:
                all_text += text + "\n"

        # 简单实体识别
        for pattern, entity_type in patterns:
            matches = re.findall(pattern, all_text)
            for match in matches:
                name = match.strip()
                if name and name not in entity_set:
                    entity_set[name] = {
                        "name": name,
                        "type": entity_type,
                        "description": f"从文档中提取的{entity_type}",
                    }

        entities = list(entity_set.values())

        # 基于共现的关系提取
        if len(entities) >= 2:
            entity_names = list(entity_set.keys())
            for i in range(min(len(entity_names), 20)):
                for j in range(i + 1, min(len(entity_names), 20)):
                    name_a = entity_names[i]
                    name_b = entity_names[j]
                    # 检查是否在同一句子中共现
                    for sentence in re.split(r'[。；.!?\n]', all_text):
                        if name_a in sentence and name_b in sentence:
                            relations.append({
                                "source": name_a,
                                "target": name_b,
                                "relation": "related_to",
                                "description": f"{name_a} 与 {name_b} 在同一上下文中提及",
                            })
                            break

        logger.info(
            "[%s] 规则提取: %d 实体, %d 关系",
            self.GUA_NAME, len(entities), len(relations),
        )

        return entities, relations

    # ========================================================================
    # v1.50 Phase B: 自动知识图谱构建（零 LLM）
    # ========================================================================

    def _try_auto_graph(self, content: str, doc_id: str) -> Dict[str, Any]:
        """尝试对文档内容执行自动图谱构建（内部方法，非阻塞）
        
        在 push_to_wiki 成功后自动调用。
        纯规则驱动，零 LLM 调用，不抛异常。
        
        Args:
            content: 文档内容
            doc_id:  文档标识
        
        Returns:
            {"ok": True/False, "entities": int, "edges": int, ...}
        """
        result = {"ok": False, "doc_id": doc_id, "entities": 0, "edges": 0}
        
        try:
            builder = get_auto_graph_builder()
            
            # 提取实体
            entities = builder.extract_entities(content)
            
            # 构建边
            edges = builder.build_from_text(content, doc_id)
            
            result["entities"] = len(entities)
            result["edges"] = len(edges)
            
            # 如果有实体或边，写入存储
            if entities or edges:
                graph_data = builder.build_full_graph(content, doc_id)
                
                store_result = self.store_graph(
                    entities=graph_data["entities"],
                    relations=graph_data["edges"],
                    doc_id=doc_id,
                )
                result["ok"] = store_result.get("ok", False)
                result["stored"] = store_result.get("ok", False)
            else:
                result["ok"] = True
                result["stored"] = False
            
            logger.debug(
                "☷ [坤] auto_graph: doc=%s → %d 实体, %d 边",
                doc_id, len(entities), len(edges),
            )
        
        except Exception as e:
            logger.warning(
                "☷ [坤] auto_graph 跳过 (doc=%s): %s", doc_id, e,
            )
            result["error"] = str(e)
        
        return result
    
    def auto_graph_from_doc(
        self,
        doc_id: str = "",
        content: str = "",
        doc_name: str = "",
    ) -> Dict[str, Any]:
        """对指定文档执行自动图谱构建（显式 API）
        
        支持通过 execute(action="auto_graph") 显式调用。
        可用于批量后端重建图谱。
        
        Args:
            doc_id:   文档标识（为空时从 content hash 生成）
            content:  文档内容
            doc_name: 文档名称（可选，用于日志）
        
        Returns:
            {
                "ok": True/False,
                "doc_id": str,
                "doc_name": str,
                "entities": [...],   # 提取的实体列表
                "edges": [...],       # 提取的边列表
                "entity_count": int,
                "edge_count": int,
                "graph_stored": bool,
                "error": str (仅失败时),
            }
        """
        result: Dict[str, Any] = {
            "ok": False,
            "doc_id": doc_id,
            "doc_name": doc_name,
            "entities": [],
            "edges": [],
            "entity_count": 0,
            "edge_count": 0,
            "graph_stored": False,
        }
        
        if not content or not content.strip():
            result["error"] = "content 为空"
            return result
        
        if not doc_id:
            doc_id = hashlib.md5(content.encode("utf-8")).hexdigest()[:16]
            result["doc_id"] = doc_id
        
        try:
            builder = get_auto_graph_builder()
            graph_data = builder.build_full_graph(content, doc_id)
            
            result["entities"] = graph_data["entities"]
            result["edges"] = graph_data["edges"]
            result["entity_count"] = graph_data["stats"]["entity_count"]
            result["edge_count"] = graph_data["stats"]["edge_count"]
            
            # 写入知识图谱存储
            if result["entities"] or result["edges"]:
                store_result = self.store_graph(
                    entities=result["entities"],
                    relations=result["edges"],
                    doc_id=doc_id,
                )
                result["graph_stored"] = store_result.get("ok", False)
            
            result["ok"] = True
            
            logger.info(
                "☷ [坤] auto_graph_from_doc: doc=%s → %d 实体, %d 边",
                doc_id, result["entity_count"], result["edge_count"],
            )
        
        except Exception as e:
            logger.error(
                "☷ [坤] auto_graph_from_doc 失败: %s", e, exc_info=True,
            )
            result["error"] = str(e)
        
        return result
    
    def get_auto_graph_stats(self) -> Dict[str, Any]:
        """获取自动图谱构建器统计信息
        
        Returns:
            AutoGraphBuilder stats + 坤卦内部知识图谱统计
        """
        builder = get_auto_graph_builder()
        builder_stats = builder.get_stats()
        
        # 读取知识图谱存储统计
        kg_stats = {"nodes_count": 0, "edges_count": 0, "graph_file": ""}
        try:
            from src.config import GRAPH_PATH
            kg_stats["graph_file"] = str(GRAPH_PATH)
            if os.path.exists(GRAPH_PATH):
                with open(GRAPH_PATH, "r", encoding="utf-8") as f:
                    kg_data = json.load(f)
                    nodes = kg_data.get("nodes", kg_data.get("entities", {}))
                    kg_stats["nodes_count"] = len(nodes)
                    kg_stats["edges_count"] = len(kg_data.get("edges", []))
        except Exception:
            pass
        
        return {
            "builder": builder_stats,
            "storage": kg_stats,
            "method": "auto_graph",
            "llm_calls": 0,  # 零 LLM 保证
        }
    
    def _add_graph_edge(self, edge: Dict[str, Any]) -> bool:
        """添加单条图谱边（内部方法）
        
        将自动提取的边写入 ChromaDB kb_events collection。
        
        Args:
            edge: 边数据 {source, target, type, confidence, doc_id, evidence}
        
        Returns:
            是否成功
        """
        try:
            import sqlite3
            from src.config import DATA_DIR
            
            db_path = str(DATA_DIR / "chunks.db")
            conn = sqlite3.connect(db_path, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            
            edge_key = f'{edge.get("source","")}_{edge.get("target","")}_{edge.get("type","")}'
            relation_id = f"auto_{hashlib.md5(edge_key.encode()).hexdigest()[:12]}"
            
            conn.execute("""
                INSERT OR REPLACE INTO relations
                (relation_id, source_type, source_id, target_type, target_id,
                 relation_type, weight, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                relation_id,
                "entity",
                edge.get("source", ""),
                "entity",
                edge.get("target", ""),
                edge.get("type", "related_to"),
                edge.get("confidence", 0.8),
                time.strftime("%Y-%m-%d %H:%M"),
            ))
            conn.commit()
            conn.close()
            return True
        
        except Exception as e:
            logger.warning("☷ [坤] _add_graph_edge 失败: %s", e)
            return False


# ============================================================================
# 模块导出
# ============================================================================

__all__ = [
    "KunGua",
    "SHORT_TERM_MAX",
    "SESSION_TTL",
    "SESSION_MAX_COUNT",
]
