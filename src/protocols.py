"""
protocols.py — Agent 通信协议 v4.0
标准化消息格式 + JSON Schema 定义
"""
from typing import Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import time


class MessageType(str, Enum):
    TASK_REQUEST = "task_request"
    TASK_RESULT = "task_result"
    REFLECTION = "reflection"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ProtocolMessage:
    """Agent 间通信的标准消息"""
    msg_id: str
    source: str
    target: str
    msg_type: MessageType
    payload: Dict[str, Any]
    priority: Priority = Priority.NORMAL
    correlation_id: str = ""
    reply_to: str = ""
    timestamp: float = field(default_factory=time.time)
    ttl_seconds: int = 300

    def to_dict(self) -> Dict:
        return {
            "msg_id": self.msg_id,
            "source": self.source,
            "target": self.target,
            "msg_type": self.msg_type.value,
            "payload": self.payload,
            "priority": self.priority.value,
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
            "timestamp": self.timestamp,
            "ttl_seconds": self.ttl_seconds,
        }

    def is_expired(self) -> bool:
        return (time.time() - self.timestamp) > self.ttl_seconds

    @classmethod
    def from_dict(cls, data: Dict) -> "ProtocolMessage":
        return cls(
            msg_id=data.get("msg_id", ""),
            source=data.get("source", ""),
            target=data.get("target", ""),
            msg_type=MessageType(data.get("msg_type", "task_request")),
            payload=data.get("payload", {}),
            priority=Priority(data.get("priority", "normal")),
            correlation_id=data.get("correlation_id", ""),
            reply_to=data.get("reply_to", ""),
            timestamp=data.get("timestamp", time.time()),
            ttl_seconds=data.get("ttl_seconds", 300),
        )


# JSON Schema 定义
TOOL_SCHEMAS = {
    "search_knowledge": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索查询"},
            "top_k": {"type": "integer", "description": "返回结果数", "default": 5, "minimum": 1, "maximum": 20},
        },
        "required": ["query"],
    },
    "search_wiki": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索查询"},
        },
        "required": ["query"],
    },
    "call_llm": {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "LLM 提示词"},
        },
        "required": ["prompt"],
    },
    "done": {
        "type": "object",
        "properties": {
            "reason": {"type": "string", "description": "完成原因"},
        },
        "required": ["reason"],
    },
}
