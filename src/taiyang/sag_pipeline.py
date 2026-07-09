"""
sag_pipeline.py — 太阳·筑基 SAG 三阶段检索管线

任务 3：SAG 三阶段管线融合五层路由

三阶段流程：
  阶段 1: Seed Retrieval（种子检索）
    ├─ Path A: 实体引导路径（entity_guided_recall）
    └─ Path B: 直接向量检索（hybrid_search）

  阶段 2: Query-Time Expansion（查询时多跳扩展，H=1）
    └─ 从 seed events 反查关联 entities → SQL JOIN 新 events

  阶段 3: LLM Rerank（LLM 精排）
    ├─ 粗排 Top-100
    └─ LLM 精排 → Top-K

最后 merge 为 chunk_ids 列表返回。

📋 ADR-001: SAG 三阶段作为太阳核心检索范式
📋 ADR-003: Event 作为召回索引，Chunk 作为最终输出载体
📋 ADR-006: 控制 LLM 调用次数（SAG 三阶段最多 3 次）

性能优化 (Round 1 审计):
- FIX-11: 候选集大小上限 MAX_SEED_CHUNKS=200, MAX_MULTI_HOP_EVENTS=50
- FIX-12: 阶段 2 entity 查找改为批量并行
- FIX-13: SQLite 调用包装到 asyncio.to_thread()
- FIX-14: 日志降级 + isEnabledFor() 预检查
"""
import json
import logging
import asyncio
import time
from typing import List, Dict, Any, Optional

from src.taiyang.shared import _events_to_chunks, _deduplicate_chunks

logger = logging.getLogger("taiyang.sag_pipeline")

# ===== 候选集大小上限 =====
MAX_SEED_CHUNKS = 200       # 阶段 1 种子检索 chunk 上限
MAX_MULTI_HOP_EVENTS = 50   # 阶段 2 多跳新事件上限
MAX_EVENTS_TO_CHUNKS = 30   # Event→Chunk 映射时处理的 event 上限
COARSE_RANK_TOP = 100       # 粗排阶段取 top-N


