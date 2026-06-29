"""
state_manager.py — 对话状态管理 v4.0
多轮上下文 + 中间结果缓存
"""
import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import OrderedDict

logger = logging.getLogger(__name__)


@dataclass
class ConversationState:
    """单个对话的状态"""
    session_id: str
    history: List[Dict] = field(default_factory=list)
    intermediate_results: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    turn_count: int = 0

    def add_turn(self, role: str, content: str):
        self.history.append({"role": role, "content": content, "timestamp": time.time()})
        self.turn_count += 1
        self.last_active = time.time()

    def get_recent_history(self, max_turns: int = 6) -> List[Dict]:
        return self.history[-max_turns:]

    def is_expired(self, ttl_seconds: int = 3600) -> bool:
        return (time.time() - self.last_active) > ttl_seconds


class StateManager:
    """对话状态管理器（LRU 缓存）"""

    def __init__(self, max_sessions: int = 100, ttl_seconds: int = 3600):
        self._sessions: OrderedDict[str, ConversationState] = OrderedDict()
        self._max_sessions = max_sessions
        self._ttl_seconds = ttl_seconds

    def get_or_create(self, session_id: str) -> ConversationState:
        """获取或创建对话状态"""
        if session_id in self._sessions:
            state = self._sessions[session_id]
            state.last_active = time.time()
            self._sessions.move_to_end(session_id)
            return state

        # 清理过期
        self._cleanup()

        state = ConversationState(session_id=session_id)
        self._sessions[session_id] = state
        if len(self._sessions) > self._max_sessions:
            self._sessions.popitem(last=False)
        return state

    def _cleanup(self):
        """清理过期会话"""
        expired = [sid for sid, s in self._sessions.items() if s.is_expired(self._ttl_seconds)]
        for sid in expired:
            del self._sessions[sid]

    def get_stats(self) -> Dict:
        return {
            "active_sessions": len(self._sessions),
            "max_sessions": self._max_sessions,
        }


# 全局实例
_state_manager = None

def get_state_manager() -> StateManager:
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager
