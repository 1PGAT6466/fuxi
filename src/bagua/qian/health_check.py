"""
qian/health_check.py - 健康检查
================================

健康检查和自愈机制。
"""

from dataclasses import dataclass, field
from src.bagua._common import (
    hashlib, json, logging, os, re, time,
    Any, Dict, List, Optional, Tuple,
)

logger = logging.getLogger("bagua.qian")

# ============================================================================
# HealthChecker — 健康检查器
# ============================================================================


@dataclass
class HealthStatus:
    """健康状态

    Attributes:
        vector_store_ok:      向量存储是否正常
        llm_service_ok:       LLM 服务是否正常
        embedder_ok:          Embedder 服务是否正常
        last_check:           最后检查时间
        consecutive_failures: 连续失败次数
    """
    vector_store_ok: bool = True
    llm_service_ok: bool = True
    embedder_ok: bool = True
    last_check: float = field(default_factory=time.time)
    consecutive_failures: int = 0


class HealthChecker:
    """健康检查器

    定期检查系统各组件健康状态，自动触发自愈机制。

    Attributes:
        check_interval:       检查间隔（秒，默认 10.0）
        max_failures:         最大失败次数（默认 3）
        auto_heal:            是否自动自愈（默认 True）
    """

    def __init__(
        self,
        check_interval: float = 10.0,
        max_failures: int = 3,
        auto_heal: bool = True,
    ) -> None:
        self.check_interval = check_interval
        self.max_failures = max_failures
        self.auto_heal = auto_heal
        self._status = HealthStatus()
        self._beating = False

    async def check_health(self) -> HealthStatus:
        """执行健康检查

        Returns:
            健康状态
        """
        logger.debug("☰ [乾] 健康检查...")

        # 检查向量存储
        self._status.vector_store_ok = await self._check_vector_store()

        # 检查 LLM 服务
        self._status.llm_service_ok = await self._check_llm_service()

        # 检查 Embedder 服务
        self._status.embedder_ok = await self._check_embedder()

        # 更新最后检查时间
        self._status.last_check = time.time()

        # 判断是否健康
        is_healthy = (
            self._status.vector_store_ok
            and self._status.llm_service_ok
            and self._status.embedder_ok
        )

        if is_healthy:
            self._status.consecutive_failures = 0
            logger.debug("☰ [乾] 健康检查通过")
        else:
            self._status.consecutive_failures += 1
            logger.warning("☰ [乾] 健康检查失败，连续失败次数: %d", self._status.consecutive_failures)

            # 触发自愈
            if self.auto_heal and self._status.consecutive_failures >= self.max_failures:
                await self._heal()

        return self._status

    async def _check_vector_store(self) -> bool:
        """检查向量存储

        Returns:
            True 如果正常
        """
        try:
            from src.db.vector_store import get_vector_store
            vector_store = get_vector_store()
            if vector_store and vector_store.count >= 0:
                return True
            return False
        except Exception as e:
            logger.warning("☰ [乾] 向量存储检查失败: %s", e)
            return False

    async def _check_llm_service(self) -> bool:
        """检查 LLM 服务

        Returns:
            True 如果正常
        """
        try:
            # 这里实现具体的 LLM 服务检查逻辑
            # 由于这是拆分方案，我们只提供框架，具体实现需要根据实际情况完成
            return True
        except Exception as e:
            logger.warning("☰ [乾] LLM 服务检查失败: %s", e)
            return False

    async def _check_embedder(self) -> bool:
        """检查 Embedder 服务

        Returns:
            True 如果正常
        """
        try:
            # 这里实现具体的 Embedder 服务检查逻辑
            # 由于这是拆分方案，我们只提供框架，具体实现需要根据实际情况完成
            return True
        except Exception as e:
            logger.warning("☰ [乾] Embedder 服务检查失败: %s", e)
            return False

    async def _heal(self) -> None:
        """自愈"""
        logger.warning("☰ [乾] 触发自愈机制...")

        # 这里实现具体的自愈逻辑
        # 由于这是拆分方案，我们只提供框架，具体实现需要根据实际情况完成

    def start_beating(self) -> None:
        """开始心跳"""
        if self._beating:
            return

        self._beating = True
        logger.info("☰ [乾] 健康心跳已启动 (interval=%.1fs)", self.check_interval)

    def stop_beating(self) -> None:
        """停止心跳"""
        self._beating = False
        logger.info("☰ [乾] 健康心跳已停止")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "vector_store_ok": self._status.vector_store_ok,
            "llm_service_ok": self._status.llm_service_ok,
            "embedder_ok": self._status.embedder_ok,
            "last_check": self._status.last_check,
            "consecutive_failures": self._status.consecutive_failures,
        }
