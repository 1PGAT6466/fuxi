"""
internal_ip_filter.py — 出站请求内部 IP 过滤 (v1.50 P0 安全修复)

防止联网搜索等出站请求泄露内网信息。

设计原则：
  - 纯函数，无副作用
  - 解析 URL 中的主机名/IP，匹配内网地址段
  - 异常安全：解析失败时默认拒绝（安全优先）

内网地址范围：
  - 10.0.0.0/8
  - 172.16.0.0/12
  - 192.168.0.0/16
  - 127.0.0.0/8 (loopback)
  - localhost
  - 0.0.0.0
"""

import logging
import re
import socket
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger("internal_ip_filter")

# ============================================================================
# 内网 IP 正则模式
# ============================================================================

INTERNAL_IP_PATTERNS = [
    r"^10\.",  # 10.0.0.0/8
    r"^172\.(1[6-9]|2[0-9]|3[01])\.",  # 172.16.0.0/12
    r"^192\.168\.",  # 192.168.0.0/16
    r"^127\.",  # 127.0.0.0/8 (loopback)
    r"^localhost$",  # localhost
    r"^0\.0\.0\.0$",  # 0.0.0.0
    r"^\[::1\]$",  # IPv6 loopback
    r"^::1$",  # IPv6 loopback (无括号)
]

# 编译正则（一次性）
_INTERNAL_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INTERNAL_IP_PATTERNS]


def is_internal_ip(hostname: str) -> bool:
    """检查主机名/IP 是否为内网地址

    Args:
        hostname: 主机名或 IP 地址字符串

    Returns:
        True if 内网地址，False otherwise
    """
    if not hostname or not isinstance(hostname, str):
        return False

    host = hostname.strip().lower()

    # 1. 正则匹配已知内网模式
    for pattern in _INTERNAL_PATTERNS:
        if pattern.search(host):
            return True

    # 2. 如果是主机名，尝试 DNS 解析后检查
    if not _is_ip_address(host):
        try:
            resolved = socket.gethostbyname(host)
            for pattern in _INTERNAL_PATTERNS:
                if pattern.search(resolved):
                    logger.warning(f"[InternalIPFilter] 主机名 {host} 解析为内网 IP: {resolved}")
                    return True
        except socket.gaierror:
            # DNS 解析失败 → 无法确认，安全起见不阻止
            logger.debug(f"[InternalIPFilter] DNS 解析失败: {host}")
            pass
        except Exception as e:
            logger.debug(f"[InternalIPFilter] 主机名检查异常: {host}, {e}")

    return False


def is_internal_url(url: str) -> bool:
    """检查 URL 是否指向内网地址

    Args:
        url: 完整 URL 字符串

    Returns:
        True if 指向内网，False otherwise
    """
    if not url or not isinstance(url, str):
        return False

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False
        return is_internal_ip(hostname)
    except (ValueError, AttributeError) as e:
        logger.warning(f"[InternalIPFilter] URL 解析失败: {url[:100]}, {e}")
        # 解析失败 → 安全起见，视为内部地址（拒绝请求）
        return True


def check_outbound_url(url: str) -> bool:
    """出站请求前的 URL 安全检查

    如果 URL 指向内网地址，记录告警并拒绝。

    Args:
        url: 待检查的 URL

    Returns:
        True if 允许出站，False if 应拒绝
    """
    if is_internal_url(url):
        logger.warning(f"[InternalIPFilter] 拦截出站请求到内网地址: {url[:200]}")
        return False
    return True


def _is_ip_address(host: str) -> bool:
    """简单判断是否为 IP 地址（IPv4/IPv6）"""
    # IPv4
    parts = host.split(".")
    if len(parts) == 4:
        try:
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            return False
    # IPv6
    if ":" in host:
        return True
    return False
