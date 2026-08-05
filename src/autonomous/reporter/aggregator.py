"""
数据聚合器 (Data Aggregator)
=============================
从监控、自修复、调度器等模块聚合7维数据，为报告生成提供统一数据源。
维度：
  1. 系统健康 — 正常/异常时间占比
  2. 请求统计 — 总量、成功率、平均响应时间
  3. 错误统计 — 错误类型、数量、趋势
  4. 资源使用 — CPU/内存/磁盘平均值、峰值
  5. 知识库统计 — 文档数、向量数、查询次数
  6. 自修复统计 — 修复次数、成功率
  7. 告警统计 — 各级别告警数量
"""

import asyncio
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .config import (
    METRIC_API_ERROR_RATE,
    METRIC_API_LATENCY,
    METRIC_API_REQUEST_COUNT,
    METRIC_CPU,
    METRIC_DISK,
    METRIC_MEMORY,
)

logger = logging.getLogger("fuxi.reporter.aggregator")


# ───────────────────────────────────────────────────
# 聚合数据结构
# ───────────────────────────────────────────────────


@dataclass
class HealthDimension:
    """系统健康维度"""

    total_checks: int = 0
    healthy_count: int = 0
    degraded_count: int = 0
    unhealthy_count: int = 0
    healthy_ratio: float = 0.0
    avg_response_time: float = 0.0


@dataclass
class RequestDimension:
    """请求统计维度"""

    total_requests: int = 0
    success_count: int = 0
    error_count: int = 0
    success_rate: float = 0.0
    avg_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0


@dataclass
class ErrorDimension:
    """错误统计维度"""

    total_errors: int = 0
    error_types: Dict[str, int] = field(default_factory=dict)
    error_trend: str = "stable"  # rising | falling | stable
    trend_change_pct: float = 0.0


@dataclass
class ResourceDimension:
    """资源使用维度"""

    cpu_avg: float = 0.0
    cpu_peak: float = 0.0
    memory_avg: float = 0.0
    memory_peak: float = 0.0
    disk_avg: float = 0.0
    disk_peak: float = 0.0
    disk_used_gb: float = 0.0


@dataclass
class KnowledgeDimension:
    """知识库统计维度"""

    document_count: int = 0
    vector_count: int = 0
    query_count: int = 0
    avg_query_latency: float = 0.0


@dataclass
class RepairDimension:
    """自修复统计维度"""

    total_repairs: int = 0
    success_count: int = 0
    failed_count: int = 0
    rolled_back_count: int = 0
    success_rate: float = 0.0
    action_summary: Dict[str, int] = field(default_factory=dict)


@dataclass
class AlertDimension:
    """告警统计维度"""

    total_alerts: int = 0
    p0_count: int = 0
    p1_count: int = 0
    p2_count: int = 0
    p3_count: int = 0
    resolved_count: int = 0
    active_count: int = 0


@dataclass
class AggregatedData:
    """完整聚合数据"""

    report_type: str = "daily"  # daily | weekly
    start_time: datetime = field(default_factory=lambda: datetime.now() - timedelta(hours=24))
    end_time: datetime = field(default_factory=datetime.now)
    generated_at: datetime = field(default_factory=datetime.now)

    health: HealthDimension = field(default_factory=HealthDimension)
    requests: RequestDimension = field(default_factory=RequestDimension)
    errors: ErrorDimension = field(default_factory=ErrorDimension)
    resources: ResourceDimension = field(default_factory=ResourceDimension)
    knowledge: KnowledgeDimension = field(default_factory=KnowledgeDimension)
    repairs: RepairDimension = field(default_factory=RepairDimension)
    alerts: AlertDimension = field(default_factory=AlertDimension)

    # 趋势对比（与前一周期对比）
    prev_health_ratio: Optional[float] = None
    prev_request_count: Optional[int] = None
    prev_error_count: Optional[int] = None
    prev_cpu_avg: Optional[float] = None
    prev_alert_count: Optional[int] = None


# ───────────────────────────────────────────────────
# 聚合器
# ───────────────────────────────────────────────────


