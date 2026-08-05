"""
quota_manager.py — 伏羲用户配额管理
=====================================
用户级 token 配额限制，支持按日/月配额、配额检查、管理员配置。

使用方式:
    from src.services.quota_manager import QuotaManager

    quota = QuotaManager.get_instance()

    # 检查配额
    allowed, remaining = await quota.check_quota("user123", estimated_tokens=1000)

    # 消费配额
    await quota.consume("user123", tokens=500)
"""

import json
import logging
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger("quota_manager")

# 数据库路径
DB_PATH = Path(__file__).parent.parent.parent / "data" / "quota.db"

# 默认配额（可通过环境变量覆盖）
DEFAULT_DAILY_LIMIT = 100_000    # 10万 tokens/天
DEFAULT_MONTHLY_LIMIT = 2_000_000  # 200万 tokens/月
DEFAULT_PER_REQUEST_LIMIT = 8_000  # 单次请求最大 tokens


class QuotaManager:
    """用户配额管理器"""

    _instance: Optional["QuotaManager"] = None

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self._ensure_db()

    @classmethod
    def get_instance(cls) -> "QuotaManager":
        if cls._instance is None:
            cls._instance = QuotaManager()
        return cls._instance

    def _ensure_db(self) -> None:
        """确保数据库和表存在"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_quotas (
                    user_id TEXT PRIMARY KEY,
                    daily_limit INTEGER DEFAULT 100000,
                    monthly_limit INTEGER DEFAULT 2000000,
                    per_request_limit INTEGER DEFAULT 8000,
                    daily_used INTEGER DEFAULT 0,
                    monthly_used INTEGER DEFAULT 0,
                    last_reset_date TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS quota_overrides (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    quota_type TEXT NOT NULL,
                    value INTEGER NOT NULL,
                    reason TEXT DEFAULT '',
                    created_by TEXT DEFAULT 'admin',
                    created_at TEXT,
                    expires_at TEXT
                )
            """)
            conn.commit()

    def _get_or_create_user_quota(self, user_id: str) -> Dict:
        """获取或创建用户配额记录"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM user_quotas WHERE user_id = ?", (user_id,)
            ).fetchone()

            if row:
                return dict(row)

            # 创建新用户配额
            now = datetime.now().isoformat()
            conn.execute(
                """
                INSERT INTO user_quotas
                (user_id, daily_limit, monthly_limit, per_request_limit,
                 daily_used, monthly_used, last_reset_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, 0, 0, ?, ?, ?)
                """,
                (user_id, DEFAULT_DAILY_LIMIT, DEFAULT_MONTHLY_LIMIT,
                 DEFAULT_PER_REQUEST_LIMIT, date.today().isoformat(), now, now),
            )
            conn.commit()
            return {
                "user_id": user_id,
                "daily_limit": DEFAULT_DAILY_LIMIT,
                "monthly_limit": DEFAULT_MONTHLY_LIMIT,
                "per_request_limit": DEFAULT_PER_REQUEST_LIMIT,
                "daily_used": 0,
                "monthly_used": 0,
            }

    def _reset_if_new_day(self, user_id: str) -> None:
        """如果是新的一天，重置日用量"""
        today = date.today().isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                UPDATE user_quotas
                SET daily_used = 0, last_reset_date = ?, updated_at = ?
                WHERE user_id = ? AND last_reset_date != ?
                """,
                (today, datetime.now().isoformat(), user_id, today),
            )
            conn.commit()

    async def check_quota(self, user_id: str = "anonymous",
                          estimated_tokens: int = 0) -> Tuple[bool, Dict]:
        """检查用户配额是否足够

        Args:
            user_id: 用户 ID
            estimated_tokens: 预估本次请求的 token 数

        Returns:
            (是否允许, 配额信息)
        """
        self._reset_if_new_day(user_id)
        quota = self._get_or_create_user_quota(user_id)

        # 检查单次请求限制
        if estimated_tokens > quota["per_request_limit"]:
            return False, {
                "reason": "per_request_limit_exceeded",
                "message": f"单次请求超过限制 ({estimated_tokens} > {quota['per_request_limit']} tokens)",
                "remaining_daily": quota["daily_limit"] - quota["daily_used"],
                "remaining_monthly": quota["monthly_limit"] - quota["monthly_used"],
            }

        # 检查日配额
        remaining_daily = quota["daily_limit"] - quota["daily_used"]
        if estimated_tokens > remaining_daily:
            return False, {
                "reason": "daily_limit_exceeded",
                "message": f"日配额不足 (剩余 {remaining_daily} tokens)",
                "remaining_daily": remaining_daily,
                "remaining_monthly": quota["monthly_limit"] - quota["monthly_used"],
            }

        # 检查月配额
        remaining_monthly = quota["monthly_limit"] - quota["monthly_used"]
        if estimated_tokens > remaining_monthly:
            return False, {
                "reason": "monthly_limit_exceeded",
                "message": f"月配额不足 (剩余 {remaining_monthly} tokens)",
                "remaining_daily": remaining_daily,
                "remaining_monthly": remaining_monthly,
            }

        return True, {
            "remaining_daily": remaining_daily,
            "remaining_monthly": remaining_monthly,
            "estimated_tokens": estimated_tokens,
        }

    async def consume(self, user_id: str = "anonymous", tokens: int = 0) -> bool:
        """消费用户配额"""
        try:
            self._reset_if_new_day(user_id)
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """
                    UPDATE user_quotas
                    SET daily_used = daily_used + ?,
                        monthly_used = monthly_used + ?,
                        updated_at = ?
                    WHERE user_id = ?
                    """,
                    (tokens, tokens, datetime.now().isoformat(), user_id),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"[QuotaManager] 消费配额失败: {e}")
            return False

    def set_user_quota(self, user_id: str, daily_limit: Optional[int] = None,
                       monthly_limit: Optional[int] = None,
                       per_request_limit: Optional[int] = None,
                       reason: str = "", created_by: str = "admin") -> bool:
        """设置用户配额（管理员操作）"""
        try:
            self._get_or_create_user_quota(user_id)
            with sqlite3.connect(str(self.db_path)) as conn:
                updates = []
                params = []
                if daily_limit is not None:
                    updates.append("daily_limit = ?")
                    params.append(daily_limit)
                if monthly_limit is not None:
                    updates.append("monthly_limit = ?")
                    params.append(monthly_limit)
                if per_request_limit is not None:
                    updates.append("per_request_limit = ?")
                    params.append(per_request_limit)

                if updates:
                    updates.append("updated_at = ?")
                    params.append(datetime.now().isoformat())
                    params.append(user_id)
                    conn.execute(
                        f"UPDATE user_quotas SET {', '.join(updates)} WHERE user_id = ?",
                        params,
                    )

                # 记录配额变更
                for qtype, value in [("daily", daily_limit), ("monthly", monthly_limit),
                                      ("per_request", per_request_limit)]:
                    if value is not None:
                        conn.execute(
                            """
                            INSERT INTO quota_overrides
                            (user_id, quota_type, value, reason, created_by, created_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (user_id, qtype, value, reason, created_by,
                             datetime.now().isoformat()),
                        )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"[QuotaManager] 设置配额失败: {e}")
            return False

    def get_quota_info(self, user_id: str = "anonymous") -> Dict:
        """获取用户配额信息"""
        self._reset_if_new_day(user_id)
        quota = self._get_or_create_user_quota(user_id)
        return {
            "user_id": user_id,
            "daily_limit": quota["daily_limit"],
            "monthly_limit": quota["monthly_limit"],
            "per_request_limit": quota["per_request_limit"],
            "daily_used": quota["daily_used"],
            "monthly_used": quota["monthly_used"],
            "daily_remaining": quota["daily_limit"] - quota["daily_used"],
            "monthly_remaining": quota["monthly_limit"] - quota["monthly_used"],
        }
