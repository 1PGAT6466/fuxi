"""
运维监控 API 路由
提供健康检查、指标采集和告警管理接口
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from src.api.auth import require_admin
from src.api.response import error, success
from src.auth.auth_middleware import require_auth_dep

router = APIRouter(
    prefix="/api/ops",
    tags=["运维监控"],
    dependencies=[Depends(require_auth_dep)],
)

# 全局实例（延迟初始化）
_health_checker: Any = None
_metrics_collector: Any = None
_alert_engine: Any = None
_notifier: Any = None
_log_analyzer: Any = None
_plugin_syncer: Any = None
_knowledge_syncer: Any = None
_cache_manager: Any = None


def _get_health_checker() -> Any:
    """延迟初始化健康检查器（单例）"""
    global _health_checker
    if _health_checker is None:
        from src.autonomous.monitor.health_checker import HealthChecker

        _health_checker = HealthChecker()
    return _health_checker


def _get_metrics_collector() -> Any:
    """延迟初始化指标采集器（单例）"""
    global _metrics_collector
    if _metrics_collector is None:
        from src.autonomous.monitor.metrics_collector import MetricsCollector

        _metrics_collector = MetricsCollector()
    return _metrics_collector


def _get_alert_engine() -> Any:
    """延迟初始化告警引擎（单例）"""
    global _alert_engine
    if _alert_engine is None:
        from src.autonomous.monitor.alert_engine import AlertEngine

        _alert_engine = AlertEngine()
    return _alert_engine


def _get_notifier() -> Any:
    """延迟初始化通知器（单例）"""
    global _notifier
    if _notifier is None:
        from src.autonomous.monitor.notifier import Notifier

        _notifier = Notifier()
    return _notifier


def _get_log_analyzer() -> Any:
    """延迟初始化日志分析器（单例）"""
    global _log_analyzer
    if _log_analyzer is None:
        from src.autonomous.monitor.log_analyzer import LogAnalyzer

        _log_analyzer = LogAnalyzer()
    return _log_analyzer


def _get_plugin_syncer() -> Any:
    """延迟初始化插件同步器（单例）"""
    global _plugin_syncer
    if _plugin_syncer is None:
        from src.autonomous.sync.plugin_sync import PluginSyncer

        _plugin_syncer = PluginSyncer()
    return _plugin_syncer


def _get_knowledge_syncer() -> Any:
    """延迟初始化知识同步器（单例）"""
    global _knowledge_syncer
    if _knowledge_syncer is None:
        from src.autonomous.sync.knowledge_sync import KnowledgeSyncer

        _knowledge_syncer = KnowledgeSyncer()
    return _knowledge_syncer


def _get_cache_manager() -> Any:
    """延迟初始化缓存管理器（单例）"""
    global _cache_manager
    if _cache_manager is None:
        from src.autonomous.sync.cache_manager import CacheManager

        _cache_manager = CacheManager()
    return _cache_manager


class AlertRuleCreate(BaseModel):
    """创建告警规则请求"""

    id: str
    name: str
    metric: str
    condition: str
    threshold: float
    level: int
    description: str = ""
    enabled: bool = True
    cooldown: int = 300


@router.get("/health")
async def get_health_status() -> JSONResponse:
    """获取系统健康状态"""
    checker = _get_health_checker()
    health = await checker.check_all()

    return success(
        data={
            "status": health.status.value,
            "services": [
                {
                    "name": s.name,
                    "status": s.status.value,
                    "response_time": round(s.response_time, 3),
                    "message": s.message,
                    "details": s.details,
                    "checked_at": s.checked_at.isoformat(),
                }
                for s in health.services
            ],
            "checked_at": health.checked_at.isoformat(),
            "duration": round(health.duration, 3),
        },
        message="健康状态查询成功",
    )


@router.get("/health/history")
async def get_health_history(limit: int = Query(default=100, ge=1, le=1000)) -> JSONResponse:
    """获取健康检查历史"""
    checker = _get_health_checker()
    history = checker.get_history(limit)

    return success(
        data={
            "history": [
                {
                    "status": h.status.value,
                    "checked_at": h.checked_at.isoformat(),
                    "duration": round(h.duration, 3),
                    "services_summary": {s.name: s.status.value for s in h.services},
                }
                for h in history
            ],
            "total": len(history),
        },
        message="健康历史查询成功",
    )


@router.get("/metrics")
async def get_metrics(
    name: str = Query(..., description="指标名称"),
    start_time: Optional[str] = Query(None, description="开始时间 ISO格式"),
    end_time: Optional[str] = Query(None, description="结束时间 ISO格式"),
    limit: int = Query(default=100, ge=1, le=10000),
) -> JSONResponse:
    """获取指标数据"""
    collector = _get_metrics_collector()

    start_dt = datetime.fromisoformat(start_time) if start_time else None
    end_dt = datetime.fromisoformat(end_time) if end_time else None

    metrics = collector.query_metrics(name, start_dt, end_dt, limit)

    return success(
        data={
            "metrics": [
                {"name": m.name, "value": m.value, "timestamp": m.timestamp.isoformat(), "tags": m.tags}
                for m in metrics
            ],
            "total": len(metrics),
        },
        message="指标查询成功",
    )


@router.get("/metrics/aggregated")
async def get_aggregated_metrics(
    name: str = Query(..., description="指标名称"),
    interval: int = Query(default=60, description="聚合间隔（秒）"),
    start_time: Optional[str] = Query(None, description="开始时间 ISO格式"),
    end_time: Optional[str] = Query(None, description="结束时间 ISO格式"),
) -> JSONResponse:
    """获取聚合指标"""
    collector = _get_metrics_collector()

    start_dt = datetime.fromisoformat(start_time) if start_time else None
    end_dt = datetime.fromisoformat(end_time) if end_time else None

    metrics = collector.get_aggregated_metrics(name, interval, start_dt, end_dt)

    return success(
        data={
            "metrics": [
                {
                    "name": m.name,
                    "interval": m.interval,
                    "avg": round(m.avg, 3),
                    "min": round(m.min, 3),
                    "max": round(m.max, 3),
                    "count": m.count,
                    "timestamp": m.timestamp.isoformat(),
                }
                for m in metrics
            ],
            "total": len(metrics),
        },
        message="聚合指标查询成功",
    )


@router.get("/alerts")
async def get_alerts(
    level: Optional[int] = Query(None, description="告警级别 0-3"), limit: int = Query(default=100, ge=1, le=1000)
) -> JSONResponse:
    """获取告警列表"""
    engine = _get_alert_engine()

    from src.autonomous.monitor.alert_engine import AlertLevel

    level_enum = AlertLevel(level) if level is not None else None

    alerts = engine.get_active_alerts(level_enum)
    alerts = alerts[:limit]

    return success(data={"alerts": [engine.to_dict(a) for a in alerts], "total": len(alerts)}, message="告警查询成功")


@router.get("/alerts/history")
async def get_alert_history(
    level: Optional[int] = Query(None, description="告警级别 0-3"), limit: int = Query(default=100, ge=1, le=1000)
) -> JSONResponse:
    """获取告警历史"""
    engine = _get_alert_engine()

    from src.autonomous.monitor.alert_engine import AlertLevel

    level_enum = AlertLevel(level) if level is not None else None

    alerts = engine.get_alert_history(level=level_enum, limit=limit)

    return success(
        data={"alerts": [engine.to_dict(a) for a in alerts], "total": len(alerts)}, message="告警历史查询成功"
    )


@router.get("/alerts/rules")
async def get_alert_rules() -> JSONResponse:
    """获取告警规则"""
    engine = _get_alert_engine()
    rules = engine.get_rules()

    return success(
        data={
            "rules": [
                {
                    "id": r.id,
                    "name": r.name,
                    "metric": r.metric,
                    "condition": r.condition,
                    "threshold": r.threshold,
                    "level": r.level.name,
                    "description": r.description,
                    "enabled": r.enabled,
                    "cooldown": r.cooldown,
                }
                for r in rules
            ],
            "total": len(rules),
        },
        message="告警规则查询成功",
    )


@router.post("/alerts/rules")
async def create_alert_rule(rule_data: AlertRuleCreate) -> JSONResponse:
    """创建告警规则"""
    from src.autonomous.monitor.alert_engine import AlertLevel, AlertRule

    engine = _get_alert_engine()

    if rule_data.id in engine.rules:
        raise HTTPException(status_code=400, detail=f"规则ID已存在: {rule_data.id}")

    rule = AlertRule(
        id=rule_data.id,
        name=rule_data.name,
        metric=rule_data.metric,
        condition=rule_data.condition,
        threshold=rule_data.threshold,
        level=AlertLevel(rule_data.level),
        description=rule_data.description,
        enabled=rule_data.enabled,
        cooldown=rule_data.cooldown,
    )

    engine.add_rule(rule)

    return success(data={"id": rule.id, "name": rule.name}, message="告警规则创建成功")


# ==================== 通知管理 ====================


@router.get("/notifications/history")
async def get_notification_history(
    channel: Optional[str] = Query(None, description="通知渠道: wecom, email, webhook"),
    status: Optional[str] = Query(None, description="状态: pending, sent, failed"),
    limit: int = Query(default=100, ge=1, le=1000),
) -> JSONResponse:
    """获取通知历史"""
    notifier = _get_notifier()

    from src.autonomous.monitor.notifier import NotificationChannel

    channel_enum = NotificationChannel(channel) if channel else None

    records = notifier.get_history(channel=channel_enum, status=status, limit=limit)

    return success(
        data={"notifications": [notifier.to_dict(r) for r in records], "total": len(records)},
        message="通知历史查询成功",
    )


@router.post("/notifications/test")
async def send_test_notification(
    channel: str = Query(..., description="通知渠道: wecom, email, webhook"),
    message: str = Query(default="这是一条测试通知", description="测试消息"),
) -> JSONResponse:
    """发送测试通知"""
    notifier = _get_notifier()

    from src.autonomous.monitor.notifier import NotificationChannel

    try:
        channel_enum = NotificationChannel(channel)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的通知渠道: {channel}")

    try:
        record = await notifier.send_test_notification(channel_enum, message)
        return success(data=notifier.to_dict(record), message="测试通知发送成功")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 日志分析 ====================


@router.get("/logs/analysis")
async def get_log_analysis(window_seconds: int = Query(default=3600, description="分析窗口（秒）")) -> JSONResponse:
    """获取日志分析报告"""
    analyzer = _get_log_analyzer()

    report = analyzer.generate_report(window_seconds)

    return success(data=report, message="日志分析报告生成成功")


@router.get("/logs/patterns")
async def get_log_patterns(min_count: int = Query(default=1, ge=1, description="最小匹配次数")) -> JSONResponse:
    """获取日志模式"""
    analyzer = _get_log_analyzer()

    patterns = analyzer.get_patterns(min_count)

    return success(data={"patterns": patterns, "total": len(patterns)}, message="日志模式查询成功")


@router.get("/logs/statistics")
async def get_log_statistics(window_seconds: int = Query(default=300, description="统计窗口（秒）")) -> JSONResponse:
    """获取日志统计"""
    analyzer = _get_log_analyzer()

    stats = analyzer.get_statistics(window_seconds)

    return success(
        data={
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
        message="日志统计查询成功",
    )


@router.get("/logs/results")
async def get_analysis_results(
    rule_type: Optional[str] = Query(
        None, description="规则类型: error_rate_spike, latency_spike, pattern_match, volume_anomaly"
    ),
    alert_level: Optional[str] = Query(None, description="告警级别: P0, P1, P2, P3"),
    limit: int = Query(default=100, ge=1, le=1000),
) -> JSONResponse:
    """获取分析结果"""
    analyzer = _get_log_analyzer()

    from src.autonomous.monitor.log_analyzer import AnalysisRuleType

    rule_type_enum = AnalysisRuleType(rule_type) if rule_type else None

    results = analyzer.get_analysis_results(rule_type=rule_type_enum, alert_level=alert_level, limit=limit)

    return success(data={"results": results, "total": len(results)}, message="分析结果查询成功")


@router.get("/logs/rules")
async def get_log_analysis_rules() -> JSONResponse:
    """获取日志分析规则"""
    analyzer = _get_log_analyzer()

    rules = analyzer.get_rules()

    return success(
        data={
            "rules": [
                {
                    "id": r.id,
                    "name": r.name,
                    "type": r.rule_type.value,
                    "description": r.description,
                    "enabled": r.enabled,
                    "alert_level": r.alert_level,
                    "window_size": r.window_size,
                    "error_rate_threshold": r.error_rate_threshold,
                    "latency_threshold": r.latency_threshold,
                    "pattern": r.pattern,
                    "volume_min": r.volume_min,
                    "volume_max": r.volume_max,
                }
                for r in rules
            ],
            "total": len(rules),
        },
        message="分析规则查询成功",
    )


# ==================== 数据同步 ====================


@router.get("/sync/plugins/status")
async def get_plugin_sync_status(
    source: Optional[str] = Query(None, description="插件源: npm, github, pypi")
) -> JSONResponse:
    """获取插件同步状态"""
    syncer = _get_plugin_syncer()
    status = syncer.get_status(source)

    return success(data=status, message="插件同步状态查询成功")


@router.post("/sync/plugins/trigger")
async def trigger_plugin_sync(
    source: Optional[str] = Query(None, description="插件源: npm, github, pypi，为空则同步全部")
) -> JSONResponse:
    """手动触发插件同步"""
    syncer = _get_plugin_syncer()

    if syncer.is_running:
        return error("插件同步正在进行中", status_code=409)

    if source:
        record = await syncer.sync_source(source)
        result = {
            "source": record.source,
            "status": record.status,
            "total_plugins": record.total_plugins,
            "new_plugins": record.new_plugins,
            "updated_plugins": record.updated_plugins,
            "duration_ms": record.duration_ms,
        }
    else:
        results = await syncer.sync_all()
        result = {
            src: {
                "status": r.status,
                "total_plugins": r.total_plugins,
                "new_plugins": r.new_plugins,
                "updated_plugins": r.updated_plugins,
            }
            for src, r in results.items()
        }

    return success(data=result, message="插件同步已触发")


@router.get("/sync/plugins/history")
async def get_plugin_sync_history(
    source: Optional[str] = Query(None, description="插件源: npm, github, pypi"),
    limit: int = Query(default=50, ge=1, le=500),
) -> JSONResponse:
    """获取插件同步历史"""
    syncer = _get_plugin_syncer()
    history = syncer.get_history(source, limit)

    return success(
        data={
            "history": history,
            "total": len(history),
        },
        message="插件同步历史查询成功",
    )


@router.get("/sync/knowledge/status")
async def get_knowledge_sync_status() -> JSONResponse:
    """获取知识库同步状态"""
    syncer = _get_knowledge_syncer()
    status = syncer.get_status()

    return success(data=status, message="知识库同步状态查询成功")


@router.post("/sync/knowledge/trigger")
async def trigger_knowledge_sync() -> JSONResponse:
    """手动触发知识库同步"""
    syncer = _get_knowledge_syncer()

    if syncer.is_running:
        return error("知识库同步正在进行中", status_code=409)

    record = await syncer.sync()

    return success(
        data={
            "status": record.status,
            "phase": record.phase,
            "total_files": record.total_files,
            "added": record.added,
            "modified": record.modified,
            "deleted": record.deleted,
            "vectorized": record.vectorized,
            "indexed": record.indexed,
            "graph_updated": record.graph_updated,
            "duration_ms": record.duration_ms,
        },
        message="知识库同步已触发",
    )


@router.get("/sync/knowledge/history")
async def get_knowledge_sync_history(limit: int = Query(default=50, ge=1, le=500)) -> JSONResponse:
    """获取知识库同步历史"""
    syncer = _get_knowledge_syncer()
    history = syncer.get_history(limit)

    return success(
        data={
            "history": history,
            "total": len(history),
        },
        message="知识库同步历史查询成功",
    )


@router.get("/cache/stats")
async def get_cache_stats() -> JSONResponse:
    """获取缓存统计"""
    manager = _get_cache_manager()
    stats = await manager.get_stats()

    return success(
        data={
            "total_entries": stats.total_entries,
            "total_size_mb": stats.total_size_mb,
            "hit_count": stats.hit_count,
            "miss_count": stats.miss_count,
            "hit_rate": stats.hit_rate,
            "l1_size": stats.l1_size,
            "l2_size": stats.l2_size,
            "penetration_blocked": stats.penetration_blocked,
        },
        message="缓存统计查询成功",
    )


@router.post("/cache/clear")
async def clear_cache(
    rules: Optional[List[str]] = Query(None, description="清理规则: expired, oversize, lru, all")
) -> JSONResponse:
    """清理缓存"""
    manager = _get_cache_manager()

    if rules is None:
        rules = ["expired", "oversize"]

    result = await manager.cleanup(rules=rules)

    return success(
        data={
            "cleaned_entries": result.cleaned_entries,
            "freed_mb": result.freed_mb,
            "rules_applied": result.rules_applied,
        },
        message="缓存清理完成",
    )


@router.post("/cache/warmup")
async def warmup_cache(queries: Optional[List[str]] = Query(None, description="预热查询列表")) -> JSONResponse:
    """缓存预热"""
    manager = _get_cache_manager()
    result = await manager.warmup(queries=queries)

    return success(
        data={
            "warmed_up": result.warmed_up,
            "failed": result.failed,
            "total_time_ms": result.total_time_ms,
        },
        message="缓存预热完成",
    )


@router.get("/cache/consistency")
async def check_cache_consistency() -> JSONResponse:
    """缓存一致性检查"""
    manager = _get_cache_manager()
    result = await manager.check_consistency()

    return success(
        data={
            "total_checked": result.total_checked,
            "consistent": result.consistent,
            "inconsistent": result.inconsistent,
            "repaired": result.repaired,
            "errors": result.errors,
        },
        message="缓存一致性检查完成",
    )
