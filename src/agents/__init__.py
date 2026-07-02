"""
base_agent.py — Agent 基类 v4.0
所有 Agent 继承此类，提供统一的 run()/reflect()/tools 接口
"""
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AgentMessage:
    """Agent 间通信的标准化消息"""
    source: str
    target: str
    msg_type: str  # "task_request", "task_result", "reflection", "error"
    payload: Dict[str, Any]
    correlation_id: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "source": self.source,
            "target": self.target,
            "msg_type": self.msg_type,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
        }


@dataclass
class ToolResult:
    """工具执行结果"""
    tool_name: str
    success: bool
    data: Any
    error: str = ""
    duration_ms: float = 0


@dataclass
class AgentContext:
    """Agent 执行上下文"""
    query: str
    history: List[Dict] = field(default_factory=list)
    intermediate_results: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    step: int = 0
    max_steps: int = 5
    total_tokens: int = 0
    max_tokens: int = 4000


class BaseAgent(ABC):
    """Agent 基类：统一 run()/reflect()/tools 接口"""

    def __init__(self, agent_id: str, description: str = ""):
        self.agent_id = agent_id
        self.description = description
        self._tools: Dict[str, callable] = {}
        self._metrics = {
            "total_runs": 0,
            "total_errors": 0,
            "total_duration_ms": 0,
            "total_tokens": 0,
        }

    def register_tool(self, name: str, func: callable):
        """注册工具"""
        self._tools[name] = func

    def get_tool_definitions(self) -> List[Dict]:
        """返回工具定义（供 LLM function calling）"""
        return []

    @abstractmethod
    async def run(self, ctx: AgentContext) -> Dict:
        """执行 Agent 主逻辑"""
        pass

    async def reflect(self, ctx: AgentContext, result: Dict) -> Dict:
        """反思执行结果，决定是否需要重试"""
        return {"should_retry": False, "reason": ""}

    async def execute_tool(self, tool_name: str, params: Dict) -> ToolResult:
        """执行工具"""
        if tool_name not in self._tools:
            return ToolResult(tool_name=tool_name, success=False, data=None, error=f"Tool '{tool_name}' not found")

        start = time.time()
        try:
            result = await self._tools[tool_name](**params)
            duration = (time.time() - start) * 1000
            return ToolResult(tool_name=tool_name, success=True, data=result, duration_ms=duration)
        except Exception as e:
            duration = (time.time() - start) * 1000
            return ToolResult(tool_name=tool_name, success=False, data=None, error=str(e), duration_ms=duration)

    def get_metrics(self) -> Dict:
        """返回 Agent 指标"""
        avg_duration = (
            self._metrics["total_duration_ms"] / self._metrics["total_runs"]
            if self._metrics["total_runs"] > 0 else 0
        )
        return {**self._metrics, "avg_duration_ms": round(avg_duration, 1)}

    def _record_run(self, duration_ms: float, tokens: int = 0, error: bool = False):
        """记录运行指标"""
        self._metrics["total_runs"] += 1
        self._metrics["total_duration_ms"] += duration_ms
        self._metrics["total_tokens"] += tokens
        if error:
            self._metrics["total_errors"] += 1
