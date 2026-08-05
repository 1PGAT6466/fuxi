"""
kun/session_manager.py — 坤卦会话管理
====================================

管理短期对话记忆和会话。
"""

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bagua.kun")

# 短期记忆上限
SHORT_TERM_MAX: int = 200

# Session TTL（秒）— 超过此时间未活动的 session 将被自动清理
SESSION_TTL: float = 3600.0

# 全局 session 数量上限
SESSION_MAX_COUNT: int = 1000


class SessionManager:
    """会话管理器

    管理短期对话记忆和会话。

    Attributes:
        sessions: 会话字典
        last_cleanup: 上次清理时间
    """

    def __init__(self):
        """初始化会话管理器"""
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.last_cleanup: float = time.time()

    def store_conversation(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """存储对话

        Args:
            session_id: 会话 ID
            role: 角色
            content: 内容
            metadata: 元数据

        Returns:
            是否成功
        """
        try:
            # 清理过期会话
            self._cleanup_expired_sessions()

            # 初始化会话
            if session_id not in self.sessions:
                self.sessions[session_id] = {
                    "created_at": time.time(),
                    "last_active": time.time(),
                    "conversations": [],
                }

            # 添加对话
            conversation = {
                "role": role,
                "content": content,
                "timestamp": time.time(),
                "metadata": metadata or {},
            }

            self.sessions[session_id]["conversations"].append(conversation)
            self.sessions[session_id]["last_active"] = time.time()

            # 限制对话数量
            if len(self.sessions[session_id]["conversations"]) > SHORT_TERM_MAX:
                self.sessions[session_id]["conversations"] = self.sessions[session_id]["conversations"][-SHORT_TERM_MAX:]

            return True
        except Exception as e:
            logger.error(f"存储对话失败: {e}")
            return False

    def recall_conversation(
        self,
        session_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """召回对话

        Args:
            session_id: 会话 ID
            limit: 数量限制

        Returns:
            对话列表
        """
        try:
            if session_id not in self.sessions:
                return []

            conversations = self.sessions[session_id]["conversations"]
            return conversations[-limit:] if limit > 0 else conversations
        except Exception as e:
            logger.error(f"召回对话失败: {e}")
            return []

    def _cleanup_expired_sessions(self) -> None:
        """清理过期会话"""
        try:
            current_time = time.time()

            # 检查是否需要清理
            if current_time - self.last_cleanup < 60:  # 每分钟清理一次
                return

            self.last_cleanup = current_time

            # 清理过期会话
            expired_sessions = []
            for session_id, session_data in self.sessions.items():
                if current_time - session_data["last_active"] > SESSION_TTL:
                    expired_sessions.append(session_id)

            for session_id in expired_sessions:
                self._remove_session(session_id)

            # 限制会话数量
            if len(self.sessions) > SESSION_MAX_COUNT:
                # 按最后活动时间排序
                sorted_sessions = sorted(
                    self.sessions.items(),
                    key=lambda x: x[1]["last_active"],
                )

                # 删除最旧的会话
                for session_id, _ in sorted_sessions[:len(self.sessions) - SESSION_MAX_COUNT]:
                    self._remove_session(session_id)

            if expired_sessions:
                logger.info(f"清理了 {len(expired_sessions)} 个过期会话")
        except Exception as e:
            logger.error(f"清理过期会话失败: {e}")

    def _remove_session(self, session_id: str) -> None:
        """删除会话

        Args:
            session_id: 会话 ID
        """
        try:
            if session_id in self.sessions:
                del self.sessions[session_id]
        except Exception as e:
            logger.error(f"删除会话失败: {e}")

    def get_session_count(self) -> int:
        """获取会话数量

        Returns:
            会话数量
        """
        return len(self.sessions)

    def get_conversation_count(self, session_id: str) -> int:
        """获取对话数量

        Args:
            session_id: 会话 ID

        Returns:
            对话数量
        """
        if session_id not in self.sessions:
            return 0
        return len(self.sessions[session_id]["conversations"])

    def clear_session(self, session_id: str) -> bool:
        """清空会话

        Args:
            session_id: 会话 ID

        Returns:
            是否成功
        """
        try:
            if session_id in self.sessions:
                self.sessions[session_id]["conversations"] = []
                return True
            return False
        except Exception as e:
            logger.error(f"清空会话失败: {e}")
            return False

    def clear_all_sessions(self) -> bool:
        """清空所有会话

        Returns:
            是否成功
        """
        try:
            self.sessions.clear()
            return True
        except Exception as e:
            logger.error(f"清空所有会话失败: {e}")
            return False
