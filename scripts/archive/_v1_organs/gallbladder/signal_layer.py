"""
organs/gallbladder.py — 🫀 胆（决断之官）v1.43

胆 = 查询路由决策引擎。从大脑解耦，独立判断"这个查询该走哪条路"。

核心功能：
  - 意图分类：6 种意图（compare/numeric_lookup/definition/how_to/material_selector/table_query）
  - 路由决策：简单事实 → 四肢（向量）/ 需要推理 → 肝（多路+Rerank）/ 需要外部 → 皮肤（Web）/ 不确定 → 追问
  - 上下文消歧：利用上文补充意图判断
"""

import asyncio
import logging
import re
import traceback
from typing import Any, Dict, List

from src.hypothalamus.meridian import Meridian, Signal, SignalPriority
from ..organ_base import OrganBase, OrganMetadata, Element, PrenatalBagua, PostnatalBagua, Stem

logger = logging.getLogger("gallbladder")

# Intent patterns (migrated from brain.py Instinct)
_INTENT_PATTERNS = {
    "compare": [r"和.*比较", r"和.*区别", r"对比", r"vs\.?", r"差异", r"哪个更", r"优缺点", r"选哪个", r"更适合", r"比起", r"相对于", r"与.*相比"],
    "numeric_lookup": [r"参数", r"温度", r"熔点", r"密度", r"收缩率", r"强度", r"硬度", r"拉伸", r"弯曲", r"规格", r"尺寸公差", r"多少度", r"多少mpa"],
    "table_query": [r"bom", r"清单", r"采购", r"型号表", r"物料表", r"选型表", r"有哪些.*型号"],
    "definition": [r"是什么", r"定义", r"什么叫", r"什么是", r"含义", r"全称", r"缩写"],
    "how_to": [r"怎么", r"如何", r"步骤", r"流程", r"方法", r"操作", r"配置", r"设置", r"安装", r"部署"],
    "material_selector": [r"选材", r"哪种材料", r"用什么材料", r"材料选择", r"替代.*材料", r"替代品", r"可以代替"],
}
_INTENT_ORDER = ["compare", "numeric_lookup", "material_selector", "table_query", "definition", "how_to"]


class GallbladderAgent(OrganBase):
    """胆智能体——决断之官"""

    def __init__(self, meridian: Meridian):
        super().__init__(meridian, OrganMetadata(
            organ_id="gallbladder", name="胆·决断", emoji="🫀",
            description="查询路由决策引擎：意图分类 + 路由判断",
            prenatal_gua=PrenatalBagua.ZHEN, prenatal_direction="东北",
            postnatal_gua=PostnatalBagua.XUN, postnatal_direction="东南",
            element=Element.WOOD, stem=Stem.YI,
            palace_number=4, ui_position="southeast",
            peak_hour="23:00-01:00", rest_hour="11:00-13:00"))

        self.meridian.register_organ(self.organ_id, self.md.name, self.md.emoji, self.md.description)
        self.meridian.subscribe(self.organ_id, "decide_route", self._handle_decide)
        self.meridian.subscribe(self.organ_id, "heartbeat", self._handle_heartbeat)
        self._decisions = 0
        self._running = False
        self._task = None

    def _handle_heartbeat(self, signal: Signal) -> None:
        self.meridian.heartbeat(self.organ_id)

    def _handle_decide(self, signal: Signal) -> None:
        """接收大脑发来的查询 → 决策路由"""
        query = signal.payload.get("query", "")
        context = signal.payload.get("context", [])
        internal_hits = signal.payload.get("internal_hits", 0)

        if not query:
            self.meridian.reply(signal, {"route": "chat", "reason": "empty query"})
            return

        try:
            intent = self._classify(query, context)
            route = self._decide_route(intent, internal_hits)
            self._decisions += 1

            logger.info(f"[Gallbladder] '{query[:40]}...' -> intent={intent['intent']}, route={route}")

            self.meridian.reply(signal, {
                "route": route,
                "intent": intent,
                "reason": f"intent={intent['intent']}, hits={internal_hits}",
            })
        except Exception as e:
            logger.error(f"[Gallbladder] Decision failed: {e}")
            self.meridian.reply(signal, {"route": "chat", "error": str(e)})

    def _classify(self, query: str, context: List[str]) -> Dict:
        """多意图分类"""
        query_lower = query.strip().lower()
        intents = {}
        primary = "general_search"
        primary_score = 0

        for intent in _INTENT_ORDER:
            patterns = _INTENT_PATTERNS.get(intent, [])
            matches = sum(1 for p in patterns if re.search(p, query_lower))
            if matches > 0:
                score = min(matches / max(len(patterns) * 0.2, 1), 1.0)
                intents[intent] = round(score, 2)
                if score > primary_score:
                    primary = intent
                    primary_score = score

        # Context-aware disambiguation
        if context:
            ctx_text = " ".join(context).lower()
            if any(kw in ctx_text for kw in ["材料", "pa", "pom", "pc"]):
                if "material_selector" not in intents:
                    intents["material_selector"] = 0.5
            if any(kw in ctx_text for kw in ["对比", "比较"]):
                if "compare" not in intents:
                    intents["compare"] = 0.4

        return {"intent": primary, "intents": intents, "count": len(intents)}

    def _decide_route(self, intent: Dict, internal_hits: int) -> str:
        """路由决策树"""
        intents = intent.get("intents", {})

        # Unanswerable → ask follow-up
        if not intents or intent.get("intent") == "general_search":
            if internal_hits < 2:
                return "clarify"

        # Compare/material → needs graph + multi-path
        if "compare" in intents or "material_selector" in intents:
            return "reasoning"

        # Table query → needs structured data
        if "table_query" in intents:
            return "table_search"

        # Fact lookup with low hits → try external
        if internal_hits < 2 and ("numeric_lookup" in intents or "definition" in intents):
            return "external_search"

        # Default → vector search
        return "vector_search"

    def start_working(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._decide_loop())

    async def _decide_loop(self) -> None:
        while self._running:
            try:
                self.meridian.heartbeat(self.organ_id)
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Gallbladder] Loop error: {e}")
                await asyncio.sleep(5)

    def stats(self) -> Dict:
        return {"decisions": self._decisions}
