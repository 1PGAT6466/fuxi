"""
ingestion — 伏羲多源知识接入模块 v1.44
=====================================
提供统一的多源数据接入能力，支持：
- 数据库接入 (DatabaseConnector)
- REST API 接入 (APIConnector)
- 文件系统接入 (FileConnector)
- 网页爬取接入 (WebConnector)

所有连接器通过 ConnectorManager 统一管理和调度。
"""

from .connectors import (
    DataSource,
    DatabaseConnector,
    APIConnector,
    FileConnector,
    WebConnector,
    ConnectorManager,
)

__all__ = [
    "DataSource",
    "DatabaseConnector",
    "APIConnector",
    "FileConnector",
    "WebConnector",
    "ConnectorManager",
]
