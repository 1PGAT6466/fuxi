"""
v2.1 兼容层：Meridian — 基于 IntentBus 的完整兼容壳

旧代码使用 Meridian 的 register_organ、send、broadcast、stats 等 API，
现在通过兼容壳映射到 IntentBus 或本地实现。
"""
import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Set

from src.bagua.intent_bus import IntentBus, Signal as BusSignal, Priority as BusPriority

# ---------------------------------------------------------------------------
# 旧 Priority 枚举（兼容 test_meridian.py）
# ---------------------------------------------------------------------------


class SignalPriority(IntEnum):
    """信号优先级 — 兼容旧 API"""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


# ---------------------------------------------------------------------------
# 旧 Signal dataclass（兼容 test_meridian.py & organs）
# ---------------------------------------------------------------------------


@dataclass
class Signal:
    """经络中的一条信号 — 兼容旧 API"""
    signal_id: str = field(default_factory=lambda: str(__import__('uuid').uuid4())[:8])
    source: str = ""
    target: str = ""
    signal_type: str = ""
    payload: Any = None
    priority: SignalPriority = SignalPriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    reply_to: str = ""
    expect_reply: bool = False
    trace_id: str = ""

    def __lt__(self, other):
        return id(self) < id(other)


# ---------------------------------------------------------------------------
# OrganInfo（兼容旧 API）
# ---------------------------------------------------------------------------


@dataclass
class OrganInfo:
    """器官注册信息"""
    organ_id: str
    name: str
    emoji: str
    description: str
    alive: bool = True
    last_heartbeat: float = field(default_factory=time.time)
    signals_sent: int = 0
    signals_received: int = 0


# ---------------------------------------------------------------------------
# Meridian — 兼容壳（基于 IntentBus + 本地实现）
# ---------------------------------------------------------------------------


