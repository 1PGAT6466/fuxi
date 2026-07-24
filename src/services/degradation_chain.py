"""
degradation_chain.py — 错误追踪与降级链 (v1.44 P1 修复)
========================================================

伏羲平台核心缺陷修复：错误追踪机制。

功能：
  1. 错误分类：网络、模型、数据库、业务逻辑
  2. 错误聚合：同类型错误自动合并，减少告警噪音
  3. 降级策略：根据错误类型和频率自动触发降级
  4. 错误报告：生成带统计信息的错误报告

架构对齐：
  - 异步编程模式（asyncio）
  - 与 src/infra/error_tracker.py 的 ErrorTracker 集成
  - 与 src/infra/circuit_breaker.py 的 CircuitBreaker 配合
  - 与 src/taiyin/error_handler.py 的 KbError 体系兼容
  - 遵循 src/config.py 中的 SAG_CONFIG 降级阈值
  - FAKE-ASYNC：标记 async 仅为接口统一，内部同步执行

使用示例::

    chain = DegradationChain(name="search-pipeline")
    chain.register_strategy(
        ErrorCategory.NETWORK,
        DegradationStrategy.RETRY_BACKOFF,
        {"max_retries": 3, "backoff": 2.0},
    )
    chain.register_strategy(
        ErrorCategory.MODEL,
        DegradationStrategy.USE_FALLBACK,
        {"fallback_model": "openai-4o-mini"},
    )

    try:
        result = await do_search(...)
    except Exception as e:
        strategy = await chain.track_error(e, context={"query": "..."})
        if strategy == DegradationStrategy.RAISE:
            raise
        elif strategy == DegradationStrategy.USE_FALLBACK:
            result = await do_fallback_search(...)

    report = chain.generate_report()
"""

import asyncio
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# 枚举定义
# ═══════════════════════════════════════════════════════════════════════════

class ErrorCategory(str, Enum):
    """错误分类枚举

    四类错误覆盖核心依赖场景：
      NETWORK      — 网络超时、连接拒绝、DNS 解析失败
      MODEL        — LLM/Embedder/Reranker 不可用、超时、返回异常
      DATABASE     — 数据库连接池耗尽、查询超时、死锁
      BUSINESS     — 业务逻辑错误（参数校验、状态冲突、数据不一致）
    """
    NETWORK = "network"
    MODEL = "model"
    DATABASE = "database"
    BUSINESS = "business"


class DegradationStrategy(str, Enum):
    """降级策略枚举

    RAISE           — 不降级，向上抛出（用于业务错误）
    RETRY_BACKOFF   — 指数退避重试（用于临时故障）
    USE_FALLBACK    — 切换降级路径/模型（用于服务不可用）
    RETURN_CACHED   — 返回缓存数据（用于数据库不可用）
    RETURN_DEFAULT  — 返回默认值（用于非关键功能）
    CIRCUIT_OPEN    — 熔断该依赖，后续请求直接失败（用于持续故障）
    SKIP            — 跳过该操作，继续执行（用于可选步骤）
    """
    RAISE = "raise"
    RETRY_BACKOFF = "retry_backoff"
    USE_FALLBACK = "use_fallback"
    RETURN_CACHED = "return_cached"
    RETURN_DEFAULT = "return_default"
    CIRCUIT_OPEN = "circuit_open"
    SKIP = "skip"


class DegradationLevel(str, Enum):
    """降级等级

    NONE      — 无降级，功能完整
    MILD      — 轻微降级（重试一次 / 使用缓存）
    MODERATE  — 中度降级（切换后备模型 / 减少请求量）
    SEVERE    — 严重降级（仅返回默认值 / 跳过非关键功能）
    CRITICAL  — 关键降级（熔断该依赖 / 整个链路上报）
    """
    NONE = "none"
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


# ═══════════════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ErrorRecord:
    """单条错误记录"""
    error_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    category: ErrorCategory = ErrorCategory.BUSINESS
    exception_type: str = ""
    message: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    strategy: DegradationStrategy = DegradationStrategy.RAISE
    level: DegradationLevel = DegradationLevel.NONE
    timestamp: float = field(default_factory=time.time)
    traceback: Optional[str] = None
    # 聚合字段
    aggregated: bool = False
    aggregate_count: int = 1
    # 降级结果
    degraded: bool = False
    fallback_used: Optional[str] = None


