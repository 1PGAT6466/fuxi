"""
kun/utils.py — 坤卦工具函数
===========================

提供坤卦模块的工具函数。
"""

import hashlib
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("bagua.kun")


def compute_content_hash(content: str) -> str:
    """计算内容哈希值

    Args:
        content: 内容

    Returns:
        内容哈希值
    """
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def extract_keywords(content: str) -> List[str]:
    """提取关键词

    Args:
        content: 内容

    Returns:
        关键词列表
    """
    # 简单实现：提取中文和英文单词
    words = re.findall(r'[\u4e00-\u9fa5]+|[a-zA-Z]+', content)
    return list(set(words))


def truncate_content(content: str, max_length: int = 200) -> str:
    """截断内容

    Args:
        content: 内容
        max_length: 最大长度

    Returns:
        截断后的内容
    """
    if len(content) <= max_length:
        return content
    return content[:max_length] + "..."


def format_timestamp(timestamp: float) -> str:
    """格式化时间戳

    Args:
        timestamp: 时间戳

    Returns:
        格式化后的时间字符串
    """
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))


def parse_timestamp(timestamp_str: str) -> float:
    """解析时间戳

    Args:
        timestamp_str: 时间字符串

    Returns:
        时间戳
    """
    return time.mktime(time.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S"))


def validate_session_id(session_id: str) -> bool:
    """验证会话 ID

    Args:
        session_id: 会话 ID

    Returns:
        是否有效
    """
    return bool(session_id and isinstance(session_id, str))


def validate_content(content: str) -> bool:
    """验证内容

    Args:
        content: 内容

    Returns:
        是否有效
    """
    return bool(content and isinstance(content, str))


def sanitize_filename(filename: str) -> str:
    """清理文件名

    Args:
        filename: 文件名

    Returns:
        清理后的文件名
    """
    # 移除非法字符
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    return filename


def ensure_dir(path: str) -> None:
    """确保目录存在

    Args:
        path: 目录路径
    """
    if not os.path.exists(path):
        os.makedirs(path)


def read_json_file(path: str) -> Dict[str, Any]:
    """读取 JSON 文件

    Args:
        path: 文件路径

    Returns:
        JSON 数据
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"读取 JSON 文件失败: {path}, 错误: {e}")
        return {}


def write_json_file(path: str, data: Dict[str, Any]) -> bool:
    """写入 JSON 文件

    Args:
        path: 文件路径
        data: JSON 数据

    Returns:
        是否成功
    """
    try:
        ensure_dir(os.path.dirname(path))
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"写入 JSON 文件失败: {path}, 错误: {e}")
        return False
