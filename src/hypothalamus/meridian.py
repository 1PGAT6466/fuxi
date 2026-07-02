"""
hypothalamus/meridian.py — 伏羲经络系统（全身信号总线）v1.40

经络 = 伏羲体内唯一的通信网络。
所有器官通过经络收发信号，大脑通过经络指挥全身。

设计原则：
- pub/sub 模式：器官订阅自己关心的信号类型
- 异步非阻塞：不因一个器官慢而拖累全身
- 可追溯：每条信号有唯一起源和目标
- 优先级：紧急信号（心跳异常）优先于普通信号（查询日志）
"""

import asyncio
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Set
import logging

logger = logging.getLogger("meridian")


class SignalPriority(IntEnum):
    """信号优先级"""
    CRITICAL = 0    # 紧急：心跳停跳、LLM 全部不可用
    HIGH = 1        # 高：器官异常、检索失败
    NORMAL = 2      # 普通：搜索请求、Wiki 查询
    LOW = 3         # 低：日志记录、统计更新


@dataclass
class Signal:
    """经络中的一条信号"""
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    source: str = ""          # 发送器官 (brain/stomach/spleen/lung/liver/heart/skeleton/skin/limbs)
    target: str = ""          # 接收器官（空=广播）。支持单个器官ID、多个（逗号分隔）、"*"=全局广播
    signal_type: str = ""     # 信号类型 (query/result/alert/heartbeat/update/command)
    payload: Any = None       # 信号携带的数据
    priority: SignalPriority = SignalPriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    reply_to: str = ""        # 回复给哪个信号
    expect_reply: bool = False  # 是否需要回复
    trace_id: str = ""        # 追踪链路 ID

    def __lt__(self, other):
        return id(self) < id(other)


@dataclass
class OrganInfo:
    """器官注册信息"""
    organ_id: str
    name: str                          # 人类可读名称
    emoji: str                         # 图标
    description: str
    alive: bool = True
    last_heartbeat: float = field(default_factory=time.time)
    signals_sent: int = 0
    signals_received: int = 0


