import asyncio
"""
organs/liver.py — 🛡️ 肝（免疫与解毒）v1.41

肝 = 质量防线，全身免疫中枢。离 ☲ 火。
过滤有害信息、从错误中学习、建立免疫记忆。
v1.41: 免疫记忆改用 data_store + 异常日志修复 + 异步测试
"""

import logging
import time
import traceback
from typing import Any, Dict, List

from src.hypothalamus.meridian import Meridian, Signal, SignalPriority
from .organ_base import OrganBase, OrganMetadata, Element, PrenatalBagua, PostnatalBagua, Stem

logger = logging.getLogger("liver")


class LiverAgent(OrganBase):
    """肝智能体——免疫解毒
    
    自主判断信息质量，从错误中建免疫记忆。
    """

    def __init__(self, meridian: Meridian):
        super().__init__(meridian, OrganMetadata(
            organ_id="liver", name="肝·免疫", emoji="🛡️", description="质量过滤与免疫记忆",
            prenatal_gua=PrenatalBagua.ZHEN, prenatal_direction="东北",
            postnatal_gua=PostnatalBagua.ZHEN, postnatal_direction="东",
            element=Element.WOOD, stem=Stem.JIA,
            palace_number=3, ui_position="east",
            peak_hour="23:00-01:00", rest_hour="11:00-13:00"))
        self._running = False
        self._task = None
        self._immune_memory: Dict[str, Dict] = {}
        self._filtered_count = 0
        self._load_immune_memory()

        self.meridian.register_organ(
            self.organ_id, "肝", "🛡️",
            "免疫解毒：质量评估→有害过滤→免疫记忆",
        )
        self.meridian.subscribe(self.organ_id, "filter_results", self._handle_filter)
        self.meridian.subscribe(self.organ_id, "learn_feedback", self._handle_learn)
        self.meridian.subscribe(self.organ_id, "detect_fever", self._handle_detect_fever)
        self.meridian.subscribe(self.organ_id, "heartbeat", self._handle_heartbeat)

    async def _handle_heartbeat(self, signal: Signal) -> None:
        self.meridian.heartbeat(self.organ_id)

    async def _handle_filter(self, signal: Signal) -> None:
        results = signal.payload.get("results", [])
        query = signal.payload.get("query", "")
        filtered = await self._filter(results, query)
        self.meridian.reply(signal, {
            "filtered": filtered,
            "original_count": len(results),
            "filtered_count": self._filtered_count,
        })

    async def _handle_learn(self, signal: Signal) -> None:
        source = signal.payload.get("source", "")
        is_harmful = signal.payload.get("is_harmful", False)
        if source and is_harmful:
            if source not in self._immune_memory:
                self._immune_memory[source] = {"toxicity": 0.0, "count": 0}
            self._immune_memory[source]["count"] += 1
            self._immune_memory[source]["toxicity"] = min(
                self._immune_memory[source]["toxicity"] + 0.2, 1.0
            )
            logger.info(f"[Liver] Learned harmful source: {source} "
                        f"(toxicity={self._immune_memory[source]['toxicity']:.1f})")
            self._save_immune_memory()
        self.meridian.reply(signal, {"ok": True})

    async def _filter(self, results: List[Dict], query: str) -> List[Dict]:
        clean = []
        for r in results:
            source_file = r.get("file_name", "")
            if source_file in self._immune_memory:
                toxicity = self._immune_memory[source_file]["toxicity"]
                if toxicity > 0.6:
                    r["_toxic"] = True
                    r["_toxicity"] = toxicity
                    self._filtered_count += 1
                    continue
            text = r.get("text", "").strip()
            if len(text) < 10:
                continue
            if sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or c.isascii()) / max(len(text), 1) < 0.5:
                continue
            clean.append(r)
        return clean

    def quick_assess(self, results: List[Dict]) -> Dict:
        if not results:
            return {"verdict": "EMPTY", "score": 0.0}
        rerank_scores = [r.get("_rerank_score", 0) for r in results if r.get("_rerank_score", 0) > 0]
        if rerank_scores:
            avg = sum(rerank_scores) / len(rerank_scores)
            if avg >= 7.0:
                return {"verdict": "PASS", "score": avg / 10.0}
            elif avg >= 3.0:
                return {"verdict": "RETRY", "score": avg / 10.0}
        raw_scores = [r.get("score", 0) for r in results[:5]]
        avg_raw = sum(raw_scores) / max(len(raw_scores), 1)
        return {"verdict": "PASS" if avg_raw >= 3 else "RETRY", "score": min(avg_raw / 10.0, 1.0)}

    def _load_immune_memory(self) -> None:
        """从 data_store 加载免疫记忆"""
        try:
            from src.db.data_store import load_config
            cfg = load_config()
            mem = cfg.get("liver_immune_memory", {})
            if isinstance(mem, dict):
                self._immune_memory = mem
                logger.info(f"[Liver] Loaded {len(mem)} immune memories")
        except Exception as e:
            logger.warning(f"[Liver] Load immune memory failed: {e}")

    def _save_immune_memory(self) -> None:
        """通过 data_store 持久化免疫记忆"""
        try:
            from src.db.data_store import load_config, save_config
            cfg = load_config()
            cfg["liver_immune_memory"] = self._immune_memory
            save_config(cfg)
        except Exception as e:
            logger.warning(f"[Liver] Save immune memory failed: {e}\n{traceback.format_exc()}")


    async def start_filtering(self) -> None:
        """启动肝脏循环 — v1.42 P0修复"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._filter_loop())
    
    async def _filter_loop(self) -> None:
        """持续心跳 + 定期免疫过滤"""
        while self._running:
            try:
                self.meridian.heartbeat(self.organ_id)
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Liver] Filter loop error: {e}")
                await asyncio.sleep(10)

    async def _handle_detect_fever(self, signal: Signal) -> None:
        """v1.43: 发烧检测——监控阈值，触发告警"""
        import time as _time
        metrics = signal.payload.get("metrics", {})
        alerts = []

        thresholds = {
            "hit_rate_drop_ratio": 0.3,
            "wiki_lag_seconds": 300,
            "chunk_growth_spike": 500,
            "graph_isolated_ratio": 0.5,
        }

        hit_rate = metrics.get("hit_rate", 1.0)
        prev = metrics.get("prev_hit_rate", hit_rate)
        if prev > 0 and (prev - hit_rate) / prev > thresholds["hit_rate_drop_ratio"]:
            alerts.append(f"hit_rate_drop: {prev:.2f}->{hit_rate:.2f}")

        wiki_lag = metrics.get("wiki_lag_seconds", 0)
        if wiki_lag > thresholds["wiki_lag_seconds"]:
            alerts.append(f"wiki_stall: {wiki_lag}s")

        chunk_rate = metrics.get("chunk_growth_per_hour", 0)
        if chunk_rate > thresholds["chunk_growth_spike"]:
            alerts.append(f"chunk_spike: {chunk_rate}/hr")

        iso_ratio = metrics.get("graph_isolated_ratio", 0)
        if iso_ratio > thresholds["graph_isolated_ratio"]:
            alerts.append(f"isolated_nodes: {iso_ratio:.0%}")

        if alerts:
            self._fever_active = True
            self._fever_count += 1
            self._fever_log.append({"time": _time.time(), "alerts": alerts})
            logger.warning(f"[Liver] FEVER #{self._fever_count}: {'; '.join(alerts)}")
            self.meridian.send(Signal(
                source=self.organ_id, target="brain",
                signal_type="fever_alert",
                payload={"alerts": alerts, "fever_count": self._fever_count},
                priority=SignalPriority.HIGH,
            ))
        else:
            self._fever_active = False

        self.meridian.reply(signal, {"fever": self._fever_active, "alerts": alerts})

    def stats(self) -> Dict:
        return {
            "immune_memory_size": len(self._immune_memory),
            "filtered_total": self._filtered_count,
            "alive": self.meridian.is_alive(self.organ_id),
        }
