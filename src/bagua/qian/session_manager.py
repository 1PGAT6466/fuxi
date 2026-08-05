"""
qian/session_manager.py - Session 隔离
======================================

每个 session_id 有独立的状态和 think() 调用。
"""

from dataclasses import dataclass, field
from src.bagua._common import (
    hashlib, json, logging, os, re, time,
    Any, Dict, List, Optional, Tuple,
)

logger = logging.getLogger("bagua.qian")

# ============================================================================
# SessionManager — Session 隔离管理器
# ============================================================================


@dataclass
class SessionState:
    """Session 内部状态

    Attributes:
        session_id:           Session ID
        created_at:           创建时间
        last_activity:        最后活动时间
        think_count:          think() 调用次数
        context:              上下文信息
    """
    session_id: str
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    think_count: int = 0
    context: Dict[str, Any] = field(default_factory=dict)


class SessionManager:
    """Session 隔离管理器

    管理多个 Session 的状态，确保每个 Session 有独立的状态和 think() 调用。

    Attributes:
        sessions:             Session 字典
        session_ttl:          Session TTL（秒）
        max_sessions:         最大 Session 数量
    """

    def __init__(
        self,
        session_ttl: float = 3600.0,
        max_sessions: int = 1000,
    ) -> None:
        self.sessions: Dict[str, SessionState] = {}
        self.session_ttl = session_ttl
        self.max_sessions = max_sessions

    def get_or_create_session(self, session_id: str) -> SessionState:
        """获取或创建 Session"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.last_activity = time.time()
            logger.debug("☰ [乾] 获取 Session: %s (think_count=%d)", session_id, session.think_count)
            return session

        # 检查 Session 数量
        if len(self.sessions) >= self.max_sessions:
            logger.warning("☰ [乾] Session 数量超过上限 (%d)，清理过期 Session", self.max_sessions)
            self._cleanup_expired_sessions()

        # 创建新 Session
        session = SessionState(session_id=session_id)
        self.sessions[session_id] = session
        logger.info("☰ [乾] 创建 Session: %s", session_id)
        return session

    def clear_session(self, session_id: str) -> None:
        """清除 Session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info("☰ [乾] 清除 Session: %s", session_id)

    def clear_all_sessions(self) -> None:
        """清除所有 Session"""
        self.sessions.clear()
        logger.info("☰ [乾] 清除所有 Session")

    def _cleanup_expired_sessions(self) -> None:
        """清理过期 Session"""
        now = time.time()
        expired_sessions = [
            session_id
            for session_id, session in self.sessions.items()
            if now - session.last_activity > self.session_ttl
        ]

        for session_id in expired_sessions:
            del self.sessions[session_id]
            logger.debug("☰ [乾] 清理过期 Session: %s", session_id)

        if expired_sessions:
            logger.info("☰ [乾] 清理过期 Session: %d 个", len(expired_sessions))

    def get_session_count(self) -> int:
        """获取 Session 数量"""
        return len(self.sessions)

    def get_session_summary(self) -> Dict[str, Any]:
        """获取 Session 摘要"""
        return {
            "session_count": len(self.sessions),
            "session_ttl": self.session_ttl,
            "max_sessions": self.max_sessions,
            "sessions": [
                {
                    "session_id": session.session_id,
                    "created_at": session.created_at,
                    "last_activity": session.last_activity,
                    "think_count": session.think_count,
                }
                for session in self.sessions.values()
            ],
        }