class Meridian:
    """经络系统——伏羲全身唯一的信号总线
    
    使用方式（在 Brain 中）：
        meridian = Meridian()
        
        # 大脑发出命令
        signal_id = meridian.send(Signal(
            source="brain",
            target="limbs",
            signal_type="query",
            payload={"query": "PA66拉伸强度"}
        ))
        
        # 器官订阅信号
        @meridian.subscribe("limbs", "query")
        async def handle_query(signal):
            results = await search(signal.payload["query"])
            meridian.reply(signal, results)
"""

    def __init__(self):
        # 订阅表：{organ_id: {signal_type: [handler, ...]}}
        self._subscriptions: Dict[str, Dict[str, List[Callable]]] = defaultdict(
            lambda: defaultdict(list)
        )
        # 注册的器官
        self._organs: Dict[str, OrganInfo] = {}
        # 信号历史（最近 500 条）
        self._history: List[Signal] = []
        self._max_history = 500
        # 活跃信号（等待回复的）
        self._pending: Dict[str, Signal] = {}
        # 回复结果
        self._replies: Dict[str, asyncio.Future] = {}
        # 异步队列
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._services: Dict[str, Callable] = {}
        # 四象注册表（四象归位）
        self._symbols: Dict[str, Dict] = {}
    
    # ========== 器官注册 ==========
    
    def register_organ(self, organ_id: str, name: str, emoji: str, 
                       description: str = "") -> OrganInfo:
        """注册一个器官到经络"""
        info = OrganInfo(
            organ_id=organ_id,
            name=name,
            emoji=emoji,
            description=description,
        )
        self._organs[organ_id] = info
        logger.info(f"[Meridian] Organ registered: {emoji} {name} ({organ_id})")
        return info

    # ========== 象注册（四象归位） ==========
    
    def register_symbol(self, symbol_id: str, name: str, handler) -> None:
        """注册一个象到经络"""
        self._symbols[symbol_id] = {
            "name": name,
            "handler": handler,
            "registered_at": time.time(),
        }
        logger.info(f"[Meridian] Symbol registered: {name} ({symbol_id})")

    async def call_symbol(self, symbol_id: str, method: str, params: dict = None, timeout: float = 5.0):
        """调用另一个象的方法"""
        symbol = self._symbols.get(symbol_id)
        if not symbol:
            raise ValueError(f"Unknown symbol: {symbol_id}")
        handler = symbol["handler"]
        fn = getattr(handler, method)
        return await asyncio.wait_for(fn(**(params or {})), timeout=timeout)

    def last_heartbeat_ago(self, organ_id: str) -> float:
        """返回最后一次心跳距今的秒数"""
        info = self._organs.get(organ_id)
        if not info:
            return 0
        return time.time() - info.last_heartbeat

    # ========== 1.40 P3: Service Bridge (decouple organ direct calls) ==========

    def register_service(self, service_key: str, service_fn: Callable) -> None:
        """Register a service function so organs call it via meridian
        instead of directly importing db/services modules."""
        self._services[service_key] = service_fn
        logger.debug(f"[Meridian] Service registered: {service_key}")

    def call_service(self, service_key: str, *args: Any, **kwargs: Any) -> Any:
        """Synchronous service call through meridian bridge."""
        if service_key not in self._services:
            raise RuntimeError(
                f"Service {service_key!r} not registered on Meridian. "
                f"Call meridian.register_service({service_key!r}, fn) first."
            )
        return self._services[service_key](*args, **kwargs)

    async def call_service_async(self, service_key: str, *args: Any, **kwargs: Any) -> Any:
        """Async service call through meridian bridge."""
        if service_key not in self._services:
            raise RuntimeError(f"Service {service_key!r} not registered on Meridian.")
        fn = self._services[service_key]
        if asyncio.iscoroutinefunction(fn):
            return await fn(*args, **kwargs)
        return fn(*args, **kwargs)
    
    def heartbeat(self, organ_id: str) -> None:
        """器官上报心跳"""
        if organ_id in self._organs:
            self._organs[organ_id].last_heartbeat = time.time()
            self._organs[organ_id].alive = True
    
    def is_alive(self, organ_id: str) -> bool:
        """检查器官是否存活（心跳检测已禁用，已注册器官始终返回True）"""
        if organ_id not in self._organs and organ_id not in self._symbols:
            return False
        # 心跳检测已禁用：不启用系统使用心跳检测
        return True
    
    def get_organ(self, organ_id: str) -> Optional[OrganInfo]:
        """获取器官信息"""
        return self._organs.get(organ_id)
    
    def list_organs(self) -> List[OrganInfo]:
        """列出所有器官"""
        return list(self._organs.values())
    
    # ========== 四象查询（四象归位） ==========
    
    def get_symbol(self, symbol_id: str):
        """获取象的处理器"""
        symbol = self._symbols.get(symbol_id)
        if symbol:
            return symbol.get("handler")
        return None
    
    def get_symbol_status(self, symbol_id: str) -> dict:
        """获取象的状态"""
        symbol = self._symbols.get(symbol_id)
        if not symbol:
            return {"symbol": symbol_id, "alive": False, "status": "not_registered"}
        
        handler = symbol.get("handler")
        if handler and hasattr(handler, "get_status"):
            return handler.get_status()
        
        return {
            "symbol": symbol_id,
            "alive": True,
            "status": "unknown",
            "name": symbol.get("name", ""),
        }
    
    def list_symbols(self) -> list:
        """列出所有象"""
        result = []
        for symbol_id, info in self._symbols.items():
            handler = info.get("handler")
            status = handler.get_status() if handler and hasattr(handler, "get_status") else {}
            result.append({
                "symbol_id": symbol_id,
                "name": info.get("name", ""),
                "status": status,
            })
        return result
    
    # ========== 订阅 ==========
    
    def subscribe(self, organ_id: str, signal_type: str, 
                  handler: Callable) -> None:
        """器官订阅某种信号类型
        
        Args:
            organ_id: 订阅者器官 ID
            signal_type: 信号类型（query/result/alert/heartbeat/update/command）
            handler: async 回调函数 async def handler(signal: Signal)
        """
        self._subscriptions[organ_id][signal_type].append(handler)
        # 通配符 "*" 表示订阅所有信号
        self._subscriptions[organ_id]["*"].append(handler)
    
    # ========== 发送 ==========
    
    def send(self, signal: Signal) -> str:
        """发送信号到经络——非阻塞，投递到异步队列"""
        signal.timestamp = time.time()
        self._add_to_history(signal)
        self._queue.put_nowait((int(signal.priority), signal))
        
        if signal.source in self._organs:
            self._organs[signal.source].signals_sent += 1
        
        return signal.signal_id
    
    async def send_and_wait(self, signal: Signal, timeout: float = 5.0) -> Optional[Any]:
        """发送信号并等待回复"""
        signal.expect_reply = True
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._replies[signal.signal_id] = future
        self.send(signal)
        
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"[Meridian] Signal {signal.signal_id} timed out waiting for reply")
            self._replies.pop(signal.signal_id, None)
            return None
    
    def reply(self, original_signal: Signal, data: Any) -> None:
        """回复一个信号"""
        reply_signal = Signal(
            source=original_signal.target,
            target=original_signal.source,
            signal_type="reply",
            payload=data,
            reply_to=original_signal.signal_id,
            trace_id=original_signal.trace_id,
        )
        self.send(reply_signal)
        
        # 如果有未来等待，设置结果
        fid = original_signal.signal_id
        if fid in self._replies:
            try:
                self._replies[fid].set_result(data)
            except Exception as e:
                logger.warning(f"[Meridian] reply set failed for {fid}: {e}")
            self._replies.pop(fid, None)
    
    def get_health(self) -> dict:
        """v1.42: 经络健康指标"""
        return {
            "organs_registered": len(self._organs),
            "queue_size": self._queue.qsize() if self._queue else 0,
            "pending_replies": len(self._replies),
            "total_signals_sent": sum(o.signals_sent for o in self._organs.values()),
        }

    def broadcast(self, source: str, signal_type: str, payload: Any,
                  priority: SignalPriority = SignalPriority.NORMAL) -> str:
        """广播信号给所有器官"""
        return self.send(Signal(
            source=source,
            target="*",
            signal_type=signal_type,
            payload=payload,
            priority=priority,
        ))
    
    # ========== 分发引擎 ==========
    
    async def _dispatch(self, signal: Signal) -> None:
        """将信号分发给匹配的订阅者"""
        dispatched = 0
        
        # 确定目标器官列表
        if signal.target == "*":
            targets = list(self._organs.keys())
        else:
            targets = [t.strip() for t in signal.target.split(",") if t.strip()]
        
        for organ_id in targets:
            if organ_id not in self._subscriptions:
                continue
            
            # 匹配信号类型 + 通配符
            handlers = []
            handlers.extend(self._subscriptions[organ_id].get(signal.signal_type, []))
            handlers.extend(self._subscriptions[organ_id].get("*", []))
            
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(signal)
                    else:
                        handler(signal)
                    dispatched += 1
                    
                    if organ_id in self._organs:
                        self._organs[organ_id].signals_received += 1
                except Exception as e:
                    logger.error(f"[Meridian] Handler error for {organ_id}/{signal.signal_type}: {e}")
        
        if dispatched == 0 and signal.expect_reply:
            logger.debug(f"[Meridian] Signal {signal.signal_id} had no subscribers: {signal.source}→{signal.target}/{signal.signal_type}")
    
    # ========== 生命周期 ==========
    
    async def start(self) -> None:
        """启动经络引擎"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("[Meridian] 经络系统已启动 ⚡")
    
    async def stop(self) -> None:
        """停止经络引擎"""
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("[Meridian] 经络系统已停止")
    
    async def _run_loop(self) -> None:
        """主循环：从队列取信号 → 分发"""
        while self._running:
            try:
                _, signal = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._dispatch(signal)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Meridian] Dispatch error: {e}")
    
    # ========== 辅助 ==========
    
    def _add_to_history(self, signal: Signal) -> None:
        self._history.append(signal)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
    
    def get_history(self, limit: int = 50) -> List[Dict]:
        """获取信号历史"""
        return [
            {
                "signal_id": s.signal_id,
                "source": s.source,
                "target": s.target,
                "type": s.signal_type,
                "priority": s.priority.name,
                "timestamp": s.timestamp,
            }
            for s in self._history[-limit:]
        ]
    
    def stats(self) -> Dict:
        """经络系统统计"""
        return {
            "organs_registered": len(self._organs),
            "organs_alive": sum(1 for o in self._organs.values() if self.is_alive(o.organ_id)),
            "signals_in_history": len(self._history),
            "queue_size": self._queue.qsize(),
            "pending_replies": len(self._replies),
            "running": self._running,
        }