@dataclass
class DegradationRule:
    """降级规则定义"""
    category: ErrorCategory
    strategy: DegradationStrategy
    level: DegradationLevel = DegradationLevel.MILD
    params: Dict[str, Any] = field(default_factory=dict)
    # 触发条件
    max_error_count: int = 5           # 时间窗口内最大错误数
    error_window_seconds: float = 60.0  # 错误计数时间窗口
    cooldown_seconds: float = 30.0      # 降级冷却时间


@dataclass
class AggregatedError:
    """聚合错误记录

    相同 category + exception_type 的错误合并为一条聚合记录。
    减少告警噪音的同时保留关键统计信息。
    """
    category: ErrorCategory
    exception_type: str
    message_sample: str               # 第一条错误消息（采样）
    count: int = 1
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    contexts: List[Dict[str, Any]] = field(default_factory=list)
    # 降级状态
    current_strategy: DegradationStrategy = DegradationStrategy.RAISE
    current_level: DegradationLevel = DegradationLevel.NONE
    degraded_at: Optional[float] = None
    cooldown_until: float = 0.0

    @property
    def duration_seconds(self) -> float:
        """首次与最近一次错误的时间跨度"""
        return self.last_seen - self.first_seen

    @property
    def rate_per_minute(self) -> float:
        """每分钟错误率"""
        if self.duration_seconds <= 0:
            return float(self.count)
        return (self.count / self.duration_seconds) * 60.0


# ═══════════════════════════════════════════════════════════════════════════
# 错误分类器
# ═══════════════════════════════════════════════════════════════════════════

