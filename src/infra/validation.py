"""
validation.py — 请求验证
输入验证 + 清理
"""
import re
import logging
from typing import Any

logger = logging.getLogger("infra.validation")


class ValidationError(Exception):
    """验证错误"""
    pass


def validate_query(query: str, max_length: int = 1000) -> str:
    """验证查询"""
    if not query or not query.strip():
        raise ValidationError("查询不能为空")

    query = query.strip()
    if len(query) > max_length:
        raise ValidationError(f"查询长度超过限制 ({max_length})")

    # 清理潜在的注入
    query = re.sub(r'[<>"\']', '', query)

    return query


def validate_top_k(top_k: Any, default: int = 10, max_value: int = 100) -> int:
    """验证top_k参数"""
    try:
        top_k = int(top_k)
    except (TypeError, ValueError):
        return default

    if top_k < 1:
        return default
    if top_k > max_value:
        return max_value

    return top_k


def validate_file_path(file_path: str) -> str:
    """验证文件路径"""
    if not file_path or not file_path.strip():
        raise ValidationError("文件路径不能为空")

    file_path = file_path.strip()

    # 检查路径遍历
    if '..' in file_path:
        raise ValidationError("无效的文件路径")

    return file_path


def sanitize_input(text: str, max_length: int = 10000) -> str:
    """清理输入"""
    if not text:
        return ""

    text = text.strip()
    if len(text) > max_length:
        text = text[:max_length]

    # 清理潜在的XSS
    text = text.replace('<script', '&lt;script')
    text = text.replace('</script', '&lt;/script')

    return text
