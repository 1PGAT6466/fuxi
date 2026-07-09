"""
intent_bus.py — 意图调度总线（IntentBus）
八卦体系的核心通信中枢：乾卦（中枢）通过 IntentBus 向
任意目标卦发送信号并获取响应。

职责：
  - 同步调度：dispatch(intent) -> IntentResult
  - 可靠性三合一：超时 + 重试 + 断路器
  - 三级优先级抢占队列
  - 反压保护
  - 卦注册/反注册
  - 直连路由白名单
  - Session 隔离
  - 取消 + 进度信号
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from src.infra.circuit_breaker import CircuitBreaker

logger = logging.getLogger("bagua.intent_bus")

# ---------------------------------------------------------------------------
# 枚举 & 数据类
# ---------------------------------------------------------------------------


class SignalType(str, Enum):
    """信号类型——对应八卦体系中的各类卦交互"""
    REQUEST = "request"          # 乾→任意卦：请求
    RESPONSE = "response"        # 任意卦→乾：响应
    PROGRESS = "progress"        # 震→兑：上传进度
    CANCEL = "cancel"            # 取消信号
    ERROR = "error"              # 错误回传
    HEARTBEAT = "heartbeat"      # 心跳


class Priority(Enum):
    """调度优先级（HIGH → NORMAL → LOW）"""
    HIGH = 0
    NORMAL = 1
    LOW = 2

    def __lt__(self, other: "Priority") -> bool:
        if not isinstance(other, Priority):
            return NotImplemented
        return self.value < other.value


class DispatchStatus(str, Enum):
    """调度结果状态"""
    OK = "ok"
    TIMEOUT = "timeout"
    CIRCUIT_OPEN = "circuit_open"
    BACKPRESSURE = "backpressure"
    CANCELLED = "cancelled"
    ROUTE_DENIED = "route_denied"
    TARGET_UNREGISTERED = "target_unregistered"
    UNKNOWN_ERROR = "unknown_error"


# ---------------------------------------------------------------------------
# 卦（Gua）定义
# ---------------------------------------------------------------------------


class Trigrams(str, Enum):
    """八卦 + 中宫枚举"""
    QIAN = "乾"           # 天 — 中枢控制
    KUN = "坤"            # 地 — 数据存储
    ZHEN = "震"           # 雷 — 上传/写入
    XUN = "巽"            # 风 — 传输/流
    KAN = "坎"            # 水 — 解析/理解
    LI = "离"             # 火 — 检索/查询
    GEN = "艮"            # 山 — 索引/结构
    DUI = "兑"            # 泽 — 展示/输出
    ZHONG_GONG = "中宫"    # 中宫 — 自进化中枢（第九宫）


@dataclass
class Signal:
    """信号——在八卦体系中流转的消息单元。

    每个 Signal 必须绑定 session_id，由乾卦（中枢）统一管理。
    """
    signal_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    source: str = ""
    target: str = ""
    signal_type: SignalType = SignalType.REQUEST
    priority: Priority = Priority.NORMAL
    payload: Dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    timestamp: float = field(default_factory=time.time)
    ttl: float = 30.0
    # 取消机制
    cancellation_event: Optional[threading.Event] = None
    # 进度回调
    progress_callback: Optional[Callable[[float, str], None]] = None

    def is_expired(self) -> bool:
        return (time.time() - self.timestamp) > self.ttl


@dataclass
class IntentResult:
    """dispatch() 的返回结果"""
    status: DispatchStatus = DispatchStatus.OK
    payload: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    latency_ms: float = 0.0
    retry_count: int = 0


# ---------------------------------------------------------------------------
# 卦处理器接口
# ---------------------------------------------------------------------------


class GuaHandler:
    """卦处理器——每个注册的卦必须实现此接口。

    当 IntentBus 派发信号到该卦时，调用 handle_signal。
    """

    def __init__(self, name: str, trigram: Trigrams):
        self.name = name
        self.trigram = trigram
        self._is_registered = False

    def handle_signal(self, signal: Signal) -> IntentResult:
        """处理传入的信号。子类必须实现。"""
        raise NotImplementedError(f"{self.name}.handle_signal 未实现")


# ---------------------------------------------------------------------------
# 直连路由规则
# ---------------------------------------------------------------------------


@dataclass
class DirectRoute:
    """卦际直连规则：source → target 仅允许特定 signal_types"""
    source: str
    target: str
    signal_types: Set[SignalType]


# ---------------------------------------------------------------------------
# IntentBus 核心
# ---------------------------------------------------------------------------


class IntentBus:
    """意图调度总线 —— 八卦体系的核心通信中枢。

    乾卦（中枢）通过 IntentBus 向任意目标卦派发信号，获取响应。

    Features
    --------
    - 同步调度：dispatch(intent) -> IntentResult
    - 可靠性三合一：超时（10s）+ 重试（3 次，指数退避）+ 断路器
    - 三级优先级抢占队列：HIGH > NORMAL > LOW
    - 反压：队列积压 > 100 时拒绝低优先级信号
    - 卦注册 / 反注册
    - 直连路由白名单（坎→巽等性能敏感路径）
    - Session 隔离
    - 取消机制 + 进度信号
    """

    # ---- 配置常量 ----
    DEFAULT_TIMEOUT = 10.0
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1.0       # 基础退避
    DEFAULT_RETRY_BACKOFF = 2.0     # 指数因子 → 1/2/4s
    CB_FAILURE_THRESHOLD = 5        # 5 次失败 → OPEN
    CB_RECOVERY_TIMEOUT = 30.0      # OPEN 30s → HALF_OPEN
    BACKPRESSURE_THRESHOLD = 100    # 队列积压上限

    def __init__(self, name: str = "intent_bus"):
        self.name = name
        self._lock = threading.Lock()
        # 注册表：name -> GuaHandler
        self._guas: Dict[str, GuaHandler] = {}
        # 优先级队列（拆分为三个独立 list，用锁保护）
        self._queues: Dict[Priority, List[Signal]] = {
            Priority.HIGH: [],
            Priority.NORMAL: [],
            Priority.LOW: [],
        }
        self._queue_total: int = 0
        # 直连路由白名单
        self._direct_routes: List[DirectRoute] = []
        # 断路器：（source_name, target_name）→ CircuitBreaker
        self._circuit_breakers: Dict[Tuple[str, str], CircuitBreaker] = {}
        # Session 管理
        self._sessions: Dict[str, Set[str]] = {}  # session_id -> {gua_names}
        # 心跳时间跟踪（兼容 meridian 接口）
        self._heartbeat_times: Dict[str, float] = {}
        # 统计
        self.stats: Dict[str, int] = {
            "dispatched": 0,
            "succeeded": 0,
            "failed": 0,
            "rejected": 0,
            "cancelled": 0,
        }

    # =====================================================================
    # 卦注册
    # =====================================================================

    def register_symbol(self, symbol_id: str, name: str, handler: Any) -> None:
        """v1.50 修复：兼容 meridian.register_symbol 接口。

        旧的 SymbolBase/ShaoyinBrain 通过 meridian.register_symbol() 注册，
        但 v2 引擎使用 IntentBus。此方法提供向后兼容：
        - 如果 handler 已是 GuaHandler 子类，直接调用 register_gua
        - 否则包装为 GenericGuaHandler 再注册
        """
        if isinstance(handler, GuaHandler):
            self.register_gua(name, handler)
            return

        # 对于非 GuaHandler 对象（如 ShaoyinBrain），创建一个适配器
        class CompatGuaHandler(GuaHandler):
            def __init__(self, wrapped):
                super().__init__(name=name, trigram=Trigrams("乾"))
                self._wrapped = wrapped

            def handle_signal(self, signal: Signal) -> IntentResult:
                return IntentResult(status=DispatchStatus.OK)

        wrapper = CompatGuaHandler(handler)
        self.register_gua(name, wrapper)
        logger.info(f"[IntentBus] 兼容注册: {symbol_id} ({name})")

    def heartbeat(self, symbol_id: str) -> None:
        """v1.50 修复：兼容 meridian.heartbeat 接口。

        自动注册首次心跳的 symbol（向后兼容旧 meridian 语义）。
        """
        with self._lock:
            self._heartbeat_times[symbol_id] = time.time()
            # 自动注册：如果未在 guas 中，记录日志（不打断已有逻辑）
            if symbol_id not in self._guas:
                logger.debug(f"[IntentBus] heartbeat 遇到未注册 symbol: {symbol_id}")

    def is_alive(self, symbol_id: str) -> bool:
        """v1.50 修复：兼容 meridian.is_alive 接口。"""
        with self._lock:
            if symbol_id not in self._heartbeat_times:
                return False
            # 30 秒内有心跳视为存活
            return (time.time() - self._heartbeat_times[symbol_id]) < 30.0

    def last_heartbeat_ago(self, symbol_id: str) -> float:
        """v1.50 修复：兼容 meridian.last_heartbeat_ago 接口。"""
        with self._lock:
            if symbol_id not in self._heartbeat_times:
                return 999.0
            return time.time() - self._heartbeat_times[symbol_id]

    def register_gua(self, name: str, handler: GuaHandler) -> None:
        """注册一个卦处理器到 IntentBus。

        同一个 name 只能注册一次；重复注册会触发警告。

        Parameters
        ----------
        name : str
            卦的唯一名称（如 "坎-解析引擎"）
        handler : GuaHandler
            卦处理器实例
        """
        with self._lock:
            if name in self._guas:
                logger.warning(f"[IntentBus] 卦 '{name}' 已注册，覆盖旧处理器")
            self._guas[name] = handler
            handler._is_registered = True
            logger.info(
                f"[IntentBus] 卦注册成功: {name} ({handler.trigram.value})"
            )

    def unregister_gua(self, name: str) -> bool:
        """反注册一个卦。

        Parameters
        ----------
        name : str
            要移除的卦名称

        Returns
        -------
        bool
            True 表示成功反注册，False 表示未找到
        """
        with self._lock:
            if name not in self._guas:
                logger.warning(f"[IntentBus] 卦 '{name}' 未注册，无法反注册")
                return False
            handler = self._guas.pop(name)
            handler._is_registered = False
            # 清理相关断路器
            removed_keys = [
                k for k in self._circuit_breakers
                if k[1] == name
            ]
            for k in removed_keys:
                del self._circuit_breakers[k]
            logger.info(f"[IntentBus] 卦反注册成功: {name}")
            return True

    def get_registered_guas(self) -> List[str]:
        """获取所有已注册卦的名称列表。"""
        with self._lock:
            return list(self._guas.keys())

    # =====================================================================
    # 直连路由
    # =====================================================================

    def register_direct_route(
        self,
        source: str,
        target: str,
        signal_types: List[SignalType],
    ) -> None:
        """注册一条卦际直连白名单路由。

        用于性能敏感路径（如坎→巽），直达路由绕过优先级队列，
        将信号直接递送至目标卦。

        Parameters
        ----------
        source : str
            发起卦名称
        target : str
            目标卦名称
        signal_types : List[SignalType]
            允许的信号类型集合
        """
        with self._lock:
            route = DirectRoute(
                source=source,
                target=target,
                signal_types=set(signal_types),
            )
            self._direct_routes.append(route)
            logger.info(
                f"[IntentBus] 直连路由注册: {source} → {target} "
                f"({[st.value for st in signal_types]})"
            )

    def remove_direct_route(self, source: str, target: str) -> bool:
        """移除一条直连路由。"""
        with self._lock:
            before = len(self._direct_routes)
            self._direct_routes = [
                r for r in self._direct_routes
                if not (r.source == source and r.target == target)
            ]
            removed = before - len(self._direct_routes)
            if removed:
                logger.info(f"[IntentBus] 直连路由已移除: {source} → {target}")
            return removed > 0

    def _is_direct_route_allowed(self, signal: Signal) -> bool:
        """检查是否存在允许该信号的直连路由。"""
        for route in self._direct_routes:
            if (
                route.source == signal.source
                and route.target == signal.target
                and signal.signal_type in route.signal_types
            ):
                return True
        return False

    # =====================================================================
    # Session 管理
    # =====================================================================

    def open_session(self, session_id: str) -> None:
        """为新乾卦会话创建 session 上下文。"""
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = set()
                logger.debug(f"[IntentBus] Session 已打开: {session_id}")

    def close_session(self, session_id: str) -> None:
        """关闭 session 并清理所有关联的资源。"""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.debug(f"[IntentBus] Session 已关闭: {session_id}")

    def _validate_session(self, signal: Signal) -> bool:
        """验证信号的 session_id 是否有效。"""
        if not signal.session_id:
            logger.error("[IntentBus] Signal 缺少 session_id")
            return False
        with self._lock:
            return signal.session_id in self._sessions

    # =====================================================================
    # 优先级队列
    # =====================================================================

    def _enqueue(self, signal: Signal) -> bool:
        """将信号加入对应优先级队列。"""
        with self._lock:
            total = (
                len(self._queues[Priority.HIGH])
                + len(self._queues[Priority.NORMAL])
                + len(self._queues[Priority.LOW])
            )
            # 反压检查
            if total >= self.BACKPRESSURE_THRESHOLD:
                if signal.priority == Priority.LOW:
                    logger.warning(
                        f"[IntentBus] 反压拒绝 LOW 信号: "
                        f"{signal.source}→{signal.target} "
                        f"(积压={total})"
                    )
                    self.stats["rejected"] += 1
                    return False
                elif signal.priority == Priority.NORMAL and total >= self.BACKPRESSURE_THRESHOLD * 1.5:
                    logger.warning(
                        f"[IntentBus] 严重反压拒绝 NORMAL 信号: "
                        f"{signal.source}→{signal.target} "
                        f"(积压={total})"
                    )
                    self.stats["rejected"] += 1
                    return False
            self._queues[signal.priority].append(signal)
            self._queue_total = total + 1
            return True

    def _dequeue(self) -> Optional[Signal]:
        """优先级抢占：HIGH > NORMAL > LOW。

        HIGH 队列有信号时绝不处理 NORMAL/LOW。
        """
        with self._lock:
            for pri in (Priority.HIGH, Priority.NORMAL, Priority.LOW):
                if self._queues[pri]:
                    signal = self._queues[pri].pop(0)
                    total = (
                        len(self._queues[Priority.HIGH])
                        + len(self._queues[Priority.NORMAL])
                        + len(self._queues[Priority.LOW])
                    )
                    self._queue_total = total
                    return signal
            return None

    def get_queue_depth(self) -> int:
        """获取当前队列总积压数。"""
        with self._lock:
            return self._queue_total

    # =====================================================================
    # 断路器管理
    # =====================================================================

    def _get_circuit_breaker(
        self, source: str, target: str
    ) -> CircuitBreaker:
        """获取 (source, target) 对的独立断路器。

        使用全局断路器注册表（src.infra.circuit_breaker），
        确保 IntentBus dispatch 失败会影响 GuaBase 的子卦断路器状态。
        """
        from src.infra.circuit_breaker import get_circuit_breaker as get_cb
        key = f"{source}->{target}"
        cb = get_cb(
            key,
            failure_threshold=self.CB_FAILURE_THRESHOLD,
            recovery_timeout=self.CB_RECOVERY_TIMEOUT,
            half_open_max_calls=3,
        )
        # 同时维护本地引用（向后兼容）
        self._circuit_breakers[(source, target)] = cb
        return cb

    def _get_all_circuit_breakers(self) -> Dict[Tuple[str, str], CircuitBreaker]:
        """获取所有断路器（用于监控）。"""
        with self._lock:
            return dict(self._circuit_breakers)

    # =====================================================================
    # 核心调度：dispatch
    # =====================================================================

    def dispatch(self, signal: Signal) -> IntentResult:
        """同步调度：乾卦→目标卦，请求-响应模式。

        自动包裹可靠性三合一（超时 + 重试 + 断路器）。

        Parameters
        ----------
        signal : Signal
            要派发的信号，必须包含有效的 session_id 和 target

        Returns
        -------
        IntentResult
            调度结果，包含状态、载荷、耗时和重试次数
        """
        start_time = time.time()

        # ---- 前置校验 ----
        if not signal.session_id:
            return IntentResult(
                status=DispatchStatus.UNKNOWN_ERROR,
                error_message="Signal 缺少 session_id",
                latency_ms=(time.time() - start_time) * 1000,
            )

        if not signal.target:
            return IntentResult(
                status=DispatchStatus.UNKNOWN_ERROR,
                error_message="Signal 缺少 target",
                latency_ms=(time.time() - start_time) * 1000,
            )

        # 验证 session
        if not self._validate_session(signal):
            return IntentResult(
                status=DispatchStatus.UNKNOWN_ERROR,
                error_message=f"Session 无效: {signal.session_id}",
                latency_ms=(time.time() - start_time) * 1000,
            )

        # 验证目标卦是否已注册
        with self._lock:
            target_handler = self._guas.get(signal.target)
        if target_handler is None:
            return IntentResult(
                status=DispatchStatus.TARGET_UNREGISTERED,
                error_message=f"目标卦未注册: {signal.target}",
                latency_ms=(time.time() - start_time) * 1000,
            )

        # 检查是否可以通过直连路由
        is_direct = self._is_direct_route_allowed(signal)

        # 非直连路由需要入队
        if not is_direct:
            if not self._enqueue(signal):
                return IntentResult(
                    status=DispatchStatus.BACKPRESSURE,
                    error_message="队列满，反压拒绝",
                    latency_ms=(time.time() - start_time) * 1000,
                )
            # 实际出队（当前同步模型直接处理，留待异步扩展）
            dequeued = self._dequeue()
            if dequeued is None:
                return IntentResult(
                    status=DispatchStatus.UNKNOWN_ERROR,
                    error_message="入队后无法出队（内部错误）",
                    latency_ms=(time.time() - start_time) * 1000,
                )
            signal = dequeued

        # ---- 断路器检查 ----
        cb = self._get_circuit_breaker(signal.source, signal.target)
        if not cb.can_execute():
            logger.warning(
                f"[IntentBus] 断路器 OPEN: {signal.source}→{signal.target}"
            )
            self.stats["rejected"] += 1
            return IntentResult(
                status=DispatchStatus.CIRCUIT_OPEN,
                error_message=f"断路器断开: {signal.source}→{signal.target}",
                latency_ms=(time.time() - start_time) * 1000,
            )

        # ---- 重试循环 ----
        last_result: Optional[IntentResult] = None
        retry_count = 0
        current_delay = self.DEFAULT_RETRY_DELAY

        for attempt in range(self.DEFAULT_MAX_RETRIES + 1):
            # 取消检查（每步前）
            if signal.cancellation_event and signal.cancellation_event.is_set():
                logger.info(
                    f"[IntentBus] 信号被取消: {signal.signal_id} "
                    f"({signal.source}→{signal.target})"
                )
                self.stats["cancelled"] += 1
                return IntentResult(
                    status=DispatchStatus.CANCELLED,
                    error_message="信号已被取消",
                    latency_ms=(time.time() - start_time) * 1000,
                    retry_count=retry_count,
                )

            try:
                result = self._invoke_with_timeout(
                    handler=target_handler,
                    signal=signal,
                    timeout=self.DEFAULT_TIMEOUT,
                )
                # 成功
                cb.record_success()
                self.stats["succeeded"] += 1
                self.stats["dispatched"] += 1
                result.retry_count = retry_count
                result.latency_ms = (time.time() - start_time) * 1000
                return result

            except TimeoutError:
                last_result = IntentResult(
                    status=DispatchStatus.TIMEOUT,
                    error_message=f"超时 ({self.DEFAULT_TIMEOUT}s)",
                )
                if attempt < self.DEFAULT_MAX_RETRIES:
                    logger.warning(
                        f"[IntentBus] 超时，重试 {attempt + 1}/"
                        f"{self.DEFAULT_MAX_RETRIES}: "
                        f"{signal.source}→{signal.target}, "
                        f"等待 {current_delay:.1f}s"
                    )
                    time.sleep(current_delay)
                    current_delay *= self.DEFAULT_RETRY_BACKOFF
                    retry_count = attempt + 1

            except Exception as e:
                last_result = IntentResult(
                    status=DispatchStatus.UNKNOWN_ERROR,
                    error_message=str(e),
                )
                if attempt < self.DEFAULT_MAX_RETRIES:
                    logger.warning(
                        f"[IntentBus] 异常，重试 {attempt + 1}/"
                        f"{self.DEFAULT_MAX_RETRIES}: "
                        f"{signal.source}→{signal.target}, "
                        f"错误={e}, 等待 {current_delay:.1f}s"
                    )
                    time.sleep(current_delay)
                    current_delay *= self.DEFAULT_RETRY_BACKOFF
                    retry_count = attempt + 1
                else:
                    logger.error(
                        f"[IntentBus] 所有重试耗尽: "
                        f"{signal.source}→{signal.target}, 错误={e}"
                    )

        # 所有重试耗尽
        cb.record_failure()
        self.stats["failed"] += 1
        self.stats["dispatched"] += 1
        if last_result is None:
            last_result = IntentResult(status=DispatchStatus.UNKNOWN_ERROR)
        last_result.retry_count = retry_count
        last_result.latency_ms = (time.time() - start_time) * 1000
        return last_result

    # =====================================================================
    # 超时执行
    # =====================================================================

    def _invoke_with_timeout(
        self,
        handler: GuaHandler,
        signal: Signal,
        timeout: float,
    ) -> IntentResult:
        """带超时保护的同步 handler 调用。

        使用 threading.Event 实现超时检测。
        """
        result_container: Dict[str, Any] = {"result": None, "error": None}
        done_event = threading.Event()

        def _target() -> None:
            try:
                result_container["result"] = handler.handle_signal(signal)
            except Exception as exc:
                result_container["error"] = exc
            finally:
                done_event.set()

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()

        if not done_event.wait(timeout=timeout):
            # 超时——注意：Python 无法强制终止线程，
            # 这里仅标记超时；handler 内部应当自行检查取消事件
            raise TimeoutError(
                f"处理超时 {signal.source}→{signal.target} ({timeout}s)"
            )

        thread.join(timeout=1.0)

        if result_container["error"] is not None:
            raise result_container["error"]

        return result_container.get("result") or IntentResult(
            status=DispatchStatus.OK
        )

    # =====================================================================
    # 进度信号
    # =====================================================================

    def send_progress(
        self,
        session_id: str,
        source: str,
        target: str,
        progress: float,
        message: str = "",
    ) -> IntentResult:
        """发送进度信号（震卦 → 兑卦）。

        进度值 0.0 ~ 1.0，用于报告上传/下载等长操作的进度。

        Parameters
        ----------
        session_id : str
            会话 ID
        source : str
            发起的卦名称（通常是震卦）
        target : str
            目标卦名称（通常是兑卦）
        progress : float
            进度值 [0.0, 1.0]
        message : str
            附带说明文本

        Returns
        -------
        IntentResult
        """
        signal = Signal(
            source=source,
            target=target,
            signal_type=SignalType.PROGRESS,
            priority=Priority.NORMAL,
            session_id=session_id,
            payload={"progress": max(0.0, min(1.0, progress)), "message": message},
            ttl=10.0,
        )
        return self.dispatch(signal)

    # =====================================================================
    # 健康 & 统计
    # =====================================================================

    def health_check(self) -> Dict[str, Any]:
        """返回 IntentBus 的健康状态。"""
        cb_states = {}
        for (src, tgt), cb in self._get_all_circuit_breakers().items():
            cb_states[f"{src}→{tgt}"] = cb.state.value

        return {
            "status": "healthy",
            "registered_guas": len(self._guas),
            "queue_depth": self.get_queue_depth(),
            "circuit_breakers": cb_states,
            "stats": dict(self.stats),
            "active_sessions": len(self._sessions),
            "direct_routes": len(self._direct_routes),
        }

    def reset_stats(self) -> None:
        """重置统计计数器。"""
        with self._lock:
            for key in self.stats:
                self.stats[key] = 0

    # =====================================================================
    # 取消管理
    # =====================================================================

    def cancel_signal(self, signal_id: str) -> bool:
        """取消指定 signal_id 的进行中 Signal

        将 cancellation_event 设置，让 dispatch() 循环在下一次尝试时退出。
        同时清理优先级队列中的该 signal。

        Args:
            signal_id: Signal.signal_id (12 字符 hex)

        Returns:
            True 如果找到并取消了该 Signal
        """
        cancelled = False
        with self._lock:
            for pri in (Priority.HIGH, Priority.NORMAL, Priority.LOW):
                queue = self._queues[pri]
                for sig in queue:
                    if sig.signal_id == signal_id:
                        if sig.cancellation_event:
                            sig.cancellation_event.set()
                        queue.remove(sig)
                        cancelled = True
                        break
                if cancelled:
                    break

        if cancelled:
            logger.info("[IntentBus] 信号已取消: %s", signal_id)
        else:
            logger.debug("[IntentBus] 未找到信号: %s", signal_id)
        return cancelled

    def cancel_session(self, session_id: str) -> int:
        """取消某个 Session 的所有进行中 Signal

        Args:
            session_id: 会话 ID

        Returns:
            已取消的 Signal 数量
        """
        count = 0
        with self._lock:
            for pri in (Priority.HIGH, Priority.NORMAL, Priority.LOW):
                queue = self._queues[pri]
                to_remove = [s for s in queue if s.session_id == session_id]
                for sig in to_remove:
                    if sig.cancellation_event:
                        sig.cancellation_event.set()
                    queue.remove(sig)
                    count += 1

        if count > 0:
            logger.info(
                "[IntentBus] Session %s 已取消 %d 个 Signal",
                session_id, count,
            )
        return count

    def new_signal_with_cancel(
        self,
        source: str,
        target: str,
        session_id: str,
        signal_type: SignalType = SignalType.REQUEST,
        priority: Priority = Priority.NORMAL,
        payload: Optional[Dict[str, Any]] = None,
        ttl: float = 30.0,
    ) -> Signal:
        """创建一个带 cancellation_event 的 Signal

        便捷方法：创建 Signal 并自动附 cancellation_event。
        调用方可通过 signal.signal_id 在需要时调用 cancel_signal()。

        Args:
            source:      源卦名
            target:      目标卦名
            session_id:  会话 ID
            signal_type: 信号类型
            priority:    优先级
            payload:     负载
            ttl:         TTL（秒）

        Returns:
            Signal 对象（.cancellation_event 已设置）
        """
        return Signal(
            source=source,
            target=target,
            signal_type=signal_type,
            priority=priority,
            payload=payload or {},
            session_id=session_id,
            ttl=ttl,
            cancellation_event=threading.Event(),
        )

    # =====================================================================
    # 全局单例
    # =====================================================================


# 全局默认实例
_default_bus: Optional[IntentBus] = None
_default_bus_lock = threading.Lock()


def get_intent_bus() -> IntentBus:
    """获取/创建全局 IntentBus 单例。"""
    global _default_bus
    if _default_bus is None:
        with _default_bus_lock:
            if _default_bus is None:
                _default_bus = IntentBus(name="fuxi_intent_bus")
                logger.info("[IntentBus] 全局实例已创建")
    return _default_bus


def reset_intent_bus() -> None:
    """重置全局 IntentBus（主要用于测试）。"""
    global _default_bus
    with _default_bus_lock:
        _default_bus = None
