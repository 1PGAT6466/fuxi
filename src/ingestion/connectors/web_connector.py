"""
web_connector.py — 网页爬取连接器
================================
支持从指定 URL/域名爬取网页内容，提取文本并转换为统一文档格式。
实现特性：robots.txt 合规检查、速率限制、HTML 清洗、同源策略。
"""
import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

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


class WebConnector(DataSource):
    """
    WebConnector — 网页爬取知识接入连接器

    从网页中提取文本内容，自动去除导航栏、广告、脚本等非内容元素。

    特性：
    - robots.txt 合规检查
    - 可配置爬取深度和最大页数
    - 自动 HTML 清洗（去除 script/style/nav 等）
    - 速率限制（请求间隔控制）
    - 同源策略（默认只爬取相同域名）

    配置示例::

        config = ConnectorConfig(
            name="技术博客爬虫",
            source_type=SourceType.WEB,
            headers={"User-Agent": "Fuxi-Bot/1.44"},
            extra={
                "start_urls": ["https://docs.example.com/"],
                "max_pages": 50,
                "max_depth": 3,
                "crawl_delay": 1.0,
                "same_domain_only": True,
                "follow_robots_txt": True,
            }
        )
        connector = WebConnector(config)
        docs = await connector.ingest()
    """

    # 需要去除的 HTML 标签
    _REMOVE_TAGS = {
        "script", "style", "nav", "footer", "header",
        "aside", "noscript", "iframe", "form",
        "button", "input", "select", "textarea",
    }

    # 需要去除的 CSS class/id 关键词
    _REMOVE_CLASS_PATTERNS = [
        r"nav", r"menu", r"sidebar", r"footer", r"header",
        r"advertisement", r"ad-", r"banner", r"popup",
        r"cookie", r"social", r"comment", r"related",
    ]

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self._session: Optional[aiohttp.ClientSession] = None
        self._visited_urls: Set[str] = set()
        self._allowed_domains: Set[str] = set()
        self._robots_allowed: bool = True
        self._disallowed_paths: List[str] = []
        self._crawl_delay: float = 1.0
        self._pages_crawled: int = 0
        self._pages_failed: int = 0

    async def connect(self) -> bool:
        """
        初始化 HTTP 会话并检查 robots.txt。

        Returns:
            bool: 初始化成功返回 True

        Raises:
            ConnectionError: 创建会话失败时抛出
        """
        self._set_status(ConnectorStatus.CONNECTING)

        try:
            self._validate_config(["start_urls"])
            start_urls = self.config.extra["start_urls"]
            if isinstance(start_urls, str):
                start_urls = [start_urls]

            # 收集允许的域名
            for url in start_urls:
                domain = urlparse(url).netloc
                if domain:
                    self._allowed_domains.add(domain)

            # 爬取参数
            self._crawl_delay = self.config.extra.get(
                "crawl_delay", 1.0
            )
            self._robots_allowed = self.config.extra.get(
                "follow_robots_txt", True
            )

            # 检查 robots.txt
            if self._robots_allowed and self._allowed_domains:
                for domain in list(self._allowed_domains):
                    try:
                        await self._check_robots_txt(domain)
                    except Exception as e:
                        logger.warning(
                            "[%s] robots.txt 检查失败 (%s): %s",
                            self.name, domain, str(e)
                        )

            # 创建 aiohttp 会话
            headers = {
                "User-Agent": "Fuxi-Ingestion/1.44",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                **self.config.headers,
            }

            connector = aiohttp.TCPConnector(
                limit=5,
                force_close=True,
                enable_cleanup_closed=True,
            )
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(
                headers=headers,
                connector=connector,
                timeout=timeout,
            )

            self._set_status(ConnectorStatus.CONNECTED)
            logger.info(
                "[%s] 网页爬虫就绪 (起始 URL: %d 个, 延迟: %.1fs)",
                self.name, len(start_urls), self._crawl_delay
            )
            return True

        except ConnectionError:
            raise
        except Exception as e:
            self._set_error(str(e))
            raise ConnectionError(self.name, str(e))

    async def _check_robots_txt(self, domain: str) -> None:
        """检查并解析 robots.txt"""
        robots_url = f"http://{domain}/robots.txt"
        try:
            async with self._session.get(
                robots_url,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    content = await resp.text()
                    await self._parse_robots_txt(content)
                    logger.info(
                        "[%s] robots.txt 已加载 (%s)",
                        self.name, domain
                    )
        except Exception:
            logger.debug(
                "[%s] 无法获取 robots.txt (%s)，允许所有路径",
                self.name, domain
            )

    async def _parse_robots_txt(self, content: str) -> None:
        """解析 robots.txt 内容"""
        user_agent_match = None
        for line in content.splitlines():
            line = line.strip().lower()

            if line.startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip()
                user_agent_match = (
                    agent == "*"
                    or "fuxi" in agent
                    or "bot" in agent
                )
                continue

            if user_agent_match and line.startswith("disallow:"):
                path = line.split(":", 1)[1].strip()
                if path:
                    self._disallowed_paths.append(path)

            if user_agent_match and line.startswith("crawl-delay:"):
                try:
                    delay = float(line.split(":", 1)[1].strip())
                    self._crawl_delay = max(self._crawl_delay, delay)
                except ValueError:
                    pass

    async def fetch(self, **kwargs) -> List[Dict[str, Any]]:
        """
        爬取网页并提取内容。

        Args:
            **kwargs: 可选参数
                - urls: 手动指定 URL 列表（覆盖 start_urls）
                - max_pages: 最大爬取页数
                - max_depth: 最大爬取深度

        Returns:
            List[Dict[str, Any]]: 网页内容列表
                [{"url": str, "title": str, "html": str, "text": str}, ...]

        Raises:
            FetchError: 爬取失败时抛出
        """
        if not self._session or not self.is_connected:
            raise FetchError(self.name, "网页爬虫未连接，请先调用 connect()")

        start_urls = kwargs.get(
            "urls",
            self.config.extra.get("start_urls", [])
        )
        if isinstance(start_urls, str):
            start_urls = [start_urls]

        max_pages = kwargs.get(
            "max_pages",
            self.config.extra.get("max_pages", 100)
        )
        max_depth = kwargs.get(
            "max_depth",
            self.config.extra.get("max_depth", 3)
        )
        same_domain = self.config.extra.get("same_domain_only", True)

        try:
            results = []
            self._visited_urls.clear()
            self._pages_crawled = 0
            self._pages_failed = 0

            # BFS 爬取
            url_queue: List[tuple] = [
                (url, 0) for url in start_urls
            ]

            while url_queue and self._pages_crawled < max_pages:
                url, depth = url_queue.pop(0)

                if url in self._visited_urls:
                    continue
                if depth > max_depth:
                    continue
                if not self._is_allowed(url, same_domain):
                    continue

                self._visited_urls.add(url)

                # 速率限制
                await asyncio.sleep(self._crawl_delay)

                result = await self._crawl_page(url)
                if result:
                    results.append(result)
                    self._pages_crawled += 1

                    # 提取页面中的链接加入队列
                    if depth < max_depth:
                        links = await self._extract_links(
                            result["html"], url, same_domain
                        )
                        for link in links:
                            if link not in self._visited_urls:
                                url_queue.append((link, depth + 1))
                else:
                    self._pages_failed += 1

            logger.info(
                "[%s] 爬取完成: %d 成功, %d 失败",
                self.name, self._pages_crawled, self._pages_failed
            )
            return results

        except Exception as e:
            raise FetchError(self.name, str(e))

    async def _crawl_page(self, url: str) -> Optional[Dict[str, Any]]:
        """爬取单个页面"""
        try:
            async with self._session.get(url) as resp:
                if resp.status != 200:
                    logger.debug(
                        "[%s] HTTP %d: %s",
                        self.name, resp.status, url
                    )
                    return None

                content_type = resp.headers.get("Content-Type", "")
                if "text/html" not in content_type.lower():
                    logger.debug(
                        "[%s] 跳过非 HTML: %s (%s)",
                        self.name, url, content_type
                    )
                    return None

                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")

                # 提取标题
                title = ""
                title_tag = soup.find("title")
                if title_tag:
                    title = title_tag.get_text(strip=True)
                else:
                    h1 = soup.find("h1")
                    if h1:
                        title = h1.get_text(strip=True)

                # 清洗 HTML
                self._clean_soup(soup)

                # 提取文本
                text = self._extract_text(soup)

                return {
                    "url": url,
                    "title": title,
                    "html": str(soup),
                    "text": text,
                }

        except asyncio.TimeoutError:
            logger.warning("[%s] 超时: %s", self.name, url)
            return None
        except aiohttp.ClientError as e:
            logger.debug("[%s] 请求失败 %s: %s", self.name, url, str(e))
            return None
        except Exception as e:
            logger.warning("[%s] 爬取异常 %s: %s", self.name, url, str(e))
            return None

    def _clean_soup(self, soup: BeautifulSoup) -> None:
        """清洗 HTML DOM，去除非内容元素"""
        # 去除不相关标签
        for tag_name in self._REMOVE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # 根据 class/id 去除广告、导航等
        for pattern in self._REMOVE_CLASS_PATTERNS:
            regex = re.compile(pattern, re.IGNORECASE)
            for tag in soup.find_all(
                class_=regex
            ):
                tag.decompose()
            for tag in soup.find_all(
                id=regex
            ):
                tag.decompose()

        # 去除空标签
        for tag in soup.find_all():
            if not tag.get_text(strip=True) and tag.name not in (
                "br", "hr", "img", "input", "meta", "link"
            ):
                tag.decompose()

    def _extract_text(self, soup: BeautifulSoup) -> str:
        """从清洗后的 DOM 提取纯文本"""
        # 获取 body 内容
        body = soup.find("body")
        if not body:
            body = soup

        # 替换换行标签
        for br in body.find_all("br"):
            br.replace_with("\n")
        for p in body.find_all("p"):
            p.append("\n")
        for li in body.find_all("li"):
            li.append("\n")
        for div in body.find_all("div"):
            div.append("\n")

        text = body.get_text(separator="\n", strip=True)

        # 压缩多余空行
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)

        return text.strip()

    async def _extract_links(
        self, html: str, base_url: str, same_domain: bool
    ) -> List[str]:
        """从 HTML 中提取链接"""
        soup = BeautifulSoup(html, "html.parser")
        links = []
        base_domain = urlparse(base_url).netloc

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            # 跳过空链接、锚点、javascript
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)

            # 只保留 http/https
            if parsed.scheme not in ("http", "https"):
                continue

            # 同源检查
            if same_domain and parsed.netloc != base_domain:
                continue

            # 去重和规范化
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if clean_url not in self._visited_urls:
                links.append(clean_url)

        return links

    def _is_allowed(self, url: str, same_domain: bool) -> bool:
        """检查 URL 是否允许爬取"""
        parsed = urlparse(url)

        # 同源检查
        if same_domain and self._allowed_domains:
            if parsed.netloc not in self._allowed_domains:
                return False

        # robots.txt 合规检查
        if self._disallowed_paths:
            path = parsed.path or "/"
            for disallowed in self._disallowed_paths:
                if path.startswith(disallowed):
                    logger.debug(
                        "[%s] robots.txt 禁止: %s",
                        self.name, url
                    )
                    return False

        return True

    async def transform(self, raw_data: List[Dict[str, Any]]) -> List[UnifiedDocument]:
        """
        将爬取的网页内容转换为统一文档格式。

        Args:
            raw_data: crawl() 返回的网页内容列表

        Returns:
            List[UnifiedDocument]: 统一文档列表

        Raises:
            TransformError: 转换失败时抛出
        """
        if not raw_data:
            return []

        try:
            documents = []
            for page in raw_data:
                title = page.get("title", "")
                text = page.get("text", "")

                if not text or len(text.strip()) < 50:
                    logger.debug(
                        "[%s] 页面内容过短，跳过: %s",
                        self.name, page.get("url", "")
                    )
                    continue

                doc = UnifiedDocument(
                    title=title or "无标题页面",
                    content=text,
                    source_type=SourceType.WEB,
                    source_url=page.get("url", ""),
                    metadata={
                        "connector": self.name,
                        "page_url": page.get("url", ""),
                        "crawl_time": time.time(),
                        "content_length": len(text),
                    },
                    language="zh",
                )
                documents.append(doc)

            logger.info(
                "[%s] 转换完成: %d 页 → %d 个文档",
                self.name, len(raw_data), len(documents)
            )
            return documents

        except Exception as e:
            raise TransformError(self.name, str(e))

    async def disconnect(self) -> None:
        """关闭 HTTP 会话"""
        try:
            if self._session and not self._session.closed:
                await self._session.close()
                self._session = None
        except Exception as e:
            logger.warning("[%s] 关闭会话时出错: %s", self.name, str(e))
        finally:
            self._visited_urls.clear()
            self._disallowed_paths.clear()
            self._set_status(ConnectorStatus.DISCONNECTED)

    @property
    def stats(self) -> Dict[str, Any]:
        base_stats = super().stats
        base_stats.update({
            "pages_crawled": self._pages_crawled,
            "pages_failed": self._pages_failed,
            "visited_urls": len(self._visited_urls),
        })
        return base_stats

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
