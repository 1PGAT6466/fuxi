"""
日志分析器模块
实时日志流分析、错误模式识别、异常检测
"""

import asyncio
import logging
import re
import statistics
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Pattern

logger = logging.getLogger(__name__)


class AnalysisRuleType(Enum):
    """分析规则类型"""

    ERROR_RATE_SPIKE = "error_rate_spike"  # 错误率突增
    LATENCY_SPIKE = "latency_spike"  # 响应时间突增
    PATTERN_MATCH = "pattern_match"  # 模式匹配
    VOLUME_ANOMALY = "volume_anomaly"  # 日志量异常


@dataclass
class LogEntry:
    """日志条目"""

    timestamp: datetime
    level: str  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message: str
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_error(self) -> bool:
        return self.level in ("ERROR", "CRITICAL")


@dataclass
class AnalysisRule:
    """分析规则"""

    id: str
    name: str
    rule_type: AnalysisRuleType
    description: str
    enabled: bool = True

    # 通用配置
    window_size: int = 300  # 分析窗口（秒）
    check_interval: int = 60  # 检查间隔（秒）

    # 错误率突增配置
    error_rate_threshold: float = 50.0  # 突增百分比

    # 响应时间突增配置
    latency_threshold: float = 100.0  # 突增百分比

    # 模式匹配配置
    pattern: str = ""  # 正则表达式
    pattern_flags: int = re.IGNORECASE

    # 日志量异常配置
    volume_min: int = 100  # 最小日志量
    volume_max: int = 10000  # 最大日志量

    # 告警级别
    alert_level: str = "P1"  # P0, P1, P2, P3


@dataclass
class AnalysisResult:
    """分析结果"""

    rule_id: str
    rule_name: str
    rule_type: AnalysisRuleType
    alert_level: str
    triggered: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class LogPattern:
    """日志模式"""

    pattern: str
    regex: Optional[Pattern] = None
    count: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    examples: List[str] = field(default_factory=list)


@dataclass
class LogStatistics:
    """日志统计"""

    total_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    level_counts: Dict[str, int] = field(default_factory=dict)
    source_counts: Dict[str, int] = field(default_factory=dict)
    error_rate: float = 0.0
    avg_latency: Optional[float] = None
    p95_latency: Optional[float] = None
    p99_latency: Optional[float] = None