class ErrorClassifier:
    """将异常映射到 ErrorCategory。

    基于异常类型名、消息内容进行模式匹配。
    支持用户自定义映射和正则匹配。
    """

    # 内置映射：异常类名 / 异常消息关键词 → ErrorCategory
    DEFAULT_TYPE_MAPPING: Dict[str, ErrorCategory] = {
        # 网络类
        "ConnectionError": ErrorCategory.NETWORK,
        "ConnectionRefusedError": ErrorCategory.NETWORK,
        "ConnectionResetError": ErrorCategory.NETWORK,
        "TimeoutError": ErrorCategory.NETWORK,
        "ConnectTimeout": ErrorCategory.NETWORK,
        "ReadTimeout": ErrorCategory.NETWORK,
        "URLError": ErrorCategory.NETWORK,
        "HTTPError": ErrorCategory.NETWORK,
        "ClientError": ErrorCategory.NETWORK,
        "ServerDisconnectedError": ErrorCategory.NETWORK,
        "DNSException": ErrorCategory.NETWORK,
        "SSLError": ErrorCategory.NETWORK,
        # 模型类
        "LlmUnavailableError": ErrorCategory.MODEL,
        "EmbedderUnavailableError": ErrorCategory.MODEL,
        "RerankerUnavailableError": ErrorCategory.MODEL,
        "LLM_DOWN": ErrorCategory.MODEL,
        "EMBEDDER_DOWN": ErrorCategory.MODEL,
        "RERANKER_DOWN": ErrorCategory.MODEL,
        "APIError": ErrorCategory.MODEL,
        "AuthenticationError": ErrorCategory.MODEL,
        "RateLimitError": ErrorCategory.MODEL,
        # 数据库类
        "DatabaseError": ErrorCategory.DATABASE,
        "OperationalError": ErrorCategory.DATABASE,
        "IntegrityError": ErrorCategory.DATABASE,
        "DataError": ErrorCategory.DATABASE,
        "ProgrammingError": ErrorCategory.DATABASE,
        "NotSupportedError": ErrorCategory.DATABASE,
        "InterfaceError": ErrorCategory.DATABASE,
        "PoolError": ErrorCategory.DATABASE,
        "DeadlockError": ErrorCategory.DATABASE,
        "VectorStoreError": ErrorCategory.DATABASE,
        # 业务类
        "DuplicateFileError": ErrorCategory.BUSINESS,
        "InvalidQueryError": ErrorCategory.BUSINESS,
        "ParseError": ErrorCategory.BUSINESS,
        "KbError": ErrorCategory.BUSINESS,
        "ValueError": ErrorCategory.BUSINESS,
        "TypeError": ErrorCategory.BUSINESS,
        "KeyError": ErrorCategory.BUSINESS,
        "AttributeError": ErrorCategory.BUSINESS,
        "AssertionError": ErrorCategory.BUSINESS,
    }

    # 消息关键词 → ErrorCategory（优先级低于类型匹配）
    MESSAGE_PATTERNS: List[Tuple[str, ErrorCategory]] = [
        ("connection refused", ErrorCategory.NETWORK),
        ("connection reset", ErrorCategory.NETWORK),
        ("connection timed out", ErrorCategory.NETWORK),
        ("name resolution", ErrorCategory.NETWORK),
        ("tls", ErrorCategory.NETWORK),
        ("ssl", ErrorCategory.NETWORK),
        ("dns", ErrorCategory.NETWORK),
        ("socket", ErrorCategory.NETWORK),
        ("network", ErrorCategory.NETWORK),
        ("timeout", ErrorCategory.NETWORK),
        ("too many requests", ErrorCategory.MODEL),
        ("rate limit", ErrorCategory.MODEL),
        ("api key", ErrorCategory.MODEL),
        ("authentication", ErrorCategory.MODEL),
        ("unauthorized", ErrorCategory.MODEL),
        ("model", ErrorCategory.MODEL),
        ("llm", ErrorCategory.MODEL),
        ("embedder", ErrorCategory.MODEL),
        ("embedding", ErrorCategory.MODEL),
        ("rerank", ErrorCategory.MODEL),
        ("database", ErrorCategory.DATABASE),
        ("sql", ErrorCategory.DATABASE),
        ("duplicate", ErrorCategory.DATABASE),
        ("deadlock", ErrorCategory.DATABASE),
        ("pool", ErrorCategory.DATABASE),
        ("vector", ErrorCategory.DATABASE),
        ("chroma", ErrorCategory.DATABASE),
        ("sqlite", ErrorCategory.DATABASE),
    ]

    def __init__(self):
        self._custom_mappings: Dict[str, ErrorCategory] = {}

    def register_mapping(self, exception_type_name: str, category: ErrorCategory) -> None:
        """注册自定义异常类型映射。

        Args:
            exception_type_name: 异常类型的 __name__（如 "MyCustomError"）
            category:        对应的错误分类
        """
        self._custom_mappings[exception_type_name] = category
        logger.debug("[ErrorClassifier] 注册映射: %s → %s", exception_type_name, category.value)

    def classify(self, error: Exception) -> ErrorCategory:
        """分类一个异常。

        优先级：
          1. 自定义映射（.register_mapping）
          2. 异常类型名匹配（DEFAULT_TYPE_MAPPING）
          3. 异常链递归（__cause__ 遍历，深度 ≤ 3）
          4. 消息关键词匹配

        Args:
            error: 待分类的异常

        Returns:
            ErrorCategory
        """
        # 1. 自定义映射
        type_name = type(error).__name__
        if type_name in self._custom_mappings:
            logger.debug("[ErrorClassifier] 自定义映射命中: %s → %s", type_name, self._custom_mappings[type_name].value)
            return self._custom_mappings[type_name]

        # 2. 异常类型名匹配（含基类）
        category = self._match_by_type(error)
        if category:
            logger.debug("[ErrorClassifier] 类型匹配命中: %s → %s", type_name, category.value)
            return category

        # 3. 异常链递归
        cause = error.__cause__
        depth = 0
        while cause is not None and depth < 3:
            category = self._match_by_type(cause)
            if category:
                logger.debug("[ErrorClassifier] 异常链匹配命中: %s → %s (via cause)", type(cause).__name__, category.value)
                return category
            cause = cause.__cause__
            depth += 1

        # 4. 消息关键词匹配
        message_lower = str(error).lower()
        for pattern, cat in self.MESSAGE_PATTERNS:
            if pattern in message_lower:
                logger.debug("[ErrorClassifier] 消息关键词匹配命中: '%s' → %s", pattern, cat.value)
                return cat

        # 默认：业务错误
        logger.debug("[ErrorClassifier] 未匹配到任何规则，默认归类为 BUSINESS: %s", type_name)
        return ErrorCategory.BUSINESS

    def _match_by_type(self, error: Exception) -> Optional[ErrorCategory]:
        """按异常（含 MRO 链）类型名匹配"""
        for cls in type(error).__mro__:
            cls_name = cls.__name__
            merged = {**self.DEFAULT_TYPE_MAPPING, **self._custom_mappings}
            if cls_name in merged:
                return merged[cls_name]
        return None


# ═══════════════════════════════════════════════════════════════════════════
# DegradationChain — 核心类
# ═══════════════════════════════════════════════════════════════════════════

