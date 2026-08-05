"""
伏羲自运转模块 (Autonomous Module)
===================================
Phase 1: 调度器 — 让伏羲拥有自主时间感知与任务编排能力。
Phase 1: 健康监控 — 系统健康检查、指标采集与告警引擎。
Phase 2: 自修复 — 接收告警，自动修复，快照回滚，安全防护。
Phase 3: 数据同步 — 插件源同步、知识库同步、缓存管理。
Phase 3: 报告生成 — 7维数据聚合，日报/周报自动生成。
"""

from .healer import HealerConfig, HealerEngine
from .monitor import AlertEngine, HealthChecker, MetricsCollector, MonitorConfig
from .reporter import ReportGenerator, get_report_generator
from .sync import CacheManager, KnowledgeSyncer, PluginSyncer
