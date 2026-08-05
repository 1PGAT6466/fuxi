"""
指标采集器模块
采集系统指标和业务指标，存储到SQLite，支持聚合查询
"""

import asyncio
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import psutil

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """指标数据点"""

    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class AggregatedMetric:
    """聚合指标"""

    name: str
    interval: int  # 秒
    avg: float
    min: float
    max: float
    count: int
    timestamp: datetime


class MetricsCollector:
    """指标采集器 - 采集系统和业务指标"""

    def __init__(self, config=None):
        from .config import MonitorConfig

        self.config = config or MonitorConfig()
        self._init_db()
        self._metrics_buffer: List[MetricPoint] = []
        self._buffer_size = 100

    def _init_db(self):
        """初始化SQLite数据库"""
        self.conn = sqlite3.connect(self.config.metrics_db_path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                value REAL NOT NULL,
                timestamp REAL NOT NULL,
                tags TEXT
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_name_time 
            ON metrics(name, timestamp)
        """)
        self.conn.commit()

    async def collect_all(self) -> Dict[str, float]:
        """采集所有指标"""
        metrics = {}

        # 系统指标
        system_metrics = await self._collect_system_metrics()
        metrics.update(system_metrics)

        # 业务指标
        business_metrics = await self._collect_business_metrics()
        metrics.update(business_metrics)

        # 批量写入
        await self._batch_write(metrics)

        logger.info(f"采集 {len(metrics)} 个指标")
        return metrics

    async def _collect_system_metrics(self) -> Dict[str, float]:
        """采集系统指标"""
        metrics = {}

        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        metrics["system.cpu.percent"] = cpu_percent

        # 内存
        mem = psutil.virtual_memory()
        metrics["system.memory.percent"] = mem.percent
        metrics["system.memory.used_gb"] = mem.used / (1024**3)
        metrics["system.memory.available_gb"] = mem.available / (1024**3)

        # 磁盘
        disk = psutil.disk_usage("/")
        metrics["system.disk.percent"] = disk.percent
        metrics["system.disk.used_gb"] = disk.used / (1024**3)
        metrics["system.disk.free_gb"] = disk.free / (1024**3)

        # 网络
        net = psutil.net_io_counters()
        metrics["system.network.bytes_sent"] = net.bytes_sent
        metrics["system.network.bytes_recv"] = net.bytes_recv

        # 进程
        process = psutil.Process()
        metrics["system.process.cpu_percent"] = process.cpu_percent()
        metrics["system.process.memory_mb"] = process.memory_info().rss / (1024**2)

        return metrics

    async def _collect_business_metrics(self) -> Dict[str, float]:
        """采集业务指标 - 从Prometheus或其他监控系统获取"""
        # 这里预留接口，实际从Prometheus/业务系统获取
        # 示例：从API获取业务指标
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.config.api_base_url}/metrics", timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            "business.qps": data.get("qps", 0),
                            "business.latency_avg": data.get("latency_avg", 0),
                            "business.error_rate": data.get("error_rate", 0),
                            "business.active_connections": data.get("active_connections", 0),
                        }
        except Exception as e:
            logger.warning(f"业务指标采集失败: {e}")

        return {}

    async def _batch_write(self, metrics: Dict[str, float]):
        """批量写入指标"""
        now = time.time()
        tags_str = "{}"

        self.conn.executemany(
            "INSERT INTO metrics (name, value, timestamp, tags) VALUES (?, ?, ?, ?)",
            [(name, value, now, tags_str) for name, value in metrics.items()],
        )
        self.conn.commit()

    def query_metrics(
        self, name: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None, limit: int = 1000
    ) -> List[MetricPoint]:
        """查询指标数据"""
        if start_time is None:
            start_time = datetime.now() - timedelta(hours=1)
        if end_time is None:
            end_time = datetime.now()

        cursor = self.conn.execute(
            """
            SELECT name, value, timestamp, tags FROM metrics
            WHERE name = ? AND timestamp BETWEEN ? AND ?
            ORDER BY timestamp DESC LIMIT ?
            """,
            (name, start_time.timestamp(), end_time.timestamp(), limit),
        )

        return [
            MetricPoint(
                name=row[0], value=row[1], timestamp=datetime.fromtimestamp(row[2]), tags=eval(row[3]) if row[3] else {}
            )
            for row in cursor.fetchall()
        ]

    def get_aggregated_metrics(
        self, name: str, interval: int = 60, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> List[AggregatedMetric]:
        """获取聚合指标"""
        if start_time is None:
            start_time = datetime.now() - timedelta(hours=1)
        if end_time is None:
            end_time = datetime.now()

        cursor = self.conn.execute(
            """
            SELECT 
                name,
                AVG(value) as avg_val,
                MIN(value) as min_val,
                MAX(value) as max_val,
                COUNT(*) as cnt,
                CAST(timestamp / ? as INTEGER) * ? as bucket
            FROM metrics
            WHERE name = ? AND timestamp BETWEEN ? AND ?
            GROUP BY bucket
            ORDER BY bucket DESC
            """,
            (interval, interval, name, start_time.timestamp(), end_time.timestamp()),
        )

        return [
            AggregatedMetric(
                name=row[0],
                interval=interval,
                avg=row[1],
                min=row[2],
                max=row[3],
                count=row[4],
                timestamp=datetime.fromtimestamp(row[5]),
            )
            for row in cursor.fetchall()
        ]

    def cleanup_old_metrics(self, days: Optional[int] = None):
        """清理旧指标数据"""
        days = days or self.config.metrics_retention_days
        cutoff = time.time() - (days * 86400)
        self.conn.execute("DELETE FROM metrics WHERE timestamp < ?", (cutoff,))
        self.conn.commit()
        logger.info(f"清理 {days} 天前的指标数据")

    def close(self):
        """关闭数据库连接"""
        self.conn.close()
