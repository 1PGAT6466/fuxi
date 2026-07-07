#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xun.py — 巽卦 ☴ · 伏羲 v2.1

巽为风，主数据接入与管道。
对应能力：文档导入、ETL、多模态接入、数据管道编排。

v2.1 Phase 1: 融合皮肤(SkinAgent)外部搜索能力
  → Brave Search API 搜索、URL 内容抓取、交叉验证、结果缓存
  → 独立于 organs/ 目录，保留完整 aiohttp 网络调用逻辑
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import socket
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import ipaddress

import aiohttp

from src.bagua.base_gua import (
    GuaBase,
    DegradationRule,
    FallbackAction,
    CircuitState,
)

logger = logging.getLogger("bagua.xun")


class XunGua(GuaBase):
    """巽卦 ☴ — 数据接入与管道

    融合了皮肤(SkinAgent)的外部搜索与触角能力：
    - search_external: Brave Search API 外部搜索
    - fetch_url: URL 内容抓取（带 SSRF 防护）
    - cross_validate: 交叉验证外部内容与查询相关性
    - get_cache_stats: 缓存统计

    保留完整 aiohttp 异步网络调用逻辑。

    Usage::

        xun = XunGua()
        xun.start()

        # 外部搜索
        result = await xun.search_external("Python 3.12 release notes", top_k=5)

        # URL 抓取
        content = await xun.fetch_url("https://example.com")

        # 缓存统计
        stats = xun.get_cache_stats()

        xun.stop()
    """

    GUA_NAME = "xun"
    GUA_EMOJI = "☴"
    GUA_DESCRIPTION = "数据接入与管道 — 文档导入、ETL、多模态、外部搜索"

    # 缓存配置
    MAX_CACHE_SIZE: int = 100

    # Brave Search 配置
    BRAVE_SEARCH_URL: str = "https://api.search.brave.com/res/v1/web/search"
    DEFAULT_TOP_K: int = 5

    # 抓取配置
    FETCH_TIMEOUT: float = 15.0
    SEARCH_TIMEOUT: float = 10.0
    MAX_CONTENT_LENGTH: int = 2000

    # 交叉验证配置
    MIN_CONTENT_LENGTH: int = 50
    MIN_CROSS_VALIDATE_SCORE: float = 0.3

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        # 搜索统计
        self._search_count: int = 0

        # 结果缓存：{cache_key: [extracted_results]}
        self._cache: Dict[str, List[Dict[str, Any]]] = {}

        # 请求计数
        self._request_count: int = 0
        self._blocked_count: int = 0

        # HTTP 会话（延迟初始化）
        self._http_session: Optional[aiohttp.ClientSession] = None

    # ========================================================================
    # GuaBase 接口实现
    # ========================================================================

    def _setup_dependencies(self) -> None:
        """注册依赖：Brave Search API、网络连接"""
        self.register_dependency(
            "brave_search_api",
            failure_threshold=3,
            recovery_timeout=60.0,
            half_open_max_calls=2,
        )
        self.register_dependency(
            "network",
            failure_threshold=5,
            recovery_timeout=30.0,
            half_open_max_calls=3,
        )

    def _setup_degradation_rules(self) -> None:
        """定义降级规则"""

        # 规则 1: Brave Search API 不可用 → 返回缓存或空结果
        def brave_unavailable() -> bool:
            cb = self.get_dependency("brave_search_api")
            if cb is None:
                return False
            return not cb.is_healthy

        self.add_rule(DegradationRule(
            name="brave_api_degraded",
            condition_fn=brave_unavailable,
            fallback=FallbackAction(
                name="cache_or_empty_fallback",
                handler=self._search_fallback_handler,
                description="Brave API 不可用时返回缓存结果或空列表",
            ),
            priority=10,
        ))

        # 规则 2: 网络完全不可用 → 仅返回缓存
        def network_down() -> bool:
            cb = self.get_dependency("network")
            if cb is None:
                return False
            return not cb.is_healthy

        self.add_rule(DegradationRule(
            name="network_degraded",
            condition_fn=network_down,
            fallback=FallbackAction(
                name="cache_only_fallback",
                handler=self._search_fallback_handler,
                description="网络不可用时仅返回缓存结果",
            ),
            priority=20,
        ))

    def _execute_core(self, params: Dict[str, Any]) -> Any:
        """统一执行入口：按 operation 分发

        Supported operations:
            - "search": 执行 _search_internal()（本地 ChromaDB 向量检索）
            - "fetch": 执行 fetch_url()（同步入口，提示需异步调用）
            - "stats": 返回统计信息
            - "cache_stats": 返回缓存统计
            - "barrier_check": 检查安全屏障

        注意："search" operation 通过 execute() 同步调用 _search_internal()，
        乾卦 dispatch 时会自动将 payload 中的 operation 设为 "search"。
        """
        operation = params.get("operation", params.get("intent", "unknown"))

        if operation in ("search", "SEARCH"):
            # 本地 ChromaDB 向量检索（乾卦 SEARCH→巽 的核心路径）
            query = params.get("query", "")
            top_k = int(params.get("top_k", 5))
            collection = params.get("collection", None)
            return self._search_internal(query=query, top_k=top_k, collection=collection)

        elif operation == "fetch":
            return {
                "error": "fetch_url 是异步方法，请直接调用 instance.fetch_url()",
                "hint": "使用 await xun.fetch_url(url) 代替 execute()",
            }

        elif operation == "stats":
            return self.stats()

        elif operation == "cache_stats":
            return self.get_cache_stats()

        elif operation == "barrier_check":
            ip = params.get("ip", "")
            return {"result": self.barrier_check(ip)}

        else:
            # fallback: 兼容旧的 dispatch（只传 intent 不传 operation 的情况）
            intent = params.get("intent", "")
            if intent == "SEARCH":
                query = params.get("query", "")
                top_k = int(params.get("top_k", 5))
                return self._search_internal(query=query, top_k=top_k, collection=params.get("collection", None))
            raise ValueError("未知操作: %s" % operation)

    # ========================================================================
    # 本地 ChromaDB 向量检索（乾卦 SEARCH→巽 的核心检索路径）
    # ========================================================================

    @staticmethod
    def _search_internal(
        query: str,
        top_k: int = 5,
        collection: Optional[str] = None,
    ) -> Dict[str, Any]:
        """本地 ChromaDB 向量检索

        检索路径：乾卦 SEARCH 意图 → 巽卦 → VectorStore.query()
        → ChromaDB → 返回检索结果

        Args:
            query:      查询文本
            top_k:      返回结果数（默认 5）
            collection: 目标 collection 名称（默认使用 VectorStore 默认值）

        Returns:
            {
                "results": [{"text": "...", "source": "...", "score": ...}, ...],
                "total_matched": N,
                "ms": elapsed,
            }
        """
        start_time = time.time()
        if not query or not query.strip():
            elapsed = (time.time() - start_time) * 1000
            return {"results": [], "total_matched": 0, "ms": round(elapsed, 1)}

        try:
            from src.db.vector_store import VectorStore, COLLECTION_NAME
            from src.services.embedder import embed_text, cosine_sim
            import asyncio as _asyncio

            # 生成查询向量
            query_vec = _asyncio.run(embed_text(query.strip()))
            if not query_vec:
                elapsed = (time.time() - start_time) * 1000
                logger.warning("[巽卦] _search_internal: embed 返回空向量")
                return {"results": [], "total_matched": 0, "ms": round(elapsed, 1)}

            # 构建 VectorStore 实例
            col_name = collection or COLLECTION_NAME
            vs = VectorStore(collection_name=col_name)

            # 执行 ChromaDB 查询
            chroma_result = vs.query(
                query_embedding=query_vec,
                n_results=top_k,
            )

            if isinstance(chroma_result, dict) and chroma_result.get("error"):
                elapsed = (time.time() - start_time) * 1000
                logger.warning(
                    "[巽卦] _search_internal: ChromaDB query 失败: %s",
                    chroma_result.get("reason", "unknown"),
                )
                return {"results": [], "total_matched": 0, "ms": round(elapsed, 1)}

            # 格式化结果
            ids_list = chroma_result.get("ids", [[]])
            if ids_list and isinstance(ids_list, list) and len(ids_list) > 0:
                ids = ids_list[0] if isinstance(ids_list[0], list) else ids_list
            else:
                ids = []

            distances_list = chroma_result.get("distances", [[]])
            if distances_list and isinstance(distances_list, list) and len(distances_list) > 0:
                distances = distances_list[0] if isinstance(distances_list[0], list) else distances_list
            else:
                distances = []

            docs_list = chroma_result.get("documents", [[]])
            if docs_list and isinstance(docs_list, list) and len(docs_list) > 0:
                documents = docs_list[0] if isinstance(docs_list[0], list) else docs_list
            else:
                documents = []

            metas_list = chroma_result.get("metadatas", [[]])
            if metas_list and isinstance(metas_list, list) and len(metas_list) > 0:
                metadatas = metas_list[0] if isinstance(metas_list[0], list) else metas_list
            else:
                metadatas = []

            # 组装最终结果
            results: List[Dict[str, Any]] = []
            for i in range(len(ids)):
                doc = documents[i] if i < len(documents) else ""
                dist = distances[i] if i < len(distances) else 0.0
                meta = metadatas[i] if i < len(metadatas) else {}
                score = max(0.0, 1.0 - float(dist)) if isinstance(dist, (int, float)) else 0.0

                results.append({
                    "id": ids[i] if i < len(ids) else "",
                    "text": doc[:2000] if doc else "",
                    "source": meta.get("source", meta.get("file", "unknown")),
                    "score": round(score, 4),
                    "metadata": meta,
                })

            elapsed = (time.time() - start_time) * 1000
            logger.info(
                "[巽卦] _search_internal OK: query='%s' top_k=%d matched=%d ms=%.1f",
                query[:60], top_k, len(results), elapsed,
            )
            return {
                "results": results,
                "total_matched": len(results),
                "ms": round(elapsed, 1),
            }

        except ImportError as exc:
            elapsed = (time.time() - start_time) * 1000
            logger.warning("[巽卦] _search_internal ImportError: %s", exc)
            return {"results": [], "total_matched": 0, "ms": round(elapsed, 1)}
        except Exception as exc:
            elapsed = (time.time() - start_time) * 1000
            logger.error("[巽卦] _search_internal 异常: %s", exc, exc_info=True)
            return {"results": [], "total_matched": 0, "ms": round(elapsed, 1)}

    def _search_fallback_handler(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """搜索降级兜底：优先返回缓存结果"""
        query = params.get("query", "")
        cache_key = query.lower().strip()
        if cache_key in self._cache:
            if logger.isEnabledFor(logging.DEBUG):
                logger.info("[巽卦] 降级返回缓存结果: %s", query[:50])
            else:
                logger.info("[巽卦] 降级返回缓存结果: query_len=%d", len(query))
            return {"results": self._cache[cache_key], "from_cache": True, "degraded": True}
        return {"results": [], "error": "搜索服务降级中", "degraded": True}

    # ========================================================================
    # Brave Search 外部搜索（迁移自 SkinAgent.search_external）
    # ========================================================================

    async def search_external(
        self,
        query: str,
        top_k: int = 5,
        *,
        fetch_content: bool = True,
    ) -> Dict[str, Any]:
        """外部搜索：Brave Search API → 抓取 URL 内容 → 交叉验证

        完整保留原 SkinAgent.search_external 功能：
        1. 检查缓存
        2. 调用 Brave Search API
        3. 抓取前 N 条结果的 URL 内容
        4. 交叉验证内容与查询相关性
        5. 缓存高质量结果

        Args:
            query: 搜索查询字符串
            top_k: 返回结果数量上限（默认 5）
            fetch_content: 是否抓取 URL 内容（默认 True）

        Returns:
            {
                "results": [{"text": ..., "source_url": ..., "title": ..., "score": ...}, ...],
                "from_cache": bool,
            }
        """
        brave_cb = self.get_dependency("brave_search_api")

        # 检查缓存
        cache_key = query.lower().strip()
        if cache_key in self._cache:
            if logger.isEnabledFor(logging.DEBUG):
                logger.info("[巽卦·触角] Cache hit: %s", query[:50])
            else:
                logger.info("[巽卦·触角] Cache hit: query_len=%d", len(query))
            return {"results": self._cache[cache_key], "from_cache": True}

        try:
            # 获取 API Key
            api_key = os.getenv("BRAVE_API_KEY", "")
            search_results: List[Dict[str, str]] = []

            if api_key:
                session = await self._get_http_session()
                async with session.get(
                    self.BRAVE_SEARCH_URL,
                    params={"q": query, "count": min(top_k, 10)},
                    headers={
                        "X-Subscription-Token": api_key,
                        "Accept": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=self.SEARCH_TIMEOUT),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        search_results = [
                            {
                                "title": r.get("title", ""),
                                "url": r.get("url", ""),
                                "snippet": r.get("description", ""),
                            }
                            for r in data.get("web", {}).get("results", [])[:top_k]
                        ]

                        # 记录成功
                        if brave_cb is not None:
                            brave_cb.record_success()
                    else:
                        logger.warning(
                            "[巽卦·触角] Brave API 返回 %d: %s",
                            resp.status, query[:50],
                        )
                        if brave_cb is not None:
                            brave_cb.record_failure()

            # 抓取内容并交叉验证
            extracted: List[Dict[str, Any]] = []
            if fetch_content and search_results:
                network_cb = self.get_dependency("network")
                for sr in search_results[:3]:
                    url = sr.get("url", "")
                    if not url:
                        continue
                    content = await self.fetch_url(url)
                    if content:
                        score = self.cross_validate(query, content, search_results)
                        if score > self.MIN_CROSS_VALIDATE_SCORE:
                            extracted.append({
                                "text": content[:self.MAX_CONTENT_LENGTH],
                                "source_url": url,
                                "title": sr.get("title", ""),
                                "score": score,
                            })
                        if network_cb is not None:
                            network_cb.record_success()

            # 缓存高质量结果
            if extracted:
                self._add_to_cache(cache_key, extracted)

            self._search_count += 1
            return {"results": extracted, "from_cache": False}

        except aiohttp.ClientError as exc:
            logger.warning("[巽卦·触角] 网络异常: %s", exc)
            if brave_cb is not None:
                brave_cb.record_failure()
            return {"results": [], "error": str(exc)}
        except Exception as exc:
            logger.warning("[巽卦·触角] 外探失败: %s", exc)
            if brave_cb is not None:
                brave_cb.record_failure()
            return {"results": [], "error": str(exc)}

    # ========================================================================
    # URL 内容抓取（迁移自 SkinAgent._antenna_fetch）
    # ========================================================================

    async def fetch_url(self, url: str) -> str:
        """抓取 URL 内容（带 SSRF 防护）

        完整保留原 SkinAgent._antenna_fetch 的安全逻辑：
        - 协议白名单（仅 http/https）
        - localhost 拦截
        - 内网 IP 段拦截
        - DNS 解析内网检查

        Args:
            url: 目标 URL

        Returns:
            抓取到的文本内容（最多 2000 字符），失败返回 ""
        """
        if not url:
            return ""

        # --- SSRF 防护层 ---
        parsed = urlparse(url)

        # 协议白名单
        if parsed.scheme not in ("http", "https"):
            logger.warning("[SSRF防护] 拒绝非 http/https 协议: %s", parsed.scheme)
            return ""

        hostname = parsed.hostname
        if not hostname:
            return ""

        # localhost 拦截
        if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            logger.warning("[SSRF防护] 拒绝 localhost: %s", hostname)
            return ""

        # IP 地址检查
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                logger.warning("[SSRF防护] 拒绝内网/保留 IP: %s", hostname)
                return ""
        except ValueError:
            # 非 IP 地址（域名），检查 DNS 解析
            try:
                resolved = socket.getaddrinfo(hostname, None)
                for _fam, _typ, _proto, _cname, addr in resolved:
                    resolved_ip = addr[0]
                    try:
                        rip = ipaddress.ip_address(resolved_ip)
                        if rip.is_private or rip.is_loopback or rip.is_link_local or rip.is_multicast or rip.is_reserved:
                            logger.warning(
                                "[SSRF防护] DNS 解析到内网/保留 IP: %s -> %s",
                                hostname, resolved_ip,
                            )
                            return ""
                    except ValueError:
                        pass
            except socket.gaierror:
                logger.warning("[SSRF防护] DNS 解析失败: %s", hostname)
                return ""

        # --- 正常抓取 ---
        try:
            session = await self._get_http_session()
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=self.FETCH_TIMEOUT),
            ) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    # 去除 script/style 标签
                    text = re.sub(
                        r'<script[^>]*>.*?</script>', '', html,
                        flags=re.DOTALL | re.IGNORECASE,
                    )
                    text = re.sub(
                        r'<style[^>]*>.*?</style>', '', text,
                        flags=re.DOTALL | re.IGNORECASE,
                    )
                    # 去除 HTML 标签
                    text = re.sub(r'<[^>]+>', ' ', text)
                    # 压缩空白
                    text = re.sub(r'\s+', ' ', text)
                    return text.strip()[:self.MAX_CONTENT_LENGTH]
        except aiohttp.ClientError:
            logger.debug("[巽卦] 抓取失败: %s", url, exc_info=True)
        except Exception:
            logger.debug("[巽卦] 抓取异常: %s", url, exc_info=True)

        return ""

    # ========================================================================
    # 交叉验证（迁移自 SkinAgent._antenna_verify）
    # ========================================================================

    def cross_validate(
        self,
        query: str,
        content: str,
        all_results: list,
    ) -> float:
        """交叉验证：评估外部内容与查询的相关性

        完整保留原 SkinAgent._antenna_verify 逻辑：
        1. 内容长度不足 → 0 分
        2. 关键词匹配得分（支持中英文）
        3. 多个来源的交叉验证加分

        Args:
            query: 原始查询字符串
            content: 抓取到的文本内容
            all_results: 所有搜索结果列表

        Returns:
            相关性分数 [0.0, 1.0]
        """
        if not content or len(content) < self.MIN_CONTENT_LENGTH:
            return 0.0

        # 提取查询关键词（中英文分词）
        import re
        query_tokens = re.findall(
            r'[\u4e00-\u9fff]+|[a-zA-Z]{2,}',
            query.lower(),
        )
        if not query_tokens:
            # fallback: 空格分词
            query_tokens = [w.lower() for w in query.split() if len(w) > 1] or [query.lower()]

        content_lower = content.lower()

        # 关键词匹配
        matches = sum(1 for w in query_tokens if w in content_lower)
        keyword_score = matches / max(len(query_tokens), 1)

        # 交叉验证：有多个搜索结果来源时加分
        cross_validated = len(all_results) >= 2

        return min(keyword_score + (0.2 if cross_validated else 0.0), 1.0)

    # ========================================================================
    # 安全屏障（迁移自 SkinAgent.barrier_check）
    # ========================================================================

    def barrier_check(self, ip: str = "") -> str:
        """安全屏障检查

        原 SkinAgent.barrier_check 的等价实现。
        当前为占位实现，后续可按需扩展 IP 黑名单/速率限制。

        Args:
            ip: 来源 IP 地址

        Returns:
            检查结果，当前始终为 "pass"
        """
        self._request_count += 1
        return "pass"

    # ========================================================================
    # 缓存管理
    # ========================================================================

    def _add_to_cache(self, cache_key: str, results: List[Dict[str, Any]]) -> None:
        """添加结果到缓存，超过上限时淘汰最旧条目"""
        self._cache[cache_key] = results
        if len(self._cache) > self.MAX_CACHE_SIZE:
            # 淘汰最早加入的条目
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.debug("[巽卦] 缓存淘汰: %s", oldest_key[:50])

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息

        Returns:
            {
                "cache_size": int,
                "max_cache_size": int,
                "cache_keys": [...],
                "search_count": int,
            }
        """
        return {
            "cache_size": len(self._cache),
            "max_cache_size": self.MAX_CACHE_SIZE,
            "cache_keys": list(self._cache.keys())[:20],
            "search_count": self._search_count,
        }

    def clear_cache(self) -> None:
        """清空缓存"""
        count = len(self._cache)
        self._cache.clear()
        logger.info("[巽卦] 缓存已清空 (%d 条)", count)

    # ========================================================================
    # HTTP 会话管理
    # ========================================================================

    async def _get_http_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()
        return self._http_session

    async def _close_http_session(self) -> None:
        """关闭 HTTP 会话"""
        if self._http_session is not None and not self._http_session.closed:
            await self._http_session.close()
            self._http_session = None

    # ========================================================================
    # 统计与生命周期
    # ========================================================================

    def stats(self) -> Dict[str, Any]:
        """返回综合统计信息"""
        return {
            "search_count": self._search_count,
            "cache_size": len(self._cache),
            "request_count": self._request_count,
            "blocked_count": self._blocked_count,
            "is_alive": self.is_alive,
            "uptime_sec": self.uptime_sec,
            "health": self.health.value,
        }

    def stop(self) -> None:
        """停止巽卦：关闭 HTTP 会话"""
        if self._http_session is not None and not self._http_session.closed:
            # 异步关闭需要通过事件循环调度
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(self._close_http_session())
                else:
                    loop.run_until_complete(self._close_http_session())
            except RuntimeError:
                pass
        super().stop()


__all__ = ["XunGua"]
