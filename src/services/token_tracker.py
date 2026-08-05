"""
token_tracker.py — 伏羲 Token 使用量追踪
=========================================
追踪 LLM API 调用的 token 消耗，按用户/会话/模型维度统计并持久化。

使用方式:
    from src.services.token_tracker import TokenTracker

    tracker = TokenTracker()
    await tracker.record(
        user_id="user123",
        session_id="session456",
        model="mimo-v2.5-pro",
        prompt_tokens=100,
        completion_tokens=200,
        total_tokens=300,
        cost=0.006,
    )
"""

import logging
import sqlite3
import time
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("token_tracker")

# 数据库路径
DB_PATH = Path(__file__).parent.parent.parent / "data" / "token_usage.db"


class TokenTracker:
    """Token 使用量追踪器"""

    _instance: Optional["TokenTracker"] = None

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self._ensure_db()

    @classmethod
    def get_instance(cls) -> "TokenTracker":
        if cls._instance is None:
            cls._instance = TokenTracker()
        return cls._instance

    def _ensure_db(self) -> None:
        """确保数据库和表存在"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL DEFAULT 'anonymous',
                    session_id TEXT DEFAULT '',
                    model TEXT NOT NULL,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    cost REAL DEFAULT 0.0,
                    created_at TEXT NOT NULL,
                    date TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_user_date
                ON token_usage(user_id, date)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_model
                ON token_usage(model)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_date
                ON token_usage(date)
            """)
            conn.commit()

    async def record(
        self,
        user_id: str = "anonymous",
        session_id: str = "",
        model: str = "unknown",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        cost: float = 0.0,
    ) -> bool:
        """记录一次 token 使用"""
        try:
            now = datetime.now()
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """
                    INSERT INTO token_usage
                    (user_id, session_id, model, prompt_tokens, completion_tokens, total_tokens, cost, created_at, date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        session_id,
                        model,
                        prompt_tokens,
                        completion_tokens,
                        total_tokens,
                        cost,
                        now.isoformat(),
                        now.date().isoformat(),
                    ),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"[TokenTracker] 记录失败: {e}")
            return False

    def get_daily_usage(self, user_id: str = "anonymous",
                        target_date: Optional[str] = None) -> Dict:
        """获取用户某日的 token 使用量"""
        target_date = target_date or date.today().isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT
                    COUNT(*) as request_count,
                    SUM(prompt_tokens) as total_prompt,
                    SUM(completion_tokens) as total_completion,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost) as total_cost
                FROM token_usage
                WHERE user_id = ? AND date = ?
                """,
                (user_id, target_date),
            ).fetchone()
            return dict(row) if row else {}

    def get_user_stats(self, user_id: str = "anonymous",
                       days: int = 30) -> List[Dict]:
        """获取用户最近 N 天的统计"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    date,
                    COUNT(*) as request_count,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost) as total_cost
                FROM token_usage
                WHERE user_id = ?
                GROUP BY date
                ORDER BY date DESC
                LIMIT ?
                """,
                (user_id, days),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_model_stats(self, days: int = 30) -> List[Dict]:
        """按模型统计使用量"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    model,
                    COUNT(*) as request_count,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost) as total_cost
                FROM token_usage
                WHERE date >= date('now', '-{} days')
                GROUP BY model
                ORDER BY total_tokens DESC
                """.format(days),
            ).fetchall()
            return [dict(r) for r in rows]

    def extract_usage_from_response(self, response: Dict) -> Dict:
        """从 LLM API 响应中提取 token 使用量

        支持 OpenAI 兼容格式的 usage 字段:
        {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 200,
                "total_tokens": 300
            }
        }
        """
        usage = response.get("usage", {})
        if isinstance(usage, dict):
            return {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
