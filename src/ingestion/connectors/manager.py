"""
manager.py — ConnectorManager 连接器管理器
===========================================
统一管理所有数据源连接器的生命周期：
- 注册/注销连接器
- 批量接入
- 状态收集
- 健康检查
- 事件回调
"""
import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from .base import (
    DataSource,
    ConnectorConfig,
    UnifiedDocument,
    ConnectorStatus,
    ConnectionError,
    FetchError,
    TransformError,
)

logger = logging.getLogger(__name__)


class ConnectorManager:
    """
    ConnectorManager — 多源连接器管理器

    管理所有 DataSource 实例的生命周期，提供：
    - 统一注册接口
    - 批量/并行接入
    - 状态收集与监控
    - 健康检查调度
    - 事件回调（连接、接入完成、错误）

    使用示例::

        manager = ConnectorManager()

        # 注册连接器
        manager.register(DatabaseConnector(db_config))
        manager.register(APIConnector(api_config))

        # 批量接入
        results = await manager.ingest_all()

        # 状态概览
        print(manager.get_stats())
    """

    def __init__(self, max_concurrency: int = 5):
        """
        Args:
            max_concurrency: 并行接入的最大连接器数量
        """
        self._connectors: Dict[str, DataSource] = {}
        self._max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)

        # 事件回调
        self._on_connect: List[Callable] = []
        self._on_ingest_complete: List[Callable] = []
        self._on_error: List[Callable] = []

        # 统计
        self._total_ingestions: int = 0
        self._total_documents: int = 0
        self._total_errors: int = 0
        self._started_at: float = time.time()

    # ========== 注册管理 ==========

    def register(self, connector: DataSource) -> None:
        """
        注册一个连接器。

        Args:
            connector: DataSource 实例

        Raises:
            ValueError: 连接器名称重复时抛出
        """
        if connector.name in self._connectors:
            raise ValueError(f"连接器 '{connector.name}' 已注册")

        self._connectors[connector.name] = connector
        logger.info(
            "[ConnectorManager] 注册连接器: %s (类型: %s)",
            connector.name, connector.source_type.value
        )

    def unregister(self, name: str) -> Optional[DataSource]:
        """
        注销一个连接器。

        Args:
            name: 连接器名称

        Returns:
            被移除的连接器实例，不存在返回 None
        """
        connector = self._connectors.pop(name, None)
        if connector:
            logger.info("[ConnectorManager] 注销连接器: %s", name)
        return connector

    def get(self, name: str) -> Optional[DataSource]:
        """
        根据名称获取连接器。

        Args:
            name: 连接器名称

        Returns:
            DataSource 实例或 None
        """
        return self._connectors.get(name)

    def list_connectors(self) -> List[str]:
        """获取所有已注册连接器的名称列表"""
        return list(self._connectors.keys())

    @property
    def connector_count(self) -> int:
        """已注册连接器数量"""
        return len(self._connectors)

    # ========== 事件回调 ==========

    def on_connect(self, callback: Callable) -> None:
        """注册连接成功回调"""
        self._on_connect.append(callback)

    def on_ingest_complete(self, callback: Callable) -> None:
        """注册接入完成回调"""
        self._on_ingest_complete.append(callback)

    def on_error(self, callback: Callable) -> None:
        """注册错误回调"""
        self._on_error.append(callback)

    async def _trigger_callbacks(
        self, callbacks: List[Callable], *args, **kwargs
    ) -> None:
        """触发回调链"""
        for cb in callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(*args, **kwargs)
                else:
                    cb(*args, **kwargs)
            except Exception as e:
                logger.error(
                    "[ConnectorManager] 回调异常: %s", str(e)
                )

    # ========== 接入操作 ==========

    async def connect_all(self) -> Dict[str, bool]:
        """
        并行连接所有已注册的连接器。

        Returns:
            Dict[str, bool]: {连接器名称: 是否连接成功}
        """
        logger.info(
            "[ConnectorManager] 开始并行连接 %d 个数据源...",
            self.connector_count
        )

        tasks = []
        for name, connector in self._connectors.items():
            tasks.append(self._connect_one(name, connector))

        results = dict(await asyncio.gather(*tasks))
        success_count = sum(1 for v in results.values() if v)
        logger.info(
            "[ConnectorManager] 连接完成: %d/%d 成功",
            success_count, self.connector_count
        )
        return results

    async def _connect_one(
        self, name: str, connector: DataSource
    ) -> tuple:
        """连接单个连接器"""
        try:
            success = await connector.connect()
            if success:
                await self._trigger_callbacks(
                    self._on_connect, connector=connector
                )
            return name, success
        except Exception as e:
            logger.error(
                "[ConnectorManager] 连接 '%s' 失败: %s",
                name, str(e)
            )
            await self._trigger_callbacks(
                self._on_error,
                connector=connector,
                error=e,
                phase="connect"
            )
            return name, False

    async def ingest(
        self,
        connector_name: str,
        **kwargs
    ) -> List[UnifiedDocument]:
        """
        使用指定连接器执行接入流程。

        Args:
            connector_name: 连接器名称
            **kwargs: 传递给 connect/fetch 的参数

        Returns:
            List[UnifiedDocument]: 统一文档列表

        Raises:
            ValueError: 连接器未注册时抛出
            ConnectionError, FetchError, TransformError
        """
        connector = self._connectors.get(connector_name)
        if not connector:
            raise ValueError(f"连接器 '{connector_name}' 未注册")

        try:
            docs = await connector.ingest(**kwargs)
            self._total_ingestions += 1
            self._total_documents += len(docs)

            await self._trigger_callbacks(
                self._on_ingest_complete,
                connector=connector,
                document_count=len(docs)
            )
            return docs

        except (ConnectionError, FetchError, TransformError):
            self._total_errors += 1
            raise
        except Exception as e:
            self._total_errors += 1
            await self._trigger_callbacks(
                self._on_error,
                connector=connector,
                error=e,
                phase="ingest"
            )
            raise

    async def ingest_all(
        self,
        parallel: bool = True,
        **kwargs
    ) -> Dict[str, List[UnifiedDocument]]:
        """
        批量接入：对所有已注册连接器执行接入。

        Args:
            parallel: 是否并行执行（默认 True）
            **kwargs: 传递给各连接器 fetch() 的参数

        Returns:
            Dict[str, List[UnifiedDocument]]: {连接器名称: 文档列表}
        """
        if parallel:
            return await self._ingest_parallel(**kwargs)
        else:
            return await self._ingest_sequential(**kwargs)

    async def _ingest_parallel(self, **kwargs) -> Dict[str, List[UnifiedDocument]]:
        """并行接入（通过信号量控制并发数）"""
        async def _do_ingest(name: str, connector: DataSource):
            async with self._semaphore:
                try:
                    docs = await connector.ingest(**kwargs)
                    self._total_ingestions += 1
                    self._total_documents += len(docs)
                    return name, docs
                except Exception as e:
                    self._total_errors += 1
                    logger.error(
                        "[ConnectorManager] 接入 '%s' 失败: %s",
                        name, str(e)
                    )
                    return name, []

        tasks = [
            _do_ingest(name, connector)
            for name, connector in self._connectors.items()
        ]
        results = dict(await asyncio.gather(*tasks))
        return results

    async def _ingest_sequential(self, **kwargs) -> Dict[str, List[UnifiedDocument]]:
        """顺序接入"""
        results = {}
        for name, connector in self._connectors.items():
            try:
                docs = await connector.ingest(**kwargs)
                results[name] = docs
                self._total_ingestions += 1
                self._total_documents += len(docs)
            except Exception as e:
                logger.error(
                    "[ConnectorManager] 接入 '%s' 失败: %s",
                    name, str(e)
                )
                results[name] = []
                self._total_errors += 1
        return results

    # ========== 健康检查 ==========

    async def health_check(self) -> Dict[str, Dict[str, Any]]:
        """
        对所有注册连接器执行健康检查。

        Returns:
            Dict[str, Dict]: {连接器名称: {healthy: bool, detail: str}}
        """
        async def _check(name: str, connector: DataSource):
            try:
                healthy = await connector.health_check()
                detail = "正常" if healthy else f"状态: {connector.status.value}"
                return name, {"healthy": healthy, "detail": detail}
            except Exception as e:
                return name, {"healthy": False, "detail": str(e)}

        tasks = [
            _check(name, connector)
            for name, connector in self._connectors.items()
        ]
        return dict(await asyncio.gather(*tasks))

    # ========== 状态统计 ==========

    def get_stats(self) -> Dict[str, Any]:
        """
        获取管理器整体状态和统计信息。

        Returns:
            Dict: 包含连接器列表、统计数据和各连接器详情的完整状态
        """
        connectors_detail = {}
        for name, connector in self._connectors.items():
            connectors_detail[name] = connector.stats

        return {
            "connector_count": self.connector_count,
            "total_ingestions": self._total_ingestions,
            "total_documents": self._total_documents,
            "total_errors": self._total_errors,
            "uptime_seconds": time.time() - self._started_at,
            "connectors": connectors_detail,
            "connected_count": sum(
                1 for c in self._connectors.values()
                if c.is_connected
            ),
            "error_count": sum(
                1 for c in self._connectors.values()
                if c.status == ConnectorStatus.ERROR
            ),
        }

    # ========== 生命周期 ==========

    async def disconnect_all(self) -> None:
        """断开所有连接器的连接并释放资源"""
        logger.info(
            "[ConnectorManager] 断开 %d 个连接器...",
            self.connector_count
        )

        async def _disconnect(name: str, connector: DataSource):
            try:
                await connector.disconnect()
                return name, True
            except Exception as e:
                logger.error(
                    "[ConnectorManager] 断开 '%s' 时出错: %s",
                    name, str(e)
                )
                return name, False

        tasks = [
            _disconnect(name, connector)
            for name, connector in self._connectors.items()
        ]
        await asyncio.gather(*tasks)

        self._connectors.clear()
        logger.info("[ConnectorManager] 所有连接器已断开")

    def __repr__(self) -> str:
        connected = sum(
            1 for c in self._connectors.values() if c.is_connected
        )
        return (
            f"<ConnectorManager("
            f"registered={self.connector_count}, "
            f"connected={connected}, "
            f"docs={self._total_documents})>"
        )
