"""
brain.py — 少阴·炼化 决策合成中枢
合并大脑(决策)+心(路由)+Self-RAG+CRAG
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List

from src.infra.symbol_base import SymbolBase

logger = logging.getLogger("shaoyin.brain")


class ShaoyinBrain(SymbolBase):
    """少阴·炼化 — 决策合成中枢"""

    def __init__(self, meridian):
        super().__init__(
            meridian=meridian,
            symbol_id="shaoyin",
            name="少阴·炼化",
            emoji="🌙",
            description="决策合成中枢：问题进来 → 答案出去"
        )
        self._thought_count = 0
        self._retry_count = 0
        self._self_rag = None
        self._crag = None

    def _get_self_rag(self):
        """延迟加载Self-RAG"""
        if self._self_rag is None:
            try:
                from src.shaoyin.smart_self_rag import SmartSelfRAG
                self._self_rag = SmartSelfRAG()
            except Exception:
                pass
        return self._self_rag

    def _get_crag(self):
        """延迟加载CRAG"""
        if self._crag is None:
            try:
                from src.shaoyin.crag_corrector import CRAGCorrector
                self._crag = CRAGCorrector()
            except Exception:
                pass
        return self._crag

    async def think(self, query: str, history: List[Dict] = None, trace_id: str = None) -> Dict:
        """决策合成入口"""
        self._set_status("processing")
        start_time = time.time()

        if not trace_id:
            from src.infra.logging import get_trace_id
            trace_id = get_trace_id()

        try:
            # Step 1: 意图识别
            intent = self._classify_intent(query)
            logger.info(f"[{trace_id}] [少阴] 意图识别: {intent.get('intent', 'unknown')}")

            # Step 2: 策略选择
            strategy = self._select_strategy(intent)
            logger.info(f"[{trace_id}] [少阴] 策略选择: {strategy}")

            # Step 3: 检索（调用太阳）
            results = await self._retrieve(query, strategy)

            # Step 4: Self-RAG反思（条件触发）
            self_rag = self._get_self_rag()
            reflection_pass = True
            if self_rag:
                max_score = max((r.get("score", 0) for r in results), default=0)
                reflection = await self_rag.reflect_if_needed(query, results, {
                    "max_score": max_score,
                    "query_type": intent.get("intent", "general"),
                })
                reflection_pass = reflection.action == "pass"
                if not reflection_pass:
                    logger.info(f"[{trace_id}] [少阴] Self-RAG未通过: {reflection.reason}")

            # Step 5: CRAG纠正（如果Self-RAG未通过）
            crag_status = "GOOD"
            if not reflection_pass:
                crag = self._get_crag()
                if crag:
                    new_results = await crag.correct_and_retry(query, results)
                    if new_results and len(new_results) > 0:
                        results = new_results
                        crag_status = "NEED_REWRITE"
                        logger.info(f"[{trace_id}] [少阴] CRAG纠正完成: {len(new_results)} results")
                    else:
                        crag_status = "OFF_TOPIC"

            # Step 6: 合成
            answer = await self._compose(query, results, history)

            # Step 7: 校验
            confidence = self._validate(answer, results)

            # Step 8: 纠错
            if confidence < 0.5:
                answer = await self._retry(query, results, history, confidence)

            duration = (time.time() - start_time) * 1000
            self._thought_count += 1

            # 记录成长数据
            try:
                from src.growth.growth_recorder import GrowthRecordPoints
                recorder = GrowthRecordPoints()
                await recorder.record_shaoyin_decision(
                    query=query, trace_id=trace_id or "",
                    intent=intent.get("intent", "unknown"), strategy=strategy,
                    confidence=confidence, retry_count=1 if confidence < 0.5 else 0,
                    duration_ms=duration,
                )
            except Exception:
                pass

            logger.info(f"[{trace_id}] [少阴] 决策完成: {query[:30]}... → confidence={confidence:.2f}, {duration:.0f}ms")

            return {
                "answer": answer,
                "confidence": confidence,
                "intent": intent,
                "strategy": strategy,
                "sources": self._extract_sources(results),
                "duration_ms": duration,
                "trace_id": trace_id,
                "reflection_pass": reflection_pass,
                "crag_status": crag_status,
            }

        except Exception as e:
            logger.error(f"[{trace_id}] [少阴] 决策失败: {e}")
            return {"answer": "抱歉，处理您的问题时出现错误。", "confidence": 0, "error": str(e), "trace_id": trace_id}
        finally:
            self._set_status("idle")

    def _classify_intent(self, query: str) -> Dict:
        """意图识别"""
        try:
            from src.hypothalamus.brain import Instinct
            return Instinct.classify_intent(query)
        except Exception:
            return {"intent": "general_search", "intents": {}, "count": 0}

    def _select_strategy(self, intent: Dict) -> str:
        """策略选择"""
        primary = intent.get("intent", "general_search")
        if primary in ("numeric_lookup", "material_selector", "compare"):
            return "deep"
        elif primary == "table_query":
            return "table"
        else:
            return "fast"

    async def _retrieve(self, query: str, strategy: str) -> List[Dict]:
        """检索（调用太阳）"""
        try:
            from src.taiyang.retrieval import hybrid_search
            return await hybrid_search(query, top_k=10)
        except Exception as e:
            logger.warning(f"[少阴] 检索失败: {e}")
            return []

    async def _compose(self, query: str, results: List[Dict], history: List[Dict] = None) -> str:
        """LLM 合成"""
        try:
            from src.infra.llm import call_deepseek
            context = "\n".join([r.get("text", "")[:200] for r in results[:5]])
            prompt = f"基于以下信息回答问题：\n{context}\n\n问题：{query}"
            answer = await call_deepseek(prompt)
            if answer:
                return answer
        except Exception as e:
            logger.warning(f"[少阴] LLM 合成失败: {e}")

        # 降级：模板拼接
        if results:
            return f"根据知识库信息：{results[0].get('text', '')[:500]}"
        return "知识库中未找到相关信息。"

    def _validate(self, answer: str, results: List[Dict]) -> float:
        """校验"""
        if not answer or len(answer) < 20:
            return 0.3
        if not results:
            return 0.5
        return 0.8

    async def _retry(self, query: str, results: List[Dict], history: List[Dict], prev_confidence: float) -> str:
        """重试"""
        self._retry_count += 1
        try:
            from src.infra.llm import call_deepseek
            context = "\n".join([r.get("text", "")[:300] for r in results[:8]])
            prompt = f"请更准确地回答以下问题，参考文档：\n{context}\n\n问题：{query}"
            answer = await call_deepseek(prompt)
            if answer:
                return answer
        except Exception:
            pass
        return "知识库中未找到相关信息。"

    def _extract_sources(self, results: List[Dict]) -> List[str]:
        """提取来源"""
        sources = []
        for r in results[:5]:
            fn = r.get("file_name", "")
            if fn and fn not in sources:
                sources.append(fn)
        return sources

    def _get_metrics(self) -> dict:
        """返回决策指标"""
        return {
            "thoughts": self._thought_count,
            "retries": self._retry_count,
        }
