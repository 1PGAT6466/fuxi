"""
tests/test_connectors.py — 多源知识接入系统测试用例
===================================================
测试覆盖：
1. DataSource 抽象基类
2. DatabaseConnector (SQLite)
3. FileConnector
4. APIConnector / WebConnector
5. ConnectorManager 管理功能
6. 错误处理与边界情况
"""
import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ingestion.connectors.base import (
    DataSource,
    ConnectorConfig,
    UnifiedDocument,
    SourceType,
    ConnectorStatus,
    ConnectionError,
    FetchError,
    TransformError,
)
from ingestion.connectors.database import DatabaseConnector
from ingestion.connectors.file_connector import FileConnector
from ingestion.connectors.manager import ConnectorManager


class TestDataSourceBase(unittest.TestCase):
    """测试 DataSource 抽象基类"""

    def test_cannot_instantiate_abstract(self):
        """抽象类不能直接实例化"""
        with self.assertRaises(TypeError):
            DataSource(ConnectorConfig(name="test"))

    def test_concrete_subclass_instantiation(self):
        """具体子类可以正常实例化"""

        class SimpleConnector(DataSource):
            async def connect(self) -> bool:
                self._set_status(ConnectorStatus.CONNECTED)
                return True

            async def fetch(self, **kwargs) -> List[Any]:
                return [{"data": "test"}]

            async def transform(self, raw_data: List[Any]) -> List[UnifiedDocument]:
                return [
                    UnifiedDocument(
                        title="test",
                        content=str(item),
                        source_type=self.source_type,
                    )
                    for item in raw_data
                ]

        config = ConnectorConfig(
            name="simple",
            source_type=SourceType.API,
            extra={"url": "http://example.com"},
        )
        connector = SimpleConnector(config)

        self.assertEqual(connector.name, "simple")
        self.assertEqual(connector.status, ConnectorStatus.UNINITIALIZED)
        self.assertFalse(connector.is_connected)
        self.assertEqual(connector.source_type, SourceType.API)

    def test_connector_config(self):
        """测试 ConnectorConfig 数据类"""
        config = ConnectorConfig(
            name="test-source",
            source_type=SourceType.DATABASE,
            timeout=60,
            retry_count=5,
            extra={"host": "localhost", "port": 5432},
        )
        self.assertEqual(config.name, "test-source")
        self.assertEqual(config.timeout, 60)
        self.assertEqual(config.retry_count, 5)
        self.assertEqual(config.extra["host"], "localhost")

    def test_unified_document(self):
        """测试 UnifiedDocument 数据类"""
        doc = UnifiedDocument(
            title="测试文档",
            content="这是测试内容",
            source_type=SourceType.FILE,
            source_url="/tmp/test.txt",
            metadata={"key": "value"},
        )
        self.assertEqual(doc.title, "测试文档")
        self.assertEqual(doc.content, "这是测试内容")
        self.assertIsNotNone(doc.doc_id)

        d = doc.to_dict()
        self.assertEqual(d["title"], "测试文档")
        self.assertEqual(d["metadata"]["key"], "value")

    def test_connector_status_enum(self):
        """测试连接器状态枚举"""
        self.assertEqual(ConnectorStatus.UNINITIALIZED.value, "uninitialized")
        self.assertEqual(ConnectorStatus.CONNECTED.value, "connected")
        self.assertEqual(ConnectorStatus.ERROR.value, "error")

    def test_source_type_enum(self):
        """测试数据源类型枚举"""
        self.assertEqual(SourceType.DATABASE.value, "database")
        self.assertEqual(SourceType.API.value, "api")
        self.assertEqual(SourceType.FILE.value, "file")
        self.assertEqual(SourceType.WEB.value, "web")


