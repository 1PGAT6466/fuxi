"""
data_service.py — 统一数据访问服务层
==============================
将所有分散在 router/服务中的直接 DB 操作封装为服务函数。
所有对 chunks.db、chat_sessions.db、login_rate.db、auth 的
直接 sqlite3 访问都应通过这里。

设计原则:
- 每个函数返回明确的结果类型，调用方据此决策
- 自动重连：连接异常时惰性重建
- 所有路径统一从 src.config 获取，避免硬编码
"""

import sqlite3
import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, Tuple

from src.config import DATA_DIR, CHROMA_PATH

logger = logging.getLogger(__name__)

# ============ SQLite 路径统一 ============

def _ensure_dir(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

CHUNKS_DB = _ensure_dir(Path(DATA_DIR) / "chunks.db")
CHAT_SESSIONS_DB = _ensure_dir(Path(DATA_DIR) / "chat_sessions.db")
LOGIN_RATE_DB = _ensure_dir(Path(DATA_DIR) / "login_rate.db")
AUDIT_DB = _ensure_dir(Path(DATA_DIR) / "audit.db")
USERS_FILE = _ensure_dir(Path(DATA_DIR) / "users.json")
USER_PREFERENCES_FILE = _ensure_dir(Path(DATA_DIR) / "user_preferences.json")

# ============ 连接管理 ============

def _connect(db_path: str, row_factory: bool = True) -> sqlite3.Connection:
    """Create SQLite connection with WAL + busy_timeout"""
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    if row_factory:
        conn.row_factory = sqlite3.Row
    return conn


# ============ 会话管理 (chat_sessions.db) ============

def ensure_chat_tables(db_path: str = None):
    """Ensure sessions and messages tables exist (idempotent)"""
    db_path = db_path or str(CHAT_SESSIONS_DB)
    with _connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                user_id TEXT,
                last_message TEXT,
                created_at REAL,
                updated_at REAL,
                message_count INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                sources TEXT,
                timestamp REAL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
        conn.commit()


def load_all_chat_sessions(db_path: str = None) -> Tuple[Dict, Dict]:
    """Load all sessions and messages from SQLite

    Returns:
        (sessions_dict, messages_dict)
    """
    db_path = db_path or str(CHAT_SESSIONS_DB)
    ensure_chat_tables(db_path)
    sessions = {}
    messages = {}
    try:
        with _connect(db_path) as conn:
            rows = conn.execute("SELECT * FROM sessions").fetchall()
            for row in rows:
                sessions[row["id"]] = dict(row)
            msg_rows = conn.execute(
                "SELECT * FROM messages ORDER BY timestamp"
            ).fetchall()
            for row in msg_rows:
                sid = row["session_id"]
                if sid not in messages:
                    messages[sid] = []
                messages[sid].append({
                    "role": row["role"],
                    "content": row["content"],
                    "sources": json.loads(row["sources"]) if row.get("sources") else [],
                    "timestamp": row["timestamp"],
                })
        logger.info("[data_service] loaded %d sessions from SQLite", len(sessions))
    except Exception as e:  # TODO: Narrow exception type
        logger.warning("[data_service] load sessions failed: %s", e)
    return sessions, messages


def save_session_to_db(session: dict, db_path: str = None):
    """Persist a single session to SQLite"""
    db_path = db_path or str(CHAT_SESSIONS_DB)
    ensure_chat_tables(db_path)
    try:
        with _connect(db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sessions
                (id, title, user_id, last_message, created_at, updated_at, message_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                session["id"], session.get("title", ""), session.get("user_id", ""),
                session.get("last_message", ""), session.get("created_at", 0),
                session.get("updated_at", 0), session.get("message_count", 0)
            ))
            conn.commit()
    except Exception as e:  # TODO: Narrow exception type
        logger.warning("[data_service] save session failed: %s", e)


def save_message_to_db(session_id: str, msg: dict, db_path: str = None):
    """Persist a single message to SQLite"""
    db_path = db_path or str(CHAT_SESSIONS_DB)
    ensure_chat_tables(db_path)
    try:
        with _connect(db_path) as conn:
            sources_json = json.dumps(msg.get("sources", []), ensure_ascii=False)
            conn.execute("""
                INSERT INTO messages (session_id, role, content, sources, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (
                session_id, msg.get("role", ""), msg.get("content", ""),
                sources_json, msg.get("timestamp", 0)
            ))
            conn.commit()
    except Exception as e:  # TODO: Narrow exception type
        logger.warning("[data_service] save message failed: %s", e)


def delete_session_from_db(session_id: str, db_path: str = None):
    """Delete a session and its messages from SQLite"""
    db_path = db_path or str(CHAT_SESSIONS_DB)
    ensure_chat_tables(db_path)
    try:
        with _connect(db_path) as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
    except Exception as e:  # TODO: Narrow exception type
        logger.warning("[data_service] delete session failed: %s", e)


# ============ 登录限流 (login_rate.db) ============

_MAX_LOGIN_ATTEMPTS = 5
_LOGIN_WINDOW_SEC = 60


def ensure_login_rate_table(db_path: str = None):
    """Ensure login rate-limit table exists (idempotent)"""
    db_path = db_path or str(LOGIN_RATE_DB)
    with _connect(db_path, row_factory=False) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                ip TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_login_ip ON login_attempts(ip)")
        conn.commit()


def check_login_rate(ip: str, db_path: str = None,
                     max_attempts: int = None, window_sec: int = None) -> bool:
    """Check if login is within rate limits — True means allowed

    Args:
        ip: Client IP address
        db_path: SQLite path (optional)
        max_attempts: Max attempts within window
        window_sec: Sliding window in seconds

    Returns:
        True = allowed; False = rate limited
    """
    db_path = db_path or str(LOGIN_RATE_DB)
    max_attempts = max_attempts or _MAX_LOGIN_ATTEMPTS
    window_sec = window_sec or _LOGIN_WINDOW_SEC
    now = time.time()
    cutoff = now - window_sec
    ensure_login_rate_table(db_path)

    try:
        with _connect(db_path, row_factory=False) as conn:
            conn.execute("DELETE FROM login_attempts WHERE timestamp < ?", (cutoff,))
            cursor = conn.execute(
                "SELECT COUNT(*) FROM login_attempts WHERE ip = ? AND timestamp >= ?",
                (ip, cutoff)
            )
            count = cursor.fetchone()[0]

            if count >= max_attempts:
                return False

            conn.execute(
                "INSERT INTO login_attempts (ip, timestamp) VALUES (?, ?)",
                (ip, now)
            )
            conn.commit()
            return True
    except Exception as e:  # TODO: Narrow exception type
        logger.warning("[data_service] login rate check error: %s", e)
        return True  # Fail-open: allow login


# ============ 用户管理 (users.json) ============

def load_users() -> dict:
    """Load user data from users.json"""
    users_file = Path(USERS_FILE)
    if users_file.exists():
        try:
            return json.loads(users_file.read_text(encoding="utf-8"))
        except Exception:  # TODO: Narrow exception type
            logger.warning("[data_service] Failed to read users.json")
    return {}


def save_users(users: dict):
    """Save user data to users.json"""
    users_file = Path(USERS_FILE)
    users_file.parent.mkdir(parents=True, exist_ok=True)
    users_file.write_text(
        json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ============ 用户偏好 ============

def load_user_preferences(uid: str) -> dict:
    """Load preferences for a specific user"""
    prefs = {}
    pref_file = Path(USER_PREFERENCES_FILE)
    if pref_file.exists():
        try:
            all_prefs = json.loads(pref_file.read_text(encoding="utf-8"))
            prefs = all_prefs.get(uid, {})
        except Exception:  # TODO: Narrow exception type
            logger.warning("[data_service] Failed to read user preferences")
    return prefs


def save_user_preferences(uid: str, prefs: dict):
    """Save preferences for a specific user"""
    pref_file = Path(USER_PREFERENCES_FILE)
    all_prefs = {}
    if pref_file.exists():
        try:
            all_prefs = json.loads(pref_file.read_text(encoding="utf-8"))
        except Exception:  # TODO: Narrow exception type
            pass
    all_prefs[uid] = prefs
    pref_file.write_text(
        json.dumps(all_prefs, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ============ ChromaDB 路径工具 ============

def get_chroma_dir() -> str:
    """Get ChromaDB persistence directory (single source of truth)

    Priority: CHROMA_PATH config > KB_CHROMA_DIR env > data/chromadb fallback
    All modules needing ChromaDB path should use this function.
    """
    chroma_dir = CHROMA_PATH
    if not chroma_dir:
        chroma_dir = os.getenv("KB_CHROMA_DIR", str(Path(DATA_DIR) / "chromadb"))
    os.makedirs(chroma_dir, exist_ok=True)
    return chroma_dir


# ============ 审计日志 ============

def log_audit(entry: dict, db_path: str = None):
    """Write an audit log entry"""
    db_path = db_path or str(AUDIT_DB)
    try:
        with _connect(db_path, row_factory=False) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT,
                    user_id TEXT,
                    ip TEXT,
                    details TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                "INSERT INTO audit_logs (event_type, user_id, ip, details, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    entry.get("event_type", ""),
                    entry.get("user_id", ""),
                    entry.get("ip", ""),
                    json.dumps(entry.get("details", {}), ensure_ascii=False),
                    entry.get("timestamp", time.strftime("%Y-%m-%d %H:%M:%S")),
                )
            )
            conn.commit()
    except Exception as e:  # TODO: Narrow exception type
        logger.warning("[data_service] Audit log write failed: %s", e)


logger.info("[data_service] Data service layer loaded")