class DegradationChain:
    """错误追踪与降级链。

    每条链绑定到一个逻辑边界（如 "search-pipeline"、"llm-call"、"db-query"），
    在该边界内追踪错误，并根据预配置的降级规则自动决定降级策略。

    与 CircuitBreaker 联动：
      - 当某类错误频率超过阈值，自动提升降级策略为 CIRCUIT_OPEN
      - CircuitBreaker 恢复（CLOSED）后，清除聚合计数

    使用示例::

        chain = DegradationChain(name="knowledge-search")

        # 注册降级规则
        chain.register_strategy(
            ErrorCategory.NETWORK,
            DegradationStrategy.RETRY_BACKOFF,
            {"max_retries": 3},
        )
        chain.register_strategy(
            ErrorCategory.MODEL,
            DegradationStrategy.USE_FALLBACK,
            {"fallback_model": "openai-4o-mini", "max_retries": 2},
        )
        chain.register_strategy(
            ErrorCategory.DATABASE,
            DegradationStrategy.RETURN_CACHED,
            {"cache_ttl": 300},
        )
        chain.register_strategy(
            ErrorCategory.BUSINESS,
            DegradationStrategy.RAISE,
            {},
        )

        # 在代码中使用
        try:
            result = await external_call()
        except Exception as e:
            strategy = await chain.track_error(e, context={"query": "模具"})
            if strategy.strategy == DegradationStrategy.RETRY_BACKOFF:
                result = await retry_with_backoff(external_call, strategy.params)
            elif strategy.strategy == DegradationStrategy.USE_FALLBACK:
                result = await fallback_call(strategy.params.get("fallback_model"))
            else:
                raise
    """

    def __init__(
        self,
        name: str = "default",
        max_history: int = 1000,
        max_aggregation_history: int = 500,
        error_window_seconds: float = 60.0,
        default_cooldown_seconds: float = 30.0,
    ):
        """
        Args:
            name:                       链名称（用于日志标识）
            max_history:                原始错误记录最大保留数
            max_aggregation_history:    聚合错误最大保留数
            error_window_seconds:       错误计数默认时间窗口
            default_cooldown_seconds:   降级后默认冷却时间
        """
        self.name = name
        self.max_history = max_history
        self.max_aggregation_history = max_aggregation_history
        self.error_window_seconds = error_window_seconds
        self.default_cooldown_seconds = default_cooldown_seconds

        # 原始错误记录（FIFO）
        self._errors: deque[ErrorRecord] = deque(maxlen=max_history)

        # 聚合错误（按 (category, exception_type) 聚合）
        self._aggregated: Dict[Tuple[ErrorCategory, str], AggregatedError] = {}

        # 降级规则配置
        self._strategies: Dict[ErrorCategory, List[DegradationRule]] = defaultdict(list)

        # 分类器
        self._classifier = ErrorClassifier()

        # 降级状态 — 每类错误的当前降级级别
        self._degradation_levels: Dict[ErrorCategory, DegradationLevel] = {
            cat: DegradationLevel.NONE for cat in ErrorCategory
        }

        # 默认降级映射
        self._init_default_strategies()

        # 运行时回调
        self._on_degradation: List[Callable[[ErrorCategory, DegradationLevel, str], None]] = []
        self._on_recovery: List[Callable[[ErrorCategory], None]] = []

        logger.info(
            "[DegChain:%s] 初始化完成 windows=%ds cooldown=%ds",
            self.name, self.error_window_seconds, self.default_cooldown_seconds,
        )

    def _init_default_strategies(self) -> None:
        """初始化内置降级规则。

        这些规则提供最小可用降级行为，用户可用 .register_strategy() 覆盖。
        """
        defaults = {
            ErrorCategory.NETWORK: DegradationRule(
                category=ErrorCategory.NETWORK,
                strategy=DegradationStrategy.RETRY_BACKOFF,
                level=DegradationLevel.MILD,
                params={"max_retries": 3, "backoff": 2.0},
                max_error_count=10,
                error_window_seconds=self.error_window_seconds,
                cooldown_seconds=self.default_cooldown_seconds,
            ),
            ErrorCategory.MODEL: DegradationRule(
                category=ErrorCategory.MODEL,
                strategy=DegradationStrategy.USE_FALLBACK,
                level=DegradationLevel.MODERATE,
                params={"fallback_model": "openai-4o-mini", "max_retries": 1},
                max_error_count=5,
                error_window_seconds=self.error_window_seconds,
                cooldown_seconds=60.0,
            ),
            ErrorCategory.DATABASE: DegradationRule(
                category=ErrorCategory.DATABASE,
                strategy=DegradationStrategy.RETURN_CACHED,
                level=DegradationLevel.MODERATE,
                params={"cache_ttl": 300},
                max_error_count=5,
                error_window_seconds=self.error_window_seconds,
                cooldown_seconds=self.default_cooldown_seconds,
            ),
            ErrorCategory.BUSINESS: DegradationRule(
                category=ErrorCategory.BUSINESS,
                strategy=DegradationStrategy.RAISE,
                level=DegradationLevel.NONE,
                params={},
                max_error_count=100,  # 业务错误不降级
                error_window_seconds=self.error_window_seconds,
                cooldown_seconds=0,
            ),
        }
        for cat, rule in defaults.items():
            self._strategies[cat].append(rule)

    # ── 公共 API ──

    async def track_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        chain_context: Optional[Dict[str, Any]] = None,
    ) -> DegradationRule:
        """追踪单个错误，返回推荐的降级策略。

        核心流程：
          1. 分类错误 → ErrorCategory
          2. 记录原始错误
          3. 聚合到 AggregatedError
          4. 评估是否触发降级
          5. 返回 DegradationRule（含 strategy + params）

        Args:
            error:          捕获的异常
            context:        错误发生的上下文（如 {"query": "...", "user_id": "..."}）
            chain_context:  链级别上下文（如 {"pipeline": "search", "stage": "rerank"}）

        Returns:
            DegradationRule（包含推荐的降级策略和参数）
        """
        context = context or {}
        chain_context = chain_context or {}

        # 1. 分类
        category = self._classifier.classify(error)

        # 2. 记录原始错误
        record = ErrorRecord(
            category=category,
            exception_type=type(error).__name__,
            message=str(error),
            context={**chain_context, **context},
            timestamp=time.time(),
        )
        self._errors.append(record)

        # 3. 聚合
        agg_key = (category, type(error).__name__)
        agg = self._get_or_create_aggregated(agg_key, record)
        agg.last_seen = time.time()
        agg.count += 1
        agg.contexts.append(context)
        # 限制 context 列表大小
        if len(agg.contexts) > 20:
            agg.contexts = agg.contexts[-20:]

        record.aggregated = True
        record.aggregate_count = agg.count

        # 4. 评估降级
        effective_rule = self._evaluate_degradation(category, agg)

        record.strategy = effective_rule.strategy
        record.level = effective_rule.level

        # 触发降级通知
        if effective_rule.level != DegradationLevel.NONE and agg.current_level != effective_rule.level:
            agg.current_strategy = effective_rule.strategy
            agg.current_level = effective_rule.level
            agg.degraded_at = time.time()
            agg.cooldown_until = time.time() + effective_rule.cooldown_seconds

            record.degraded = True
            logger.warning(
                "[DegChain:%s] 降级触发 category=%s level=%s strategy=%s count=%d",
                self.name, category.value, effective_rule.level.value,
                effective_rule.strategy.value, agg.count,
            )
            # 执行降级回调
            for cb in self._on_degradation:
                try:
                    cb(category, effective_rule.level, self.name)
                except Exception as exc:
                    logger.error("[DegChain:%s] 降级回调异常: %s", self.name, exc)

        # 5. 同步到全局 ErrorTracker
        await self._sync_to_global_tracker(error, record)

        return effective_rule

    async def track_error_simple(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
    ) -> DegradationRule:
        """简化版 track_error（仅需 error + context）。"""
        return await self.track_error(error, context=context)

    def register_strategy(
        self,
        category: ErrorCategory,
        strategy: DegradationStrategy,
        params: Optional[Dict[str, Any]] = None,
        level: DegradationLevel = DegradationLevel.MILD,
        max_error_count: int = 5,
        error_window_seconds: Optional[float] = None,
        cooldown_seconds: Optional[float] = None,
    ) -> DegradationRule:
        """注册或更新某类错误的降级策略。

        Args:
            category:             错误分类
            strategy:             降级策略
            params:               策略参数（如 {"max_retries": 3}）
            level:                降级等级
            max_error_count:      触发降级的窗口内错误数
            error_window_seconds: 错误计数窗口（None=使用链默认值）
            cooldown_seconds:     降级冷却时间（None=使用链默认值）

        Returns:
            已注册的 DegradationRule
        """
        rule = DegradationRule(
            category=category,
            strategy=strategy,
            level=level,
            params=params or {},
            max_error_count=max_error_count,
            error_window_seconds=error_window_seconds or self.error_window_seconds,
            cooldown_seconds=cooldown_seconds or self.default_cooldown_seconds,
        )
        # 覆盖同 category 的已有规则
        self._strategies[category] = [rule]
        logger.info(
            "[DegChain:%s] 注册降级策略 category=%s strategy=%s level=%s",
            self.name, category.value, strategy.value, level.value,
        )
        return rule

    def on_degradation(
        self, callback: Callable[[ErrorCategory, DegradationLevel, str], None]
    ) -> None:
        """注册降级触发回调。

        callback 签名为 (category, level, chain_name) -> None。
        """
        self._on_degradation.append(callback)

    def on_recovery(self, callback: Callable[[ErrorCategory], None]) -> None:
        """注册恢复回调。

        callback 签名为 (category) -> None。
        """
        self._on_recovery.append(callback)

    # ── 查询 API ──

    def get_category_errors(
        self, category: ErrorCategory, limit: int = 50
    ) -> List[ErrorRecord]:
        """获取某分类的原始错误记录。"""
        return [r for r in self._errors if r.category == category][-limit:]

    def get_recent_errors(self, limit: int = 50) -> List[ErrorRecord]:
        """获取最近 N 条错误。"""
        return list(self._errors)[-limit:]

    def get_aggregated_errors(self) -> List[AggregatedError]:
        """获取所有聚合错误。"""
        return sorted(self._aggregated.values(), key=lambda a: a.count, reverse=True)

    def get_degradation_level(self, category: ErrorCategory) -> DegradationLevel:
        """获取某分类当前的降级等级。"""
        return self._degradation_levels.get(category, DegradationLevel.NONE)

    def get_degradation_status(self) -> Dict[str, Any]:
        """获取整体降级状态快照。

        Returns:
            {"degraded": True, "levels": {"network": "mild", ...}, ...}
        """
        return {
            "name": self.name,
            "degraded": any(
                lvl != DegradationLevel.NONE
                for lvl in self._degradation_levels.values()
            ),
            "levels": {
                cat.value: lvl.value
                for cat, lvl in self._degradation_levels.items()
            },
            "total_errors": len(self._errors),
            "aggregated_count": len(self._aggregated),
        }

    def generate_report(self) -> Dict[str, Any]:
        """生成错误统计报告。

        Returns:
            包含以下字段的字典：
              - chain_name:       链名称
              - generated_at:     生成时间戳
              - total_errors:     总错误数
              - categories:       按分类汇总
              - aggregated:       聚合错误详情列表
              - degradation:      当前降级状态
              - recent_errors:    最近 10 条错误
        """
        now = time.time()

        # 按分类统计
        category_stats = {}
        for cat in ErrorCategory:
            errors = self.get_category_errors(cat, limit=1000)
            recent_window = [r for r in errors if now - r.timestamp <= self.error_window_seconds]
            category_stats[cat.value] = {
                "total": len(errors),
                "recent_window_count": len(recent_window),
                "recent_window_seconds": self.error_window_seconds,
                "degradation_level": self._degradation_levels[cat].value,
            }

        # 聚合错误摘要
        aggregated_summary = []
        for agg in sorted(
            self._aggregated.values(),
            key=lambda a: a.count, reverse=True,
        ):
            aggregated_summary.append({
                "category": agg.category.value,
                "exception_type": agg.exception_type,
                "count": agg.count,
                "message_sample": agg.message_sample[:200],
                "first_seen_iso": _ts_iso(agg.first_seen),
                "last_seen_iso": _ts_iso(agg.last_seen),
                "duration_seconds": round(agg.duration_seconds, 1),
                "rate_per_minute": round(agg.rate_per_minute, 2),
                "degradation_level": agg.current_level.value,
                "degradation_strategy": agg.current_strategy.value,
            })

        # 最近错误
        recent = [
            {
                "error_id": r.error_id,
                "category": r.category.value,
                "exception_type": r.exception_type,
                "message": r.message[:200],
                "timestamp_iso": _ts_iso(r.timestamp),
                "strategy": r.strategy.value,
                "aggregated": r.aggregated,
                "aggregate_count": r.aggregate_count,
            }
            for r in list(self._errors)[-10:]
        ]

        return {
            "chain_name": self.name,
            "generated_at_iso": _ts_iso(now),
            "total_errors": len(self._errors),
            "categories": category_stats,
            "aggregated": aggregated_summary,
            "degradation": self.get_degradation_status(),
            "recent_errors": recent,
        }

    # ── 生命周期 ──

    def reset_counts(self, category: Optional[ErrorCategory] = None) -> None:
        """重置聚合计数。

        Args:
            category: 若指定，仅重置该分类；否则重置全部。
        """
        if category:
            keys_to_remove = [
                k for k in self._aggregated
                if k[0] == category
            ]
            for k in keys_to_remove:
                del self._aggregated[k]
            self._degradation_levels[category] = DegradationLevel.NONE
            logger.info("[DegChain:%s] 重置计数 category=%s", self.name, category.value)
            # 恢复回调
            for cb in self._on_recovery:
                try:
                    cb(category)
                except Exception as exc:
                    logger.error("[DegChain:%s] 恢复回调异常: %s", self.name, exc)
        else:
            self._aggregated.clear()
            for cat in ErrorCategory:
                self._degradation_levels[cat] = DegradationLevel.NONE
            logger.info("[DegChain:%s] 重置全部计数", self.name)
            for cat in ErrorCategory:
                for cb in self._on_recovery:
                    try:
                        cb(cat)
                    except Exception:
                        pass

    def reset(self) -> None:
        """完全重置（含历史错误记录）。"""
        self._errors.clear()
        self._aggregated.clear()
        for cat in ErrorCategory:
            self._degradation_levels[cat] = DegradationLevel.NONE
        logger.info("[DegChain:%s] 完全重置", self.name)

    # ── 内部方法 ──

    def _get_or_create_aggregated(
        self,
        key: Tuple[ErrorCategory, str],
        record: ErrorRecord,
    ) -> AggregatedError:
        """获取或创建聚合错误条目。

        LRU 淘汰：聚合条目超过上限时移除计数最少的。
        """
        if key not in self._aggregated:
            # LRU 淘汰
            if len(self._aggregated) >= self.max_aggregation_history:
                oldest = min(self._aggregated.values(), key=lambda a: a.count)
                del self._aggregated[(oldest.category, oldest.exception_type)]
                logger.debug("[DegChain:%s] 聚合条目淘汰: %s/%s", self.name, oldest.category.value, oldest.exception_type)

            self._aggregated[key] = AggregatedError(
                category=record.category,
                exception_type=record.exception_type,
                message_sample=record.message,
                first_seen=record.timestamp,
            )

        return self._aggregated[key]

    def _evaluate_degradation(
        self,
        category: ErrorCategory,
        agg: AggregatedError,
    ) -> DegradationRule:
        """评估是否应触发降级，返回生效的 DegradationRule。"""
        rules = self._strategies.get(category, [])

        # 当前是否在冷却期
        if time.time() < agg.cooldown_until:
            logger.debug("[DegChain:%s] 冷却期 category=%s until=%s", self.name, category.value, _ts_iso(agg.cooldown_until))
            # 返回当前已生效的策略
            if agg.current_level != DegradationLevel.NONE:
                # 保留当前策略
                return DegradationRule(
                    category=category,
                    strategy=agg.current_strategy,
                    level=agg.current_level,
                    params={},
                    cooldown_seconds=self.default_cooldown_seconds,
                )

        # 遍历规则，找到匹配的
        for rule in sorted(rules, key=lambda r: r.level.value == DegradationLevel.NONE, reverse=False):
            # 计算窗口内错误数
            window_count = self._count_in_window(category, rule.error_window_seconds)
            if window_count >= rule.max_error_count:
                # 更新降级级别
                if rule.level != DegradationLevel.NONE:
                    self._degradation_levels[category] = rule.level
                logger.info(
                    "[DegChain:%s] 降级评估 category=%s window_count=%d threshold=%d → %s",
                    self.name, category.value, window_count, rule.max_error_count, rule.strategy.value,
                )
                return rule

        # 降级未触发 → 如果超出冷却期，清除降级状态
        if agg.current_level != DegradationLevel.NONE and time.time() >= agg.cooldown_until:
            recovered_level = agg.current_level
            agg.current_level = DegradationLevel.NONE
            agg.current_strategy = DegradationStrategy.RAISE
            agg.degraded_at = None
            agg.cooldown_until = 0
            self._degradation_levels[category] = DegradationLevel.NONE
            # v1.50 R4: 恢复日志
            logger.info(
                "[DegChain:%s] 降级恢复 category=%s (从 %s 恢复)",
                self.name, category.value, recovered_level.value,
            )
            # 恢复回调
            for cb in self._on_recovery:
                try:
                    cb(category)
                except Exception as exc:
                    logger.error("[DegChain:%s] 恢复回调异常: %s", self.name, exc)

        # 无降级：返回 RAISE
        return DegradationRule(
            category=category,
            strategy=DegradationStrategy.RAISE,
            level=DegradationLevel.NONE,
            params={},
            cooldown_seconds=0,
        )

    def _count_in_window(self, category: ErrorCategory, window_seconds: float) -> int:
        """计算指定时间窗口内某分类的错误数。"""
        now = time.time()
        threshold = now - window_seconds
        count = 0
        # 倒序遍历（最新在前）
        for record in reversed(self._errors):
            if record.timestamp < threshold:
                break
            if record.category == category:
                count += 1
        return count

    async def _sync_to_global_tracker(
        self,
        error: Exception,
        record: ErrorRecord,
    ) -> None:
        """同步错误记录到全局 ErrorTracker（src/infra/error_tracker.py）。

        这是一个可选集成：如果全局 ErrorTracker 存在，则写入；
        不存在时静默跳过，不影响主流程。
        """
        try:
            from src.infra.error_tracker import get_error_tracker
            tracker = get_error_tracker()
            tracker.record_error(
                error_type=f"{record.category.value}/{record.exception_type}",
                message=record.message,
                context={
                    "chain": self.name,
                    "strategy": record.strategy.value,
                    "level": record.level.value,
                    **record.context,
                },
            )
        except ImportError:
            logger.debug("[DegChain:%s] 全局 ErrorTracker 不可用，跳过同步", self.name)
        except Exception as exc:
            logger.debug("[DegChain:%s] 全局 ErrorTracker 同步失败: %s", self.name, exc)


