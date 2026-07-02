"""
error_tracker.py — 错误追踪
错误分类 + 频率统计
"""
import time
import logging
from typing import Dict, List
from collections import deque

logger = logging.getLogger("infra.error_tracker")


class ErrorTracker:
    """错误追踪器"""

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self._errors = deque(maxlen=max_history)
        self._error_counts = {}

    def record_error(self, error_type: str, message: str, context: Dict = None):
        """记录错误"""
        error = {
            "type": error_type,
            "message": message,
            "context": context or {},
            "timestamp": time.time(),
        }
        self._errors.append(error)

        if error_type not in self._error_counts:
            self._error_counts[error_type] = 0
        self._error_counts[error_type] += 1

        logger.error(f"[ErrorTracker] {error_type}: {message}")

    def get_recent_errors(self, limit: int = 10) -> List[Dict]:
        """获取最近的错误"""
        return list(self._errors)[-limit:]

    def get_error_stats(self) -> Dict:
        """获取错误统计"""
        return {
            "total_errors": len(self._errors),
            "error_types": self._error_counts.copy(),
            "recent_errors": self.get_recent_errors(5),
        }


# 全局错误追踪器
_error_tracker: ErrorTracker = None


def get_error_tracker() -> ErrorTracker:
    """获取全局错误追踪器"""
    global _error_tracker
    if _error_tracker is None:
        _error_tracker = ErrorTracker()
    return _error_tracker
