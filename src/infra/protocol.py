"""
protocol.py — 象间通信协议
定义象间通信的数据结构 + 信号类型
"""
from dataclasses import dataclass, field
from typing import Any, Dict
from enum import Enum
import time


# 信号类型
class SignalType(Enum):
    QUERY = "query"
    SEARCH = "search"
    DIGEST = "digest"
    RESULT = "result"
    ANSWER = "answer"
    EXTRACTION = "extraction"
    REFLECT = "reflect"
    VALIDATE = "validate"
    CORRECT = "correct"
    ROUTE = "route"
    RETRY = "retry"
    FALLBACK = "fallback"
    HEARTBEAT = "heartbeat"
    GROWTH = "growth"
    ALERT = "alert"


# 信号优先级
class SignalPriority(Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


# 信号超时配置
SIGNAL_TIMEOUT = {
    "query": 5.0,
    "search": 3.0,
    "digest": 30.0,
    "heartbeat": 1.0,
    "reflect": 2.0,
    "default": 5.0,
}


@dataclass
class Signal:
    """经络信号"""
    source: str
    target: str
    signal_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = 2  # SignalPriority.NORMAL
    signal_id: str = ""
    timestamp: float = 0

    def __post_init__(self):
        if not self.signal_id:
            import uuid
            self.signal_id = str(uuid.uuid4())[:8]
        if not self.timestamp:
            self.timestamp = time.time()


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
