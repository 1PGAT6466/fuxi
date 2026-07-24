"""
database.py — 数据库连接器
==========================
支持 SQLite、PostgreSQL、MySQL 等数据库的数据接入。
通过异步连接池执行查询，将表数据转换为统一文档格式。
"""
import logging
from typing import Any, Dict, List, Optional

from .base import (
    DataSource,
    ConnectorConfig,
    UnifiedDocument,
    SourceType,
    ConnectorStatus,
    ConnectionError,
    FetchError,
    TransformError,
)

logger = logging.getLogger(__name__)


class DatabaseConnector(DataSource):
    """
    DatabaseConnector — 数据库知识接入连接器

    支持 SQLite（内置）及 PostgreSQL/MySQL（可选依赖）。
    将 SQL 查询结果转换为统一文档格式。

    配置示例::

        config = ConnectorConfig(
            name="知识库数据库",
            source_type=SourceType.DATABASE,
            extra={
                "db_type": "sqlite",
                "db_path": "data/knowledge.db",
                "table_name": "documents",
            }
        )
        connector = DatabaseConnector(config)
        docs = await connector.ingest()
    """

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self._connection: Any = None
        self._db_type: str = ""
        self._supported_types = {"sqlite", "postgresql", "mysql"}

    async def connect(self) -> bool:
        """
        建立数据库连接。

        支持的数据库类型:
        - sqlite: 使用 aiosqlite
        - postgresql: 使用 asyncpg
        - mysql: 使用 aiomysql

        Returns:
            bool: 连接成功返回 True

        Raises:
            ConnectionError: 连接失败或缺少依赖时抛出
        """
        self._set_status(ConnectorStatus.CONNECTING)

        try:
            self._validate_config(["db_type"])
            self._db_type = self.config.extra["db_type"].lower()

            if self._db_type not in self._supported_types:
                raise ConnectionError(
                    self.name,
                    f"不支持的数据库类型 '{self._db_type}'，"
                    f"支持: {', '.join(self._supported_types)}"
                )

            if self._db_type == "sqlite":
                await self._connect_sqlite()
            elif self._db_type == "postgresql":
                await self._connect_postgresql()
            elif self._db_type == "mysql":
                await self._connect_mysql()

            self._set_status(ConnectorStatus.CONNECTED)
            logger.info("[%s] 数据库连接成功 (类型: %s)", self.name, self._db_type)
            return True

        except ConnectionError:
            self._set_error(str(ConnectionError))
            raise
        except Exception as e:
            self._set_error(str(e))
            raise ConnectionError(self.name, str(e))

    async def _connect_sqlite(self) -> None:
        """连接 SQLite 数据库"""
        try:
            import aiosqlite
        except ImportError:
            raise ConnectionError(
                self.name,
                "缺少 aiosqlite 依赖，请执行: pip install aiosqlite"
            )

        db_path = self.config.extra.get(
            "db_path",
            self.config.extra.get("database", "data/memory.db")
        )
        self._connection = await aiosqlite.connect(db_path)
        # 启用 WAL 模式和行工厂以获得更好的并发和字典结果
        await self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.row_factory = aiosqlite.Row

    async def _connect_postgresql(self) -> None:
        """连接 PostgreSQL 数据库"""
        try:
            import asyncpg
        except ImportError:
            raise ConnectionError(
                self.name,
                "缺少 asyncpg 依赖，请执行: pip install asyncpg"
            )

        dsn = self.config.extra.get(
            "dsn",
            f"postgresql://"
            f"{self.config.extra.get('user', 'postgres')}:"
            f"{self.config.extra.get('password', '')}@"
            f"{self.config.extra.get('host', 'localhost')}:"
            f"{self.config.extra.get('port', 5432)}/"
            f"{self.config.extra.get('database', 'postgres')}"
        )
        self._connection = await asyncpg.connect(dsn)

    async def _connect_mysql(self) -> None:
        """连接 MySQL 数据库"""
        try:
            import aiomysql
        except ImportError:
            raise ConnectionError(
                self.name,
                "缺少 aiomysql 依赖，请执行: pip install aiomysql"
            )

        pool_kwargs = {
            "host": self.config.extra.get("host", "localhost"),
            "port": self.config.extra.get("port", 3306),
            "user": self.config.extra.get("user", "root"),
            "password": self.config.extra.get("password", ""),
            "db": self.config.extra.get("database", ""),
        }
        self._connection = await aiomysql.create_pool(
            minsize=1, maxsize=5, **pool_kwargs
        )

    async def fetch(self, **kwargs) -> List[Dict[str, Any]]:
        """
        执行 SQL 查询并获取结果。

        Args:
            **kwargs: 可选参数
                - query: 自定义 SQL 查询语句
                - table_name: 表名（未提供 query 时使用，查询全表）
                - columns: 指定列名列表
                - where: WHERE 条件子句
                - limit: 返回行数限制

        Returns:
            List[Dict[str, Any]]: 查询结果（字典列表）

        Raises:
            FetchError: 查询执行失败时抛出
        """
        if not self.is_connected:
            raise FetchError(self.name, "数据库未连接，请先调用 connect()")

        try:
            query = kwargs.get("query", "")
            if not query:
                query = self._build_select_query(
                    table_name=kwargs.get(
                        "table_name",
                        self.config.extra.get("table_name", "")
                    ),
                    columns=kwargs.get("columns"),
                    where=kwargs.get("where", ""),
                    limit=kwargs.get("limit", 1000),
                )

            logger.debug("[%s] 执行查询: %s", self.name, query[:200])
            rows = await self._execute_query(query)
            return rows

        except FetchError:
            raise
        except Exception as e:
            raise FetchError(self.name, str(e))

    async def _execute_query(self, query: str) -> List[Dict[str, Any]]:
        """执行 SQL 查询并转换为字典列表"""
        if self._db_type == "sqlite":
            import aiosqlite
            cursor = await self._connection.execute(query)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

        elif self._db_type == "postgresql":
            records = await self._connection.fetch(query)
            return [dict(record) for record in records]

        elif self._db_type == "mysql":
            async with self._connection.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(query)
                    rows = await cur.fetchall()
                    return rows

        return []

    @staticmethod
    def _build_select_query(
        table_name: str,
        columns: Optional[List[str]] = None,
        where: str = "",
        limit: int = 1000,
    ) -> str:
        """构建 SELECT 查询语句"""
        if not table_name:
            raise FetchError("unknown", "未指定 table_name 或 query")

        col_str = ", ".join(columns) if columns else "*"
        query = f"SELECT {col_str} FROM {table_name}"
        if where:
            query += f" WHERE {where}"
        query += f" LIMIT {limit}"
        return query

    async def transform(self, raw_data: List[Dict[str, Any]]) -> List[UnifiedDocument]:
        """
        将数据库查询结果行转换为统一文档格式。

        每行数据转换为一个 UnifiedDocument，列名作为 metadata 的一部分。

        Args:
            raw_data: 查询结果行列表

        Returns:
            List[UnifiedDocument]: 统一文档列表

        Raises:
            TransformError: 转换失败时抛出
        """
        if not raw_data:
            return []

        try:
            documents = []
            for idx, row in enumerate(raw_data):
                # 尝试从行中提取文本内容
                content_parts = []
                for key, value in row.items():
                    if isinstance(value, str) and len(value) > 20:
                        content_parts.append(f"{key}: {value}")
                    elif value is not None:
                        content_parts.append(f"{key}={value}")

                content = "\n".join(content_parts) if content_parts else str(row)
                title = (
                    row.get("title", "")
                    or row.get("name", "")
                    or row.get("subject", "")
                    or f"数据库记录 #{idx + 1}"
                )

                doc = UnifiedDocument(
                    title=str(title),
                    content=content,
                    source_type=SourceType.DATABASE,
                    source_url=(
                        f"{self._db_type}://"
                        f"{self.config.extra.get('table_name', 'unknown')}"
                        f"/row_{idx}"
                    ),
                    metadata={
                        "db_type": self._db_type,
                        "connector": self.name,
                        "row_index": idx,
                        "columns": list(row.keys()),
                        "original_row": {str(k): str(v) for k, v in row.items()},
                    },
                    language="zh",
                )
                documents.append(doc)

            logger.info(
                "[%s] 转换完成: %d 行 → %d 个文档",
                self.name, len(raw_data), len(documents)
            )
            return documents

        except Exception as e:
            raise TransformError(self.name, str(e))

    async def disconnect(self) -> None:
        """断开数据库连接，释放资源"""
        try:
            if self._connection:
                if self._db_type == "sqlite":
                    await self._connection.close()
                elif self._db_type == "postgresql":
                    await self._connection.close()
                elif self._db_type == "mysql":
                    self._connection.close()
                    await self._connection.wait_closed()
                self._connection = None
        except Exception as e:
            logger.warning("[%s] 断开连接时出错: %s", self.name, str(e))
        finally:
            self._set_status(ConnectorStatus.DISCONNECTED)

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()


# 类型别名中使用的延迟导入
try:
    import aiosqlite  # noqa: F811
except ImportError:
    pass

try:
    import asyncpg  # noqa: F811
except ImportError:
    pass

try:
    import aiomysql  # noqa: F811
except ImportError:
    pass
