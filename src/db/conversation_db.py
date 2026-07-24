"""
conversation_db.py — 对话历史持久化 (P1 核心缺陷修复)
======================================================
提供 ConversationDB 类，封装 conversation_sessions.db 的 CRUD 操作。

设计原则:
- SQLite 存储，与现有架构一致（WAL + busy_timeout + foreign_keys）
- 同步 SQLite 操作 + asyncio.to_thread 异步封装层
- 幂等初始化，可重复调用 ensure_tables()
- 线程安全单例模式
"""
import sqlite3
import os
import time
import uuid
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Any

from src.config import DATA_DIR

logger = logging.getLogger(__name__)

# ============ 数据库路径 ============

_CONVERSATIONS_DB_PATH = str(Path(DATA_DIR) / "conversation_sessions.db")


# ============ SQLite 连接工具 ============

def _connect(db_path: str = None, row_factory: bool = True) -> sqlite3.Connection:
    """创建 SQLite 连接，配置 WAL + busy_timeout + foreign_keys"""
    db_path = db_path or _CONVERSATIONS_DB_PATH
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    if row_factory:
        conn.row_factory = sqlite3.Row
    return conn


# ============ 工具函数 ============

def _safe_json_dumps(obj: Any) -> str:
    """安全 JSON 序列化，失败返回 '{}'"""
    try:
        return json.dumps(obj, ensure_ascii=False)
    except (TypeError, ValueError, OverflowError):
        return "{}"


def _safe_json_loads(s: str) -> dict:
    """安全 JSON 反序列化，失败返回 {}"""
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return {}


def _truncate_text(text: Optional[str], max_len: int) -> Optional[str]:
    """截断文本到指定长度（用于预览）"""
    if text is None:
        return None
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


# ============ ConversationDB 类 ============

