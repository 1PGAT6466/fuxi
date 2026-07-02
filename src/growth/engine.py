"""
engine.py — 成长引擎
运行在四象之上的元层，监控四象的"进步"
"""
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("growth.engine")

GROWTH_DIR = Path("data/growth")


@dataclass
class GrowthEvent:
    """成长事件"""
    symbol: str
    metric: str
    value: float
    context: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class AdjustmentRecord:
    """调整记录"""
    param: str
    old_value: float
    new_value: float
    reason: str
    rollback_value: float
    next_adjust_allowed_at: float = 0


class GrowthEngine:
    """四象自成长引擎"""

    def __init__(self):
        GROWTH_DIR.mkdir(parents=True, exist_ok=True)
        self._events: Dict[str, list] = {}
        self._baselines: Dict[str, float] = {}
        self._adjustments: list = []

    async def record_event(self, symbol: str, metric: str, value: float, context: Dict = None):
        """记录成长事件"""
        event = GrowthEvent(
            symbol=symbol,
            metric=metric,
            value=value,
            context=context or {},
        )

        # 写入日志文件
        log_file = GROWTH_DIR / f"{symbol}_quality.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "symbol": symbol,
                "metric": metric,
                "value": value,
                "context": context or {},
                "timestamp": time.time(),
            }, ensure_ascii=False) + "\n")

        logger.info(f"[Growth] {symbol}.{metric} = {value}")

    async def evaluate(self, symbol: str) -> Dict:
        """评估成长状态"""
        log_file = GROWTH_DIR / f"{symbol}_quality.jsonl"
        if not log_file.exists():
            return {"symbol": symbol, "metrics": {}, "has_improvement": False}

        events = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    events.append(json.loads(line.strip()))
                except:
                    pass

        # 计算各指标的平均值
        metrics = {}
        for event in events:
            metric = event.get("metric", "")
            value = event.get("value", 0)
            if metric not in metrics:
                metrics[metric] = []
            metrics[metric].append(value)

        avg_metrics = {}
        for metric, values in metrics.items():
            avg_metrics[metric] = sum(values) / len(values) if values else 0

        return {
            "symbol": symbol,
            "metrics": avg_metrics,
            "event_count": len(events),
            "has_improvement": False,  # 需要基线对比
        }

    def get_stats(self) -> Dict:
        """获取成长统计"""
        stats = {}
        for log_file in GROWTH_DIR.glob("*_quality.jsonl"):
            symbol = log_file.stem.replace("_quality", "")
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                stats[symbol] = {"events": len(lines)}
            except:
                stats[symbol] = {"events": 0}
        return stats
