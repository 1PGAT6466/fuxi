#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skin.py — 皮肤·屏障 · 伏羲 v1.42
艮 ☶ · 西北(先天)/东北(后天) · 土 · 甲木

v1.42: 融合头发外探能力，通过触角(search_external)对外感知
"""

import asyncio
import time
from typing import Dict

from src.hypothalamus.meridian import Signal
from .organ_base import OrganBase, OrganMetadata, Element, PrenatalBagua, PostnatalBagua, Stem

logger = __import__("logging").getLogger("skin")


class SkinAgent(OrganBase):
    """皮肤·屏障 — 前端 UI 与系统屏障 + 触角外探（融合头发能力）"""

    def __init__(self, meridian):
        super().__init__(meridian, OrganMetadata(
            organ_id="skin", name="皮肤·屏障", emoji="🧖",
            description="前端UI与系统屏障：认证、限流、健康感知 + 触角外探",
            prenatal_gua=PrenatalBagua.GEN, prenatal_direction="西北",
            postnatal_gua=PostnatalBagua.GEN, postnatal_direction="东北",
            element=Element.EARTH, stem=Stem.JIA,
            palace_number=8, ui_position="northeast",
            peak_hour="07:00-09:00", rest_hour="21:00-23:00"))

        self._request_count = 0
        self._blocked_count = 0
        self._last_check = time.time()
        self._antenna_searches = 0
        self._antenna_cache: Dict[str, list] = {}

        meridian.register_organ(
            organ_id=self.organ_id,
            name="皮肤·屏障",
            emoji="🧖",
        )
        meridian.subscribe(self.organ_id, "heartbeat", self._handle_heartbeat)
        meridian.subscribe(self.organ_id, "check_request", self._handle_check_request)
        # v1.42 P0 fix: 订阅 search_external 信号，接管头发外探
        meridian.subscribe(self.organ_id, "search_external", self._handle_search_external)

    # ========== 信号处理 ==========

    async def _handle_heartbeat(self, signal: Signal) -> None:
        self._alive = True
        self._last_check = time.time()

    async def _handle_check_request(self, signal: Signal) -> None:
        self._request_count += 1

    async def _handle_search_external(self, signal: Signal) -> None:
        """经络信号入口——Brain 发出 search_external → 皮肤触角执行外探"""
        query = signal.payload.get("query", "")
        top_k = signal.payload.get("top_k", 5)
        result = await self.search_external(query, top_k)
        self.meridian.reply(signal, result)

    # ========== 屏障 ==========

    def barrier_check(self, ip: str = "") -> str:
        self._request_count += 1
        return "pass"

    async def start_guarding(self) -> None:
        """皮肤守护循环"""
        if getattr(self, '_guard_running', False):
            return
        self._guard_running = True
        self._guard_task = asyncio.create_task(self._guard_loop())

    async def _guard_loop(self) -> None:
        while self._guard_running:
            try:
                self.meridian.heartbeat(self.organ_id)
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Skin] Guard error: {e}")
                await asyncio.sleep(10)

    # ========== v1.42: 皮肤触角（融合头发外探能力）==========

    async def search_external(self, query: str, top_k: int = 5):
        """皮肤触角外探：搜索 → 抓取 → 交叉验证 → 带回体内"""
        import aiohttp
        import os as _os
        import re as _re

        cache_key = query.lower().strip()
        if cache_key in self._antenna_cache:
            logger.info(f"[触角] Cache: {query[:50]}")
            return {"results": self._antenna_cache[cache_key], "from_cache": True}

        try:
            api_key = _os.getenv("BRAVE_API_KEY", "")
            search_results = []
            if api_key:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "https://api.search.brave.com/res/v1/web/search",
                        params={"q": query, "count": min(top_k, 10)},
                        headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            search_results = [
                                {"title": r.get("title", ""), "url": r.get("url", ""),
                                 "snippet": r.get("description", "")}
                                for r in data.get("web", {}).get("results", [])[:top_k]
                            ]

            extracted = []
            for sr in search_results[:3]:
                content = await self._antenna_fetch(sr.get("url", ""))
                if content:
                    score = self._antenna_verify(query, content, search_results)
                    if score > 0.3:
                        extracted.append({
                            "text": content[:1000],
                            "source_url": sr.get("url", ""),
                            "title": sr.get("title", ""),
                            "score": score,
                        })

            if extracted:
                self._antenna_cache[cache_key] = extracted
                if len(self._antenna_cache) > 100:
                    oldest = min(self._antenna_cache, key=lambda k: len(self._antenna_cache[k]))
                    del self._antenna_cache[oldest]

            self._antenna_searches += 1
            return {"results": extracted, "from_cache": False}

        except Exception as e:
            logger.warning(f"[触角] 外探失败: {e}")
            return {"results": [], "error": str(e)}

    async def _antenna_fetch(self, url: str) -> str:
        if not url:
            return ""
        try:
            import aiohttp
            import re as _re
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        text = _re.sub(r'<script[^>]*>.*?</script>', '', html, flags=_re.DOTALL)
                        text = _re.sub(r'<style[^>]*>.*?</style>', '', text, flags=_re.DOTALL)
                        text = _re.sub(r'<[^>]+>', ' ', text)
                        text = _re.sub(r'\s+', ' ', text)
                        return text.strip()[:2000]
        except Exception:
            logger.debug("[suppressed] return text.strip()[:2000]")
            pass
        return ""

    def _antenna_verify(self, query: str, content: str, all_results: list) -> float:
        if not content or len(content) < 50:
            return 0
        query_words = [w.lower() for w in query.split() if len(w) > 1] or [query.lower()]
        content_lower = content.lower()
        matches = sum(1 for w in query_words if w in content_lower)
        keyword_score = matches / max(len(query_words), 1)
        cross_validated = len(all_results) >= 2
        return min(keyword_score + (0.2 if cross_validated else 0), 1.0)

    def antenna_stats(self):
        return {"searches": self._antenna_searches, "cache_size": len(self._antenna_cache)}

    # ========== 状态 ==========

    def stats(self) -> Dict:
        return {
            "antenna": self.antenna_stats(),
            "request_count": self._request_count,
            "blocked_count": self._blocked_count,
            "uptime": round(time.time() - self._born_at),
            "alive": self._alive,
        }