"""
qian/degradation.py - 三层降级
==============================

三层降级：L1 重试（Mimo→DeepSeek→OpenAI 4o-mini）→ L2 ShaoyinBrain → L3 兜底直答。
"""

from dataclasses import dataclass, field
from src.bagua._common import (
    hashlib, json, logging, os, re, time,
    Any, Dict, List, Optional, Tuple,
)

logger = logging.getLogger("bagua.qian")

# ============================================================================
# DegradationCounter — 三层降级监控计数器
# ============================================================================


@dataclass
class DegradationCounter:
    """三层降级链监控计数器

    记录 L1/L2/L3 每层的触发次数和时间，支持小时级重置
    和 L2 触发频次超阈值告警。

    Attributes:
        l1_count:        L1 dispatch 失败次数
        l2_count:        L2 ShaoyinBrain 触发次数
        l3_count:        L3 兜底直答触发次数
        total_requests:  时间段内总请求数
        l1_timestamps:   L1 触发的时间戳列表
        l2_timestamps:   L2 触发的时间戳列表
        l3_timestamps:   L3 触发的时间戳列表
        hour_start:      当前统计周期开始时间
        last_reset:      上次重置时间
        last_alert_sent: 上次发送告警时间
    """
    l1_count: int = 0
    l2_count: int = 0
    l3_count: int = 0
    total_requests: int = 0
    l1_timestamps: List[float] = field(default_factory=list)
    l2_timestamps: List[float] = field(default_factory=list)
    l3_timestamps: List[float] = field(default_factory=list)
    hour_start: float = field(default_factory=time.time)
    last_reset: float = field(default_factory=time.time)
    last_alert_sent: float = 0.0

    def record_l1_failure(self) -> None:
        """记录一次 L1 dispatch 失败"""
        self.l1_count += 1
        self.l1_timestamps.append(time.time())
        self._trim_old_timestamps(self.l1_timestamps)

    def record_l2_trigger(self) -> None:
        """记录一次 L2 降级触发"""
        self.l2_count += 1
        self.l2_timestamps.append(time.time())
        self._trim_old_timestamps(self.l2_timestamps)

    def record_l3_trigger(self) -> None:
        """记录一次 L3 兜底触发"""
        self.l3_count += 1
        self.l3_timestamps.append(time.time())
        self._trim_old_timestamps(self.l3_timestamps)

    def record_request(self) -> None:
        """记录一次总请求"""
        self.total_requests += 1

    def get_l2_rate_percent(self) -> float:
        """计算当前小时 L2 触发占比（%）

        Returns:
            L2 触发次数占 L1 失败次数的百分比，若无 L1 失败则返回 0
        """
        if self.l1_count == 0:
            return 0.0
        return round((self.l2_count / self.l1_count) * 100, 2)

    def should_alert_l2(self, threshold_percent: float = 5.0) -> bool:
        """判断是否应发送 L2 超频告警

        当 L2 触发频次超过 threshold_percent%/hour 且距上次告警 > 10 分钟时
        触发告警。

        Args:
            threshold_percent: 触发阈值百分比（默认 5%）

        Returns:
            True 如果应发送告警
        """
        rate = self.get_l2_rate_percent()
        if rate < threshold_percent:
            return False
        now = time.time()
        # 避免频繁告警：至少间隔 10 分钟
        if now - self.last_alert_sent < 600:
            return False
        self.last_alert_sent = now
        return True

    def try_hourly_reset(self) -> bool:
        """尝试每小时重置计数器

        检查是否距离 hour_start 已过 1 小时，若是则重置并返回 True。
        重置前将旧数据写入磁盘备份。

        Returns:
            True 如果执行了重置
        """
        now = time.time()
        if now - self.hour_start >= 3600:
            # 备份旧数据
            self._backup_to_disk()
            # 重置
            self.l1_count = 0
            self.l2_count = 0
            self.l3_count = 0
            self.total_requests = 0
            self.l1_timestamps.clear()
            self.l2_timestamps.clear()
            self.l3_timestamps.clear()
            self.hour_start = now
            self.last_reset = now
            logger.info("☰ [乾] 降级计数器小时级重置")
            return True
        return False

    def _trim_old_timestamps(self, ts_list: List[float], window: float = 3600.0) -> None:
        """清理超过 window 秒的旧时间戳"""
        cutoff = time.time() - window
        while ts_list and ts_list[0] < cutoff:
            ts_list.pop(0)

    def _backup_to_disk(self) -> None:
        """将当前计数器快照写入磁盘备份"""
        try:
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            snapshot = {
                "hour_start": self.hour_start,
                "last_reset": self.last_reset,
                "l1_count": self.l1_count,
                "l2_count": self.l2_count,
                "l3_count": self.l3_count,
                "total_requests": self.total_requests,
                "l2_rate_percent": self.get_l2_rate_percent(),
                "written_at": time.time(),
            }
            with open(_DEGRADATION_COUNTER_PATH, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
        except (OSError, json.JSONDecodeError) as exc:
            logger.debug("☰ [乾] 降级计数器备份失败: %s", exc)

    def get_summary(self) -> Dict[str, Any]:
        """获取当前计数器摘要"""
        return {
            "l1_count": self.l1_count,
            "l2_count": self.l2_count,
            "l3_count": self.l3_count,
            "total_requests": self.total_requests,
            "l2_rate_percent": self.get_l2_rate_percent(),
            "hour_elapsed_sec": round(time.time() - self.hour_start, 1),
        }


# ============================================================================
# DegradationManager — 三层降级管理器
# ============================================================================


class DegradationManager:
    """三层降级管理器

    管理 L1/L2/L3 三层降级，确保系统在 LLM 不可用时仍能正常工作。

    Attributes:
        counter:              降级计数器
        max_l1_retries:       L1 最大重试次数（默认 2）
        l2_threshold_percent: L2 触发阈值百分比（默认 5%）
    """

    def __init__(
        self,
        max_l1_retries: int = 2,
        l2_threshold_percent: float = 5.0,
    ) -> None:
        self.counter = DegradationCounter()
        self.max_l1_retries = max_l1_retries
        self.l2_threshold_percent = l2_threshold_percent

    def record_l1_failure(self) -> None:
        """记录一次 L1 dispatch 失败"""
        self.counter.record_l1_failure()
        logger.warning("☰ [乾] L1 dispatch 失败，当前 L1 失败次数: %d", self.counter.l1_count)

    def record_l2_trigger(self) -> None:
        """记录一次 L2 降级触发"""
        self.counter.record_l2_trigger()
        logger.warning("☰ [乾] L2 ShaoyinBrain 触发，当前 L2 触发次数: %d", self.counter.l2_count)

    def record_l3_trigger(self) -> None:
        """记录一次 L3 兜底触发"""
        self.counter.record_l3_trigger()
        logger.warning("☰ [乾] L3 兜底直答触发，当前 L3 触发次数: %d", self.counter.l3_count)

    def record_request(self) -> None:
        """记录一次总请求"""
        self.counter.record_request()

    def should_alert_l2(self) -> bool:
        """判断是否应发送 L2 超频告警"""
        return self.counter.should_alert_l2(self.l2_threshold_percent)

    def get_summary(self) -> Dict[str, Any]:
        """获取当前计数器摘要"""
        return self.counter.get_summary()

    def try_hourly_reset(self) -> bool:
        """尝试每小时重置计数器"""
        return self.counter.try_hourly_reset()