class TestDatabaseConnector(unittest.TestCase):
    """测试 DatabaseConnector (SQLite)"""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="fuxi_test_")
        cls.db_path = os.path.join(cls.temp_dir, "test.db")

        # 创建测试 SQLite 数据库
        import sqlite3
        conn = sqlite3.connect(cls.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY,
                title TEXT,
                content TEXT,
                category TEXT
            )
        """)
        test_data = [
            (1, "测试文档A", "这是文档A的内容，用于测试数据接入。", "技术"),
            (2, "测试文档B", "这是文档B的内容，包含更多测试数据。", "管理"),
            (3, "测试文档C", "这是文档C的内容，验证转换功能。", "技术"),
        ]
        cursor.executemany(
            "INSERT OR REPLACE INTO documents VALUES (?, ?, ?, ?)",
            test_data
        )
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        self.config = ConnectorConfig(
            name="测试SQLite",
            source_type=SourceType.DATABASE,
            extra={
                "db_type": "sqlite",
                "db_path": self.db_path,
                "table_name": "documents",
            }
        )
        self.connector = DatabaseConnector(self.config)

    def test_initial_state(self):
        """初始状态检查"""
        self.assertEqual(self.connector.status, ConnectorStatus.UNINITIALIZED)
        self.assertFalse(self.connector.is_connected)

    def test_connect(self):
        """连接测试"""
        result = asyncio.run(self.connector.connect())
        self.assertTrue(result)
        self.assertTrue(self.connector.is_connected)
        self.assertEqual(self.connector.status, ConnectorStatus.CONNECTED)

        asyncio.run(self.connector.disconnect())

    def test_fetch_without_connect(self):
        """未连接时 fetch 应该抛出异常"""
        with self.assertRaises(FetchError):
            asyncio.run(self.connector.fetch())

    def test_fetch_full_table(self):
        """获取全表数据"""
        asyncio.run(self.connector.connect())

        rows = asyncio.run(self.connector.fetch())
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["title"], "测试文档A")

        asyncio.run(self.connector.disconnect())

    def test_fetch_with_custom_query(self):
        """自定义查询"""
        asyncio.run(self.connector.connect())

        rows = asyncio.run(
            self.connector.fetch(
                query="SELECT * FROM documents WHERE category = '技术'"
            )
        )
        self.assertEqual(len(rows), 2)

        asyncio.run(self.connector.disconnect())

    def test_fetch_with_limit(self):
        """带限制的查询"""
        asyncio.run(self.connector.connect())

        rows = asyncio.run(self.connector.fetch(limit=1))
        self.assertEqual(len(rows), 1)

        asyncio.run(self.connector.disconnect())

    def test_transform(self):
        """数据转换测试"""
        raw = [
            {"id": 1, "title": "测试A", "content": "内容A"},
            {"id": 2, "title": "测试B", "content": "内容B"},
        ]

        docs = asyncio.run(self.connector.transform(raw))
        self.assertEqual(len(docs), 2)
        self.assertIsInstance(docs[0], UnifiedDocument)
        self.assertEqual(docs[0].title, "测试A")
        self.assertIn("内容A", docs[0].content)
        self.assertEqual(docs[0].source_type, SourceType.DATABASE)

    def test_transform_empty(self):
        """空数据转换"""
        docs = asyncio.run(self.connector.transform([]))
        self.assertEqual(len(docs), 0)

    def test_ingest_full_flow(self):
        """完整接入流程"""
        docs = asyncio.run(self.connector.ingest())
        self.assertEqual(len(docs), 3)
        self.assertTrue(all(isinstance(d, UnifiedDocument) for d in docs))
        self.assertGreaterEqual(self.connector.stats["doc_count"], 3)

        asyncio.run(self.connector.disconnect())

    def test_validate_config_missing(self):
        """缺少必要配置时抛出异常"""
        bad_config = ConnectorConfig(
            name="bad",
            source_type=SourceType.DATABASE,
            extra={},
        )
        connector = DatabaseConnector(bad_config)
        with self.assertRaises(ConnectionError):
            asyncio.run(connector.connect())

    def test_async_context_manager(self):
        """异步上下文管理器"""

        async def use_context():
            async with DatabaseConnector(self.config) as conn:
                self.assertTrue(conn.is_connected)
                rows = await conn.fetch()
                self.assertEqual(len(rows), 3)
            self.assertFalse(conn.is_connected)

        asyncio.run(use_context())


class TestFileConnector(unittest.TestCase):
    """测试 FileConnector"""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="fuxi_test_files_")

        # 创建测试文件
        cls.test_files = {
            "readme.md": "# 测试文档\n\n这是一个 **Markdown** 测试文件。\n\n## 第二节\n\n更多内容在这里。",
            "config.json": json.dumps({
                "name": "测试配置",
                "version": "1.0",
                "settings": {"debug": True, "port": 8080}
            }, ensure_ascii=False),
            "data.csv": "name,age,city\n张三,30,北京\n李四,25,上海\n王五,28,深圳",
            "notes.txt": "纯文本测试文件。\n第二行内容。\n第三行。",
        }

        for filename, content in cls.test_files.items():
            filepath = os.path.join(cls.temp_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        self.config = ConnectorConfig(
            name="测试文件目录",
            source_type=SourceType.FILE,
            extra={
                "root_path": self.temp_dir,
                "patterns": ["*"],
                "recursive": False,
            }
        )
        self.connector = FileConnector(self.config)

    def test_connect_valid_path(self):
        """连接有效路径"""
        result = asyncio.run(self.connector.connect())
        self.assertTrue(result)

    def test_connect_invalid_path(self):
        """连接无效路径"""
        bad_config = ConnectorConfig(
            name="bad",
            source_type=SourceType.FILE,
            extra={"root_path": "/nonexistent/path/12345"},
        )
        connector = FileConnector(bad_config)
        with self.assertRaises(ConnectionError):
            asyncio.run(connector.connect())

    def test_fetch_files(self):
        """扫描文件"""
        asyncio.run(self.connector.connect())

        files = asyncio.run(self.connector.fetch())
        self.assertGreaterEqual(len(files), 4)

        filenames = {f["name"] for f in files}
        for expected in self.test_files.keys():
            self.assertIn(expected, filenames)

    def test_fetch_with_pattern(self):
        """按模式过滤文件"""
        asyncio.run(self.connector.connect())

        files = asyncio.run(self.connector.fetch(patterns=["*.md"]))
        self.assertGreaterEqual(len(files), 1)
        for f in files:
            self.assertTrue(f["name"].endswith(".md"))

    def test_transform_files(self):
        """文件内容转换"""
        asyncio.run(self.connector.connect())
        files = asyncio.run(self.connector.fetch())

        docs = asyncio.run(self.connector.transform(files))
        self.assertGreaterEqual(len(docs), 3)

        titles = {d.title for d in docs}
        self.assertIn("readme", titles)

        # 验证 Markdown 文件内容
        md_doc = next((d for d in docs if d.title == "readme"), None)
        self.assertIsNotNone(md_doc)
        self.assertIn("测试文档", md_doc.content)

    def test_transform_empty(self):
        """空文件列表转换"""
        docs = asyncio.run(self.connector.transform([]))
        self.assertEqual(len(docs), 0)

    def test_stats(self):
        """统计信息"""
        asyncio.run(self.connector.connect())
        asyncio.run(self.connector.ingest())

        stats = self.connector.stats
        self.assertIn("files_found", stats)
        self.assertIn("files_processed", stats)
        self.assertIn("doc_count", stats)


class TestConnectorManager(unittest.TestCase):
    """测试 ConnectorManager"""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="fuxi_test_mgr_")
        cls.db_path = os.path.join(cls.temp_dir, "test.db")

        import sqlite3
        conn = sqlite3.connect(cls.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS docs (
                id INTEGER PRIMARY KEY,
                title TEXT,
                content TEXT
            )
        """)
        cursor.execute(
            "INSERT INTO docs VALUES (1, 'Doc1', 'Content1')"
        )
        conn.commit()
        conn.close()

        # 创建测试文件
        test_file = os.path.join(cls.temp_dir, "test.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Hello World")

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        self.manager = ConnectorManager(max_concurrency=3)

        # 注册 DB 连接器
        db_config = ConnectorConfig(
            name="DB-Test",
            source_type=SourceType.DATABASE,
            extra={
                "db_type": "sqlite",
                "db_path": self.db_path,
                "table_name": "docs",
            }
        )
        self.db_connector = DatabaseConnector(db_config)
        self.manager.register(self.db_connector)

        # 注册文件连接器
        file_config = ConnectorConfig(
            name="File-Test",
            source_type=SourceType.FILE,
            extra={
                "root_path": self.temp_dir,
                "patterns": ["*.txt"],
            }
        )
        self.file_connector = FileConnector(file_config)
        self.manager.register(self.file_connector)

    def tearDown(self):
        asyncio.run(self.manager.disconnect_all())

    def test_register_and_list(self):
        """注册与列表"""
        names = self.manager.list_connectors()
        self.assertEqual(len(names), 2)
        self.assertIn("DB-Test", names)
        self.assertIn("File-Test", names)

    def test_register_duplicate(self):
        """重复注册应抛出异常"""
        with self.assertRaises(ValueError):
            self.manager.register(self.db_connector)

    def test_get_connector(self):
        """获取连接器"""
        conn = self.manager.get("DB-Test")
        self.assertIsNotNone(conn)
        self.assertIsInstance(conn, DatabaseConnector)

        conn = self.manager.get("Nonexistent")
        self.assertIsNone(conn)

    def test_unregister(self):
        """注销连接器"""
        removed = self.manager.unregister("File-Test")
        self.assertIsNotNone(removed)
        self.assertEqual(removed.name, "File-Test")

        names = self.manager.list_connectors()
        self.assertNotIn("File-Test", names)

        # 重新注册以便 tearDown 清理
        self.manager.register(self.file_connector)

    def test_connect_all(self):
        """批量连接"""
        results = asyncio.run(self.manager.connect_all())
        self.assertEqual(len(results), 2)
        self.assertTrue(results["DB-Test"])
        self.assertTrue(results["File-Test"])

    def test_ingest_single(self):
        """单个连接器接入"""
        docs = asyncio.run(self.manager.ingest("DB-Test"))
        self.assertGreaterEqual(len(docs), 1)

    def test_ingest_nonexistent(self):
        """接入未注册连接器"""
        with self.assertRaises(ValueError):
            asyncio.run(self.manager.ingest("Ghost"))

    def test_ingest_all(self):
        """批量接入"""
        results = asyncio.run(self.manager.ingest_all())

        self.assertIn("DB-Test", results)
        self.assertIn("File-Test", results)
        self.assertGreaterEqual(len(results["DB-Test"]), 1)
        self.assertGreaterEqual(len(results["File-Test"]), 1)

    def test_stats(self):
        """管理器统计"""
        asyncio.run(self.manager.ingest_all())
        stats = self.manager.get_stats()

        self.assertEqual(stats["connector_count"], 2)
        self.assertGreaterEqual(stats["total_documents"], 1)
        self.assertIn("connectors", stats)
        self.assertIn("DB-Test", stats["connectors"])
        self.assertIn("File-Test", stats["connectors"])

    def test_health_check(self):
        """健康检查"""
        health = asyncio.run(self.manager.health_check())
        self.assertIn("DB-Test", health)
        self.assertIn("File-Test", health)

    def test_callbacks(self):
        """回调事件测试"""
        callback_results = []

        async def on_complete(connector, document_count):
            callback_results.append((connector.name, document_count))

        self.manager.on_ingest_complete(on_complete)
        asyncio.run(self.manager.ingest("DB-Test"))
        self.assertEqual(len(callback_results), 1)
        self.assertEqual(callback_results[0][0], "DB-Test")

    def test_disconnect_all(self):
        """全部断开"""
        asyncio.run(self.manager.connect_all())
        asyncio.run(self.manager.disconnect_all())

        self.assertEqual(self.manager.connector_count, 0)

    def test_get_stats_initial(self):
        """初始统计"""
        stats = self.manager.get_stats()
        self.assertEqual(stats["connector_count"], 2)
        self.assertEqual(stats["total_documents"], 0)
        self.assertEqual(stats["total_errors"], 0)


