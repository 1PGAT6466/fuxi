"""
retrieval.py — 太阳·筑基 混合检索管线
合并肾(精炼)+肝(免疫)+鼻(嗅探)+胆(果断)+四肢(执行)+骨骼(结构)
"""
import asyncio
import json
import logging
import time
from typing import List, Dict, Any

from src.infra.symbol_base import SymbolBase
from src.taiyang.shared import _deduplicate_chunks

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

    async def refine(self, query: str, strategy: str = "auto", top_k: int = 15, trace_id: str = None, granularity: str = "chunk", entities: List[str] = None, tenant_id: str = "default") -> List[Dict]:
        """精炼检索入口

        Args:
            query: 用户查询
            strategy: 检索策略 (auto/fast/deep/table)
            top_k: 返回结果数
            trace_id: 链路追踪ID
            granularity: 检索粒度 (chunk/event/auto) — 任务 4 新增
            entities: 少阴提取的实体列表 — 任务 4 新增（用于 Path A）
        """
        self._set_status("processing")
        start_time = time.time()

        if not trace_id:
            from src.infra.logging import get_trace_id
            trace_id = get_trace_id()

        try:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"[{trace_id}] [太阳] 开始检索: {query[:30]}..., strategy={strategy}, granularity={granularity}")
            else:
                logger.info(f"[{trace_id}] [太阳] 开始检索: query_len={len(query)}, strategy={strategy}, granularity={granularity}")

            # ================================================================
            # 任务 4: granularity 参数路由
            # 支持 'chunk'（默认）、'event'、'auto' 三种模式
            # ================================================================
            resolved_granularity = self._resolve_granularity(query, granularity, strategy)

            # Event 粒度：走 event_search 路径
            if resolved_granularity == "event":
                from src.services.feature_flags import is_enabled
                if is_enabled("taiyang_event_search"):
                    event_result = await self.event_search(query, top_k=top_k, trace_id=trace_id)
                    chunks = event_result.get("mapped_chunks", [])
                    if chunks:
                        # 补充 Path B 向量结果
                        bm25_task = self._bm25_recall(query, top_k=top_k)
                        vector_chunks = await self._path_b_vector_search(query, top_k)
                        chunks = self._deduplicate_chunks(chunks + vector_chunks)
                        chunks.sort(
                            key=lambda x: x.get("_event_score", 0) + x.get("score", 0) * 0.5,
                            reverse=True,
                        )
                        self._search_count += 1
                        return chunks[:top_k]
                # Event 检索失败或无结果，降级到 chunk 检索
                logger.info(f"[{trace_id}] [太阳] Event粒度失败或无结果，降级为 chunk 检索")

            # Chunk 粒度：走现有混合检索路径
            # ================================================================

            # L0: 查询缓存检查
            try:
                from src.taiyang.cache import get_cache
                cached = await get_cache(query, category="", top_k=top_k)
                if cached:
                    self._cache_hits += 1
                    self._search_count += 1
                if logger.isEnabledFor(logging.DEBUG):
                    logger.info(f"[{trace_id}] [太阳] L0 缓存命中: {query[:40]}..., 返回 {len(cached)} 条")
                else:
                    logger.info(f"[{trace_id}] [太阳] L0 缓存命中: query_len={len(query)}, 返回 {len(cached)} 条")
                    return cached
            except Exception as e:  # TODO: Narrow exception type
                logger.debug(f"[{trace_id}] [太阳] 缓存检查跳过: {e}")

            # ==============================================================
            # 任务 5: L3 深度模式 → 完整 SAG 三阶段管线
            # L1/L2 保持原样（只用 Path B 向量）
            # ==============================================================
            if strategy == "deep" and self._should_use_sag(query):
                sag_chunks = await self._refine_with_sag(
                    query, strategy, top_k, trace_id, entities
                )
                if sag_chunks is not None:
                    return sag_chunks
                # SAG 降级，继续走下面标准检索

            # L1: 查询扩展
            expanded_q = self._expand_query(query)

            # L2: 多路召回（并行执行）
            import asyncio
            bm25_task = self._bm25_recall(expanded_q, top_k, tenant_id=tenant_id)
            vector_task = self._vector_recall(expanded_q, top_k, tenant_id=tenant_id)
            bm25_results, vector_results = await asyncio.gather(bm25_task, vector_task)
            logger.info(f"[{trace_id}] [太阳] BM25召回: {len(bm25_results)} results")
            logger.info(f"[{trace_id}] [太阳] 向量召回: {len(vector_results)} results")

            # L2.5: 多跳检索（如果启用）
            multi_hop_results = []
            try:
                from src.services.feature_flags import is_enabled
                if is_enabled("taiyang_multi_hop"):
                    from src.taiyang.multi_hop import multi_hop_search
                    multi_hop_results = await multi_hop_search(query, top_k=top_k)
                    logger.info(f"[{trace_id}] [太阳] 多跳检索: {len(multi_hop_results)} results")
            except Exception as e:  # TODO: Narrow exception type
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
            except Exception as e:  # TODO: Narrow exception type
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
            except Exception:  # TODO: Narrow exception type
                pass

            # 记录缓存统计
            try:
                from src.infra.cache_stats import get_cache_stats
                get_cache_stats().record_miss(duration)
            except Exception:  # TODO: Narrow exception type
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
            except Exception:  # TODO: Narrow exception type
                pass

            # L7: 写入缓存
            if expanded:
                try:
                    from src.taiyang.cache import set_cache
                    await set_cache(query, expanded, category="", top_k=top_k)
                except Exception as e:  # TODO: Narrow exception type
                    logger.debug(f"[{trace_id}] [太阳] 缓存写入跳过: {e}")

            if logger.isEnabledFor(logging.DEBUG):
                logger.info(f"[{trace_id}] [太阳] 检索完成: query={query[:30]}... → {len(expanded)} results, {duration:.0f}ms")
            else:
                logger.info(f"[{trace_id}] [太阳] 检索完成: query_len={len(query)}, {len(expanded)} results, {duration:.0f}ms")

            return expanded

        except Exception as e:  # TODO: Narrow exception type
            logger.error(f"[{trace_id}] [太阳] 检索失败: {e}")
            # 记录错误
            try:
                from src.infra.error_tracker import get_error_tracker
                get_error_tracker().record_error("retrieval_failed", str(e), {"query": query[:100], "trace_id": trace_id})
            except Exception:  # TODO: Narrow exception type
                pass
            return []
        finally:
            self._set_status("idle")

    def _expand_query(self, query: str) -> str:
        """查询扩展"""
        try:
            from src.taiyang.query_expansion import expand_query
            return expand_query(query)
        except Exception:  # TODO: Narrow exception type
            return query

    async def _bm25_recall(self, query: str, top_k: int, tenant_id: str = "default") -> List[Dict[str, Any]]:
        """BM25 召回 — FIX-D2: SQLite 调用包装到线程池"""
        try:
            import asyncio
            from src.db.memory_store import get_store
            store = get_store()
            results = await asyncio.to_thread(
                lambda: store.keyword_search(query, top_k, tenant_id=tenant_id)
            )
            return [
                {"text": r.get("text", ""), "file_name": r.get("file_name", ""),
                 "score": r.get("score", 0), "_source": "bm25"}
                for r in results
            ]
        except Exception:  # TODO: Narrow exception type
            return []

    async def _vector_recall(self, query: str, top_k: int, tenant_id: str = "default") -> List[Dict[str, Any]]:
        """向量召回 — v1.44 R2: 使用 ChromaDB where 子句实现租户隔离"""
        try:
            from src.db.vector_store import embed_texts, get_vector_store
            q_emb = await embed_texts([query])
            if not q_emb or not q_emb[0]:
                return []
            vs = get_vector_store()
            if not vs or vs.count <= 0:
                return []
            # v1.44 R2: 租户隔离 — 在 ChromaDB 层面过滤，而非事后过滤
            where_filter = {"tenant_id": tenant_id} if tenant_id != "default" else None
            result = vs.query(q_emb[0], n_results=top_k, where=where_filter)
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
        except Exception:  # TODO: Narrow exception type
            return []

    def _fuse(self, bm25_results: List[Dict], vector_results: List[Dict]) -> List[Dict[str, Any]]:
        """RRF 融合"""
        try:
            from src.taiyang.fusion import rrf_fusion
            return rrf_fusion(bm25_results, vector_results)
        except Exception:  # TODO: Narrow exception type
            return bm25_results + vector_results

    async def _rerank(self, query: str, results: List[Dict]) -> List[Dict[str, Any]]:
        """精排"""
        try:
            from src.taiyang.rerank import rerank_with_deepseek
            reranked = await rerank_with_deepseek(query, results, top_k=len(results))
            if reranked:
                return reranked
        except Exception:  # TODO: Narrow exception type
            pass
        return results

    def _expand_context(self, results: List[Dict]) -> List[Dict[str, Any]]:
        """上下文扩展"""
        try:
            from src.taiyang.results_postprocess import expand_context
            return expand_context(results)
        except Exception:  # TODO: Narrow exception type
            return results

    # ==================================================================
    # 任务 1: Event 粒度检索输出
    # ADR-003: Event 作为召回索引，Chunk 作为最终输出载体
    # ==================================================================
    async def event_search(self, query: str, top_k: int = 15, trace_id: str = None) -> Dict[str, Any]:
        """Event 粒度检索

        在 ChromaDB 中查询 event 集合（如果存在），
        或从 SQLite events 表按 entity 反查。

        Returns:
            {
                "events": [...],          # 检索到的 event 列表
                "mapped_chunks": [...],   # 通过 event.chunk_ids 映射的 chunks
                "granularity": "event",
                "source": "db_reverse" | "chroma",
            }
        """
        if not trace_id:
            from src.infra.logging import get_trace_id
            trace_id = get_trace_id()

            if logger.isEnabledFor(logging.DEBUG):
                logger.info(f"[{trace_id}] [太阳] Event粒度检索: {query[:30]}..., top_k={top_k}")
            else:
                logger.info(f"[{trace_id}] [太阳] Event粒度检索: query_len={len(query)}, top_k={top_k}")

        # 尝试 ChromaDB event 集合
        events = await self._chroma_event_search(query, top_k)
        source = "chroma" if events else "db_reverse"

        if not events:
            # 降级：从 SQLite events 表按 entity 反查
            events = await self._db_event_reverse_search(query, top_k)
            source = "db_reverse"
            if not events:
                logger.info(f"[{trace_id}] [太阳] Event粒度检索: 无结果")
                return {"events": [], "mapped_chunks": [], "granularity": "event", "source": source}

        # Event → Chunk 映射（ADR-003 粒度切换点）
        mapped_chunks = await self._event_to_chunk_mapping(events, top_k)

        logger.info(
            f"[{trace_id}] [太阳] Event粒度检索完成: "
            f"{len(events)} events → {len(mapped_chunks)} chunks ({source})"
        )

        return {
            "events": events,
            "mapped_chunks": mapped_chunks,
            "granularity": "event",
            "source": source,
        }

    async def _chroma_event_search(self, query: str, top_k: int) -> List[Dict]:
        """从 ChromaDB kb_events 集合检索

        TODO: Phase A 需要先创建 kb_events ChromaDB 集合 + 向量化 events。
        当前 events 表为空（0 条），ChromaDB event 集合也不存在。
        此处做 stub 实现，等 Phase A 完成 Event 向量化后自动生效。
        """
        try:
            from src.db.vector_store import embed_texts, get_vector_store

            q_emb = await embed_texts([query])
            if not q_emb or not q_emb[0]:
                return []

            # 尝试获取 event 集合（如果 Phase A 已创建）
            try:
                import chromadb
                from chromadb.config import Settings as ChromaSettings
                from src.data_service import get_chroma_dir

                persist_dir = get_chroma_dir()
                client = chromadb.PersistentClient(
                    path=persist_dir,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
                event_collection = client.get_collection("kb_events")

                result = event_collection.query(
                    query_embeddings=[q_emb[0]],
                    n_results=top_k,
                    include=["metadatas", "distances"],
                )

                events = []
                if result.get("ids") and result["ids"][0]:
                    for i, eid in enumerate(result["ids"][0]):
                        meta = result["metadatas"][0][i] if i < len(result.get("metadatas", [[]])[0]) else {}
                        dist = result["distances"][0][i] if i < len(result.get("distances", [[]])[0]) else 1.0
                        sim = 1.0 - float(dist)
                        if sim > 0.4:
                            events.append({
                                "event_id": eid,
                                "title": meta.get("title", ""),
                                "summary": meta.get("summary", ""),
                                "chunk_ids": json.loads(meta.get("chunk_ids", "[]")) if meta.get("chunk_ids") else [],
                                "entity_names": json.loads(meta.get("entity_names", "[]")) if meta.get("entity_names") else [],
                                "_similarity": round(sim, 4),
                                "_source": "chroma_event",
                            })
                return events

            except Exception:  # TODO: Narrow exception type
                # kb_events collection does not exist yet (Phase A not done)
                return []

        except Exception as e:  # TODO: Narrow exception type
            logger.debug(f"[太阳] ChromaDB event 检索跳过: {e}")
            return []

    async def _db_event_reverse_search(self, query: str, top_k: int) -> List[Dict]:
        """从 SQLite events 表按 entity 反查

        FIX-D2: SQLite 调用包装到 asyncio.to_thread()
        """
        try:
            from src.db.memory_store import get_store
            import asyncio
            import re

            store = get_store()

            import jieba
            words = list(jieba.cut(query))
            entities = [w for w in words if len(w) > 1]
            eng_entities = re.findall(r'[A-Za-z0-9]{2,}', query)
            entities = list(set(entities + eng_entities))[:10]

            if not entities:
                return []

            events = []
            seen_ids = set()

            # P1-4B FIX: 并行化 LIKE 查询替代串行 N+1
            async def _like_query_one(entity: str) -> List[tuple]:
                return await asyncio.to_thread(
                    lambda en=entity: store._db_conn.execute(
                        "SELECT event_id, title, summary, content, chunk_ids_json, "
                        "entity_names_json, event_type, level, file_hash, file_name "
                        "FROM events WHERE (entity_names_json LIKE ? OR title LIKE ?) AND status='active' LIMIT 10",
                        (f"%{en}%", f"%{en}%"),
                    ).fetchall()
                )

            like_results = await asyncio.gather(
                *[_like_query_one(en) for en in entities],
                return_exceptions=True
            )

            for i, rows in enumerate(like_results):
                if isinstance(rows, Exception):
                    continue
                entity = entities[i]
                for row in rows:
                    eid = row[0]
                    if eid not in seen_ids:
                        seen_ids.add(eid)
                        events.append({
                            "event_id": row[0], "title": row[1], "summary": row[2],
                            "content": row[3],
                            "chunk_ids": json.loads(row[4]) if row[4] else [],
                            "entity_names": json.loads(row[5]) if row[5] else [],
                            "category": row[6], "level": row[7],
                            "file_hash": row[8], "file_name": row[9],
                            "_source": "db_reverse", "_matched_entity": entity,
                            "_score": 0.5,
                        })

            return events[:top_k]

        except Exception as e:  # TODO: Narrow exception type
            logger.debug(f"[太阳] DB event 反查跳过: {e}")
            return []

    async def _event_to_chunk_mapping(
        self, events: List[Dict], top_k: int = 15
    ) -> List[Dict]:
        """Event → Chunk 粒度切换（ADR-003）— FIX-D2: 批量查询"""
        try:
            from src.db.memory_store import get_store

            store = get_store()
            all_chunks = {}

            # 收集所有 chunk_ids
            all_cids = set()
            event_title_map = {}
            for event in events:
                for cid in event.get("chunk_ids", []):
                    all_cids.add(cid)
                    event_title_map[cid] = event.get("title", "")

            # 批量获取 chunks
            chunk_map = store.get_chunks_batch(list(all_cids))

            for cid, chunk in chunk_map.items():
                chunk["_via_event"] = event_title_map.get(cid, "")
                chunk["_event_score"] = 0.5
                chunk["_granularity"] = "event"
                all_chunks[cid] = chunk

            chunks = list(all_chunks.values())
            chunks.sort(key=lambda x: x.get("_event_score", 0), reverse=True)
            return chunks[:top_k]

        except Exception as e:  # TODO: Narrow exception type
            logger.debug(f"[太阳] Event→Chunk 映射失败: {e}")
            return []

    # ==================================================================
    # 任务 4: granularity 解析
    # ==================================================================
    def _resolve_granularity(self, query: str, granularity: str, strategy: str) -> str:
        """解析粒度参数
        - 'chunk': chunk 粒度（默认，向后兼容）
        - 'event': event 粒度
        - 'auto': 自动检测（多跳→event，简单→chunk）
        """
        if granularity == "event":
            return "event"
        if granularity == "chunk":
            return "chunk"
        if granularity == "auto":
            return self._auto_detect_granularity(query, strategy)
        return "chunk"

    def _auto_detect_granularity(self, query: str, strategy: str) -> str:
        """自动检测查询复杂度来选择粒度"""
        if strategy == "deep":
            return "event"
        multi_hop_keywords = ["对比", "比较", "区别", "不同", "关系", "关联",
                             "相关", "影响", "原因", "结果", "过程", "vs", "相比"]
        for kw in multi_hop_keywords:
            if kw in query:
                return "event"
        if len(query) > 30:
            return "event"
        return "chunk"

    def _should_use_sag(self, query: str) -> bool:
        """判断是否应使用 SAG 管线（任务 5）"""
        try:
            from src.services.feature_flags import is_enabled
            if not is_enabled("taiyang_sag_pipeline"):
                return False
        except Exception:  # TODO: Narrow exception type
            return False
        return True

    # ==================================================================
    # 任务 5: SAG 管线集成
    # ==================================================================
    async def _refine_with_sag(self, query, strategy, top_k, trace_id=None, entities=None):
        """L3深度模式：完整SAG三阶段管线"""
        logger.info(f"[{trace_id}] [太阳] L3深度模式 -> SAG三阶段管线")
        try:
            from src.taiyang.sag_pipeline import execute_sag_pipeline
            sag_result = await execute_sag_pipeline(
                query=query, entities=entities, top_k=top_k,
                strategy=strategy, trace_id=trace_id,
                enable_path_a=True, enable_multi_hop=True, enable_rerank=True)
            chunks = sag_result.get("chunks", [])
            if len(chunks) < top_k:
                bm25_chunks = await self._bm25_recall(query, top_k)
                vector_chunks = await self._vector_recall(query, top_k)
                chunks = self._deduplicate_chunks(chunks + bm25_chunks + vector_chunks)
            self._search_count += 1
            return chunks[:top_k]
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[{trace_id}] [太阳] SAG管线失败，降级标准检索: {e}")
            return None

    def _deduplicate_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """去重辅助 — 委托给共享实现"""
        return _deduplicate_chunks(chunks)


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


async def event_search(query: str, top_k: int = 15, trace_id: str = None, tenant_id: str = "default") -> Dict[str, Any]:
    """Event 粒度检索（任务 1）— 兼容旧接口
    
    Returns:
        {
            "events": [...],
            "mapped_chunks": [...],
            "granularity": "event",
            "source": "db_reverse" | "chroma",
        }
    """
    instance = get_retrieval()
    if instance:
        return await instance.event_search(query, top_k=top_k, trace_id=trace_id)
    return {"events": [], "mapped_chunks": [], "granularity": "event", "source": "unavailable"}