class ConversationDB:
    """对话历史持久化数据库

    架构对齐：
    - SQLite 后端（WAL 模式，与项目一致）
    - 独立文件 conversation_sessions.db（不污染 chunks.db）
    - 线程安全单例
    - 异步友好：同步 DB 方法可通过 asyncio.to_thread 包装

    使用示例::

        db = ConversationDB.get_instance()
        db.ensure_tables()

        conv = db.create_conversation("user_123", "项目讨论")
        db.add_message(conv["id"], "user", "你好")
        db.add_message(conv["id"], "assistant", "你好！有什么可以帮助你的？")

        # 获取完整对话（含所有消息）
        full = db.get_conversation(conv["id"])
        for msg in full["messages"]:
            print(f"[{msg['role']}] {msg['content']}")

        # 列出用户的所有对话
        convs = db.list_conversations("user_123")
    """

    # ── 单例 ──
    _instance: Optional["ConversationDB"] = None
    _lock: Optional[Any] = None

    def __init__(self, db_path: str = None):
        self._db_path = db_path or _CONVERSATIONS_DB_PATH
        self._ensure_tables()

    @classmethod
    def get_instance(cls, db_path: str = None) -> "ConversationDB":
        """获取单例实例（线程安全）"""
        if cls._instance is None:
            import threading
            if cls._lock is None:
                cls._lock = threading.Lock()
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(db_path=db_path)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """重置单例（仅测试环境使用）"""
        cls._instance = None
        cls._lock = None

    # ── 表结构 ──

    def _ensure_tables(self):
        """幂等建表"""
        with _connect(self._db_path) as conn:
            # 对话表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    is_deleted INTEGER NOT NULL DEFAULT 0
                )
            """)
            # 消息表（外键级联删除）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                    content TEXT NOT NULL DEFAULT '',
                    timestamp REAL NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                        ON DELETE CASCADE
                )
            """)
            # 索引
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_conv_user_id "
                "ON conversations(user_id) WHERE is_deleted = 0"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_conv_updated_at "
                "ON conversations(updated_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_msg_conv_id "
                "ON messages(conversation_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_msg_timestamp "
                "ON messages(conversation_id, timestamp)"
            )
            conn.commit()

    def ensure_tables(self):
        """公开幂等建表入口（供 server.py / startup.py 调用）"""
        self._ensure_tables()
        logger.info("[ConversationDB] 表结构已就绪: %s", self._db_path)

    # ── CRUD: 对话 ──

    def create_conversation(
        self,
        user_id: str,
        title: str = "",
    ) -> Dict[str, Any]:
        """创建新对话

        Args:
            user_id: 用户唯一标识
            title:   对话标题（为空时自动生成时间戳标题）

        Returns:
            对话摘要字典：id, user_id, title, created_at, updated_at, message_count
        """
        conv_id = str(uuid.uuid4())
        now = time.time()
        if not title.strip():
            title = f"对话 {time.strftime('%m-%d %H:%M', time.localtime(now))}"

        with _connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO conversations (id, user_id, title, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (conv_id, user_id, title, now, now),
            )
            conn.commit()

        logger.debug("[ConversationDB] 创建对话 %s (user=%s)", conv_id, user_id)
        return {
            "id": conv_id,
            "user_id": user_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "message_count": 0,
        }

    def get_conversation(
        self,
        conversation_id: str,
        include_deleted: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """获取对话及其所有消息（按时间升序）

        Args:
            conversation_id: 对话 ID
            include_deleted: 是否包含软删除对话

        Returns:
            None — 若对话不存在
            完整对话字典（含 messages 列表）
        """
        with _connect(self._db_path) as conn:
            where = "WHERE id = ?" if include_deleted else "WHERE id = ? AND is_deleted = 0"
            conv = conn.execute(
                f"SELECT * FROM conversations {where}", (conversation_id,)
            ).fetchone()
            if conv is None:
                return None

            messages = conn.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC",
                (conversation_id,),
            ).fetchall()

        result = dict(conv)
        result["is_deleted"] = bool(result.pop("is_deleted"))
        result["messages"] = [
            {
                "id": m["id"],
                "role": m["role"],
                "content": m["content"],
                "timestamp": m["timestamp"],
                "metadata": _safe_json_loads(m["metadata"] if m["metadata"] else "{}"),
            }
            for m in messages
        ]
        return result

    def list_conversations(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """列出用户对话列表（摘要，不含完整消息）

        Args:
            user_id: 用户 ID
            limit:   分页大小
            offset:  分页偏移

        Returns:
            对话摘要列表（按更新时间降序）
        """
        with _connect(self._db_path) as conn:
            rows = conn.execute(
                """SELECT
                       c.id, c.title, c.created_at, c.updated_at,
                       (SELECT COUNT(*) FROM messages m
                        WHERE m.conversation_id = c.id) AS message_count,
                       (SELECT m2.content FROM messages m2
                        WHERE m2.conversation_id = c.id
                        ORDER BY m2.timestamp DESC LIMIT 1) AS last_message_preview
                   FROM conversations c
                   WHERE c.user_id = ? AND c.is_deleted = 0
                   ORDER BY c.updated_at DESC
                   LIMIT ? OFFSET ?""",
                (user_id, limit, offset),
            ).fetchall()

        return [
            {
                "id": r["id"],
                "title": r["title"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "message_count": r["message_count"],
                "last_message_preview": _truncate_text(r["last_message_preview"], 200),
            }
            for r in rows
        ]

    def delete_conversation(
        self,
        conversation_id: str,
        hard: bool = False,
    ) -> bool:
        """删除对话

        Args:
            conversation_id: 对话 ID
            hard:            False=软删除(is_deleted=1)  True=硬删除(含消息)

        Returns:
            bool — 是否成功删除
        """
        with _connect(self._db_path) as conn:
            if hard:
                cursor = conn.execute(
                    "DELETE FROM conversations WHERE id = ?", (conversation_id,)
                )
            else:
                cursor = conn.execute(
                    """UPDATE conversations
                       SET is_deleted = 1, updated_at = ?
                       WHERE id = ? AND is_deleted = 0""",
                    (time.time(), conversation_id),
                )
            conn.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(
                "[ConversationDB] %s 删除对话 %s",
                "hard" if hard else "soft",
                conversation_id,
            )
        return deleted

    # ── CRUD: 消息 ──

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict = None,
    ) -> Dict[str, Any]:
        """向对话追加一条消息

        Args:
            conversation_id: 对话 ID
            role:            角色 (user / assistant / system)
            content:         消息内容
            metadata:        附加元数据（可选）

        Returns:
            消息摘要字典：id, conversation_id, role, content, timestamp, metadata

        Raises:
            ValueError: 角色无效或对话不存在
        """
        role = role.strip().lower()
        if role not in ("user", "assistant", "system"):
            raise ValueError(f"无效角色 '{role}'，须为 user/assistant/system")

        now = time.time()
        meta_json = _safe_json_dumps(metadata or {})

        with _connect(self._db_path) as conn:
            # 校验对话存在且未删除
            conv = conn.execute(
                "SELECT id FROM conversations WHERE id = ? AND is_deleted = 0",
                (conversation_id,)
            ).fetchone()
            if conv is None:
                raise ValueError(f"对话不存在或已删除: {conversation_id}")

            cursor = conn.execute(
                """INSERT INTO messages (conversation_id, role, content, timestamp, metadata)
                   VALUES (?, ?, ?, ?, ?)""",
                (conversation_id, role, content, now, meta_json),
            )
            # 更新父对话时间戳
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
            conn.commit()
            msg_id = cursor.lastrowid

        logger.debug(
            "[ConversationDB] 添加 %s 消息到对话 %s", role, conversation_id
        )
        return {
            "id": msg_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "timestamp": now,
            "metadata": metadata or {},
        }

    # ── 辅助方法 ──

    def update_title(self, conversation_id: str, title: str) -> bool:
        """更新对话标题

        Returns:
            bool — 是否更新成功
        """
        title = title.strip()
        if not title:
            return False

        with _connect(self._db_path) as conn:
            cursor = conn.execute(
                """UPDATE conversations
                   SET title = ?, updated_at = ?
                   WHERE id = ? AND is_deleted = 0""",
                (title, time.time(), conversation_id),
            )
            conn.commit()
        return cursor.rowcount > 0

    def get_message_count(self, conversation_id: str) -> int:
        """获取对话的消息数量"""
        with _connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM messages WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            return row["cnt"] if row else 0

    def restore_conversation(self, conversation_id: str) -> bool:
        """恢复软删除的对话

        Returns:
            bool — 是否恢复成功
        """
        with _connect(self._db_path) as conn:
            cursor = conn.execute(
                """UPDATE conversations
                   SET is_deleted = 0, updated_at = ?
                   WHERE id = ? AND is_deleted = 1""",
                (time.time(), conversation_id),
            )
            conn.commit()
        return cursor.rowcount > 0


# ============ 启动初始化 ============

def init_conversation_db() -> ConversationDB:
    """服务启动时初始化对话数据库（幂等）

    供 server.py / startup.py 调用。
    返回单例实例。
    """
    instance = ConversationDB.get_instance()
    instance.ensure_tables()
    logger.info("[ConversationDB] 初始化完成: %s", instance._db_path)
    return instance


logger.info("[ConversationDB] 模块已加载")
