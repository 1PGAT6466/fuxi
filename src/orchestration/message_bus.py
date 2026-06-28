"""
message_bus.py — Agent 间异步通信 v4.0
发布/订阅 + 请求/响应
"""
import asyncio
import logging
import time
from typing import Dict, List, Callable, Awaitable, Optional
from collections import defaultdict

from src.protocols import ProtocolMessage, MessageType

logger = logging.getLogger(__name__)


class MessageBus:
    """Agent 间异步消息总线"""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._request_futures: Dict[str, asyncio.Future] = {}
        self._message_log: List[Dict] = []
        self._max_log_size = 1000

    def subscribe(self, msg_type: str, handler: Callable[[ProtocolMessage], Awaitable[None]]):
        """订阅消息类型"""
        self._subscribers[msg_type].append(handler)

    async def publish(self, message: ProtocolMessage):
        """发布消息"""
        self._log_message(message)
        handlers = self._subscribers.get(message.msg_type.value, [])
        for handler in handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"[MessageBus] Handler error: {e}")

    async def request(self, message: ProtocolMessage, timeout: float = 30) -> Optional[ProtocolMessage]:
        """请求-响应模式"""
        future = asyncio.get_event_loop().create_future()
        self._request_futures[message.correlation_id] = future
        await self.publish(message)
        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            logger.warning(f"[MessageBus] Request timeout: {message.correlation_id}")
            return None
        finally:
            self._request_futures.pop(message.correlation_id, None)

    def resolve(self, correlation_id: str, response: ProtocolMessage):
        """响应请求"""
        future = self._request_futures.get(correlation_id)
        if future and not future.done():
            future.set_result(response)

    def _log_message(self, message: ProtocolMessage):
        self._message_log.append(message.to_dict())
        if len(self._message_log) > self._max_log_size:
            self._message_log = self._message_log[-self._max_log_size:]

    def get_stats(self) -> Dict:
        return {
            "total_messages": len(self._message_log),
            "subscribers": {k: len(v) for k, v in self._subscribers.items()},
            "pending_requests": len(self._request_futures),
        }


# 全局实例
_bus = None

def get_message_bus() -> MessageBus:
    global _bus
    if _bus is None:
        _bus = MessageBus()
    return _bus
