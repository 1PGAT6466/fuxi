"""
memory.py — 记忆系统
会话记忆 + 长期记忆
"""
import json
import logging
import time
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger("services.memory")

from src.config import DATA_DIR as CONFIG_DATA_DIR
MEMORY_DIR = Path(CONFIG_DATA_DIR) / "memory"


class MemorySystem:
    """记忆系统"""

    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self._session_memory: Dict[str, List[Dict]] = {}

# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
    async def add_session_message(self, session_id: str, role: str,
                                   content: str, metadata: Dict = None):
        """添加会话消息"""
        if session_id not in self._session_memory:
            self._session_memory[session_id] = []

        message = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {},
        }

        self._session_memory[session_id].append(message)

        # 限制会话记忆长度
        max_messages = 50
        if len(self._session_memory[session_id]) > max_messages:
            self._session_memory[session_id] = self._session_memory[session_id][-max_messages:]

# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
    async def get_session_history(self, session_id: str,
                                   max_messages: int = 10) -> List[Dict]:
        """获取会话历史"""
        messages = self._session_memory.get(session_id, [])
        return messages[-max_messages:]

# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
    async def save_session(self, session_id: str):
        """保存会话到文件"""
        messages = self._session_memory.get(session_id, [])
        if not messages:
            return

        try:
            session_file = MEMORY_DIR / f"session_{session_id}.json"
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[Memory] 保存会话失败: {e}")

# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
    async def load_session(self, session_id: str) -> List[Dict]:
        """从文件加载会话"""
        session_file = MEMORY_DIR / f"session_{session_id}.json"

        if not session_file.exists():
            return []

        try:
            with open(session_file, "r", encoding="utf-8") as f:
                messages = json.load(f)
                self._session_memory[session_id] = messages
                return messages
        except Exception as e:
            logger.warning(f"[Memory] 加载会话失败: {e}")
            return []

# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
    async def add_long_term_memory(self, key: str, value: Dict):
        """添加长期记忆"""
        try:
            memory_file = MEMORY_DIR / "long_term.jsonl"
            record = {
                "key": key,
                "value": value,
                "timestamp": time.time(),
            }
            with open(memory_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"[Memory] 添加长期记忆失败: {e}")

# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
    async def search_long_term_memory(self, query: str,
                                        limit: int = 5) -> List[Dict]:
        """搜索长期记忆"""
        memory_file = MEMORY_DIR / "long_term.jsonl"

        if not memory_file.exists():
            return []

        results = []
        try:
            with open(memory_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        # 简单的关键词匹配
                        if query.lower() in json.dumps(record.get("value", {})).lower():
                            results.append(record)
                    except Exception as e:
                        logger.warning("JSON解析会话记忆失败: %s", e, exc_info=True)
        except Exception as e:
            logger.warning("搜索会话记忆失败: %s", e, exc_info=True)

        return results[-limit:]

    def get_active_sessions(self) -> List[str]:
        """获取活跃会话列表"""
        return list(self._session_memory.keys())

    def clear_session(self, session_id: str):
        """清除会话记忆"""
        if session_id in self._session_memory:
            del self._session_memory[session_id]


# 全局实例
_memory: Optional[MemorySystem] = None


def get_memory_system() -> MemorySystem:
    """获取全局记忆系统实例"""
    global _memory
    if _memory is None:
        _memory = MemorySystem()
    return _memory
