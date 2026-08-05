"""
transaction.py — 事务管理工具（P0 缺陷修复）
============================================
提供上下文管理器和装饰器，确保数据库事务自动 rollback。

修复原则:
- 兼容现有的 SQLite 连接（sqlite3.Connection）和 SQLAlchemy Session
- 上下文管理器: transaction_context()
- 装饰器: @transactional
- 自动在异常时 rollback，正常时 commit
- 所有 rollback 带日志记录

使用示例:

    # 1. SQLite 连接
    conn = _connect(db_path)
    with transaction_context(conn):
        conn.execute("INSERT INTO ...")
        conn.execute("UPDATE ...")

    # 2. SQLAlchemy session
    with transaction_context(session):
        session.add(obj)
        ...

    # 3. 装饰器模式
    @transactional(conn_factory=lambda: _connect(db_path))
    def batch_insert(conn, data):
        conn.execute("INSERT INTO ...")

作者: 代码审查修复工具
日期: 2026-07-17
"""

import functools
import logging
import sqlite3
from contextlib import contextmanager
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ============ 核心：上下文管理器 ============


@contextmanager
def transaction_context(conn_or_session):
    """事务上下文管理器 - 自动 commit/rollback

    支持:
    - sqlite3.Connection: commit() / rollback()
    - SQLAlchemy Session: commit() / rollback()
    - 任意实现 commit/rollback 接口的对象

    Args:
        conn_or_session: 数据库连接或 session 对象

    Yields:
        连接对象本身（用于 with ... as conn 语法）

    Raises:
        在 rollback 后重新抛出原始异常

    使用示例:
        conn = sqlite3.connect("data.db")
        try:
            with transaction_context(conn):
                conn.execute("INSERT INTO ...")
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            # 已自动 rollback，此处做业务处理
            ...
    """
    transaction_id = id(conn_or_session)
    logger.debug(f"[Transaction] 事务开始: {transaction_id}")

    try:
        yield conn_or_session
        # 正常退出：提交
        _commit(conn_or_session)
        logger.debug(f"[Transaction] 事务提交: {transaction_id}")
    except Exception as e:
        # 异常退出：回滚
        _rollback(conn_or_session, e)
        raise  # 重新抛出原始异常


def _commit(conn_or_session):
    """执行 commit"""
    if hasattr(conn_or_session, "commit"):
        conn_or_session.commit()


def _rollback(conn_or_session, error: Exception):
    """执行 rollback 并记录日志"""
    transaction_id = id(conn_or_session)

    try:
        if hasattr(conn_or_session, "rollback"):
            conn_or_session.rollback()
            logger.warning(
                f"[Transaction] 事务回滚: {transaction_id}, " f"错误类型={type(error).__name__}, " f"错误信息={error}",
                exc_info=True,
            )
        else:
            logger.error(
                f"[Transaction] 无法回滚: {transaction_id} 不支持 rollback(), "
                f"错误类型={type(error).__name__}, "
                f"错误信息={error}",
                exc_info=True,
            )
    except Exception as rollback_error:
        # rollback 本身也失败了（罕见场景，如连接已断开）
        logger.critical(
            f"[Transaction] rollback 本身失败: {transaction_id}, "
            f"原始错误={type(error).__name__}: {error}, "
            f"rollback错误={type(rollback_error).__name__}: {rollback_error}",
            exc_info=True,
        )


# ============ 装饰器 ============


def transactional(conn_factory: Callable[[], Any] = None, conn_arg_index: int = 0, conn_param_name: str = "conn"):
    """事务装饰器 - 自动管理 commit/rollback

    Args:
        conn_factory: 创建连接的可调用对象（如 lambda: _connect(db_path)）
                      如果为 None，则从函数参数中提取连接对象
        conn_arg_index: 连接参数的位置索引（默认第一个参数）
        conn_param_name: 连接参数的名称（关键字参数时使用）

    使用示例:
        # 方式1: 工厂函数创建连接
        @transactional(conn_factory=lambda: _connect(db_path))
        def batch_save(conn, items):
            for item in items:
                conn.execute("INSERT INTO ...", item)

        # 方式2: 从参数中提取连接
        @transactional()
        def update_record(conn, record_id, data):
            conn.execute("UPDATE ...", data, record_id)

    注意:
        - 装饰器会在函数正常返回时 commit
        - 函数抛出任何异常时自动 rollback
        - rollback 会带日志记录
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 确定连接对象
            if conn_factory is not None:
                conn = conn_factory()
                # 将连接插入参数
                new_args = list(args)
                new_args.insert(conn_arg_index, conn)
                args = tuple(new_args)
            else:
                # 从参数中提取连接
                if conn_param_name in kwargs:
                    conn = kwargs[conn_param_name]
                elif len(args) > conn_arg_index:
                    conn = args[conn_arg_index]
                else:
                    raise ValueError(
                        f"@transactional: 无法找到连接参数 " f"'{conn_param_name}' 或位置索引 {conn_arg_index}"
                    )

            transaction_id = id(conn)
            logger.debug(f"[Transaction] 事务开始 (装饰器): {transaction_id}, " f"函数={func.__name__}")

            try:
                result = func(*args, **kwargs)
                _commit(conn)
                logger.debug(f"[Transaction] 事务提交 (装饰器): {transaction_id}")
                return result
            except Exception as e:
                _rollback(conn, e)
                raise

        return wrapper

    return decorator


# ============ 兼容工具：SQLite 连接工厂 ============


def sqlite_transaction(db_path: str):
    """SQLite 事务上下文管理器工厂

    使用:
        with sqlite_transaction("data.db") as conn:
            conn.execute("INSERT INTO ...")

    Args:
        db_path: SQLite 数据库文件路径

    Returns:
        transaction_context 上下文管理器
    """
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row

    return _SQLiteTransactionContext(conn)


class _SQLiteTransactionContext:
    """SQLite 专用事务上下文（管理连接生命周期）"""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.transaction_id = id(conn)

    def __enter__(self):
        logger.debug(f"[Transaction] 事务开始 (SQLite): {self.transaction_id}")
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            _commit(self.conn)
            logger.debug(f"[Transaction] 事务提交 (SQLite): {self.transaction_id}")
        else:
            _rollback(self.conn, exc_val)

        # 关闭连接
        try:
            self.conn.close()
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass

        return False  # 不抑制异常


# ============ 批量操作辅助 ============


def execute_in_transaction(conn: sqlite3.Connection, statements_and_params: list) -> None:
    """在事务中批量执行 SQL 语句

    Args:
        conn: SQLite 连接
        statements_and_params: [(sql, params), ...] 列表

    Raises:
        任何 execute 错误都会触发 rollback

    使用:
        ops = [
            ("INSERT INTO chunks (...) VALUES (?,?,?)", row1),
            ("UPDATE stats SET count = count + 1 WHERE id = ?", (1,)),
        ]
        execute_in_transaction(conn, ops)
    """
    with transaction_context(conn):
        for sql, params in statements_and_params:
            if isinstance(params, list):
                conn.executemany(sql, params)
            elif params is not None:
                conn.execute(sql, params)
            else:
                conn.execute(sql)


logger.info("[Transaction] 事务管理模块已加载")
