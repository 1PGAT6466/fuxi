"""
api_connector.py — REST API 连接器
==================================
通过 HTTP 请求接入 REST API 数据源。
支持 GET/POST 请求、分页、认证头和速率限制。
"""
import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

import aiohttp

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


class APIConnector(DataSource):
    """
    APIConnector — REST API 知识接入连接器

    通过 HTTP 请求接入外部 API 数据源，自动处理：
    - Bearer/ApiKey 认证
    - 分页（cursor 和 offset 两种模式）
    - 速率限制与重试
    - JSON 响应解析

    配置示例::

        config = ConnectorConfig(
            name="Confluence 知识库 API",
            source_type=SourceType.API,
            timeout=30,
            retry_count=3,
            headers={"User-Agent": "Fuxi-Ingestion/1.44"},
            extra={
                "base_url": "https://wiki.example.com/rest/api",
                "endpoint": "/content",
                "auth_type": "bearer",
                "auth_token": "your-token-here",
                "pagination": {
                    "mode": "offset",
                    "limit_param": "limit",
                    "offset_param": "start",
                    "page_size": 50,
                },
            }
        )
        connector = APIConnector(config)
        docs = await connector.ingest()
    """

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self._session: Optional[aiohttp.ClientSession] = None
        self._base_url: str = ""
        self._last_request_time: float = 0.0
        self._rate_limit_delay: float = 0.0

    async def connect(self) -> bool:
        """
        初始化 HTTP 会话并验证 API 可达性。

        Returns:
            bool: 连接成功返回 True

        Raises:
            ConnectionError: 验证失败时抛出
        """
        self._set_status(ConnectorStatus.CONNECTING)

        try:
            self._validate_config(["base_url"])
            self._base_url = self.config.extra["base_url"].rstrip("/")

            # 构建请求头
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                **self.config.headers,
            }
            headers.update(self.config.extra.get("headers", {}))

            # 处理认证
            auth_type = self.config.extra.get("auth_type", "").lower()
            if auth_type == "bearer":
                if "auth_token" in self.config.extra:
                    headers["Authorization"] = f"Bearer {self.config.extra['auth_token']}"
            elif auth_type == "apikey":
                api_key = self.config.extra.get("api_key", "")
                key_header = self.config.extra.get("api_key_header", "X-API-Key")
                if api_key:
                    headers[key_header] = api_key
            elif auth_type == "basic":
                import base64
                username = self.config.extra.get("username", "")
                password = self.config.extra.get("password", "")
                token = base64.b64encode(f"{username}:{password}".encode()).decode()
                headers["Authorization"] = f"Basic {token}"

            # 速率限制
            self._rate_limit_delay = self.config.extra.get("rate_limit_delay", 0.2)

            # 创建 aiohttp 会话
            connector = aiohttp.TCPConnector(
                limit=10,
                ttl_dns_cache=300,
                force_close=False,
            )
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(
                headers=headers,
                connector=connector,
                timeout=timeout,
            )

            # 健康检查：尝试访问 base_url
            try:
                health_url = self.config.extra.get(
                    "health_endpoint",
                    self._base_url
                )
                async with self._session.get(
                    health_url,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status >= 500:
                        raise ConnectionError(
                            self.name,
                            f"API 服务器返回 {resp.status}"
                        )
            except asyncio.TimeoutError:
                logger.warning(
                    "[%s] 健康检查超时，继续连接（不影响接入流程）",
                    self.name
                )
            except aiohttp.ClientError as e:
                logger.warning(
                    "[%s] 健康检查异常: %s，继续连接",
                    self.name, str(e)
                )

            self._set_status(ConnectorStatus.CONNECTED)
            logger.info("[%s] API 连接就绪 (base_url: %s)", self.name, self._base_url)
            return True

        except ConnectionError:
            self._set_error(str(ConnectionError))
            raise
        except Exception as e:
            self._set_error(str(e))
            raise ConnectionError(self.name, str(e))

    async def fetch(self, **kwargs) -> List[Dict[str, Any]]:
        """
        从 API 获取数据，自动处理分页。

        Args:
            **kwargs: 可选参数
                - endpoint: API 端点路径（覆盖配置中的 endpoint）
                - params: URL 查询参数字典
                - method: HTTP 方法 (GET/POST，默认 GET)
                - body: POST 请求体
                - max_pages: 最大分页数（0 表示不限制）

        Returns:
            List[Dict[str, Any]]: API 响应数据列表

        Raises:
            FetchError: 请求失败时抛出
        """
        if not self._session or not self.is_connected:
            raise FetchError(self.name, "API 未连接，请先调用 connect()")

        endpoint = kwargs.get(
            "endpoint",
            self.config.extra.get("endpoint", "")
        )
        params = kwargs.get("params", self.config.extra.get("params", {}))
        method = kwargs.get("method", "GET").upper()
        body = kwargs.get("body")
        max_pages = kwargs.get("max_pages", self.config.extra.get("max_pages", 10))

        url = self._build_url(endpoint)

        try:
            pagination = self.config.extra.get("pagination", {})
            if not pagination or max_pages == 1:
                # 单次请求，不分页
                data, _ = await self._make_request(
                    url, method=method, params=params, body=body
                )
                items = self._extract_items(data)
                logger.info("[%s] 获取 %d 条数据 (单页)", self.name, len(items))
                return items
            else:
                # 分页请求
                return await self._fetch_paginated(
                    url, method, params, body, pagination, max_pages
                )

        except FetchError:
            raise
        except Exception as e:
            raise FetchError(self.name, str(e))

    async def _fetch_paginated(
        self,
        url: str,
        method: str,
        params: Dict,
        body: Optional[Dict],
        pagination: Dict,
        max_pages: int,
    ) -> List[Dict[str, Any]]:
        """分页获取所有数据"""
        all_items = []
        page = 0
        next_cursor = pagination.get("cursor_start", "")
        page_size = pagination.get("page_size", 50)
        pag_mode = pagination.get("mode", "offset")

        while max_pages <= 0 or page < max_pages:
            page_params = dict(params)

            if pag_mode == "cursor":
                cursor_param = pagination.get("cursor_param", "cursor")
                if next_cursor:
                    page_params[cursor_param] = next_cursor

            elif pag_mode == "offset":
                offset_param = pagination.get("offset_param", "offset")
                limit_param = pagination.get("limit_param", "limit")
                page_params[offset_param] = page * page_size
                page_params[limit_param] = page_size

            data, response_headers = await self._make_request(
                url, method=method, params=page_params, body=body
            )

            items = self._extract_items(data)
            all_items.extend(items)
            page += 1

            if len(items) < page_size:
                # 最后一页
                break

            # 解析下一页游标
            if pag_mode == "cursor":
                next_cursor_path = pagination.get("next_cursor_path", "next_cursor")
                cursor_response = data.get(next_cursor_path, "")
                if cursor_response:
                    next_cursor = cursor_response
                else:
                    # 尝试从响应头获取
                    next_header = pagination.get("next_header", "Link")
                    next_cursor = response_headers.get(next_header, "")
                if not next_cursor:
                    break

            # 速率限制等待
            await asyncio.sleep(self._rate_limit_delay)

        logger.info(
            "[%s] 分页获取完成: %d 页, %d 条数据",
            self.name, page, len(all_items)
        )
        return all_items

    async def _make_request(
        self,
        url: str,
        method: str = "GET",
        params: Optional[Dict] = None,
        body: Optional[Dict] = None,
    ) -> tuple:
        """执行 HTTP 请求，带重试逻辑"""
        if not self._session:
            raise FetchError(self.name, "HTTP 会话未初始化")

        last_error = None
        for attempt in range(self.config.retry_count + 1):
            try:
                # 速率限制
                elapsed = time.time() - self._last_request_time
                if elapsed < self._rate_limit_delay:
                    await asyncio.sleep(self._rate_limit_delay - elapsed)

                async with self._session.request(
                    method,
                    url,
                    params=params,
                    json=body if method in ("POST", "PUT", "PATCH") else None,
                ) as resp:
                    response_headers = dict(resp.headers)

                    if resp.status == 429:
                        retry_after = int(resp.headers.get("Retry-After", 5))
                        logger.warning(
                            "[%s] 触发速率限制 (429)，等待 %ds (第 %d/%d 次重试)",
                            self.name, retry_after, attempt + 1, self.config.retry_count
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    if resp.status >= 500 and attempt < self.config.retry_count:
                        delay = self.config.retry_delay * (2 ** attempt)
                        logger.warning(
                            "[%s] 服务器错误 %d，%s 后重试 (第 %d/%d 次)",
                            self.name, resp.status, delay, attempt + 1,
                            self.config.retry_count
                        )
                        await asyncio.sleep(delay)
                        continue

                    if resp.status >= 400:
                        text = await resp.text()
                        raise FetchError(
                            self.name,
                            f"HTTP {resp.status}: {text[:500]}"
                        )

                    data = await resp.json()
                    self._last_request_time = time.time()
                    return data, response_headers

            except aiohttp.ClientError as e:
                last_error = e
                if attempt < self.config.retry_count:
                    delay = self.config.retry_delay * (2 ** attempt)
                    logger.warning(
                        "[%s] 请求失败: %s，%s 后重试 (第 %d/%d 次)",
                        self.name, str(e), delay, attempt + 1,
                        self.config.retry_count
                    )
                    await asyncio.sleep(delay)
                else:
                    raise FetchError(self.name, str(e))

        raise FetchError(self.name, str(last_error or "未知错误"))

    def _build_url(self, endpoint: str) -> str:
        """构建完整 URL"""
        if not endpoint:
            return self._base_url
        if endpoint.startswith("http"):
            return endpoint
        return f"{self._base_url}/{endpoint.lstrip('/')}"

    def _extract_items(self, data: Any) -> List[Dict[str, Any]]:
        """
        从 API 响应中提取数据项列表。

        支持多种常见响应格式：
        - data 直接是列表
        - data["data"] 是列表
        - data["results"] 是列表
        - data["items"] 是列表

        Args:
            data: API 响应数据

        Returns:
            List[Dict[str, Any]]: 提取的数据项列表
        """
        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            items_key = self.config.extra.get(
                "items_key",
                self.config.extra.get("results_key", "")
            )
            if not items_key:
                # 自动探测
                for key in ("data", "results", "items", "records", "content"):
                    if key in data:
                        items = data[key]
                        if isinstance(items, list):
                            return items
                        if isinstance(items, dict):
                            # 可能是 {items: [...], total: N} 格式
                            for subkey in ("data", "results", "items"):
                                if subkey in items and isinstance(items[subkey], list):
                                    return items[subkey]
            else:
                items = data.get(items_key, [])
                if isinstance(items, list):
                    return items

            # 如果整个响应字典就是一条记录
            return [data]

        return []

    async def transform(self, raw_data: List[Dict[str, Any]]) -> List[UnifiedDocument]:
        """
        将 API 响应数据转换为统一文档格式。

        Args:
            raw_data: API 返回的原始数据项列表

        Returns:
            List[UnifiedDocument]: 统一文档列表

        Raises:
            TransformError: 转换失败时抛出
        """
        if not raw_data:
            return []

        try:
            documents = []
            # 获取字段映射规则
            field_map = self.config.extra.get("field_mapping", {})

            for idx, item in enumerate(raw_data):
                if not isinstance(item, dict):
                    # 非字典项转为字符串
                    doc = UnifiedDocument(
                        title=f"API 记录 #{idx + 1}",
                        content=str(item),
                        source_type=SourceType.API,
                        source_url=self._base_url,
                        metadata={
                            "connector": self.name,
                            "api_url": self._base_url,
                            "item_index": idx,
                        },
                    )
                    documents.append(doc)
                    continue

                # 根据字段映射提取内容
                title = (
                    field_map.get("title") and item.get(field_map["title"])
                    or item.get("title")
                    or item.get("name")
                    or item.get("subject")
                    or item.get("id", "")
                    or f"API 记录 #{idx + 1}"
                )

                content_fields = field_map.get("content", [])
                if content_fields:
                    content = "\n".join(
                        str(item.get(f, ""))
                        for f in content_fields
                        if f in item
                    )
                else:
                    # 自动：把所有可读字段拼接为文本
                    content = json.dumps(item, ensure_ascii=False, indent=2)

                url_key = field_map.get("url")
                source_url = (
                    url_key and item.get(url_key, "")
                    or item.get("url", "")
                    or item.get("href", "")
                    or item.get("link", "")
                    or self._base_url
                )

                doc = UnifiedDocument(
                    title=str(title),
                    content=str(content),
                    source_type=SourceType.API,
                    source_url=str(source_url),
                    metadata={
                        "connector": self.name,
                        "api_url": self._base_url,
                        "item_index": idx,
                        "original_keys": list(item.keys()),
                        "raw": item,
                    },
                    tags=item.get("tags", item.get("labels", [])),
                    language="zh",
                )
                documents.append(doc)

            logger.info(
                "[%s] 转换完成: %d 条 → %d 个文档",
                self.name, len(raw_data), len(documents)
            )
            return documents

        except Exception as e:
            raise TransformError(self.name, str(e))

    async def disconnect(self) -> None:
        """关闭 HTTP 会话，释放连接"""
        try:
            if self._session and not self._session.closed:
                await self._session.close()
                self._session = None
        except Exception as e:
            logger.warning("[%s] 关闭会话时出错: %s", self.name, str(e))
        finally:
            self._set_status(ConnectorStatus.DISCONNECTED)

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
