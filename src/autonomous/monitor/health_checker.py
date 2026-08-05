"""
健康检查器模块
并行检查所有服务健康状态，返回整体健康状态
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import aiohttp
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """健康状态枚举"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ServiceHealth:
    """单个服务的健康状态"""

    name: str
    status: HealthStatus
    response_time: float = 0.0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.now)


@dataclass
class SystemHealth:
    """系统整体健康状态"""

    status: HealthStatus
    services: List[ServiceHealth]
    checked_at: datetime
    duration: float = 0.0


class HealthChecker:
    """健康检查器 - 并行检查所有服务状态"""

    def __init__(self, config=None):
        from .config import MonitorConfig

        self.config = config or MonitorConfig()
        self.health_history: List[SystemHealth] = []
        self._checks: Dict[str, callable] = {
            "api_service": self._check_api_service,
            "chromadb": self._check_chromadb,
            "redis": self._check_redis,
            "disk_space": self._check_disk_space,
            "memory_usage": self._check_memory_usage,
        }

    async def check_all(self) -> SystemHealth:
        """并行执行所有健康检查"""
        start_time = time.time()

        # 创建并行任务
        tasks = {name: asyncio.create_task(self._run_check(name, check_fn)) for name, check_fn in self._checks.items()}

        # 等待所有任务完成
        results: List[ServiceHealth] = []
        for name, task in tasks.items():
            try:
                result = await asyncio.wait_for(task, timeout=self.config.health_check_timeout)
                results.append(result)
            except asyncio.TimeoutError:
                results.append(
                    ServiceHealth(
                        name=name,
                        status=HealthStatus.UNHEALTHY,
                        message=f"检查超时 ({self.config.health_check_timeout}s)",
                    )
                )
            except Exception as e:
                results.append(ServiceHealth(name=name, status=HealthStatus.UNHEALTHY, message=f"检查失败: {str(e)}"))

        # 计算整体状态
        overall_status = self._calculate_overall_status(results)
        duration = time.time() - start_time

        health = SystemHealth(status=overall_status, services=results, checked_at=datetime.now(), duration=duration)

        # 存储历史记录
        self._store_history(health)

        logger.info(f"健康检查完成: {overall_status.value} ({duration:.2f}s)")
        return health

    async def _run_check(self, name: str, check_fn) -> ServiceHealth:
        """执行单个健康检查"""
        try:
            return await check_fn()
        except Exception as e:
            return ServiceHealth(name=name, status=HealthStatus.UNHEALTHY, message=str(e))

    async def _check_api_service(self) -> ServiceHealth:
        """检查API服务状态"""
        try:
            async with aiohttp.ClientSession() as session:
                from urllib.parse import urljoin

                start = time.time()
                check_url = urljoin(self.config.api_base_url, "/health")
                async with session.get(check_url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    response_time = time.time() - start
                    # /health 返回的是HTML页面（前端入口），所以200就说明存活
                    if resp.status == 200:
                        return ServiceHealth(
                            name="api_service",
                            status=HealthStatus.HEALTHY,
                            response_time=response_time,
                            message="API服务正常",
                        )
                    else:
                        return ServiceHealth(
                            name="api_service",
                            status=HealthStatus.DEGRADED,
                            response_time=response_time,
                            message=f"HTTP {resp.status}",
                        )
        except Exception as e:
            return ServiceHealth(name="api_service", status=HealthStatus.UNHEALTHY, message=f"连接失败: {str(e)[:80]}")

    async def _check_chromadb(self) -> ServiceHealth:
        """检查ChromaDB状态（嵌入式，直接检查向量数量）"""
        try:
            from src.db.vector_store import get_vector_store

            vs = get_vector_store()
            if not vs:
                return ServiceHealth(name="chromadb", status=HealthStatus.UNHEALTHY, message="VectorStore 初始化失败")

            start = time.time()
            count = vs.count
            response_time = time.time() - start

            if count >= 0:
                return ServiceHealth(
                    name="chromadb",
                    status=HealthStatus.HEALTHY,
                    response_time=response_time,
                    message=f"ChromaDB正常（{count} 条向量）",
                    details={"vector_count": count},
                )
            else:
                return ServiceHealth(
                    name="chromadb",
                    status=HealthStatus.DEGRADED,
                    response_time=response_time,
                    message="ChromaDB查询失败（count=-1）",
                )
        except Exception as e:
            return ServiceHealth(name="chromadb", status=HealthStatus.UNHEALTHY, message=f"检查失败: {str(e)[:80]}")

    async def _check_redis(self) -> ServiceHealth:
        """检查Redis状态（可选服务，不可用时标记为degraded而非unhealthy）"""
        try:
            # 先检查Redis是否配置了
            redis_url = self.config.redis_url
            if not redis_url or redis_url == "redis://localhost:6379":
                # 默认值意味着未实际配置
                return ServiceHealth(
                    name="redis",
                    status=HealthStatus.HEALTHY if not self.config.redis_url else HealthStatus.DEGRADED,
                    message="Redis未配置（使用默认值）",
                    details={"url": redis_url, "configured": bool(os.getenv("REDIS_URL"))},
                )
            start = time.time()
            redis = aioredis.from_url(redis_url)
            await redis.ping()
            response_time = time.time() - start
            await redis.aclose()
            return ServiceHealth(
                name="redis", status=HealthStatus.HEALTHY, response_time=response_time, message="Redis正常"
            )
        except Exception as e:
            return ServiceHealth(
                name="redis", status=HealthStatus.DEGRADED, message=f"Redis不可用（非关键服务）: {str(e)[:80]}"
            )

    async def _check_disk_space(self) -> ServiceHealth:
        """检查磁盘空间"""
        import psutil

        try:
            disk = psutil.disk_usage("/")
            percent = disk.percent
            if percent >= self.config.disk_threshold_critical:
                status = HealthStatus.UNHEALTHY
                message = f"磁盘使用率 {percent}% (危险)"
            elif percent >= self.config.disk_threshold_warning:
                status = HealthStatus.DEGRADED
                message = f"磁盘使用率 {percent}% (警告)"
            else:
                status = HealthStatus.HEALTHY
                message = f"磁盘使用率 {percent}%"

            return ServiceHealth(
                name="disk_space",
                status=status,
                message=message,
                details={"total": disk.total, "used": disk.used, "free": disk.free, "percent": percent},
            )
        except Exception as e:
            return ServiceHealth(name="disk_space", status=HealthStatus.UNHEALTHY, message=f"检查失败: {str(e)}")

    async def _check_memory_usage(self) -> ServiceHealth:
        """检查内存使用"""
        import psutil

        try:
            mem = psutil.virtual_memory()
            percent = mem.percent
            if percent >= self.config.memory_threshold_critical:
                status = HealthStatus.UNHEALTHY
                message = f"内存使用率 {percent}% (危险)"
            elif percent >= self.config.memory_threshold_warning:
                status = HealthStatus.DEGRADED
                message = f"内存使用率 {percent}% (警告)"
            else:
                status = HealthStatus.HEALTHY
                message = f"内存使用率 {percent}%"

            return ServiceHealth(
                name="memory_usage",
                status=status,
                message=message,
                details={"total": mem.total, "available": mem.available, "used": mem.used, "percent": percent},
            )
        except Exception as e:
            return ServiceHealth(name="memory_usage", status=HealthStatus.UNHEALTHY, message=f"检查失败: {str(e)}")

    def _calculate_overall_status(self, services: List[ServiceHealth]) -> HealthStatus:
        """计算整体健康状态"""
        statuses = [s.status for s in services]

        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    def _store_history(self, health: SystemHealth):
        """存储健康检查历史"""
        self.health_history.append(health)
        if len(self.health_history) > self.config.health_history_max:
            self.health_history = self.health_history[-self.config.health_history_max :]

    def get_history(self, limit: int = 100) -> List[SystemHealth]:
        """获取健康检查历史"""
        return self.health_history[-limit:]

    def get_current_status(self) -> Optional[SystemHealth]:
        """获取最近一次健康检查结果"""
        return self.health_history[-1] if self.health_history else None
