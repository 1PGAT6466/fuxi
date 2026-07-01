"""
protocol.py — 象间通信协议
定义象间通信的数据结构
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class SymbolRequest:
    """象间请求"""
    source: str          # 来源象 ID
    target: str          # 目标象 ID
    method: str          # 调用方法
    params: Dict[str, Any] = None
    timeout_ms: int = 5000
    request_id: str = ""

    def __post_init__(self):
        if self.params is None:
            self.params = {}


@dataclass
class SymbolResponse:
    """象间响应"""
    success: bool
    data: Any = None
    error: str = ""
    duration_ms: float = 0
    request_id: str = ""
