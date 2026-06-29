"""
organs/kidney.py — 🫘 肾（数据精炼与废物排泄）v1.41

肾 = 伏羲的过滤系统。
全身血液流经肾脏，保留精华，排出废物。
v1.41: _load_access_counts 实现 + _purge_waste 真删除 + 异常不吞 + 薄弱阈值修复
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.hypothalamus.meridian import Meridian, Signal, SignalPriority
from .organ_base import OrganBase, OrganMetadata, Element, PrenatalBagua, PostnatalBagua, Stem

logger = logging.getLogger("kidney")

# 访问计数持久化文件
ACCESS_COUNTS_FILE = os.environ.get(
    "KB_ACCESS_COUNTS_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "access_counts.json"),
)


class KidneyAgent(OrganBase):
    """肾智能体——数据精炼
    
    过滤血液（全库扫描）→ 保留精华 → 排出废物 → 维持体量平衡
    """

    FILTER_INTERVAL = 25
    MAX_CHUNKS_THRESHOLD = 8000
    STALE_DAYS = 30

    def __init__(self, meridian: Meridian):
        super().__init__(meridian, OrganMetadata(
            organ_id="kidney", name="肾·精炼", emoji="🫘", description="数据精炼过滤",
            prenatal_gua=PrenatalBagua.KAN, prenatal_direction="西",
            postnatal_gua=PostnatalBagua.KAN, postnatal_direction="北",
            element=Element.WATER, stem=Stem.REN,
            palace_number=1, ui_position="north",
            peak_hour="17:00-19:00", rest_hour="05:00-07:00"))
        self._filter_count = 0
        self._purged_total = 0
        self._essence_total = 0
        self._running = False
        self._task = None

        self.meridian.register_organ(
            self.organ_id, "肾", "🫘",
            "数据精炼：过滤→保留精华→排泄废物→维持平衡",
        )
        self.meridian.subscribe(self.organ_id, "filter", self._handle_filter)
        self.meridian.subscribe(self.organ_id, "purge", self._handle_purge)
        self.meridian.subscribe(self.organ_id, "detect_deficiency", self._handle_deficiency)
        self.meridian.subscribe(self.organ_id, "heartbeat", self._handle_heartbeat)

    # ── 信号处理 ──

    async def _handle_heartbeat(self, signal: Signal) -> None:
        self.meridian.heartbeat(self.organ_id)

    async def _handle_filter(self, signal: Signal) -> None:
        result = await self._filter_blood()
        self.meridian.reply(signal, result)

    async def _handle_purge(self, signal: Signal) -> None:
        result = await self._purge_waste()
        self.meridian.reply(signal, result)

    async def _handle_deficiency(self, signal: Signal) -> None:
        category = signal.payload.get("category", "")
        result = await self._detect_deficiency(category)
        self.meridian.reply(signal, result)

    # ── 访问计数持久化 ──

    def _load_access_counts(self) -> Dict[str, int]:
        """从磁盘加载访问计数"""
        path = Path(ACCESS_COUNTS_FILE)
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("counts", {}) if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning(f"[Kidney] Failed to load access counts: {e}")
            return {}

    def _save_access_counts(self, counts: Dict[str, int]) -> None:
        """持久化访问计数"""
        path = Path(ACCESS_COUNTS_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"counts": counts, "updated_at": datetime.now(timezone.utc).isoformat()}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[Kidney] Failed to save access counts: {e}")

    # ── 核心功能 ──

    async def _filter_blood(self) -> Dict:
        """过滤全身数据——保留精华，标记废物"""
        try:
            from src.db.data_store import load_chunks

            chunks = load_chunks()
            if not chunks:
                return {"chunks": 0, "essence": 0, "waste": 0}

            essence = []
            waste = []
            access_counts = self._load_access_counts()

            for chunk in chunks:
                file_hash = chunk.get("file_hash", "")
                if file_hash:
                    chunk["access_count"] = access_counts.get(file_hash, 0)
                score = self._score_chunk(chunk)
                if score >= 0.5:
                    chunk["_quality_score"] = score
                    essence.append(chunk)
                else:
                    chunk["_quality_score"] = score
                    chunk["_waste"] = True
                    waste.append(chunk)

            self._essence_total = len(essence)
            self._filter_count += 1

            if len(chunks) > self.MAX_CHUNKS_THRESHOLD:
                await self._purge_waste()

            self.meridian.send(Signal(
                source=self.organ_id, target="brain",
                signal_type="filter_complete",
                payload={"essence": len(essence), "waste": len(waste)},
                priority=SignalPriority.LOW,
            ))

            return {
                "total_chunks": len(chunks),
                "essence": len(essence),
                "waste": len(waste),
                "essence_ratio": round(len(essence) / max(len(chunks), 1), 2),
            }
        except Exception as e:
            logger.error(f"[Kidney] Filter failed: {e}")
            return {"error": str(e)}

    async def _purge_waste(self) -> Dict:
        """排泄废物——真正删除低质/过期数据"""
        purged = 0
        try:
            from src.db.data_store import load_chunks, save_chunks

            chunks = load_chunks()
            now = time.time()
            survivors = []

            for chunk in chunks:
                last_access = chunk.get("last_accessed", 0)
                if isinstance(last_access, str):
                    try:
                        last_access = time.mktime(time.strptime(last_access, "%Y-%m-%d"))
                    except Exception:
                        last_access = 0

                days_stale = (now - float(last_access or 0)) / 86400

                if days_stale > self.STALE_DAYS:
                    purged += 1
                else:
                    survivors.append(chunk)

            if purged > 0:
                save_chunks(survivors)

            self._purged_total += purged
            logger.info(f"[Kidney] Purged {purged} stale chunks")

            if purged > 0:
                self.meridian.send(Signal(
                    source=self.organ_id, target="spleen",
                    signal_type="data_purged",
                    payload={"purged_count": purged},
                    priority=SignalPriority.LOW,
                ))

            return {"purged": purged, "total_purged": self._purged_total}
        except Exception as e:
            logger.error(f"[Kidney] Purge failed: {e}")
            return {"error": str(e)}

    async def _detect_deficiency(self, category: str = "") -> Dict:
        """检测知识薄弱领域——缺数据的主题"""
        weak_areas = []
        cat_counts: Dict[str, int] = {}
        try:
            from src.db.data_store import load_chunks

            chunks = load_chunks()
            for chunk in chunks:
                cat = chunk.get("category", "未分类"); cat = cat if isinstance(cat, str) else str(cat)
                cat_counts[cat] = cat_counts.get(cat, 0) + 1

            if cat_counts:
                avg = sum(cat_counts.values()) / len(cat_counts)
                # 修复：薄弱 = 低于平均值的 30%（而非 20%），避免误判
                threshold = avg * 0.3
                weak_areas = [
                    {"category": cat, "count": count, "deficiency": round(1 - count / max(avg, 1), 2)}
                    for cat, count in cat_counts.items()
                    if count < threshold
                ]

            if weak_areas:
                self.meridian.send(Signal(
                    source=self.organ_id, target="brain",
                    signal_type="deficiency_detected",
                    payload={"weak_areas": weak_areas},
                    priority=SignalPriority.NORMAL,
                ))

            return {"weak_areas": weak_areas, "category_distribution": cat_counts}
        except Exception as e:
            logger.error(f"[Kidney] Deficiency detection failed: {e}")
            return {"error": str(e)}

    def _score_chunk(self, chunk: Dict) -> float:
        """评分 chunk 的活性——访问频率 + 新鲜度 + 完整性"""
        score = 0.5

        # 1. 访问频率
        access_count = chunk.get("access_count", 0)
        if access_count > 10:
            score += 0.3
        elif access_count > 3:
            score += 0.15
        elif access_count == 0:
            score -= 0.3

        # 2. 新鲜度
        created_at = chunk.get("created_at", "")
        if created_at:
            try:
                created = datetime.fromisoformat(created_at.replace("Z", ""))
                days_old = (datetime.now() - created).days
                if days_old < 30:
                    score += 0.1
                elif days_old > 180:
                    score -= 0.1
            except (ValueError, TypeError) as e:
                # 不吞异常——记录警告
                logger.warning(f"[Kidney] Failed to parse created_at '{created_at}': {e}")

        # 3. 完整性
        if not chunk.get("text", "").strip():
            score -= 0.4

        return max(min(score, 1.0), 0.0)

    # ── 生命周期 ──

    async def start_filtering(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._filter_loop())
        logger.info("[Kidney] 肾脏过滤已启动 🫘")

    async def stop_filtering(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    async def _filter_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.FILTER_INTERVAL)
                self.meridian.heartbeat(self.organ_id)
                await self._filter_blood()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Kidney] Filter loop error: {e}")

    def stats(self) -> Dict:
        return {
            "filter_count": self._filter_count,
            "purged_total": self._purged_total,
            "essence_total": self._essence_total,
            "running": self._running,
            "stale_days_threshold": self.STALE_DAYS,
            "alive": self.meridian.is_alive(self.organ_id),
        }
