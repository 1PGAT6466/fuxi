"""
logging.py — 统一日志格式
为四象模块提供统一的日志格式
"""
import logging
import uuid
from typing import Optional


def get_trace_id() -> str:
    """生成唯一的 trace_id"""
    return uuid.uuid4().hex[:12]


def setup_symbol_logger(symbol_id: str) -> logging.Logger:
    """为象设置专用的 logger"""
    logger = logging.getLogger(f"symbol.{symbol_id}")
    return logger


def log_with_trace(logger: logging.Logger, level: str, message: str, trace_id: Optional[str] = None):
    """带 trace_id 的日志"""
    if trace_id is None:
        trace_id = get_trace_id()
    logger.log(getattr(logging, level.upper()), f"[{trace_id}] {message}")
