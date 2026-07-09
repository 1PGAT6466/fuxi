"""
meridian_monitor.py — 经络监控器
实时监控信号流、健康状态、性能指标
"""
import time
import logging
from typing import Dict, Optional
from collections import deque

logger = logging.getLogger("infra.meridian_monitor")


class MeridianMonitor:
    """经络监控器 — 实时监控信号流"""

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.metrics = {
            "signals_sent": 0,
            "signals_received": 0,
            "signals_timeout": 0,
            "signals_error": 0,
            "avg_latency_ms": 0,
            "queue_size": 0,
            "active_signals": 0,
        }
        self._latencies = deque(maxlen=max_history)
        self._signal_history = deque(maxlen=max_history)
        self._start_time = time.time()

    def record_signal(self, signal_id: str, source: str, target: str,
                      signal_type: str, latency_ms: float, success: bool):
        """记录信号指标"""
        self.metrics["signals_sent"] += 1

        if success:
            self.metrics["signals_received"] += 1
        else:
            self.metrics["signals_error"] += 1

        self._latencies.append(latency_ms)
        self._update_avg_latency()

        # 记录信号历史
        self._signal_history.append({
            "signal_id": signal_id,
            "source": source,
            "target": target,
            "type": signal_type,
            "latency_ms": latency_ms,
            "success": success,
            "timestamp": time.time(),
        })

    def record_timeout(self, signal_id: str, source: str, target: str):
        """记录信号超时"""
        self.metrics["signals_timeout"] += 1
        self.metrics["signals_error"] += 1

        self._signal_history.append({
            "signal_id": signal_id,
            "source": source,
            "target": target,
            "type": "timeout",
            "latency_ms": 0,
            "success": False,
            "timestamp": time.time(),
        })

    def _update_avg_latency(self):
        """更新平均延迟"""
        if self._latencies:
            self.metrics["avg_latency_ms"] = sum(self._latencies) / len(self._latencies)

    def get_health_report(self) -> Dict:
        """获取健康报告"""
        uptime = time.time() - self._start_time
        error_rate = self.metrics["signals_error"] / max(self.metrics["signals_sent"], 1)
        success_rate = self.metrics["signals_received"] / max(self.metrics["signals_sent"], 1)

        # 判断健康状态
        if error_rate > 0.1:
            status = "degraded"
        elif error_rate > 0.05:
            status = "warning"
        else:
            status = "healthy"

        return {
            "status": status,
            "uptime_seconds": uptime,
            "metrics": self.metrics.copy(),
            "error_rate": error_rate,
            "success_rate": success_rate,
            "recent_signals": list(self._signal_history)[-10:],
        }

    def get_symbol_stats(self) -> Dict[str, Dict]:
        """获取各象的信号统计"""
        stats = {}
        for record in self._signal_history:
            source = record["source"]
            target = record["target"]

            if source not in stats:
                stats[source] = {"sent": 0, "received": 0, "errors": 0}
            if target not in stats:
                stats[target] = {"sent": 0, "received": 0, "errors": 0}

            stats[source]["sent"] += 1
            if record["success"]:
                stats[target]["received"] += 1
            else:
                stats[target]["errors"] += 1

        return stats

    def get_latency_percentiles(self) -> Dict[str, float]:
        """获取延迟百分位数"""
        if not self._latencies:
            return {"p50": 0, "p90": 0, "p95": 0, "p99": 0}

        sorted_latencies = sorted(self._latencies)
        n = len(sorted_latencies)

        return {
            "p50": sorted_latencies[int(n * 0.5)],
            "p90": sorted_latencies[int(n * 0.9)],
            "p95": sorted_latencies[int(n * 0.95)],
            "p99": sorted_latencies[min(int(n * 0.99), n - 1)],
        }

    def reset(self):
        """重置监控数据"""
        self.metrics = {
            "signals_sent": 0,
            "signals_received": 0,
            "signals_timeout": 0,
            "signals_error": 0,
            "avg_latency_ms": 0,
            "queue_size": 0,
            "active_signals": 0,
        }
        self._latencies.clear()
        self._signal_history.clear()
        self._start_time = time.time()


# 全局监控器实例
_monitor: Optional[MeridianMonitor] = None


def get_monitor() -> MeridianMonitor:
    """获取全局监控器"""
    global _monitor
    if _monitor is None:
        _monitor = MeridianMonitor()
    return _monitor
