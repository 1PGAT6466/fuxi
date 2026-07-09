"""
audit.py — 审计日志服务 (v1.50)
SQLite audit_log 表，记录 who/what/when/result
"""
import sqlite3, time, os, json, logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("FUXI_DATA_DIR", "data")) / "audit.db"


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            user_id TEXT DEFAULT '',
            action TEXT NOT NULL,
            query TEXT DEFAULT '',
            result_summary TEXT DEFAULT '',
            duration_ms INTEGER DEFAULT 0,
            status TEXT DEFAULT 'ok',
            metadata TEXT DEFAULT '{}',
            ip TEXT DEFAULT ''
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)")
    conn.commit()
    return conn


def log_audit(
    action: str,
    query: str = "",
    user_id: str = "",
    result_summary: str = "",
    duration_ms: int = 0,
    status: str = "ok",
    metadata: dict = None,
    ip: str = "",
):
    """记录审计日志"""
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO audit_log (timestamp, user_id, action, query, result_summary, duration_ms, status, metadata, ip) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (time.time(), user_id, action, query[:2000], result_summary[:500], duration_ms, status, json.dumps(metadata or {}, ensure_ascii=False), ip)
        )
        conn.commit()
        conn.close()
    except Exception:  # TODO: Narrow exception type
        logger.warning("审计日志写入失败", exc_info=True)


def get_audit_stats(hours: int = 24) -> Dict:
    """获取审计统计"""
    try:
        conn = _get_conn()
        since = time.time() - hours * 3600
        rows = conn.execute(
            "SELECT action, COUNT(*), AVG(duration_ms) FROM audit_log WHERE timestamp > ? GROUP BY action",
            (since,)
        ).fetchall()
        conn.close()
        return {r[0]: {"count": r[1], "avg_ms": round(r[2] or 0)} for r in rows}
    except Exception as e:  # TODO: Narrow exception type
        logger.warning("Exception 失败: %s", e, exc_info=True)
        return {}


def get_recent_audits(limit: int = 50) -> list:
    """获取最近审计记录"""
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT timestamp, user_id, action, query, result_summary, duration_ms, status FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return [
            {"timestamp": r[0], "user_id": r[1], "action": r[2], "query": r[3][:100], "result": r[4][:100], "duration_ms": r[5], "status": r[6]}
            for r in rows
        ]
    except Exception as e:  # TODO: Narrow exception type
        logger.warning("Exception 失败: %s", e, exc_info=True)
        return []