class SAGPipeline:
    """SAG 三阶段检索管线

    遵循 ADR-001：作为太阳·筑基的标准内部检索范式
    遵循 ADR-006：LLM 调用次数控制（完整 SAG ≤ 3 次 LLM）
    """

    def __init__(self):
        self._search_count = 0

    async def execute(
        self,
        query: str,
        entities: List[str] = None,
        top_k: int = 15,
        strategy: str = "deep",
        trace_id: str = None,
        enable_path_a: bool = True,
        enable_multi_hop: bool = True,
        enable_rerank: bool = True,
    ) -> Dict[str, Any]:
        """执行完整 SAG 三阶段管线

        降级策略 (D-1~D-3, Round 2 审计):
          - 阶段 1 失败 → fallback 到纯向量检索 (Path B only)
          - 阶段 2 失败 → 跳过，复用阶段 1 结果
          - 阶段 3 失败 → 跳过，按得分排序返回
          - 整个 SAG 管线崩溃 → fallback 到纯向量检索
        """
        start_time = time.time()
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"[{trace_id or 'SAG'}] 三阶段管线启动: query={query[:30]}..., strategy={strategy}")
        elif logger.isEnabledFor(logging.INFO):
            logger.info(f"[{trace_id or 'SAG'}] 三阶段管线启动: query_len={len(query)}, strategy={strategy}")

        phase_stats = {}
        all_events = []
        all_chunks = []
        path_a_result = None
        degraded = False

        try:
            # ============================================================
            # 阶段 1: 种子检索 Seed Retrieval（Path A + Path B 并行）
            # ============================================================
            phase_start = time.time()

            try:
                path_a_task = None
                path_b_task = self._path_b_vector_search(query, top_k=100, trace_id=trace_id)

                if entities and enable_path_a:
                    path_a_task = self._path_a_entity_search(query, entities, top_k=100, trace_id=trace_id)

                if path_a_task:
                    path_b_result, path_a_result = await asyncio.gather(path_b_task, path_a_task)
                else:
                    path_b_result = await path_b_task
            except Exception as e:  # TODO: Narrow exception type
                logger.warning(f"[{trace_id or 'SAG'}] 阶段1 异常，降级到 Path B only: {e}")
                # D-1: 阶段 1 整体失败 → fallback 到纯向量
                degraded = True
                path_b_result = await self._path_b_vector_search(query, top_k=top_k, trace_id=trace_id)
                path_a_result = None

            # 合并种子结果
            if path_a_result:
                path_a_chunks = path_a_result.get("chunks", [])[:MAX_SEED_CHUNKS // 2]
                path_a_events = path_a_result.get("events", [])
                all_events.extend(path_a_events)
                all_chunks.extend(path_a_chunks)
                phase_stats["path_a"] = {
                    "events": len(path_a_events),
                    "chunks": len(path_a_chunks),
                    "entity_hits": len(path_a_result.get("entity_hits", [])),
                }

            if path_b_result:
                path_b_chunks = path_b_result[:MAX_SEED_CHUNKS // 2]
                all_chunks.extend(path_b_chunks)
                phase_stats["path_b"] = {"chunks": len(path_b_chunks)}

            all_chunks = self._deduplicate_chunks(all_chunks[:MAX_SEED_CHUNKS])
            phase_stats["seed"] = {
                "total_chunks": len(all_chunks),
                "total_events": len(all_events),
                "duration_ms": (time.time() - phase_start) * 1000,
            }

            if logger.isEnabledFor(logging.INFO):
                logger.info(
                    f"[{trace_id or 'SAG'}] 阶段1 种子检索完成: "
                    f"{len(all_chunks)} chunks, {len(all_events)} events"
                )

            # ============================================================
            # 阶段 2: 查询时多跳扩展 Query-Time Expansion (H=1)
            # ============================================================
            if enable_multi_hop and all_events and not degraded:
                phase_start = time.time()

                try:
                    multi_hop_events = await self._query_time_expansion(
                        all_events, top_k=MAX_MULTI_HOP_EVENTS
                    )
                except Exception as e:  # TODO: Narrow exception type
                    # D-2: 阶段 2 失败 → 跳过，继续使用阶段 1 结果
                    logger.warning(f"[{trace_id or 'SAG'}] 阶段2 异常，跳过: {e}")
                    multi_hop_events = []

                if multi_hop_events:
                    multi_hop_chunks = await self._events_to_chunks(
                        multi_hop_events[:MAX_EVENTS_TO_CHUNKS], top_k=30
                    )
                    all_events.extend(multi_hop_events[:MAX_MULTI_HOP_EVENTS])
                    all_chunks.extend(multi_hop_chunks)
                    all_chunks = self._deduplicate_chunks(all_chunks[:MAX_SEED_CHUNKS + 100])

                phase_stats["multi_hop"] = {
                    "new_events": len(multi_hop_events),
                    "total_chunks_after": len(all_chunks),
                    "duration_ms": (time.time() - phase_start) * 1000,
                }

                if logger.isEnabledFor(logging.INFO):
                    logger.info(
                        f"[{trace_id or 'SAG'}] 阶段2 多跳扩展完成: "
                        f"+{len(multi_hop_events)} events, 总{len(all_chunks)} chunks"
                    )

            # ============================================================
            # 【粒度切换点】Event → Chunk（ADR-003）
            # ============================================================
            if all_events and len(all_chunks) < top_k:
                event_chunks = await self._events_to_chunks(
                    all_events[:MAX_EVENTS_TO_CHUNKS], top_k=top_k + 20
                )
                all_chunks.extend(event_chunks)
                all_chunks = self._deduplicate_chunks(all_chunks[:MAX_SEED_CHUNKS + 100])

            # ============================================================
            # 阶段 3: LLM Rerank（精排）
            # ============================================================
            if enable_rerank and all_chunks:
                phase_start = time.time()

                # 粗排：先按得分排序
                all_chunks.sort(
                    key=lambda x: x.get("_event_score", 0) + x.get("score", 0) * 0.5 + x.get("_similarity", 0),
                    reverse=True,
                )
                coarse_ranked = all_chunks[:COARSE_RANK_TOP]

                try:
                    reranked_chunks = await self._llm_rerank(query, coarse_ranked, top_k)
                    final_chunks = reranked_chunks if reranked_chunks else coarse_ranked[:top_k]
                    phase_stats["rerank"] = {
                        "before_count": len(coarse_ranked),
                        "after_count": len(final_chunks),
                        "duration_ms": (time.time() - phase_start) * 1000,
                    }
                except Exception as e:  # TODO: Narrow exception type
                    # D-3: 阶段 3 失败 → 按得分排序返回
                    logger.warning(f"[{trace_id or 'SAG'}] 阶段3 异常，按得分排序: {e}")
                    final_chunks = coarse_ranked[:top_k]
                    phase_stats["rerank"] = {
                        "method": "score_sort_fallback",
                        "error": str(e)[:100],
                        "chunks": len(final_chunks),
                        "duration_ms": (time.time() - phase_start) * 1000,
                    }

                if logger.isEnabledFor(logging.INFO):
                    logger.info(
                        f"[{trace_id or 'SAG'}] 阶段3 LLM精排完成: "
                        f"{len(coarse_ranked)}→{len(final_chunks)} chunks"
                    )
            else:
                all_chunks.sort(
                    key=lambda x: x.get("_event_score", 0) + x.get("score", 0) * 0.5 + x.get("_similarity", 0),
                    reverse=True,
                )
                final_chunks = all_chunks[:top_k]
                phase_stats["rerank"] = {"method": "score_sort", "chunks": len(final_chunks)}

            # ============================================================
            # 组装返回
            # ============================================================
            total_duration_ms = (time.time() - start_time) * 1000
            self._search_count += 1

            return {
                "chunks": final_chunks,
                "events": all_events[:20],
                "metadata": {
                    "phase_stats": phase_stats,
                    "total_duration_ms": total_duration_ms,
                    "search_count": self._search_count,
                    "pipeline": "sag_three_phase",
                    "degraded": degraded,
                    "entities_used": entities or [],
                    "paths_used": {
                        "path_a": path_a_result is not None,
                        "path_b": True,
                        "multi_hop": enable_multi_hop and len(all_events) > 0,
                    },
                },
            }

        except Exception as e:  # TODO: Narrow exception type
            # D-整体: 整个 SAG 管线崩溃 → fallback 到纯向量检索
            logger.error(
                f"[{trace_id or 'SAG'}] SAG 三阶段管线整体失败，降级到纯向量: {e}", exc_info=True
            )
            try:
                vector_chunks = await self._path_b_vector_search(query, top_k=top_k, trace_id=trace_id)
            except Exception as vec_e:  # TODO: Narrow exception type
                logger.error(f"[{trace_id or 'SAG'}] 纯向量降级也失败: {vec_e}")
                vector_chunks = []

            total_duration_ms = (time.time() - start_time) * 1000
            self._search_count += 1

            return {
                "chunks": vector_chunks,
                "events": [],
                "metadata": {
                    "phase_stats": {"error": "sag_pipeline_crash", "fallback": "pure_vector"},
                    "total_duration_ms": total_duration_ms,
                    "search_count": self._search_count,
                    "pipeline": "fallback_vector",
                    "degraded": True,
                    "entities_used": entities or [],
                    "paths_used": {"path_a": False, "path_b": True, "multi_hop": False},
                },
            }

    # ==================================================================
    # 阶段 1 子方法
    # ==================================================================

    async def _path_a_entity_search(
        self, query: str, entities: List[str], top_k: int, trace_id: str = None
    ) -> Dict[str, Any]:
        """Path A: 实体引导的结构化召回"""
        try:
            from src.taiyang.entity_guided_recall import entity_guided_search
            return await entity_guided_search(
                query=query, entities_list=entities, top_k=top_k, trace_id=trace_id,
            )
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[SAG Path A] 实体引导召回失败: {e}")
            return {"events": [], "chunks": [], "entity_hits": [], "path": "path_a_error"}

    async def _path_b_vector_search(
        self, query: str, top_k: int, trace_id: str = None
    ) -> List[Dict]:
        """Path B: 轻量级纯向量检索（P1-3A FIX: 不再路由到完整混合检索管线）

        直接调用 ChromaDB query()，跳过 retrieval.refine() 的 L0-L7 完整管线。
        这样可以避免 Path B 与 SAG 阶段 3 的 LLM rerank 重复计算。
        """
        try:
            from src.db.vector_store import embed_texts, get_vector_store

            # 向量化查询
            q_emb = await embed_texts([query])
            if not q_emb or not q_emb[0]:
                return []

            vs = get_vector_store()
            if not vs or vs.count <= 0:
                return []

            # 直接 ChromaDB 查询（轻量，不触发完整检索管线）
            result = vs.query(q_emb[0], n_results=min(top_k, 200))
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
                        "_recall_path": "Path B",
                        "_similarity": round(sim, 4),
                    })
            return results
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[SAG Path B] 向量检索失败: {e}")
            return []

    # ==================================================================
    # 阶段 2: 查询时多跳扩展
    # ==================================================================

    async def _query_time_expansion(
        self, seed_events: List[Dict], top_k: int = 20
    ) -> List[Dict]:
        """查询时多跳扩展（H=1）

        从 seed events 收集 entity_names → SQL JOIN 新 events
        FIX-12: 多个 entity_name 的查询并行化
        FIX-13: SQLite 调用包装到线程池
        """
        try:
            from src.db.memory_store import get_store

            # 收集所有 seed entity names
            seed_event_ids = {e.get("event_id") for e in seed_events}
            all_entity_names = set()
            for ev in seed_events:
                for en in ev.get("entity_names", []):
                    all_entity_names.add(en)

            if not all_entity_names:
                return []

            entity_list = list(all_entity_names)[:10]
            store = get_store()

            # FIX-12: 对每个 entity_name 并行查询
            async def _query_one_entity(entity_name: str) -> List[Dict]:
                try:
                    # M-7: 动态 SQL 拼接改为参数化
                    sql = (
                        "SELECT event_id, title, summary, content, chunk_ids_json, "
                        "entity_names_json, event_type, level, file_hash, file_name "
                        "FROM events WHERE entity_names_json LIKE ? AND status='active'"
                    )
                    params = [f"%{entity_name}%"]
                    if seed_event_ids:
                        placeholders = ",".join("?" * len(seed_event_ids))
                        sql += f" AND event_id NOT IN ({placeholders})"
                        params.extend(seed_event_ids)
                    sql += " LIMIT ?"
                    params.append(top_k)

                    rows = await asyncio.to_thread(
                        lambda: store._db_conn.execute(sql, params).fetchall()
                    )

                    events = []
                    for row in rows:
                        eid = row[0]
                        if eid not in seed_event_ids:
                            events.append({
                                "event_id": row[0],
                                "title": row[1],
                                "summary": row[2],
                                "content": row[3],
                                "chunk_ids": json.loads(row[4]) if row[4] else [],
                                "entity_names": json.loads(row[5]) if row[5] else [],
                                "category": row[6],
                                "level": row[7],
                                "file_hash": row[8],
                                "file_name": row[9],
                                "_from_multi_hop": True,
                                "_hop": 1,
                                "_via_entity": entity_name,
                                "_score": 0.7,
                            })
                    return events
                except Exception:  # TODO: Narrow exception type
                    return []

            # 并行执行所有 entity_name 查询
            results = await asyncio.gather(*[_query_one_entity(en) for en in entity_list])

            # 合并去重
            seen = set(seed_event_ids)
            all_new_events = []
            for events_list in results:
                for ev in events_list:
                    if ev["event_id"] not in seen:
                        seen.add(ev["event_id"])
                        all_new_events.append(ev)
                        if len(all_new_events) >= MAX_MULTI_HOP_EVENTS:
                            break
                if len(all_new_events) >= MAX_MULTI_HOP_EVENTS:
                    break

            return all_new_events[:MAX_MULTI_HOP_EVENTS]

        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[SAG 多跳] 扩展失败: {e}")
            return []

    async def _events_to_chunks(
        self, events: List[Dict], top_k: int = 30
    ) -> List[Dict]:
        """Event → Chunk 映射 — 委托给共享实现

        保留包装方法以保持内部调用兼容，实际逻辑在 src.taiyang.shared 中。
        """
        try:
            return _events_to_chunks(
                events, top_k=top_k, max_events=MAX_EVENTS_TO_CHUNKS
            )
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[SAG] Event→Chunk失败: {e}")
            return []

    # ==================================================================
    # 阶段 3: LLM Rerank
    # ==================================================================

    async def _llm_rerank(
        self, query: str, chunks: List[Dict], top_k: int = 15
    ) -> List[Dict]:
        """LLM 精排"""
        if not chunks:
            return []

        try:
            from src.taiyang.rerank import rerank_with_deepseek
            reranked = await rerank_with_deepseek(query, chunks, top_k=top_k)
            if reranked:
                return reranked
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[SAG Rerank] DeepSeek Rerank失败: {e}")

        return sorted(
            chunks,
            key=lambda x: x.get("_event_score", 0) + x.get("score", 0) * 0.5,
            reverse=True,
        )[:top_k]

    # ==================================================================
    # 辅助方法
    # ==================================================================

    def _deduplicate_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """去重 — 委托给共享实现"""
        return _deduplicate_chunks(chunks)


# ========== 全局实例 ==========
_sag_pipeline_instance: Optional[SAGPipeline] = None


def get_sag_pipeline() -> SAGPipeline:
    global _sag_pipeline_instance
    if _sag_pipeline_instance is None:
        _sag_pipeline_instance = SAGPipeline()
    return _sag_pipeline_instance


async def execute_sag_pipeline(
    query: str,
    entities: List[str] = None,
    top_k: int = 15,
    strategy: str = "deep",
    trace_id: str = None,
    enable_path_a: bool = True,
    enable_multi_hop: bool = True,
    enable_rerank: bool = True,
) -> Dict[str, Any]:
    """兼容旧接口"""
    pipeline = get_sag_pipeline()
    return await pipeline.execute(
        query=query,
        entities=entities,
        top_k=top_k,
        strategy=strategy,
        trace_id=trace_id,
        enable_path_a=enable_path_a,
        enable_multi_hop=enable_multi_hop,
        enable_rerank=enable_rerank,
    )
