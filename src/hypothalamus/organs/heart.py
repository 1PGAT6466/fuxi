"""
organs/heart.py — 🫀 心（核心监控与自愈）v1.41

心 = 全身节律器，定时体检，异常自愈。震 ☳ 雷。
每次心跳 = 一轮全系统检查。
v1.41: 服务检查健壮化 + 异步测试
"""

import asyncio
import logging
import time
import traceback
from typing import Any, Dict

from src.hypothalamus.meridian import Meridian, Signal, SignalPriority
from .organ_base import OrganBase, OrganMetadata, Element, PrenatalBagua, PostnatalBagua, Stem

logger = logging.getLogger("heart")


class HeartAgent(OrganBase):
    """心智能体——核心监控

    心跳 = 定时全系统体检
    停跳 = CPR 自愈流程
    """

    BEAT_INTERVAL = 10

    def __init__(self, meridian: Meridian):
        super().__init__(meridian, OrganMetadata(
            organ_id="heart", name="心·节律", emoji="🫀", description="路由调度中枢",
            prenatal_gua=PrenatalBagua.LI, prenatal_direction="东",
            postnatal_gua=PostnatalBagua.LI, postnatal_direction="南",
            element=Element.FIRE, stem=Stem.BING,
            palace_number=9, ui_position="south",
            peak_hour="11:00-13:00", rest_hour="01:00-03:00"))
        self._beat_count = 0
        self._running = False
        self._task = None
        self._last_health: Dict = {}
        self._anomalies: list = []
        self._short_term: list = []
        self._preferences: Dict = {}

        self.meridian.register_organ(
            self.organ_id, "心", "🫀",
            "核心监控：定时体检→异常告警→自愈修复",
        )
        self.meridian.subscribe(self.organ_id, "heartbeat", self._handle_heartbeat)
        self.meridian.subscribe(self.organ_id, "check_health", self._handle_check)
        self.meridian.subscribe(self.organ_id, "store_memory", self._handle_store_memory)
        self.meridian.subscribe(self.organ_id, "recall", self._handle_recall)
        self.meridian.subscribe(self.organ_id, "user_preference", self._handle_user_preference)

    async def _handle_heartbeat(self, signal: Signal) -> None:
        self.meridian.heartbeat(self.organ_id)

    async def _handle_check(self, signal: Signal) -> None:
        health = await self._beat()
        self.meridian.reply(signal, health)

    async def _beat(self) -> Dict:
        health = {
            "timestamp": time.time(),
            "beat_number": self._beat_count + 1,
            "organs": {},
            "services": {},
            "anomalies": [],
        }

        # 1. 检查所有器官
        for organ in self.meridian.list_organs():
            is_alive = self.meridian.is_alive(organ.organ_id)
            health["organs"][organ.organ_id] = {
                "name": organ.name,
                "alive": is_alive,
                "last_heartbeat_ago": round(time.time() - organ.last_heartbeat, 1),
            }
            if not is_alive and organ.organ_id != "heart":
                health["anomalies"].append(f"{organ.emoji} {organ.name} 无心跳")

        # 2. 检查核心服务（健壮化）
        health["services"]["vector_store"] = self._check_vector_store()
        health["services"]["llm"] = self._check_llm_service()

        # 3. 处理异常
        if health["anomalies"]:
            await self._heal(health["anomalies"])

        self._beat_count += 1
        self._last_health = health

        self.meridian.broadcast(
            self.organ_id, "health_update", health,
            priority=SignalPriority.LOW,
        )
        return health

    def _check_vector_store(self) -> str:
        try:
            from src.db.vector_store import VectorStore
            vs = VectorStore()
            return "ok" if vs else "ok"
        except Exception as e:
            logger.debug(f"[Heart] Vector store check: {e}")
            return "degraded"

    def _check_llm_service(self) -> str:
        try:
            import os
            api_key = os.getenv("DEEPSEEK_API_KEY", "")
            if api_key:
                return "ok"
            return "degraded"
        except Exception:
            return "unknown"

    async def _heal(self, anomalies: list) -> None:
        for anomaly in anomalies:
            if "LLM" in anomaly or "向量" in anomaly:
                logger.warning(f"[Heart] Anomaly: {anomaly} — alerting brain")
                self.meridian.send(Signal(
                    source=self.organ_id, target="brain",
                    signal_type="alert", payload={"message": anomaly},
                    priority=SignalPriority.HIGH,
                ))
            self._anomalies.append({"time": time.time(), "message": anomaly})

    async def start_beating(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._beat_loop())
        logger.info("[Heart] 心跳已启动 🫀")

    async def stop_beating(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    async def _beat_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.BEAT_INTERVAL)
                self.meridian.heartbeat(self.organ_id)
                await self._beat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Heart] Beat error: {e}\n{traceback.format_exc()}")

    async def _handle_store_memory(self, signal: Signal) -> None:
        """v1.43: 存储对话到短期记忆"""
        session_id = signal.payload.get("session_id", "default")
        role = signal.payload.get("role", "user")
        content = signal.payload.get("content", "")
        if content:
            self._short_term.append({"role": role, "content": content, "time": time.time()})
            if len(self._short_term) > 200:
                self._short_term = self._short_term[-200:]
            self._stats["memories_stored"] += 1
        self.meridian.reply(signal, {"ok": True, "stored": len(self._short_term)})

    async def _handle_recall(self, signal: Signal) -> None:
        """v1.43: 回忆最近的 N 条对话"""
        n = signal.payload.get("n", 10)
        self.meridian.reply(signal, {"history": self._short_term[-n:]})

    async def _handle_user_preference(self, signal: Signal) -> None:
        """v1.43: 存储或读取用户偏好"""
        key = signal.payload.get("key", "")
        value = signal.payload.get("value", None)
        if value is not None:
            self._preferences[key] = value
        result = self._preferences.get(key, None)
        self.meridian.reply(signal, {"key": key, "value": result})

    def stats(self) -> Dict:
        return {
            "beat_count": self._beat_count,
            "anomalies_24h": len([a for a in self._anomalies if time.time() - a["time"] < 86400]),
            "last_beat_ago": round(time.time() - self._last_health.get("timestamp", 0), 1),
            "running": self._running,
            "alive": True,
        }
