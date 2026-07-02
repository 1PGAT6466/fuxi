"""
retrieval.py — 太阳·筑基 混合检索管线
合并肾(精炼)+肝(免疫)+鼻(嗅探)+胆(果断)+四肢(执行)+骨骼(结构)
"""
import asyncio
import logging
import time
from typing import List, Dict, Any, Optional

from src.infra.symbol_base import SymbolBase

logger = logging.getLogger("taiyang.retrieval")


class TaiyangRetrieval(SymbolBase):
    """太阳·筑基 — 精炼排序中枢"""

    def __init__(self, meridian):
        super().__init__(
            meridian=meridian,
            symbol_id="taiyang",
            name="太阳·筑基",
            emoji="☀️",
            description="精炼排序中枢：查询进来 → 精排结果出去"
        )
        self._search_count = 0
        self._cache_hits = 0

    async def refine(self, query: str, strategy: str = "auto", top_k: int = 15, trace_id: str = None) -> List[Dict]:
        """精炼检索入口"""
        self._set_status("processing")
        start_time = time.time()

        if not trace_id:
            from src.infra.logging import get_trace_id
            trace_id = get_trace_id()

        try:
            logger.info(f"[{trace_id}] [太阳] 开始检索: {query[:30]}..., strategy={strategy}")

            # L1: 查询扩展
            expanded_q = self._expand_query(query)

            # L2: 多路召回（并行执行）
            import asyncio
            bm25_task = self._bm25_recall(expanded_q, top_k)
            vector_task = self._vector_recall(expanded_q, top_k)
            bm25_results, vector_results = await asyncio.gather(bm25_task, vector_task)
            logger.info(f"[{trace_id}] [太阳] BM25召回: {len(bm25_results)} results")
            logger.info(f"[{trace_id}] [太阳] 向量召回: {len(vector_results)} results")

            # L2.5: 多跳检索（如果启用）
            multi_hop_results = []
            try:
                from src.taiyin.flags import is_enabled
                if is_enabled("taiyang_multi_hop"):
                    from src.taiyang.multi_hop import multi_hop_search
                    multi_hop_results = await multi_hop_search(query, top_k=top_k)
                    logger.info(f"[{trace_id}] [太阳] 多跳检索: {len(multi_hop_results)} results")
            except Exception as e:
                logger.debug(f"[{trace_id}] [太阳] 多跳检索跳过: {e}")

            # L2.6: 知识图谱查询
            graph_results = []
            try:
                from src.services.graph_traversal import find_paths
                graph_paths = find_paths(query)
                if graph_paths:
                    from src.taiyang.graph import GraphRouter
                    router = GraphRouter()
                    entity_context = router.get_entity_context(query)
                    if entity_context.get("found"):
                        logger.info(f"[{trace_id}] [太阳] 图谱查询: {entity_context.get('count', 0)} 实体")
            except Exception as e:
                logger.debug(f"[{trace_id}] [太阳] 图谱查询跳过: {e}")

            # L3: 融合
            fused = self._fuse(bm25_results, vector_results)

            # L4: 精排
            reranked = await self._rerank(query, fused)

            # L5: 扩展
            expanded = self._expand_context(reranked)

            # L6: 合并多跳结果
            if multi_hop_results:
                from src.taiyang.results_postprocess import merge_search_results
                expanded = merge_search_results(expanded, [], multi_hop_results)

            self._search_count += 1
            duration = (time.time() - start_time) * 1000

            # 记录在线评测指标
            try:
                from src.services.online_eval import get_online_evaluator
                evaluator = get_online_evaluator()
                await evaluator.record_search_metric(query, expanded, duration, trace_id)
            except Exception:
                pass

            # 记录缓存统计
            try:
                from src.infra.cache_stats import get_cache_stats
                get_cache_stats().record_miss(duration)
            except Exception:
                pass

            # 记录成长数据
            try:
                from src.growth.growth_recorder import GrowthRecordPoints
                recorder = GrowthRecordPoints()
                max_score = max([r.get("score", 0) for r in expanded], default=0)
                await recorder.record_taiyang_search(
                    query=query, trace_id=trace_id or "", search_mode=strategy,
                    result_count=len(expanded), max_score=max_score, duration_ms=duration,
                )
            except Exception:
                pass

            logger.info(f"[{trace_id}] [太阳] 检索完成: {query[:30]}... → {len(expanded)} results, {duration:.0f}ms")

            return expanded

        except Exception as e:
            logger.error(f"[{trace_id}] [太阳] 检索失败: {e}")
            # 记录错误
            try:
                from src.infra.error_tracker import get_error_tracker
                get_error_tracker().record_error("retrieval_failed", str(e), {"query": query[:100], "trace_id": trace_id})
            except Exception:
                pass
            return []
        finally:
            self._set_status("idle")

    def _expand_query(self, query: str) -> str:
        """查询扩展"""
        try:
            from src.taiyang.query_expansion import expand_query
            return expand_query(query)
        except Exception:
            return query

    async def _bm25_recall(self, query: str, top_k: int) -> List[Dict]:
        """BM25 召回"""
        try:
            from src.db.memory_store import get_store
            store = get_store()
            results = store.keyword_search(query, top_k)
            return [{"text": r.get("text", ""), "file_name": r.get("file_name", ""), "score": r.get("score", 0), "_source": "bm25"} for r in results]
        except Exception:
            return []

    async def _vector_recall(self, query: str, top_k: int) -> List[Dict]:
        """向量召回"""
        try:
            from src.db.vector_store import embed_texts, get_vector_store
            q_emb = await embed_texts([query])
            if not q_emb or not q_emb[0]:
                return []
            vs = get_vector_store()
            if not vs or vs.count <= 0:
                return []
            result = vs.query(q_emb[0], n_results=top_k)
            if not result.get("ids") or not result["ids"][0]:
                return []
            results = []
            for i, vid in enumerate(result["ids"][0]):
                meta = result["metadatas"][0][i] if i < len(result["metadatas"][0]) else {}
                dist = result["distances"][0][i] if i < len(result["distances"][0]) else 0
                sim = 1.0 - float(dist)
                if sim > 0.15:
                    results.append({
                        "file_hash": meta.get("file_hash", ""),
                        "text": meta.get("text", ""),
                        "file_name": meta.get("file_name", ""),
                        "score": round(sim * 10, 2),
                        "_source": "vector",
                        "_similarity": round(sim, 4),
                    })
            return results
        except Exception:
            return []

    def _fuse(self, bm25_results: List[Dict], vector_results: List[Dict]) -> List[Dict]:
        """RRF 融合"""
        try:
            from src.taiyang.fusion import rrf_fusion
            return rrf_fusion(bm25_results, vector_results)
        except Exception:
            return bm25_results + vector_results

    async def _rerank(self, query: str, results: List[Dict]) -> List[Dict]:
        """精排"""
        try:
            from src.taiyang.rerank import rerank_with_deepseek
            reranked = await rerank_with_deepseek(query, results, top_k=len(results))
            if reranked:
                return reranked
        except Exception:
            pass
        return results

    def _expand_context(self, results: List[Dict]) -> List[Dict]:
        """上下文扩展"""
        try:
            from src.taiyang.results_postprocess import expand_context
            return expand_context(results)
        except Exception:
            return results

    def _get_metrics(self) -> dict:
        """返回检索指标"""
        return {
            "search_count": self._search_count,
            "cache_hit_rate": self._cache_hits / max(self._search_count, 1),
        }


# 全局实例
_retrieval_instance = None

def get_retrieval(meridian=None) -> TaiyangRetrieval:
    """获取全局检索实例"""
    global _retrieval_instance
    if _retrieval_instance is None and meridian:
        _retrieval_instance = TaiyangRetrieval(meridian)
    return _retrieval_instance

async def hybrid_search(query: str, **kwargs) -> List[Dict]:
    """兼容旧接口的混合检索"""
    instance = get_retrieval()
    if instance:
        return await instance.refine(query, **kwargs)
    return []
