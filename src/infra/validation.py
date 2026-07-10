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
    """清理输入 - 增强XSS防护"""
    if not text:
        return ""

    text = text.strip()
    if len(text) > max_length:
        text = text[:max_length]

    # 1. 拦截所有HTML标签（包括事件处理器）
    # 移除所有 <xxx> 标签，但保留内容
    text = re.sub(r'<[^>]*>', '', text)
    
    # 2. 拦截危险协议
    # javascript: 协议（大小写不敏感，处理各种编码）
    text = re.sub(r'javascript\s*:', 'javascript:', text, flags=re.IGNORECASE)
    text = re.sub(r'javascript:', '[BLOCKED]', text, flags=re.IGNORECASE)
    
    # data: 协议（大小写不敏感）
    text = re.sub(r'data\s*:', 'data:', text, flags=re.IGNORECASE)
    text = re.sub(r'data:', '[BLOCKED]', text, flags=re.IGNORECASE)
    
    # vbscript: 协议
    text = re.sub(r'vbscript\s*:', 'vbscript:', text, flags=re.IGNORECASE)
    text = re.sub(r'vbscript:', '[BLOCKED]', text, flags=re.IGNORECASE)
    
    # 3. 拦截事件处理器属性（on*）
    # 匹配 on开头的属性，如 onclick, onerror, onload, onmouseover 等
    text = re.sub(r'\bon\w+\s*=', '[BLOCKED]=', text, flags=re.IGNORECASE)
    
    # 4. 拦截常见的XSS攻击模式
    # alert(), confirm(), prompt() 等
    text = re.sub(r'\b(alert|confirm|prompt|eval|document\.cookie|window\.location)\s*\(', '[BLOCKED](', text, flags=re.IGNORECASE)
    
    # 5. 拦截 HTML 实体编码绕过
    # &lt;script 等
    text = re.sub(r'&lt;\s*script', '&lt;[BLOCKED]', text, flags=re.IGNORECASE)
    text = re.sub(r'&lt;\s*/\s*script', '&lt;/[BLOCKED]', text, flags=re.IGNORECASE)
    
    # 6. 拦截 SVG/XSS 攻击
    text = re.sub(r'<svg[^>]*>.*?</svg>', '[BLOCKED SVG]', text, flags=re.IGNORECASE | re.DOTALL)
    
    # 7. 拦截 CSS 表达式攻击
    text = re.sub(r'expression\s*\(', '[BLOCKED](', text, flags=re.IGNORECASE)
    
    return text
