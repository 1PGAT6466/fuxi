"""
services/table_parser.py — 表格解析兼容层（v1.50）
重定向到 src.taiyang.table_parser，提供 Markdown 表格提取与行解析。
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# ============================================================
# 从实际实现重导出所有公共 API
# ============================================================
from src.taiyang.table_parser import (  # noqa: F401
    parse_table_to_rows,
    extract_tables_from_markdown,
)

__all__ = [
    "parse_table_to_rows",
    "extract_tables_from_markdown",
]
