"""
base.py — DataSource 抽象基类
=============================
定义多源知识接入系统的统一接口。
所有具体连接器必须继承此类并实现：
- connect()  — 连接数据源
- fetch()    — 获取原始数据
- transform() — 转换为统一格式
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time
import uuid
import logging

logger = logging.getLogger(__name__)


class ConnectorStatus(str, Enum):
    """连接器状态枚举"""
    UNINITIALIZED = "uninitialized"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class SourceType(str, Enum):
    """数据源类型枚举"""
    DATABASE = "database"
    API = "api"
    FILE = "file"
    WEB = "web"


@dataclass
class UnifiedDocument:
    """统一文档格式 — 所有数据源转换后的目标格式"""
    doc_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    title: str = ""
    content: str = ""
    source_type: SourceType = SourceType.FILE
    source_url: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunks: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    tags: List[str] = field(default_factory=list)
    language: str = "zh"
    raw_data: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "content": self.content,
            "source_type": self.source_type.value if isinstance(self.source_type, SourceType) else self.source_type,
            "source_url": self.source_url,
            "metadata": self.metadata,
            "chunks": self.chunks,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": self.tags,
            "language": self.language,
        }


@dataclass
class ConnectorConfig:
    """连接器通用配置"""
    name: str = ""
    source_type: SourceType = SourceType.FILE
    timeout: int = 30
    retry_count: int = 3
    retry_delay: float = 1.0
    headers: Dict[str, str] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


class ConnectionError(Exception):
    """数据源连接异常"""

    def __init__(self, source_name: str, detail: str = ""):
        self.source_name = source_name
        self.detail = detail
        super().__init__(f"连接数据源 '{source_name}' 失败: {detail}")


class FetchError(Exception):
    """数据获取异常"""

    def __init__(self, source_name: str, detail: str = ""):
        self.source_name = source_name
        self.detail = detail
        super().__init__(f"从数据源 '{source_name}' 获取数据失败: {detail}")


class TransformError(Exception):
    """数据转换异常"""

    def __init__(self, source_name: str, detail: str = ""):
        self.source_name = source_name
        self.detail = detail
        super().__init__(f"转换数据源 '{source_name}' 的数据失败: {detail}")


class DataSource(ABC):
    """
    DataSource — 多源知识接入抽象基类

    所有具体连接器（数据库、API、文件、网页）均需继承此类，
    并实现 connect()、fetch()、transform() 三个核心方法。

    使用示例::

        class MyConnector(DataSource):
            async def connect(self) -> bool:
                # 建立连接逻辑
                ...

            async def fetch(self, **kwargs) -> List[Any]:
                # 获取原始数据
                ...

            async def transform(self, raw_data: List[Any]) -> List[UnifiedDocument]:
                # 转换为统一格式
                ...
    """

    def __init__(self, config: ConnectorConfig):
        """
        Args:
            config: 连接器配置对象
        """
        self.config = config
        self.name = config.name
        self.source_type = config.source_type
        self._status: ConnectorStatus = ConnectorStatus.UNINITIALIZED
        self._connected_at: float = 0.0
        self._last_error: Optional[str] = None
        self._fetch_count: int = 0
        self._doc_count: int = 0

    # ========== 状态属性 ==========

    @property
    def status(self) -> ConnectorStatus:
        """获取当前连接器状态"""
        return self._status

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._status == ConnectorStatus.CONNECTED

    @property
    def last_error(self) -> Optional[str]:
        """获取最后一次错误信息"""
        return self._last_error

    @property
    def stats(self) -> Dict[str, Any]:
        """获取连接器统计信息"""
        return {
            "name": self.name,
            "source_type": self.source_type.value,
            "status": self._status.value,
            "fetch_count": self._fetch_count,
            "doc_count": self._doc_count,
            "connected_at": self._connected_at,
            "last_error": self._last_error,
        }

    # ========== 抽象方法 — 子类必须实现 ==========

    @abstractmethod
    async def connect(self) -> bool:
        """
        连接数据源，返回是否成功。

        Returns:
            bool: True 表示连接成功，False 表示失败

        Raises:
            ConnectionError: 连接失败时抛出
        """

    @abstractmethod
    async def fetch(self, **kwargs) -> List[Any]:
        """
        从数据源获取原始数据。

        Args:
            **kwargs: 查询参数，由具体实现定义（如 SQL 查询、API 参数等）

        Returns:
            List[Any]: 原始数据列表

        Raises:
            FetchError: 获取失败时抛出
        """

    @abstractmethod
    async def transform(self, raw_data: List[Any]) -> List[UnifiedDocument]:
        """
        将原始数据转换为统一文档格式。

        Args:
            raw_data: fetch() 返回的原始数据列表

        Returns:
            List[UnifiedDocument]: 统一格式的文档列表

        Raises:
            TransformError: 转换失败时抛出
        """

    # ========== 组合方法 — 一键完成连接+获取+转换 ==========

    async def ingest(self, **kwargs) -> List[UnifiedDocument]:
        """
        一键接入流程：连接 → 获取 → 转换。

        这是推荐的对外接口，封装了整个数据接入流程。

        Args:
            **kwargs: 传递给 fetch() 的查询参数

        Returns:
            List[UnifiedDocument]: 统一格式的文档列表

        Raises:
            ConnectionError, FetchError, TransformError
        """
        if not self.is_connected:
            success = await self.connect()
            if not success:
                raise ConnectionError(
                    self.name,
                    f"无法连接数据源 (状态: {self._status.value})"
                )

        try:
            raw_data = await self.fetch(**kwargs)
            self._fetch_count += 1

            documents = await self.transform(raw_data)
            self._doc_count += len(documents)

            logger.info(
                "[%s] 接入完成：获取 %d 条原始数据 → %d 个统一文档",
                self.name, len(raw_data), len(documents)
            )
            return documents

        except (ConnectionError, FetchError, TransformError):
            raise
        except Exception as e:
            self._set_error(str(e))
            raise FetchError(self.name, f"接入流程异常: {str(e)}")

    # ========== 内部辅助方法 ==========

    def _set_status(self, status: ConnectorStatus) -> None:
        """更新连接器状态"""
        self._status = status
        if status == ConnectorStatus.CONNECTED:
            self._connected_at = time.time()
        logger.debug("[%s] 状态变更: → %s", self.name, status.value)

    def _set_error(self, error: str) -> None:
        """记录错误信息"""
        self._last_error = error
        self._status = ConnectorStatus.ERROR
        logger.error("[%s] 错误: %s", self.name, error)

    def _validate_config(self, required_keys: List[str]) -> None:
        """
        验证配置中必须包含指定的键。

        Args:
            required_keys: 必须在 self.config.extra 中存在的键列表

        Raises:
            ValueError: 缺少必要配置时抛出
        """
        missing = [k for k in required_keys if k not in self.config.extra]
        if missing:
            raise ValueError(
                f"[{self.name}] 缺少必要配置: {', '.join(missing)}"
            )

    async def disconnect(self) -> None:
        """
        断开数据源连接（默认空操作，子类可覆写以释放资源）。

        例如：关闭数据库连接池、关闭文件句柄等。
        """
        self._status = ConnectorStatus.DISCONNECTED
        logger.info("[%s] 已断开连接", self.name)

    async def health_check(self) -> bool:
        """
        健康检查 — 默认通过 connect() 判断。

        Returns:
            bool: True 表示健康
        """
        try:
            if not self.is_connected:
                return await self.connect()
            return True
        except Exception:
            return False

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__}(name={self.name!r}, "
            f"type={self.source_type.value}, status={self._status.value})>"
        )
