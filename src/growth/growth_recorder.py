"""
growth_recorder.py — 成长引擎 Phase 1 记录器
只记录不调整，建立基线数据
"""
import os
import json
import time
import logging
from typing import Dict, List

logger = logging.getLogger("growth.recorder")

GROWTH_DIR = "data/growth"


class GrowthRecorder:
    """成长引擎 Phase 1 记录器"""

    def __init__(self):
        os.makedirs(GROWTH_DIR, exist_ok=True)
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

    async def record(self, symbol: str, metric: str, value: float,
                     context: Dict = None):
        """记录成长事件"""
        record = {
            "timestamp": time.time(),
            "symbol": symbol,
            "metric": metric,
            "value": value,
            "context": context or {},
        }

        log_file = os.path.join(GROWTH_DIR, f"{symbol}_quality.jsonl")
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[Growth] 写入失败: {e}")
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

    async def query(self, symbol: str, metric: str = None,
                    since: str = None) -> List[Dict]:
        """查询成长记录"""
        log_file = os.path.join(GROWTH_DIR, f"{symbol}_quality.jsonl")

        if not os.path.exists(log_file):
            return []

        records = []
        since_seconds = self._parse_since(since) if since else 0

        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line.strip())

                    if metric and record.get("metric") != metric:
                        continue

                    if since_seconds and record.get("timestamp", 0) < time.time() - since_seconds:
                        continue

                    records.append(record)
                except Exception as e:  # TODO: Narrow exception type
                    logger.warning("JSON解析成长记录失败: %s", e, exc_info=True)
                    continue

        return records

    def _parse_since(self, since: str) -> int:
        """解析时间范围"""
        if since.endswith("d"):
            return int(since[:-1]) * 86400
        elif since.endswith("h"):
            return int(since[:-1]) * 3600
        elif since.endswith("m"):
            return int(since[:-1]) * 60
        return 0


class GrowthRecordPoints:
    """成长记录点"""

    def __init__(self):
        self.recorder = GrowthRecorder()

    async def record_shaoyang_extraction(self, file_hash: str, file_name: str,
                                          chunk_count: int, event_count: int,
                                          entity_count: int, duration_ms: float):
        """记录少阳提取"""
        success_rate = 1.0 if event_count > 0 else 0.0
        await self.recorder.record(
            symbol="shaoyang",
            metric="extraction_success_rate",
            value=success_rate,
            context={
                "file_hash": file_hash,
                "file_name": file_name,
                "chunk_count": chunk_count,
                "event_count": event_count,
                "entity_count": entity_count,
                "duration_ms": duration_ms,
            }
        )

        entity_coverage = entity_count / max(chunk_count, 1)
        await self.recorder.record(
            symbol="shaoyang",
            metric="entity_coverage",
            value=entity_coverage,
            context={"file_hash": file_hash}
        )

    async def record_taiyang_search(self, query: str, trace_id: str,
                                     search_mode: str, result_count: int,
                                     max_score: float, duration_ms: float):
        """记录太阳检索"""
        await self.recorder.record(
            symbol="taiyang",
            metric="result_count",
            value=result_count,
            context={
                "query": query[:100],
                "trace_id": trace_id,
                "search_mode": search_mode,
                "max_score": max_score,
                "duration_ms": duration_ms,
            }
        )

        await self.recorder.record(
            symbol="taiyang",
            metric="search_latency_ms",
            value=duration_ms,
            context={"query": query[:100], "search_mode": search_mode}
        )

    async def record_shaoyin_decision(self, query: str, trace_id: str,
                                       intent: str, strategy: str,
                                       confidence: float, retry_count: int,
                                       duration_ms: float):
        """记录少阴决策"""
        await self.recorder.record(
            symbol="shaoyin",
            metric="confidence_avg",
            value=confidence,
            context={
                "query": query[:100],
                "trace_id": trace_id,
                "intent": intent,
                "strategy": strategy,
                "retry_count": retry_count,
                "duration_ms": duration_ms,
            }
        )

        await self.recorder.record(
            symbol="shaoyin",
            metric="retry_rate",
            value=1.0 if retry_count > 0 else 0.0,
            context={"query": query[:100], "retry_count": retry_count}
        )

    async def record_taiyin_request(self, trace_id: str, endpoint: str,
                                     method: str, status_code: int,
                                     duration_ms: float):
        """记录太阴请求"""
        await self.recorder.record(
            symbol="taiyin",
            metric="request_count",
            value=1,
            context={
                "trace_id": trace_id,
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "duration_ms": duration_ms,
            }
        )

        is_error = 1.0 if status_code >= 500 else 0.0
        await self.recorder.record(
            symbol="taiyin",
            metric="error_rate",
            value=is_error,
            context={"endpoint": endpoint, "status_code": status_code}
        )
