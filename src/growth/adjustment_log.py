"""
adjustment_log.py — 成长引擎·参数调整记录
"""
import json
import time
import logging
from typing import Dict, List
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger("growth.adjustment_log")

from src.config import DATA_DIR as CONFIG_DATA_DIR
ADJUSTMENT_DIR = Path(CONFIG_DATA_DIR) / "growth"


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


class AdjustmentLog:
    """参数调整日志"""

    def __init__(self):
        ADJUSTMENT_DIR.mkdir(parents=True, exist_ok=True)
        self._records: List[AdjustmentRecord] = []
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

    async def record(self, record: AdjustmentRecord):
        """记录调整"""
        self._records.append(record)

        log_file = ADJUSTMENT_DIR / "adjustment_log.jsonl"
        try:
            entry = {
                "param": record.param,
                "old_value": record.old_value,
                "new_value": record.new_value,
                "reason": record.reason,
                "rollback_value": record.rollback_value,
                "rollback_condition": record.rollback_condition,
                "next_adjust_allowed_at": record.next_adjust_allowed_at,
                "timestamp": record.timestamp,
            }
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[AdjustmentLog] 写入失败: {e}")
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

    async def get_pending_adjustments(self, symbol: str = None) -> List[Dict]:
        """获取待处理的调整"""
        log_file = ADJUSTMENT_DIR / "adjustment_log.jsonl"
        if not log_file.exists():
            return []

        records = []
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        records.append(json.loads(line.strip()))
                    except Exception as e:  # TODO: Narrow exception type
                        logger.warning("JSON解析调整记录失败: %s", e, exc_info=True)
        except Exception as e:  # TODO: Narrow exception type
            logger.warning("Exception 失败: %s", e, exc_info=True)

        return records[-20:]
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

    async def rollback(self, record: Dict):
        """回滚调整"""
        logger.warning(f"[AdjustmentLog] 回滚: {record.get('param')}")
