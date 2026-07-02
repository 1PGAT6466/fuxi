"""
server.py — 太阴·显化 对外接口中枢
合并皮肤(屏障)+三焦(通道)的能力
"""
import logging
import time
from typing import Dict, Any, Optional

from src.infra.symbol_base import SymbolBase

logger = logging.getLogger("taiyin.server")


class TaiyinServer(SymbolBase):
    """太阴·显化 — 对外接口中枢"""

    def __init__(self, meridian):
        super().__init__(
            meridian=meridian,
            symbol_id="taiyin",
            name="太阴·显化",
            emoji="🌑",
            description="对外接口中枢：一个入口，一个出口"
        )
        self._request_count = 0
        self._error_count = 0

    async def handle_query(self, query: str, history: list = None, trace_id: str = None) -> Dict:
        """处理用户查询 — 路由到少阴"""
        from src.infra.logging import get_trace_id
        if not trace_id:
            trace_id = get_trace_id()

        self._request_count += 1
        start_time = time.time()

        try:
            logger.info(f"[{trace_id}] [太阴] 收到查询: {query[:50]}...")

            # 调用少阴决策
            shaoyin = self.meridian.get_symbol("shaoyin")
            if shaoyin:
                result = await shaoyin.think(query, history=history, trace_id=trace_id)
            else:
                # 降级：直接调用太阳检索+LLM合成
                result = await self._fallback_query(query, trace_id)

            duration = (time.time() - start_time) * 1000
            result["trace_id"] = trace_id
            result["duration_ms"] = duration

            # 记录成长数据
            try:
                from src.growth.growth_recorder import GrowthRecordPoints
                recorder = GrowthRecordPoints()
                await recorder.record_taiyin_request(
                    trace_id=trace_id, endpoint="/api/chat",
                    method="POST", status_code=200, duration_ms=duration,
                )
            except Exception:
                pass

            logger.info(f"[{trace_id}] [太阴] 查询完成: {duration:.0f}ms, confidence={result.get('confidence', 0):.2f}")

            return result

        except Exception as e:
            self._error_count += 1
            logger.error(f"[{trace_id}] [太阴] 查询失败: {e}")

            # 记录错误
            try:
                from src.growth.growth_recorder import GrowthRecordPoints
                recorder = GrowthRecordPoints()
                duration = (time.time() - start_time) * 1000
                await recorder.record_taiyin_request(
                    trace_id=trace_id or "", endpoint="/api/chat",
                    method="POST", status_code=500, duration_ms=duration,
                )
            except Exception:
                pass

            return {
                "answer": "抱歉，处理您的问题时出现错误。",
                "confidence": 0,
                "error": str(e),
                "trace_id": trace_id,
            }

    async def handle_search(self, query: str, top_k: int = 10, trace_id: str = None) -> Dict:
        """处理搜索请求 — 路由到太阳"""
        from src.infra.logging import get_trace_id
        if not trace_id:
            trace_id = get_trace_id()

        self._request_count += 1
        start_time = time.time()

        try:
            logger.info(f"[{trace_id}] [太阴] 收到搜索: {query[:50]}...")

            # 调用太阳检索
            taiyang = self.meridian.get_symbol("taiyang")
            if taiyang:
                results = await taiyang.refine(query, top_k=top_k, trace_id=trace_id)
            else:
                from src.taiyang.retrieval import hybrid_search
                results = await hybrid_search(query, top_k=top_k)

            duration = (time.time() - start_time) * 1000

            # 记录成长数据
            try:
                from src.growth.growth_recorder import GrowthRecordPoints
                recorder = GrowthRecordPoints()
                await recorder.record_taiyin_request(
                    trace_id=trace_id, endpoint="/api/search",
                    method="GET", status_code=200, duration_ms=duration,
                )
            except Exception:
                pass

            return {
                "results": results,
                "count": len(results),
                "trace_id": trace_id,
                "duration_ms": duration,
            }

        except Exception as e:
            self._error_count += 1
            logger.error(f"[{trace_id}] [太阴] 搜索失败: {e}")

            # 记录错误
            try:
                from src.growth.growth_recorder import GrowthRecordPoints
                recorder = GrowthRecordPoints()
                duration = (time.time() - start_time) * 1000
                await recorder.record_taiyin_request(
                    trace_id=trace_id or "", endpoint="/api/search",
                    method="GET", status_code=500, duration_ms=duration,
                )
            except Exception:
                pass

            return {"results": [], "count": 0, "error": str(e), "trace_id": trace_id}

    async def handle_ingest(self, file_path: str, source: str = "upload", trace_id: str = None) -> Dict:
        """处理入库请求 — 路由到少阳"""
        from src.infra.logging import get_trace_id
        if not trace_id:
            trace_id = get_trace_id()

        self._request_count += 1
        start_time = time.time()

        try:
            logger.info(f"[{trace_id}] [太阴] 收到入库: {file_path}")

            # 调用少阳消化
            shaoyang = self.meridian.get_symbol("shaoyang")
            if shaoyang:
                result = await shaoyang.digest(file_path, source=source)
            else:
                from src.shaoyang.pipeline import ShaoyangPipeline
                pipeline = ShaoyangPipeline(self.meridian)
                result = await pipeline.digest(file_path, source=source)

            duration = (time.time() - start_time) * 1000

            return {
                "success": True,
                "chunks": len(result.chunks),
                "events": len(result.events),
                "entities": len(result.entities),
                "duration_ms": duration,
                "trace_id": trace_id,
            }

        except Exception as e:
            self._error_count += 1
            logger.error(f"[{trace_id}] [太阴] 入库失败: {e}")
            return {"success": False, "error": str(e), "trace_id": trace_id}

    async def _fallback_query(self, query: str, trace_id: str) -> Dict:
        """降级查询（少阴不可用时）"""
        try:
            from src.taiyang.retrieval import hybrid_search
            from src.infra.llm import call_llm

            results = await hybrid_search(query, top_k=5)
            context = "\n".join([r.get("text", "")[:200] for r in results[:3]])
            prompt = f"基于以下信息回答问题：\n{context}\n\n问题：{query}"
            answer = await call_llm(prompt, max_tokens=1000)

            return {
                "answer": answer or "知识库中未找到相关信息。",
                "confidence": 0.5,
                "sources": [r.get("file_name", "") for r in results[:3]],
                "fallback": True,
            }
        except Exception as e:
            return {"answer": "抱歉，处理您的问题时出现错误。", "confidence": 0, "error": str(e)}

    def _get_metrics(self) -> dict:
        """返回接口指标"""
        return {
            "request_count": self._request_count,
            "error_count": self._error_count,
            "error_rate": self._error_count / max(self._request_count, 1),
        }