class TestErrorHandling(unittest.TestCase):
    """错误处理与边界情况"""

    def test_connection_error(self):
        """连接错误"""
        error = ConnectionError("TestSource", "网络不可达")
        self.assertIn("TestSource", str(error))
        self.assertIn("网络不可达", str(error))
        self.assertEqual(error.source_name, "TestSource")

    def test_fetch_error(self):
        """获取错误"""
        error = FetchError("APISource", "超时")
        self.assertEqual(error.source_name, "APISource")
        self.assertIn("超时", str(error))

    def test_transform_error(self):
        """转换错误"""
        error = TransformError("FileSource", "格式不支持")
        self.assertEqual(error.source_name, "FileSource")
        self.assertIn("格式不支持", str(error))

    def test_connector_error_state(self):
        """连接器错误状态"""
        config = ConnectorConfig(
            name="error-test",
            source_type=SourceType.FILE,
            extra={"root_path": "/nonexistent/path"},
        )
        connector = FileConnector(config)

        with self.assertRaises(ConnectionError):
            asyncio.run(connector.connect())

        self.assertEqual(connector.status, ConnectorStatus.ERROR)
        self.assertIsNotNone(connector.last_error)

    def test_disconnect_unconnected(self):
        """断开未连接的连接器"""
        config = ConnectorConfig(
            name="never-connected",
            source_type=SourceType.FILE,
            extra={"root_path": "."},
        )
        connector = FileConnector(config)
        # 不断开不应报错
        asyncio.run(connector.disconnect())
        self.assertEqual(connector.status, ConnectorStatus.DISCONNECTED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