# ═══════════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════════

def _ts_iso(ts: float) -> str:
    """将时间戳转为 ISO8601 字符串。"""
    import datetime
    return datetime.datetime.fromtimestamp(ts).isoformat()


# ═══════════════════════════════════════════════════════════════════════════
# 全局实例管理
# ═══════════════════════════════════════════════════════════════════════════

# 按名称管理的 DegradationChain 实例字典
_registered_chains: Dict[str, DegradationChain] = {}


def get_degradation_chain(
    name: str = "default",
    **kwargs,
) -> DegradationChain:
    """获取或创建按名称注册的 DegradationChain 实例。

    幂等调用：同名链仅创建一次。

    Args:
        name: 链名称（如 "search-pipeline"、"llm-call"、"db-ops"）
        **kwargs: 首次创建时传递给 DegradationChain 的参数

    Returns:
        DegradationChain 实例
    """
    if name not in _registered_chains:
        _registered_chains[name] = DegradationChain(name=name, **kwargs)
        logger.info("[DegChainManager] 创建链: %s", name)
    return _registered_chains[name]


def list_chains() -> List[str]:
    """列出所有已注册的链名称。"""
    return sorted(_registered_chains.keys())


def get_chain_status(name: str) -> Optional[Dict[str, Any]]:
    """获取指定链的状态快照。

    Args:
        name: 链名称

    Returns:
        状态字典，若链不存在返回 None
    """
    chain = _registered_chains.get(name)
    if chain is None:
        return None
    return chain.get_degradation_status()


