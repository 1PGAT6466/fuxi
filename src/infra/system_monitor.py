"""
system_monitor.py — 系统监控
CPU + 内存 + 磁盘
"""
import time
import logging
from typing import Dict

logger = logging.getLogger("infra.system_monitor")


class SystemMonitor:
    """系统监控器"""

    def __init__(self):
        self._start_time = time.time()

    def get_system_stats(self) -> Dict:
        """获取系统统计"""
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            return {
                "cpu_percent": cpu_percent,
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "memory_used_gb": round(memory.used / (1024**3), 2),
                "memory_percent": memory.percent,
                "disk_total_gb": round(disk.total / (1024**3), 2),
                "disk_used_gb": round(disk.used / (1024**3), 2),
                "disk_percent": disk.percent,
                "uptime_seconds": time.time() - self._start_time,
            }
        except ImportError:
            return {
                "cpu_percent": 0,
                "memory_total_gb": 0,
                "memory_used_gb": 0,
                "memory_percent": 0,
                "disk_total_gb": 0,
                "disk_used_gb": 0,
                "disk_percent": 0,
                "uptime_seconds": time.time() - self._start_time,
            }


# 全局系统监控器
_system_monitor: SystemMonitor = None


def get_system_monitor() -> SystemMonitor:
    """获取全局系统监控器"""
    global _system_monitor
    if _system_monitor is None:
        _system_monitor = SystemMonitor()
    return _system_monitor
