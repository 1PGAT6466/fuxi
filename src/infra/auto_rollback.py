"""
auto_rollback.py — 自动回滚机制
部署后5分钟级检测，异常时自动关闭新Flag
"""
import time
import logging
from typing import Dict, List

logger = logging.getLogger("infra.auto_rollback")


class AutoRollback:
    """自动回滚机制"""

    ROLLBACK_CONDITIONS = {
        "error_rate_threshold": 0.05,
        "p95_latency_threshold": 10.0,
        "offline_symbols_threshold": 2,
    }

    def __init__(self):
        self._check_history: List[Dict] = []
        self._last_check_time = 0

    async def check_and_rollback(self, metrics: Dict) -> Dict:
        """检查指标并决定是否回滚"""
        self._last_check_time = time.time()

        result = {
            "should_rollback": False,
            "reason": "",
            "metrics": metrics,
        }

        # 条件1：错误率 > 5%
        error_rate = metrics.get("error_rate", 0)
        if error_rate > self.ROLLBACK_CONDITIONS["error_rate_threshold"]:
            result["should_rollback"] = True
            result["reason"] = f"error_rate={error_rate:.2%} > 5%"

        # 条件2：P95延迟 > 10s
        p95_latency = metrics.get("p95_latency", 0)
        if p95_latency > self.ROLLBACK_CONDITIONS["p95_latency_threshold"]:
            result["should_rollback"] = True
            result["reason"] = f"p95_latency={p95_latency:.1f}s > 10s"

        # 条件3：2+个象离线
        offline_count = metrics.get("offline_count", 0)
        if offline_count >= self.ROLLBACK_CONDITIONS["offline_symbols_threshold"]:
            result["should_rollback"] = True
            result["reason"] = f"offline_count={offline_count} >= 2"

        self._check_history.append(result)

        if result["should_rollback"]:
            logger.warning(f"[AutoRollback] 触发回滚: {result['reason']}")

        return result

    def get_check_history(self) -> List[Dict]:
        """获取检查历史"""
        return self._check_history.copy()

    def get_last_check_time(self) -> float:
        """获取最后检查时间"""
        return self._last_check_time


# 全局实例
_auto_rollback: Optional[AutoRollback] = None


def get_auto_rollback() -> AutoRollback:
    """获取全局自动回滚实例"""
    global _auto_rollback
    if _auto_rollback is None:
        _auto_rollback = AutoRollback()
    return _auto_rollback