class Meridian:
    """v2.1 兼容层：Meridian 已由 IntentBus 替代

    保留所有旧 API 以支持现有测试和器官代码。
    """

    def __init__(self):
        # 委托到 IntentBus
        self._bus = IntentBus(name="meridian_compat")
        # 本地兼容状态
        self._organs: Dict[str, OrganInfo] = {}
        self._subscriptions: Dict[str, Dict[str, List[Callable]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._history: List[Signal] = []
        self._max_history = 500
        self._pending: Dict[str, Signal] = {}
        self._replies: Dict[str, asyncio.Future] = {}
        self._queue = None  # lazy init with asyncio.PriorityQueue
        self._running = False
        self._task = None
        self._services: Dict[str, Callable] = {}
        self._symbols: Dict[str, Dict] = {}
        self._stats_counter: Dict[str, int] = {
            "sent": 0, "received": 0, "errors": 0,
            "broadcasts": 0, "heartbeats": 0,
        }

    # ========== 器官注册 ==========

    def register_organ(self, organ_id: str, name: str, emoji: str,
                       description: str = "") -> OrganInfo:
        info = OrganInfo(organ_id=organ_id, name=name, emoji=emoji, description=description)
        self._organs[organ_id] = info
        return info

    def register_symbol(self, symbol_id: str, name: str, handler) -> None:
        self._symbols[symbol_id] = {"name": name, "handler": handler, "registered_at": time.time()}

    def get_organ(self, organ_id: str) -> Optional[OrganInfo]:
        return self._organs.get(organ_id)

    def list_organs(self) -> List[OrganInfo]:
        return list(self._organs.values())

    def is_alive(self, organ_id: str) -> bool:
        info = self._organs.get(organ_id)
        if info is None:
            return False
        return info.alive and (time.time() - info.last_heartbeat) < 30

    # ========== 心跳 ==========

    def heartbeat(self, organ_id: str) -> None:
        info = self._organs.get(organ_id)
        if info:
            info.last_heartbeat = time.time()
            info.alive = True
            self._stats_counter["heartbeats"] += 1

    def last_heartbeat_ago(self, organ_id: str) -> float:
        info = self._organs.get(organ_id)
        if info is None:
            return float("inf")
        return time.time() - info.last_heartbeat

    # ========== 信号发送 ==========

    def send(self, signal: Signal) -> str:
        signal.timestamp = time.time()
        self._add_to_history(signal)
        self._stats_counter["sent"] += 1
        # 同时也尝试通过 IntentBus 派发
        bus_signal = self._to_bus_signal(signal)
        try:
            self._bus.dispatch(bus_signal)
        except Exception:
            pass
        return signal.signal_id

    async def send_and_wait(self, signal: Signal, timeout: float = 5.0) -> Optional[Any]:
        self.send(signal)
        future = asyncio.get_event_loop().create_future()
        self._replies[signal.signal_id] = future
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def reply(self, original_signal: Signal, data: Any) -> None:
        reply_signal = Signal(
            source=original_signal.target,
            target=original_signal.source,
            signal_type="reply",
            payload=data,
            reply_to=original_signal.signal_id,
        )
        self.send(reply_signal)
        if original_signal.signal_id in self._replies:
            fut = self._replies.pop(original_signal.signal_id)
            if not fut.done():
                fut.set_result(data)

    def send_raw(self, target: str, signal_type: str, payload: Any,
                 priority: SignalPriority = SignalPriority.NORMAL) -> str:
        signal = Signal(
            source="system", target=target, signal_type=signal_type,
            payload=payload, priority=priority,
        )
        return self.send(signal)

    def broadcast(self, source: str, signal_type: str, payload: Any,
                  priority: SignalPriority = SignalPriority.NORMAL) -> List[str]:
        ids = []
        for organ_id in self._organs:
            sig = Signal(
                source=source, target=organ_id, signal_type=signal_type,
                payload=payload, priority=priority,
            )
            ids.append(self.send(sig))
        self._stats_counter["broadcasts"] += 1
        return ids

    # ========== 订阅 ==========

    def subscribe(self, organ_id: str, signal_type: str, handler: Callable) -> None:
        self._subscriptions[organ_id][signal_type].append(handler)

    # ========== 符号管理 ==========

    def get_symbol(self, symbol_id: str):
        return self._symbols.get(symbol_id, {}).get("handler")

    def get_symbol_status(self, symbol_id: str) -> dict:
        info = self._symbols.get(symbol_id, {})
        return {
            "symbol_id": symbol_id,
            "name": info.get("name", ""),
            "registered_at": info.get("registered_at", 0),
            "alive": bool(self._symbols.get(symbol_id)),
        }

    def list_symbols(self) -> list:
        return [
            {"symbol_id": sid, "name": d["name"], "registered_at": d["registered_at"]}
            for sid, d in self._symbols.items()
        ]

    # ========== 服务注册 ==========

    def register_service(self, service_key: str, service_fn: Callable) -> None:
        self._services[service_key] = service_fn

    def call_service(self, service_key: str, *args: Any, **kwargs: Any) -> Any:
        fn = self._services.get(service_key)
        if fn is None:
            raise KeyError(f"Service not found: {service_key}")
        return fn(*args, **kwargs)

    async def call_service_async(self, service_key: str, *args: Any, **kwargs: Any) -> Any:
        fn = self._services.get(service_key)
        if fn is None:
            raise KeyError(f"Service not found: {service_key}")
        if asyncio.iscoroutinefunction(fn):
            return await fn(*args, **kwargs)
        return fn(*args, **kwargs)

    # ========== 状态 / 统计 ==========

    def get_health(self) -> dict:
        alive_count = sum(1 for o in self._organs.values() if o.alive)
        return {
            "total_organs": len(self._organs),
            "alive_organs": alive_count,
            "signals_sent": self._stats_counter["sent"],
            "signals_received": self._stats_counter["received"],
            "errors": self._stats_counter["errors"],
        }

    def stats(self) -> Dict:
        return {
            "total_organs": len(self._organs),
            "alive_organs": sum(1 for o in self._organs.values() if o.alive),
            "signals_sent": self._stats_counter["sent"],
            "signals_received": self._stats_counter["received"],
            "errors": self._stats_counter["errors"],
            "broadcasts": self._stats_counter["broadcasts"],
            "heartbeats": self._stats_counter["heartbeats"],
            "history_size": len(self._history),
        }

    # ========== 历史 ==========

    def _add_to_history(self, signal: Signal) -> None:
        self._history.append(signal)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def get_history(self, limit: int = 50) -> List[Dict]:
        return [
            {
                "signal_id": s.signal_id,
                "source": s.source,
                "target": s.target,
                "signal_type": s.signal_type,
                "priority": s.priority.name if isinstance(s.priority, SignalPriority) else str(s.priority),
                "timestamp": s.timestamp,
            }
            for s in self._history[-limit:]
        ]

    # ========== 生命周期 ==========

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def _run_loop(self) -> None:
        pass

    async def _dispatch(self, signal: Signal) -> None:
        handlers = self._subscriptions.get(signal.target, {}).get(signal.signal_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(signal)
                else:
                    handler(signal)
            except Exception:
                self._stats_counter["errors"] += 1

    # ========== 内部辅助 ==========

    def _to_bus_signal(self, signal: Signal) -> BusSignal:
        prio_map = {
            SignalPriority.CRITICAL: BusPriority.HIGH,
            SignalPriority.HIGH: BusPriority.HIGH,
            SignalPriority.NORMAL: BusPriority.NORMAL,
            SignalPriority.LOW: BusPriority.LOW,
        }
        return BusSignal(
            signal_id=signal.signal_id,
            source=signal.source,
            target=signal.target,
            signal_type=BusSignal.signal_type.__class__("REQUEST"),
            priority=prio_map.get(signal.priority, BusPriority.NORMAL),
            payload={"type": signal.signal_type, "data": signal.payload},
            timestamp=signal.timestamp,
        )


__all__ = ["Meridian", "Signal", "SignalPriority", "OrganInfo"]
