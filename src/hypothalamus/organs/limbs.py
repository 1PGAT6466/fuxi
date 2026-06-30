"""
organs/limbs.py — 💪 四肢（执行能力）v1.41

四肢 = 伏羲的执行器官。
左手检索、右手查表、口表达。
v1.41: hybrid_search -> retrieval + 测试
"""

import logging
import traceback
from typing import Any, Dict, List

from src.hypothalamus.meridian import Meridian, Signal, SignalPriority
from .organ_base import OrganBase, OrganMetadata, Element, PrenatalBagua, PostnatalBagua, Stem

logger = logging.getLogger("limbs")


class LimbsAgent(OrganBase):
    """四肢智能体——执行能力

    左手 = 检索（BM25 + 向量 + RRF + Rerank）
    右手 = 查表（结构化查询）
    """

    def __init__(self, meridian: Meridian):
        super().__init__(meridian, OrganMetadata(
            organ_id="limbs", name="四肢·行功", emoji="💪", description="API响应与数据推送",
            prenatal_gua=PrenatalBagua.ZHEN, prenatal_direction="东北",
            postnatal_gua=PostnatalBagua.ZHEN, postnatal_direction="东",
            element=Element.WOOD, stem=Stem.JIA,
            palace_number=3, ui_position="east",
            peak_hour="11:00-13:00", rest_hour="23:00-01:00"))
        self._search_count = 0
        self._table_count = 0

        self.meridian.register_organ(
            self.organ_id, "四肢", "💪",
            "执行能力：左手检索 + 右手查表",
        )
        self.meridian.subscribe(self.organ_id, "search", self._handle_search)
        self.meridian.subscribe(self.organ_id, "table_query", self._handle_table)
        self.meridian.subscribe(self.organ_id, "heartbeat", self._handle_heartbeat)

    async def _handle_heartbeat(self, signal: Signal) -> None:
        self.meridian.heartbeat(self.organ_id)

    async def _handle_search(self, signal: Signal) -> None:
        query = signal.payload.get("query", "")
        top_k = signal.payload.get("top_k", 10)
        category = signal.payload.get("category", "")
        try:
            results = await self._search(query, top_k, category)
            self._search_count += 1
            self.meridian.reply(signal, {"chunks": results, "count": len(results)})
        except Exception as e:
            logger.error(f"[Limbs] Search failed: {e}\n{traceback.format_exc()}")
            self.meridian.reply(signal, {"chunks": [], "error": str(e)})

    async def _handle_table(self, signal: Signal) -> None:
        query = signal.payload.get("query", "")
        columns = signal.payload.get("columns", [])
        filters = signal.payload.get("filters", {})
        try:
            results = await self._table_query(query, columns, filters)
            self._table_count += 1
            self.meridian.reply(signal, {"rows": results, "count": len(results)})
        except Exception as e:
            logger.error(f"[Limbs] Table query failed: {e}")
            self.meridian.reply(signal, {"rows": [], "error": str(e)})

    async def _search(self, query: str, top_k: int = 10, category: str = "") -> List[Dict]:
        """实际检索 —— 优先用 retrieval.hybrid_search，fallback 到 limbs 自身能力"""
        try:
            from src.db.data_store import load_chunks
            chunks = load_chunks()

            # ✅ P2 修复：尝试多种检索入口
            try:
                from src.services.retrieval import hybrid_search
                return await hybrid_search(query, chunks, category=category, top_k=top_k, skip_cache=False)
            except (ImportError, AttributeError):
                pass

            # Fallback: 用 heart 的检索能力
            try:
                from src.hypothalamus.organs.heart import HeartAgent
                # 简单 BM25 降级
                return self._fallback_search(query, chunks, top_k)
            except Exception:
                logger.debug("[suppressed] return self._fallback_search(q")
                pass

            return []
        except Exception as e:
            logger.error(f"[Limbs] _search error: {e}")
            return []

    def _fallback_search(self, query: str, chunks: list, top_k: int) -> List[Dict]:
        """简单关键词匹配降级"""
        query_lower = query.lower()
        scored = []
        for chunk in chunks:
            text = chunk.get("text", "")
            if query_lower in text.lower():
                score = 1.0
            else:
                words = query_lower.split()
                score = sum(1 for w in words if w in text.lower()) / max(len(words), 1)
            if score > 0:
                chunk["score"] = round(score, 2)
                scored.append(chunk)

        scored.sort(key=lambda x: x.get("score", 0), reverse=True)
        return scored[:top_k]

    async def _table_query(self, query: str, columns: List[str] = None, filters: Dict = None) -> List[Dict]:
        try:
            from src.services.table_view import table_view_search
            result = await table_view_search(query, top_k=10)
            return result if isinstance(result, list) else []
        except (ImportError, AttributeError) as e:
            logger.warning(f"[Limbs] table_view unavailable: {e}")
        except Exception as e:
            logger.warning(f"[Limbs] _table_query error: {e}")
        return []

    def stats(self) -> Dict:
        return {
            "search_count": self._search_count,
            "table_count": self._table_count,
            "alive": self.meridian.is_alive(self.organ_id),
        }
