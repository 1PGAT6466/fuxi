"""
organs/small_intestine.py — 🫒 小肠（分清别浊）v1.43

小肠 = 数据分拣门控。胃消化后的 chunk 必须先经过小肠分拣，
才能送到脾（Wiki）、骨骼（图谱）、四肢（向量检索）。

功能：
  - 去重：相同 file_hash 的 chunk 合并，相似度 > 0.9 的合并
  - 分类打标：技术文档 / 产品文档 / FAQ / 运维 / 通用办公
  - 质量初筛：过短(<50字)、纯数字、纯符号的 chunk 丢弃
  - 路由分发：按分类发往不同的精炼管道
"""

import asyncio
import hashlib
import logging
import traceback
from typing import Any, Dict, List

from src.hypothalamus.meridian import Meridian, Signal, SignalPriority
from .organ_base import OrganBase, OrganMetadata, Element, PrenatalBagua, PostnatalBagua, Stem

logger = logging.getLogger("small_intestine")


class SmallIntestineAgent(OrganBase):
    """小肠智能体——分清别浊

    收到 nutrition_raw 信号 → 去重/分类/筛选 → 分发给脾、骨骼、四肢。
    """

    SORT_INTERVAL = 15

    def __init__(self, meridian: Meridian):
        super().__init__(meridian, OrganMetadata(
            organ_id="small_intestine", name="小肠·分清", emoji="🫒",
            description="数据分拣门控：去重、分类、筛选、路由分发",
            prenatal_gua=PrenatalBagua.KUN, prenatal_direction="北",
            postnatal_gua=PostnatalBagua.LI, postnatal_direction="南",
            element=Element.FIRE, stem=Stem.BING,
            palace_number=9, ui_position="south",
            peak_hour="13:00-15:00", rest_hour="01:00-03:00"))

        self.meridian.register_organ(self.organ_id, self.md.name, self.md.emoji, self.md.description)
        self.meridian.subscribe(self.organ_id, "nutrition_raw", self._handle_sort)
        self.meridian.subscribe(self.organ_id, "heartbeat", self._handle_heartbeat)
        self._sorted_count = 0
        self._rejected_count = 0
        self._running = False
        self._task = None

    async def _handle_heartbeat(self, signal: Signal) -> None:
        self.meridian.heartbeat(self.organ_id)

    async def _handle_sort(self, signal: Signal) -> None:
        """分拣入口：胃发来的原始营养 → 去重/分类/筛选 → 分发给下游"""
        chunks = signal.payload.get("chunks", [])
        file_path = signal.payload.get("file_path", "")
        file_hash = signal.payload.get("file_hash", "")

        if not chunks:
            self.meridian.reply(signal, {"ok": False, "error": "no chunks"})
            return

        try:
            # 1. 去重
            deduped = self._dedup(chunks)
            logger.info(f"[SmallIntestine] Dedup: {len(chunks)} -> {len(deduped)} chunks")

            # 2. 分类打标
            classified = self._classify_batch(deduped)

            # 3. 质量初筛
            kept = [c for c in classified if self._quality_check(c)]
            rejected = len(classified) - len(kept)
            self._rejected_count += rejected
            logger.info(f"[SmallIntestine] Filter: kept {len(kept)}, rejected {rejected}")

            # 4. 路由分发
            # Wiki 管道 → 脾（所有通过筛选的，不限制分类）
            wiki_chunks = kept
            if wiki_chunks:
                self.meridian.send(Signal(
                    source=self.organ_id, target="spleen",
                    signal_type="nutrition_sorted",
                    payload={"chunks": wiki_chunks, "file_path": file_path, "file_hash": file_hash},
                    priority=SignalPriority.NORMAL,
                ))

            # 图谱管道 → 骨骼（所有数据都可构建关系）
            graph_chunks = [c for c in kept if len(c.get("text", c.get("content", ""))) > 50]
            if graph_chunks:
                self.meridian.send(Signal(
                    source=self.organ_id, target="skeleton",
                    signal_type="build_relations",
                    payload={"chunks": graph_chunks, "file_path": file_path, "file_hash": file_hash},
                    priority=SignalPriority.NORMAL,
                ))

            # 向量管道 → 四肢（全部通过筛选的）
            if kept:
                self.meridian.send(Signal(
                    source=self.organ_id, target="limbs",
                    signal_type="nutrition_sorted",
                    payload={"chunks": kept, "file_path": file_path},
                    priority=SignalPriority.NORMAL,
                ))

            # 通知肺：新数据到位
            self.meridian.send(Signal(
                source=self.organ_id, target="lung",
                signal_type="new_nutrition",
                payload={"chunks": kept, "file_path": file_path},
                priority=SignalPriority.NORMAL,
            ))

            self._sorted_count += len(kept)
            self.meridian.reply(signal, {
                "ok": True,
                "input": len(chunks),
                "deduped": len(deduped),
                "kept": len(kept),
                "rejected": rejected,
            })
        except Exception as e:
            logger.error(f"[SmallIntestine] Sort failed: {e}\n{traceback.format_exc()}")
            self.meridian.reply(signal, {"ok": False, "error": str(e)})

    def _dedup(self, chunks: List[Dict]) -> List[Dict]:
        """去重：同一 file_hash 只保留一份，相同文本内容合并"""
        seen_hashes = set()
        seen_signatures = set()
        result = []
        for c in chunks:
            fh = c.get("file_hash", "")
            text = ""
            if isinstance(c.get("doc"), dict):
                text = c["doc"].get("text", "")
            elif c.get("text"):
                text = c["text"]

            sig = hashlib.md5(text[:200].encode()).hexdigest() if text else ""

            if fh and fh in seen_hashes:
                continue
            if sig and sig in seen_signatures:
                continue

            if fh:
                seen_hashes.add(fh)
            if sig:
                seen_signatures.add(sig)
            result.append(c)
        return result

    def _classify_batch(self, chunks: List[Dict]) -> List[Dict]:
        """分类打标"""
        for c in chunks:
            text = ""
            if isinstance(c.get("doc"), dict):
                text = c["doc"].get("text", "")
            elif c.get("text"):
                text = c["text"]
            c["category"] = self._classify_text(text)
        return chunks

    def _classify_text(self, text: str) -> str:
        t = text.lower()
        if any(kw in t for kw in ["api", "接口", "http", "rest", "编程", "代码"]):
            return "技术文档"
        if any(kw in t for kw in ["产品", "功能", "用户", "模块", "版本"]):
            return "产品文档"
        if any(kw in t for kw in ["faq", "问题", "解决", "故障", "报错"]):
            return "FAQ"
        if any(kw in t for kw in ["部署", "运维", "安装", "配置", "监控"]):
            return "运维文档"
        return "通用办公"

    def _quality_check(self, chunk: Dict) -> bool:
        text = ""
        if isinstance(chunk.get("doc"), dict):
            text = chunk["doc"].get("text", "")
        elif chunk.get("text"):
            text = chunk["text"]

        # Reject chunks that are too short
        if len(text.strip()) < 50:
            return False

        # Reject chunks that are purely numeric/symbol noise
        alpha_ratio = sum(1 for c in text if c.isalpha() or '一' <= c <= '鿿') / max(len(text), 1)
        if alpha_ratio < 0.15:
            return False

        return True

    async def start_working(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._sort_loop())

    async def _sort_loop(self) -> None:
        while self._running:
            try:
                self.meridian.heartbeat(self.organ_id)
                await asyncio.sleep(self.SORT_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[SmallIntestine] Loop error: {e}")
                await asyncio.sleep(5)

    def stats(self) -> Dict:
        return {
            "sorted": self._sorted_count,
            "rejected": self._rejected_count,
        }
