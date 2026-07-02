"""
connection_pool.py — 数据库连接池
SQLite连接复用 + 线程安全
"""
import sqlite3
import threading
import logging
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger("infra.connection_pool")


class SQLiteConnectionPool:
    """SQLite连接池"""

    def __init__(self, db_path: str, max_connections: int = 5):
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool = []
        self._lock = threading.Lock()
        self._active_connections = 0

    def _create_connection(self) -> sqlite3.Connection:
        """创建新连接"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")
        return conn

    @contextmanager
    def get_connection(self):
        """获取连接"""
        conn = None
        with self._lock:
            if self._pool:
                conn = self._pool.pop()
                self._active_connections += 1
            elif self._active_connections < self.max_connections:
                conn = self._create_connection()
                self._active_connections += 1

        if conn is None:
            # 等待连接释放
            import time
            for _ in range(10):
                time.sleep(0.1)
                with self._lock:
                    if self._pool:
                        conn = self._pool.pop()
                        self._active_connections += 1
                        break

        if conn is None:
            raise Exception("连接池已满")

        try:
            yield conn
        finally:
            with self._lock:
                self._pool.append(conn)
                self._active_connections -= 1

    def close_all(self):
        """关闭所有连接"""
        with self._lock:
            for conn in self._pool:
                try:
                    conn.close()
                except:
                    pass
            self._pool.clear()
            self._active_connections = 0


# 全局连接池
_pool: Optional[SQLiteConnectionPool] = None


def get_connection_pool(db_path: str = None) -> SQLiteConnectionPool:
    """获取全局连接池"""
    global _pool
    if _pool is None:
        from src.config import DB_PATH
        _pool = SQLiteConnectionPool(db_path or str(DB_PATH))
    return _pool