class DataAggregator:
    """
    数据聚合器
    从各模块收集数据，聚合为报告所需的7维结构。
    """

    def __init__(self):
        self._cache: Dict[str, Tuple[float, Any]] = {}  # key → (timestamp, data)

    async def aggregate(
        self,
        report_type: str = "daily",
        end_time: Optional[datetime] = None,
    ) -> AggregatedData:
        """
        聚合指定时间范围的数据。

        Args:
            report_type: "daily" 或 "weekly"
            end_time: 结束时间，默认为当前时间

        Returns:
            AggregatedData 完整的7维聚合数据
        """
        if end_time is None:
            end_time = datetime.now()

        if report_type == "daily":
            start_time = end_time - timedelta(hours=24)
            prev_start = start_time - timedelta(hours=24)
            prev_end = start_time
        else:  # weekly
            start_time = end_time - timedelta(days=7)
            prev_start = start_time - timedelta(days=7)
            prev_end = start_time

        data = AggregatedData(
            report_type=report_type,
            start_time=start_time,
            end_time=end_time,
        )

        # 并行聚合7个维度
        results = await asyncio.gather(
            self._aggregate_health(start_time, end_time),
            self._aggregate_requests(start_time, end_time),
            self._aggregate_errors(start_time, end_time),
            self._aggregate_resources(start_time, end_time),
            self._aggregate_knowledge(start_time, end_time),
            self._aggregate_repairs(start_time, end_time),
            self._aggregate_alerts(start_time, end_time),
            self._aggregate_prev_period(report_type, prev_start, prev_end),
            return_exceptions=True,
        )

        # 填充各维度（异常时使用默认值）
        if not isinstance(results[0], Exception):
            data.health = results[0]
        else:
            logger.warning(f"健康维度聚合失败: {results[0]}")

        if not isinstance(results[1], Exception):
            data.requests = results[1]
        else:
            logger.warning(f"请求维度聚合失败: {results[1]}")

        if not isinstance(results[2], Exception):
            data.errors = results[2]
        else:
            logger.warning(f"错误维度聚合失败: {results[2]}")

        if not isinstance(results[3], Exception):
            data.resources = results[3]
        else:
            logger.warning(f"资源维度聚合失败: {results[3]}")

        if not isinstance(results[4], Exception):
            data.knowledge = results[4]
        else:
            logger.warning(f"知识库维度聚合失败: {results[4]}")

        if not isinstance(results[5], Exception):
            data.repairs = results[5]
        else:
            logger.warning(f"自修复维度聚合失败: {results[5]}")

        if not isinstance(results[6], Exception):
            data.alerts = results[6]
        else:
            logger.warning(f"告警维度聚合失败: {results[6]}")

        # 趋势对比
        if not isinstance(results[7], Exception):
            prev = results[7]
            data.prev_health_ratio = prev.get("health_ratio")
            data.prev_request_count = prev.get("request_count")
            data.prev_error_count = prev.get("error_count")
            data.prev_cpu_avg = prev.get("cpu_avg")
            data.prev_alert_count = prev.get("alert_count")

        return data

    # ── 维度1：系统健康 ──

    async def _aggregate_health(self, start: datetime, end: datetime) -> HealthDimension:
        """聚合系统健康数据"""
        try:
            from src.autonomous.monitor.health_checker import HealthChecker

            checker = HealthChecker()
            history = checker.get_history(limit=1000)

            # 过滤时间范围
            records = [h for h in history if start <= h.checked_at <= end]

            if not records:
                return HealthDimension()

            healthy = sum(1 for r in records if r.status.value == "healthy")
            degraded = sum(1 for r in records if r.status.value == "degraded")
            unhealthy = sum(1 for r in records if r.status.value == "unhealthy")
            total = len(records)

            avg_rt = sum(r.duration for r in records) / total if total > 0 else 0

            return HealthDimension(
                total_checks=total,
                healthy_count=healthy,
                degraded_count=degraded,
                unhealthy_count=unhealthy,
                healthy_ratio=round(healthy / total, 4) if total > 0 else 0,
                avg_response_time=round(avg_rt, 3),
            )
        except Exception as e:
            logger.error(f"健康维度聚合异常: {e}")
            return HealthDimension()

    # ── 维度2：请求统计 ──

    async def _aggregate_requests(self, start: datetime, end: datetime) -> RequestDimension:
        """聚合请求统计数据"""
        try:
            from src.autonomous.monitor.metrics_collector import MetricsCollector

            collector = MetricsCollector()

            # 查询延迟指标
            latency_metrics = collector.query_metrics(METRIC_API_LATENCY, start, end, limit=10000)
            # 查询请求计数
            request_metrics = collector.query_metrics(METRIC_API_REQUEST_COUNT, start, end, limit=10000)
            # 查询错误率
            error_rate_metrics = collector.query_metrics(METRIC_API_ERROR_RATE, start, end, limit=10000)

            total_requests = sum(int(m.value) for m in request_metrics) if request_metrics else 0

            latencies = [m.value for m in latency_metrics]
            avg_latency = sum(latencies) / len(latencies) if latencies else 0

            # 计算 P95、P99
            p95_latency = 0.0
            p99_latency = 0.0
            if latencies:
                sorted_lat = sorted(latencies)
                p95_idx = int(len(sorted_lat) * 0.95)
                p99_idx = int(len(sorted_lat) * 0.99)
                p95_latency = sorted_lat[min(p95_idx, len(sorted_lat) - 1)]
                p99_latency = sorted_lat[min(p99_idx, len(sorted_lat) - 1)]

            # 错误率平均值
            avg_error_rate = (
                sum(m.value for m in error_rate_metrics) / len(error_rate_metrics) if error_rate_metrics else 0
            )

            error_count = int(total_requests * avg_error_rate / 100) if total_requests > 0 else 0
            success_count = total_requests - error_count

            return RequestDimension(
                total_requests=total_requests,
                success_count=success_count,
                error_count=error_count,
                success_rate=round(100 - avg_error_rate, 2) if total_requests > 0 else 100.0,
                avg_latency=round(avg_latency, 3),
                p95_latency=round(p95_latency, 3),
                p99_latency=round(p99_latency, 3),
            )
        except Exception as e:
            logger.error(f"请求维度聚合异常: {e}")
            return RequestDimension()

    # ── 维度3：错误统计 ──

    async def _aggregate_errors(self, start: datetime, end: datetime) -> ErrorDimension:
        """聚合错误统计数据"""
        try:
            from src.autonomous.monitor.log_analyzer import LogAnalyzer

            analyzer = LogAnalyzer()

            # 获取分析结果
            results = analyzer.get_analysis_results(limit=1000)

            # 按时间过滤
            filtered = []
            for r in results:
                try:
                    ts = datetime.fromisoformat(r.get("timestamp", ""))
                    if start <= ts <= end:
                        filtered.append(r)
                except (ValueError, TypeError):
                    pass

            # 按规则类型统计
            error_types: Dict[str, int] = {}
            for r in filtered:
                rule_type = r.get("rule_type", "unknown")
                error_types[rule_type] = error_types.get(rule_type, 0) + 1

            total_errors = sum(error_types.values())

            # 趋势：前半段 vs 后半段
            mid = start + (end - start) / 2
            first_half = sum(1 for r in filtered if datetime.fromisoformat(r.get("timestamp", start.isoformat())) < mid)
            second_half = total_errors - first_half

            if first_half > 0:
                change_pct = ((second_half - first_half) / first_half) * 100
            else:
                change_pct = 0

            if change_pct > 10:
                trend = "rising"
            elif change_pct < -10:
                trend = "falling"
            else:
                trend = "stable"

            return ErrorDimension(
                total_errors=total_errors,
                error_types=error_types,
                error_trend=trend,
                trend_change_pct=round(change_pct, 1),
            )
        except Exception as e:
            logger.error(f"错误维度聚合异常: {e}")
            return ErrorDimension()

    # ── 维度4：资源使用 ──

    async def _aggregate_resources(self, start: datetime, end: datetime) -> ResourceDimension:
        """聚合资源使用数据"""
        try:
            from src.autonomous.monitor.metrics_collector import MetricsCollector

            collector = MetricsCollector()

            cpu_metrics = collector.query_metrics(METRIC_CPU, start, end, limit=10000)
            mem_metrics = collector.query_metrics(METRIC_MEMORY, start, end, limit=10000)
            disk_metrics = collector.query_metrics(METRIC_DISK, start, end, limit=10000)

            def _avg_peak(metrics):
                if not metrics:
                    return 0.0, 0.0
                values = [m.value for m in metrics]
                return (
                    round(sum(values) / len(values), 2),
                    round(max(values), 2),
                )

            cpu_avg, cpu_peak = _avg_peak(cpu_metrics)
            mem_avg, mem_peak = _avg_peak(mem_metrics)
            disk_avg, disk_peak = _avg_peak(disk_metrics)

            # 获取当前磁盘使用量
            import psutil

            disk_used_gb = round(psutil.disk_usage("/").used / (1024**3), 2)

            return ResourceDimension(
                cpu_avg=cpu_avg,
                cpu_peak=cpu_peak,
                memory_avg=mem_avg,
                memory_peak=mem_peak,
                disk_avg=disk_avg,
                disk_peak=disk_peak,
                disk_used_gb=disk_used_gb,
            )
        except Exception as e:
            logger.error(f"资源维度聚合异常: {e}")
            return ResourceDimension()

    # ── 维度5：知识库统计 ──

    async def _aggregate_knowledge(self, start: datetime, end: datetime) -> KnowledgeDimension:
        """聚合知识库统计数据"""
        try:
            document_count = 0
            vector_count = 0
            query_count = 0
            avg_query_latency = 0.0

            # 尝试从 ChromaDB 获取向量数
            try:
                from src.db.vector_store import count_chunks

                vector_count = count_chunks()
            except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                pass

            # 尝试从 SQLite 获取文档数
            try:
                from src.db.data_store import load_chunks

                chunks = await asyncio.to_thread(load_chunks)
                document_count = len(chunks) if chunks else 0
            except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                pass

            # 从指标采集器获取查询次数和延迟
            try:
                from src.autonomous.monitor.metrics_collector import MetricsCollector

                collector = MetricsCollector()
                query_metrics = collector.query_metrics("business.kb_query_count", start, end, limit=10000)
                query_count = sum(int(m.value) for m in query_metrics) if query_metrics else 0

                latency_metrics = collector.query_metrics("business.kb_query_latency", start, end, limit=10000)
                if latency_metrics:
                    avg_query_latency = round(sum(m.value for m in latency_metrics) / len(latency_metrics), 3)
            except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                pass

            return KnowledgeDimension(
                document_count=document_count,
                vector_count=vector_count,
                query_count=query_count,
                avg_query_latency=avg_query_latency,
            )
        except Exception as e:
            logger.error(f"知识库维度聚合异常: {e}")
            return KnowledgeDimension()

    # ── 维度6：自修复统计 ──

    async def _aggregate_repairs(self, start: datetime, end: datetime) -> RepairDimension:
        """聚合自修复统计数据"""
        try:
            from src.autonomous.healer.engine import HealerEngine
            from src.autonomous.healer.safety import RepairStatus

            engine = HealerEngine()
            history = engine.get_history(limit=1000)

            # 按时间过滤
            filtered = []
            for r in history:
                try:
                    ts = datetime.fromisoformat(r.get("started_at", ""))
                    if start <= ts <= end:
                        filtered.append(r)
                except (ValueError, TypeError):
                    pass

            total = len(filtered)
            success = sum(1 for r in filtered if r.get("status") == "success")
            failed = sum(1 for r in filtered if r.get("status") == "failed")
            rolled_back = sum(1 for r in filtered if r.get("status") == "rolled_back")

            # 按动作汇总
            action_summary: Dict[str, int] = {}
            for r in filtered:
                action_id = r.get("action_id", "unknown")
                action_summary[action_id] = action_summary.get(action_id, 0) + 1

            success_rate = round(success / total, 4) if total > 0 else 0

            return RepairDimension(
                total_repairs=total,
                success_count=success,
                failed_count=failed,
                rolled_back_count=rolled_back,
                success_rate=success_rate,
                action_summary=action_summary,
            )
        except Exception as e:
            logger.error(f"自修复维度聚合异常: {e}")
            return RepairDimension()

    # ── 维度7：告警统计 ──

    async def _aggregate_alerts(self, start: datetime, end: datetime) -> AlertDimension:
        """聚合告警统计数据"""
        try:
            from src.autonomous.monitor.alert_engine import AlertEngine, AlertLevel

            engine = AlertEngine()

            # 获取告警历史
            history = engine.get_alert_history(limit=10000)

            # 按时间过滤
            filtered = [a for a in history if start <= a.created_at <= end]

            total = len(filtered)
            p0 = sum(1 for a in filtered if a.level == AlertLevel.P0)
            p1 = sum(1 for a in filtered if a.level == AlertLevel.P1)
            p2 = sum(1 for a in filtered if a.level == AlertLevel.P2)
            p3 = sum(1 for a in filtered if a.level == AlertLevel.P3)
            resolved = sum(1 for a in filtered if a.resolved_at is not None)
            active = total - resolved

            return AlertDimension(
                total_alerts=total,
                p0_count=p0,
                p1_count=p1,
                p2_count=p2,
                p3_count=p3,
                resolved_count=resolved,
                active_count=active,
            )
        except Exception as e:
            logger.error(f"告警维度聚合异常: {e}")
            return AlertDimension()

    # ── 前一周期对比 ──

    async def _aggregate_prev_period(
        self,
        report_type: str,
        prev_start: datetime,
        prev_end: datetime,
    ) -> Dict[str, Any]:
        """聚合前一周期数据用于趋势对比"""
        result: Dict[str, Any] = {}

        try:
            # 健康率
            health = await self._aggregate_health(prev_start, prev_end)
            result["health_ratio"] = health.healthy_ratio

            # 请求量
            requests = await self._aggregate_requests(prev_start, prev_end)
            result["request_count"] = requests.total_requests

            # 错误数
            errors = await self._aggregate_errors(prev_start, prev_end)
            result["error_count"] = errors.total_errors

            # CPU 平均
            resources = await self._aggregate_resources(prev_start, prev_end)
            result["cpu_avg"] = resources.cpu_avg

            # 告警数
            alerts = await self._aggregate_alerts(prev_start, prev_end)
            result["alert_count"] = alerts.total_alerts

        except Exception as e:
            logger.warning(f"前一周期聚合失败: {e}")

        return result
