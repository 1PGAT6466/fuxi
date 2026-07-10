"""
engine.py — 成长引擎
运行在四象之上的元层，监控四象的"进步"
三阶段：Phase 1只记录不调整 → Phase 2参数自动调整 → Phase 3策略和知识成长
"""
import json
import logging
import time
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass, field

logger = logging.getLogger("growth.engine")

from src.config import DATA_DIR as CONFIG_DATA_DIR
import asyncio
GROWTH_DIR = Path(CONFIG_DATA_DIR) / "growth"


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
    rollback_condition: str = ""
    next_adjust_allowed_at: float = 0
    timestamp: float = field(default_factory=time.time)


class GrowthEngine:
    """四象自成长引擎"""

    def __init__(self):
        GROWTH_DIR.mkdir(parents=True, exist_ok=True)
        self._events: Dict[str, list] = {}
        self._baselines: Dict[str, float] = {}
        self._adjustments: List[AdjustmentRecord] = []
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

    async def record_event(self, symbol: str, metric: str, value: float, context: Dict = None):
        """记录成长事件"""
        context = context or {}

        # 写入日志文件
        log_file = GROWTH_DIR / f"{symbol}_quality.jsonl"
        record = {
            "symbol": symbol,
            "metric": metric,
            "value": value,
            "context": context,
            "timestamp": time.time(),
        }

        try:
            def _write_log():
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            await asyncio.to_thread(_write_log)
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[Growth] 写入失败: {e}")

        # 内存缓存
        if symbol not in self._events:
            self._events[symbol] = []
        self._events[symbol].append(record)

        logger.debug(f"[Growth] {symbol}.{metric} = {value}")

    async def record_search(self, query: str, results_count: int, duration_ms: float,
                           confidence: float = 0, trace_id: str = ""):
        """记录搜索事件"""
        await self.record_event("taiyang", "search_result_count", results_count, {
            "query": query[:100],
            "duration_ms": duration_ms,
            "confidence": confidence,
            "trace_id": trace_id,
        })

    async def record_decision(self, query: str, confidence: float, duration_ms: float,
                            strategy: str = "", trace_id: str = ""):
        """记录决策事件"""
        await self.record_event("shaoyin", "decision_confidence", confidence, {
            "query": query[:100],
            "duration_ms": duration_ms,
            "strategy": strategy,
            "trace_id": trace_id,
        })

    async def record_extraction(self, file_name: str, chunks: int, events: int,
                              entities: int, duration_ms: float):
        """记录提取事件"""
        await self.record_event("shaoyang", "extraction_chunks", chunks, {
            "file_name": file_name,
            "events": events,
            "entities": entities,
            "duration_ms": duration_ms,
        })

    async def record_request(self, endpoint: str, status_code: int, duration_ms: float):
        """记录请求事件"""
        await self.record_event("taiyin", "request_duration", duration_ms, {
            "endpoint": endpoint,
            "status_code": status_code,
        })
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

    async def evaluate(self, symbol: str) -> Dict:
        """评估成长状态"""
        log_file = GROWTH_DIR / f"{symbol}_quality.jsonl"
        if not log_file.exists():
            return {"symbol": symbol, "metrics": {}, "has_improvement": False}

        events = []
        try:
            def _read_log():
                result = []
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            result.append(json.loads(line.strip()))
                        except Exception as e:
                            logger.warning("JSON解析成长事件失败: %s", e, exc_info=True)
                return result
            events = await asyncio.to_thread(_read_log)
        except Exception as e:  # TODO: Narrow exception type
            logger.warning("Exception 失败: %s", e, exc_info=True)

        # 计算各指标的统计
        metrics = {}
        for event in events:
            metric = event.get("metric", "")
            value = event.get("value", 0)
            if metric not in metrics:
                metrics[metric] = {"values": [], "count": 0}
            metrics[metric]["values"].append(value)
            metrics[metric]["count"] += 1

        avg_metrics = {}
        for metric, data in metrics.items():
            values = data["values"]
            avg_metrics[metric] = {
                "avg": sum(values) / len(values) if values else 0,
                "min": min(values) if values else 0,
                "max": max(values) if values else 0,
                "count": data["count"],
            }

        return {
            "symbol": symbol,
            "metrics": avg_metrics,
            "event_count": len(events),
            "has_improvement": False,  # Phase 2实现基线对比
        }

    async def evaluate_all(self) -> Dict:
        """评估所有象的成长状态"""
        results = {}
        for symbol in ["shaoyang", "taiyang", "shaoyin", "taiyin"]:
            results[symbol] = await self.evaluate(symbol)
        return results

    def get_stats(self) -> Dict:
        """获取成长统计"""
        stats = {}
        for log_file in GROWTH_DIR.glob("*_quality.jsonl"):
            symbol = log_file.stem.replace("_quality", "")
            try:
                def _rd():
                    with open(log_file, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                stats[symbol] = {"events": len(lines)}
            except Exception as e:  # TODO: Narrow exception type
                logger.warning("读取成长统计失败 [%s]: %s", symbol, e, exc_info=True)
                stats[symbol] = {"events": 0}
        return stats

    def get_overview(self) -> Dict:
        """获取成长概览"""
        stats = self.get_stats()
        return {
            "symbols": stats,
            "total_events": sum(s.get("events", 0) for s in stats.values()),
            "phase": "Phase 1 (只记录，不调整)",
        }
