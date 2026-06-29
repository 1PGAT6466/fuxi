import asyncio
"""
organs/spleen.py — 🩸 脾（存储与泵血中枢）v1.41

脾 = Wiki 知识中枢，自主管理知识存储和按需推送。兑 ☱ 泽（与经络共卦）。
接收胃送来的营养 → 自动分类生成Wiki → 每次搜索时自主推送相关知识。
v1.41: nutrition_ready 自己入库 + _search_wiki 走统一wiki引擎 + 异常修复
"""

import logging
import traceback
from typing import Any, Dict, List, Optional

from src.hypothalamus.meridian import Meridian, Signal, SignalPriority
from .organ_base import OrganBase, OrganMetadata, Element, PrenatalBagua, PostnatalBagua, Stem

logger = logging.getLogger("spleen")


class SpleenAgent(OrganBase):
    """脾智能体——存储泵血中枢

    自主决定存什么、推什么、清什么。
    """

    def __init__(self, meridian: Meridian):
        super().__init__(meridian, OrganMetadata(
            organ_id="spleen", name="脾·存储", emoji="🩸", description="数据存储入藏",
            prenatal_gua=PrenatalBagua.KUN, prenatal_direction="北",
            postnatal_gua=PostnatalBagua.KUN, postnatal_direction="西南",
            element=Element.EARTH, stem=Stem.JI,
            palace_number=2, ui_position="southwest",
            peak_hour="09:00-11:00", rest_hour="23:00-01:00"))
        self._running = False
        self._task = None
        self._stored_total = 0

        self.meridian.register_organ(
            self.organ_id, "脾", "🩸",
            "Wiki存储中枢：自动分类→生成Wiki→按需推送",
        )
        self.meridian.subscribe(self.organ_id, "nutrition_ready", self._handle_nutrition)
        self.meridian.subscribe(self.organ_id, "pump_wiki", self._handle_pump)
        self.meridian.subscribe(self.organ_id, "data_purged", self._handle_data_purged)
        self.meridian.subscribe(self.organ_id, "heartbeat", self._handle_heartbeat)

    async def _handle_heartbeat(self, signal: Signal) -> None:
        self.meridian.heartbeat(self.organ_id)

    async def _handle_nutrition(self, signal: Signal) -> None:
        """接收营养 → 存储 + 生成Wiki + 通知肺蒸馏"""
        chunks = signal.payload.get("chunks", [])
        file_path = signal.payload.get("file_path", "")

        if not chunks:
            self.meridian.reply(signal, {"ok": False, "error": "no chunks"})
            return

        stored = 0
        wiki_created = 0
        try:
            # 1. 存储 chunks
            from src.db.data_store import load_chunks, save_chunks
            existing = load_chunks()
            existing_file_hashes = {c.get("file_hash", "") for c in existing}
            for chunk in chunks:
                fh = chunk.get("file_hash", "")
                if fh and fh not in existing_file_hashes:
                    existing.append(chunk)
                    stored += 1
            if stored > 0:
                save_chunks(existing)
                self._stored_total += stored
                logger.info(f"[Spleen] Stored {stored} new chunks from {file_path}")

            # 2. 自动提炼 Wiki 页面
            try:
                wiki_created = await self._auto_refine_wiki(chunks, file_path)
                if wiki_created > 0:
                    logger.info(f"[Spleen] Wiki auto-refined: {wiki_created} pages")
            except Exception as e:
                logger.warning(f"[Spleen] Wiki auto-refine failed (non-blocking): {e}")

            # 3. 通知肺
            self.meridian.send(Signal(
                source=self.organ_id, target="lung",
                signal_type="new_nutrition",
                payload={"chunks": chunks, "file_path": file_path, "wiki_created": wiki_created},
                priority=SignalPriority.NORMAL,
            ))

            self.meridian.reply(signal, {"ok": True, "stored": stored, "wiki_created": wiki_created})
        except Exception as e:
            logger.error(f"[Spleen] Store nutrition failed: {e}\n{traceback.format_exc()}")
            self.meridian.reply(signal, {"ok": False, "error": str(e)})

    async def _auto_refine_wiki(self, chunks: list, file_path: str) -> int:
        """从 chunks 自动提炼 Wiki 页面"""
        created = 0
        try:
            from src.services.wiki import get_wiki_engine
            we = get_wiki_engine()
            if not we:
                logger.warning("[Spleen] Wiki engine not available")
                return 0

            full_text = " ".join(
                c.get("doc", {}).get("text", "") if isinstance(c.get("doc"), dict) else (c.get("text", "") or "")
                for c in chunks
            )
            if len(full_text.strip()) < 100:
                return 0

            category = self._classify_text(full_text)  # 不再截断，由 match_category 内部 max_len 处理
            file_name = file_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] if file_path else "auto"
            title = file_name.rsplit(".", 1)[0][:80] if "." in file_name else file_name[:80]

            page_id = we.create_page(
                title=title,
                content=full_text[:8000],
                category=category,
                tags=["auto-refined"],
                sources=[file_path],
            )
            if page_id:
                created += 1
        except Exception as e:
            logger.warning(f"[Spleen] _auto_refine_wiki error: {e}")
        return created

    def _classify_text(self, text: str) -> str:
        """委托统一分类注册表 (v1.43)"""
        try:
            from src.category_registry import match_category
            result = match_category(text)
            if result:
                return result
        except Exception:
            pass
        t = text.lower()
        if any(kw in t for kw in ["api", "接口", "部署", "运维"]):
            return "技术文档"
        return "通用办公"

    async def _handle_data_purged(self, signal: Signal) -> None:
        """肾清除了废物 → 同步 Wiki 向量索引"""
        purged = signal.payload.get("purged_count", 0)
        if purged > 0:
            try:
                # 通知 Wiki 引擎重新同步向量索引
                self.meridian.send(Signal(
                    source=self.organ_id, target="brain",
                    signal_type="wiki_sync_needed",
                    payload={"reason": "data_purged", "count": purged},
                    priority=SignalPriority.LOW,
                ))
            except Exception as e:
                logger.warning(f"[Spleen] Wiki sync notification failed: {e}")

    async def _handle_pump(self, signal: Signal) -> None:
        query = signal.payload.get("query", "")
        top_k = signal.payload.get("top_k", 3)
        wiki_hits = await self._search_wiki(query, top_k)
        self.meridian.reply(signal, {"wiki_hits": wiki_hits})

    async def _search_wiki(self, query: str, top_k: int = 3) -> List[Dict]:
        """搜索 Wiki —— 走统一 wiki 引擎"""
        try:
            from src.services.wiki import get_wiki_engine
            we = get_wiki_engine()
            # 尝试向量搜索
            if hasattr(we, '_wiki_collection') and we._wiki_collection:
                try:
                    import requests
                    from src.db.vector_store import EMBEDDER_URL
                    r = requests.post(f"{EMBEDDER_URL}/embed", json={"texts": [query]}, timeout=10)
                    if r.status_code == 200:
                        emb = r.json()["vectors"][0]
                        return we.vector_search_wiki(emb, top_k=top_k)
                except Exception:
                    pass

            # Fallback: 关键词搜索
            if hasattr(we, 'search_wiki'):
                return we.search_wiki(query, top_k)
        except Exception as e:
            logger.warning(f"[Spleen] Wiki search failed: {e}")

        return []


    async def start_working(self) -> None:
        """启动脾脏循环 — v1.42 P0修复"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._store_loop())
    
    async def _store_loop(self) -> None:
        """持续心跳 + 定期存储维护"""
        while self._running:
            try:
                self.meridian.heartbeat(self.organ_id)
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Spleen] Store loop error: {e}")
                await asyncio.sleep(10)

    def stats(self) -> Dict:
        wiki_count = 0
        try:
            from src.services.wiki import get_wiki_engine
            we = get_wiki_engine()
            if hasattr(we, '_wiki_collection') and we._wiki_collection:
                wiki_count = we._wiki_collection.count()
        except Exception as e:
            logger.warning(f"[spleen] Stats load failed: {e}")

        return {
            "wiki_pages": wiki_count,
            "stored_total": self._stored_total,
            "alive": self.meridian.is_alive(self.organ_id),
        }