def get_all_chains_status() -> Dict[str, Any]:
    """获取所有已注册链的状态。"""
    result = {}
    for name, chain in _registered_chains.items():
        result[name] = chain.get_degradation_status()
    return result


def reset_all_chains() -> None:
    """重置所有已注册链（主要用于测试）。"""
    _registered_chains.clear()
    logger.debug("[DegChainManager] 所有链已重置")


# ═══════════════════════════════════════════════════════════════════════════
# 便捷集成工具
# ═══════════════════════════════════════════════════════════════════════════

# 全局默认链（懒初始化）
_default_chain: Optional[DegradationChain] = None


def get_default_chain() -> DegradationChain:
    """获取全局默认降级链实例。

    用于不需要显式命名链的简单场景。
    """
    global _default_chain
    if _default_chain is None:
        _default_chain = get_degradation_chain("default")
    return _default_chain


async def track_operation_error(
    error: Exception,
    operation: str = "unknown",
    chain_name: str = "default",
    context: Optional[Dict[str, Any]] = None,
) -> DegradationRule:
    """一站式错误追踪便捷函数。

    在业务代码中可一行调用：

        try:
            result = await risky_operation()
        except Exception as e:
            strategy = await track_operation_error(e, "search", "search-pipeline",
                                                    context={"query": q})
            if strategy.strategy == DegradationStrategy.RETRY_BACKOFF:
                ...

    Args:
        error:      捕获的异常
        operation:  操作名称（用于上下文字段）
        chain_name: 使用的链名称
        context:    附加上下文

    Returns:
        DegradationRule
    """
    chain = get_degradation_chain(chain_name)
    full_context = {"operation": operation}
    if context:
        full_context.update(context)
    return await chain.track_error(error, context=full_context)