class LogAnalyzer:
    """日志分析器"""

    def __init__(self, config=None):
        from .config import MonitorConfig

        self.config = config or MonitorConfig()

        # 日志缓冲区
        self._log_buffer: deque = deque(maxlen=10000)

        # 统计数据
        self._window_stats: Dict[str, LogStatistics] = {}  # window_key -> stats
        self._current_stats = LogStatistics()

        # 模式库
        self._patterns: Dict[str, LogPattern] = {}

        # 分析规则
        self._rules: Dict[str, AnalysisRule] = {}

        # 分析结果历史
        self._results: List[AnalysisResult] = []

        # 告警回调
        self._alert_callbacks: List[Callable] = []

        # 加载默认规则
        self._load_default_rules()

    def _load_default_rules(self):
        """加载默认分析规则"""
        default_rules = [
            AnalysisRule(
                id="error_rate_spike",
                name="错误率突增",
                rule_type=AnalysisRuleType.ERROR_RATE_SPIKE,
                description="错误率突增超过50%",
                error_rate_threshold=50.0,
                window_size=300,
                alert_level="P1",
            ),
            AnalysisRule(
                id="latency_spike",
                name="响应时间突增",
                rule_type=AnalysisRuleType.LATENCY_SPIKE,
                description="响应时间突增超过100%",
                latency_threshold=100.0,
                window_size=300,
                alert_level="P1",
            ),
            AnalysisRule(
                id="critical_error_pattern",
                name="严重错误模式",
                rule_type=AnalysisRuleType.PATTERN_MATCH,
                description="匹配严重错误模式",
                pattern=r"(?:FATAL|CRITICAL|OUT OF MEMORY|SEGFAULT|CORE DUMP)",
                pattern_flags=re.IGNORECASE,
                alert_level="P0",
            ),
            AnalysisRule(
                id="database_error_pattern",
                name="数据库错误模式",
                rule_type=AnalysisRuleType.PATTERN_MATCH,
                description="匹配数据库错误模式",
                pattern=r"(?:deadlock|connection refused|too many connections|table.*lock)",
                pattern_flags=re.IGNORECASE,
                alert_level="P1",
            ),
            AnalysisRule(
                id="volume_anomaly",
                name="日志量异常",
                rule_type=AnalysisRuleType.VOLUME_ANOMALY,
                description="日志量超出正常范围",
                volume_min=100,
                volume_max=10000,
                window_size=300,
                alert_level="P2",
            ),
        ]

        for rule in default_rules:
            self._rules[rule.id] = rule

    def add_rule(self, rule: AnalysisRule):
        """添加分析规则"""
        self._rules[rule.id] = rule
        logger.info(f"添加分析规则: {rule.name}")

    def remove_rule(self, rule_id: str):
        """移除分析规则"""
        if rule_id in self._rules:
            del self._rules[rule_id]
            logger.info(f"移除分析规则: {rule_id}")

    def get_rules(self) -> List[AnalysisRule]:
        """获取所有分析规则"""
        return list(self._rules.values())

    def add_alert_callback(self, callback: Callable):
        """添加告警回调"""
        self._alert_callbacks.append(callback)

    async def _trigger_alert(self, result: AnalysisResult):
        """触发告警"""
        for callback in self._alert_callbacks:
            try:
                await callback(result)
            except Exception as e:
                logger.error(f"告警回调执行失败: {e}")

    def ingest_log(self, entry: LogEntry):
        """摄入日志条目"""
        self._log_buffer.append(entry)

        # 更新统计
        self._update_statistics(entry)

        # 模式匹配
        self._match_patterns(entry)

    def ingest_logs(self, entries: List[LogEntry]):
        """批量摄入日志条目"""
        for entry in entries:
            self.ingest_log(entry)

    def _update_statistics(self, entry: LogEntry):
        """更新统计数据"""
        self._current_stats.total_count += 1
        self._current_stats.level_counts[entry.level] = self._current_stats.level_counts.get(entry.level, 0) + 1

        if entry.source:
            self._current_stats.source_counts[entry.source] = self._current_stats.source_counts.get(entry.source, 0) + 1

        if entry.is_error:
            self._current_stats.error_count += 1

        if entry.level == "WARNING":
            self._current_stats.warning_count += 1

        # 更新错误率
        if self._current_stats.total_count > 0:
            self._current_stats.error_rate = (self._current_stats.error_count / self._current_stats.total_count) * 100

        # 更新延迟统计（如果metadata中有latency）
        latency = entry.metadata.get("latency")
        if latency is not None:
            if self._current_stats.avg_latency is None:
                self._current_stats.avg_latency = latency
            else:
                # 移动平均
                self._current_stats.avg_latency = (self._current_stats.avg_latency * 0.9) + (latency * 0.1)

    def _match_patterns(self, entry: LogEntry):
        """模式匹配"""
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            if rule.rule_type != AnalysisRuleType.PATTERN_MATCH:
                continue
            if not rule.pattern:
                continue

            try:
                if re.search(rule.pattern, entry.message, rule.pattern_flags):
                    pattern_key = f"{rule.id}:{rule.pattern}"
                    if pattern_key not in self._patterns:
                        self._patterns[pattern_key] = LogPattern(
                            pattern=rule.pattern,
                            regex=re.compile(rule.pattern, rule.pattern_flags),
                            first_seen=entry.timestamp,
                        )

                    pattern = self._patterns[pattern_key]
                    pattern.count += 1
                    pattern.last_seen = entry.timestamp

                    # 保留最近的示例
                    if len(pattern.examples) < 5:
                        pattern.examples.append(entry.message[:200])
            except re.error as e:
                logger.error(f"正则表达式错误: {rule.pattern} - {e}")

    async def analyze(self) -> List[AnalysisResult]:
        """执行分析"""
        results = []
        now = datetime.now()

        for rule in self._rules.values():
            if not rule.enabled:
                continue

            try:
                result = await self._analyze_rule(rule, now)
                if result and result.triggered:
                    results.append(result)
                    await self._trigger_alert(result)
            except Exception as e:
                logger.error(f"分析规则执行失败: {rule.id} - {e}")

        # 保存结果
        self._results.extend(results)
        if len(self._results) > 1000:
            self._results = self._results[-1000:]

        return results

    async def _analyze_rule(self, rule: AnalysisRule, now: datetime) -> Optional[AnalysisResult]:
        """分析单个规则"""
        if rule.rule_type == AnalysisRuleType.ERROR_RATE_SPIKE:
            return await self._analyze_error_rate_spike(rule, now)
        elif rule.rule_type == AnalysisRuleType.LATENCY_SPIKE:
            return await self._analyze_latency_spike(rule, now)
        elif rule.rule_type == AnalysisRuleType.PATTERN_MATCH:
            return await self._analyze_pattern_match(rule, now)
        elif rule.rule_type == AnalysisRuleType.VOLUME_ANOMALY:
            return await self._analyze_volume_anomaly(rule, now)
        return None

    async def _analyze_error_rate_spike(self, rule: AnalysisRule, now: datetime) -> AnalysisResult:
        """分析错误率突增"""
        # 获取窗口内的日志
        window_start = now - timedelta(seconds=rule.window_size)
        window_logs = [log for log in self._log_buffer if log.timestamp >= window_start]

        if len(window_logs) < 10:
            return AnalysisResult(
                rule_id=rule.id,
                rule_name=rule.name,
                rule_type=rule.rule_type,
                alert_level=rule.alert_level,
                triggered=False,
                message="日志量不足，无法分析",
            )

        # 计算当前错误率
        error_count = sum(1 for log in window_logs if log.is_error)
        current_rate = (error_count / len(window_logs)) * 100

        # 获取历史错误率（上一个窗口）
        prev_window_start = window_start - timedelta(seconds=rule.window_size)
        prev_window_logs = [log for log in self._log_buffer if prev_window_start <= log.timestamp < window_start]

        if prev_window_logs:
            prev_error_count = sum(1 for log in prev_window_logs if log.is_error)
            prev_rate = (prev_error_count / len(prev_window_logs)) * 100

            # 计算突增百分比
            if prev_rate > 0:
                spike_percentage = ((current_rate - prev_rate) / prev_rate) * 100
            else:
                spike_percentage = 100.0 if current_rate > 0 else 0.0

            triggered = spike_percentage > rule.error_rate_threshold

            return AnalysisResult(
                rule_id=rule.id,
                rule_name=rule.name,
                rule_type=rule.rule_type,
                alert_level=rule.alert_level,
                triggered=triggered,
                message=f"错误率突增 {spike_percentage:.1f}% (当前: {current_rate:.1f}%, 历史: {prev_rate:.1f}%)",
                details={
                    "current_rate": current_rate,
                    "previous_rate": prev_rate,
                    "spike_percentage": spike_percentage,
                    "window_logs_count": len(window_logs),
                    "error_count": error_count,
                },
            )

        return AnalysisResult(
            rule_id=rule.id,
            rule_name=rule.name,
            rule_type=rule.rule_type,
            alert_level=rule.alert_level,
            triggered=False,
            message="无历史数据对比",
        )

    async def _analyze_latency_spike(self, rule: AnalysisRule, now: datetime) -> AnalysisResult:
        """分析响应时间突增"""
        window_start = now - timedelta(seconds=rule.window_size)
        window_logs = [log for log in self._log_buffer if log.timestamp >= window_start and "latency" in log.metadata]

        if len(window_logs) < 10:
            return AnalysisResult(
                rule_id=rule.id,
                rule_name=rule.name,
                rule_type=rule.rule_type,
                alert_level=rule.alert_level,
                triggered=False,
                message="延迟数据不足",
            )

        current_latencies = [log.metadata["latency"] for log in window_logs]
        current_avg = statistics.mean(current_latencies)

        # 获取历史延迟
        prev_window_start = window_start - timedelta(seconds=rule.window_size)
        prev_window_logs = [
            log
            for log in self._log_buffer
            if prev_window_start <= log.timestamp < window_start and "latency" in log.metadata
        ]

        if prev_window_logs:
            prev_latencies = [log.metadata["latency"] for log in prev_window_logs]
            prev_avg = statistics.mean(prev_latencies)

            if prev_avg > 0:
                spike_percentage = ((current_avg - prev_avg) / prev_avg) * 100
            else:
                spike_percentage = 100.0 if current_avg > 0 else 0.0

            triggered = spike_percentage > rule.latency_threshold

            return AnalysisResult(
                rule_id=rule.id,
                rule_name=rule.name,
                rule_type=rule.rule_type,
                alert_level=rule.alert_level,
                triggered=triggered,
                message=f"响应时间突增 {spike_percentage:.1f}% (当前: {current_avg:.2f}s, 历史: {prev_avg:.2f}s)",
                details={
                    "current_avg_latency": current_avg,
                    "previous_avg_latency": prev_avg,
                    "spike_percentage": spike_percentage,
                    "p95_latency": (
                        sorted(current_latencies)[int(len(current_latencies) * 0.95)] if current_latencies else 0
                    ),
                    "p99_latency": (
                        sorted(current_latencies)[int(len(current_latencies) * 0.99)] if current_latencies else 0
                    ),
                },
            )

        return AnalysisResult(
            rule_id=rule.id,
            rule_name=rule.name,
            rule_type=rule.rule_type,
            alert_level=rule.alert_level,
            triggered=False,
            message="无历史数据对比",
        )

    async def _analyze_pattern_match(self, rule: AnalysisRule, now: datetime) -> AnalysisResult:
        """分析模式匹配"""
        pattern_key = f"{rule.id}:{rule.pattern}"
        pattern = self._patterns.get(pattern_key)

        if pattern and pattern.count > 0:
            return AnalysisResult(
                rule_id=rule.id,
                rule_name=rule.name,
                rule_type=rule.rule_type,
                alert_level=rule.alert_level,
                triggered=True,
                message=f"匹配到错误模式: {pattern.count}次",
                details={
                    "pattern": rule.pattern,
                    "count": pattern.count,
                    "first_seen": pattern.first_seen.isoformat() if pattern.first_seen else None,
                    "last_seen": pattern.last_seen.isoformat() if pattern.last_seen else None,
                    "examples": pattern.examples[:3],
                },
            )

        return AnalysisResult(
            rule_id=rule.id,
            rule_name=rule.name,
            rule_type=rule.rule_type,
            alert_level=rule.alert_level,
            triggered=False,
            message="未匹配到模式",
        )

    async def _analyze_volume_anomaly(self, rule: AnalysisRule, now: datetime) -> AnalysisResult:
        """分析日志量异常"""
        window_start = now - timedelta(seconds=rule.window_size)
        window_logs = [log for log in self._log_buffer if log.timestamp >= window_start]

        volume = len(window_logs)

        if volume < rule.volume_min:
            return AnalysisResult(
                rule_id=rule.id,
                rule_name=rule.name,
                rule_type=rule.rule_type,
                alert_level=rule.alert_level,
                triggered=True,
                message=f"日志量过低: {volume} (最小: {rule.volume_min})",
                details={"volume": volume, "threshold": rule.volume_min, "type": "low"},
            )
        elif volume > rule.volume_max:
            return AnalysisResult(
                rule_id=rule.id,
                rule_name=rule.name,
                rule_type=rule.rule_type,
                alert_level=rule.alert_level,
                triggered=True,
                message=f"日志量过高: {volume} (最大: {rule.volume_max})",
                details={"volume": volume, "threshold": rule.volume_max, "type": "high"},
            )

        return AnalysisResult(
            rule_id=rule.id,
            rule_name=rule.name,
            rule_type=rule.rule_type,
            alert_level=rule.alert_level,
            triggered=False,
            message=f"日志量正常: {volume}",
        )

    def get_statistics(self, window_seconds: int = 300) -> LogStatistics:
        """获取统计信息"""
        now = datetime.now()
        window_start = now - timedelta(seconds=window_seconds)

        window_logs = [log for log in self._log_buffer if log.timestamp >= window_start]

        if not window_logs:
            return LogStatistics()

        stats = LogStatistics(
            total_count=len(window_logs),
            error_count=sum(1 for log in window_logs if log.is_error),
            warning_count=sum(1 for log in window_logs if log.level == "WARNING"),
            level_counts=defaultdict(int),
            source_counts=defaultdict(int),
        )

        latencies = []
        for log in window_logs:
            stats.level_counts[log.level] += 1
            if log.source:
                stats.source_counts[log.source] += 1
            if "latency" in log.metadata:
                latencies.append(log.metadata["latency"])

        if stats.total_count > 0:
            stats.error_rate = (stats.error_count / stats.total_count) * 100

        if latencies:
            latencies.sort()
            stats.avg_latency = statistics.mean(latencies)
            stats.p95_latency = latencies[int(len(latencies) * 0.95)]
            stats.p99_latency = latencies[int(len(latencies) * 0.99)]

        return stats

    def get_patterns(self, min_count: int = 1) -> List[Dict[str, Any]]:
        """获取日志模式"""
        patterns = []
        for key, pattern in self._patterns.items():
            if pattern.count >= min_count:
                patterns.append(
                    {
                        "pattern": pattern.pattern,
                        "count": pattern.count,
                        "first_seen": pattern.first_seen.isoformat() if pattern.first_seen else None,
                        "last_seen": pattern.last_seen.isoformat() if pattern.last_seen else None,
                        "examples": pattern.examples[:3],
                    }
                )
        return sorted(patterns, key=lambda x: x["count"], reverse=True)

    def get_analysis_results(
        self, rule_type: Optional[AnalysisRuleType] = None, alert_level: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取分析结果"""
        results = self._results

        if rule_type:
            results = [r for r in results if r.rule_type == rule_type]
        if alert_level:
            results = [r for r in results if r.alert_level == alert_level]

        return [
            {
                "rule_id": r.rule_id,
                "rule_name": r.rule_name,
                "rule_type": r.rule_type.value,
                "alert_level": r.alert_level,
                "triggered": r.triggered,
                "message": r.message,
                "details": r.details,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in results[-limit:]
        ]

    def generate_report(self, window_seconds: int = 3600) -> Dict[str, Any]:
        """生成分析报告"""
        stats = self.get_statistics(window_seconds)
        patterns = self.get_patterns()
        recent_results = self.get_analysis_results(limit=50)

        return {
            "report_time": datetime.now().isoformat(),
            "window_seconds": window_seconds,
            "statistics": {
                "total_count": stats.total_count,
                "error_count": stats.error_count,
                "warning_count": stats.warning_count,
                "error_rate": stats.error_rate,
                "level_counts": dict(stats.level_counts),
                "source_counts": dict(stats.source_counts),
                "avg_latency": stats.avg_latency,
                "p95_latency": stats.p95_latency,
                "p99_latency": stats.p99_latency,
            },
            "patterns": patterns[:20],
            "recent_alerts": recent_results,
            "rules_status": [
                {
                    "id": rule.id,
                    "name": rule.name,
                    "type": rule.rule_type.value,
                    "enabled": rule.enabled,
                    "alert_level": rule.alert_level,
                }
                for rule in self._rules.values()
            ],
        }
