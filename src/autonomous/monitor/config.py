"""
监控配置模块
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class MonitorConfig:
    """监控配置"""

    # 健康检查配置
    health_check_interval: int = 30  # 秒
    health_check_timeout: int = 3  # 单项检查超时（秒），修复：原来10秒导致3项×10=30秒超时

    # 指标采集配置
    metrics_collect_interval: int = 60  # 秒
    metrics_db_path: str = "data/metrics.db"  # SQLite路径

    # 告警配置
    alert_check_interval: int = 30  # 秒
    alert_cooldown: int = 300  # 告警冷却期（秒）

    # 服务端点
    api_base_url: str = os.getenv("API_BASE_URL", "http://127.0.0.1:8080")
    chromadb_url: str = os.getenv("CHROMADB_URL", "http://127.0.0.1:8080")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # 阈值配置
    cpu_threshold_warning: float = 80.0
    cpu_threshold_critical: float = 95.0
    memory_threshold_warning: float = 85.0
    memory_threshold_critical: float = 95.0
    disk_threshold_warning: float = 90.0
    disk_threshold_critical: float = 95.0
    api_latency_threshold: float = 5.0  # 秒
    api_error_rate_threshold: float = 5.0  # 百分比

    # 存储配置
    health_history_max: int = 1000  # 最大历史记录数
    metrics_retention_days: int = 7  # 指标保留天数

    # 聚合配置
    aggregation_intervals: List[int] = field(default_factory=lambda: [60, 300, 3600])  # 1分钟/5分钟/1小时
