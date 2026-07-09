"""
entity_guided_recall.py — 太阳·筑基 Path A：实体引导的结构化召回

任务 2：实体引导召回 Path A
- 1) 向量检索 entity 集合（阈值 0.9）
- 2) SQL JOIN events 表（通过 entity-chunk 关联）
- 3) 合并去重

Phase A 已创建 events/entities 表在 SQLite 中，ChromaDB kb_chunks 是主索引。
当前 Phase B：先用 SQLite entities 表做文本匹配 + events 表做 JOIN，
后续 Phase C 引入 pgvector 后可升级为向量检索。

📋 ADR-002: 实体引导回溯的控制面归少阴，数据面归太阳
📋 ADR-003: Event 作为召回索引，Chunk 作为最终输出载体

性能优化 (Round 1 审计):
- FIX-03: _match_entities() 批量 IN 查询代替 N+1
- FIX-04: _get_events_by_entities() 批量 event_id 查询
- FIX-05: _events_to_chunks() 批量 chunk_id 查询
- FIX-06: SQLite 调用包装到 asyncio.to_thread()
- FIX-07: 实体查询缓存 _entity_cache + _chunk_cache
- FIX-08: threshold 参数实际用于模糊匹配判定
"""
import json
import logging
import asyncio
import time
from typing import List, Dict, Any, Optional

logger = logging.getLogger("taiyang.entity_guided_recall")


class EntityGuidedRecall:
    """Path A：实体引导的结构化召回引擎

    流程：
      查询实体列表 → 精确匹配 entities 表 → SQL JOIN events 表
      → 通过 events.chunk_ids 映射回 chunk → 合并去重排序

    性能特性:
      - 批量 SQL 查询（无 N+1）
      - L1/L2 缓存（实体查询、chunk 映射）
      - async-safe（SQLite 调用在线程池中执行）
    """

    # cache config
    _ENTITY_CACHE_TTL = 300  # 5 分钟
    _CHUNK_CACHE_TTL = 600  # 10 分钟
    _MAX_CACHE_ENTRIES = 500

    def __init__(self):
        self._entity_cache: Dict[str, tuple] = {}  # key → (results, timestamp)
        self._chunk_cache: Dict[str, tuple] = {}   # chunk_id → (chunk_data, timestamp)

    # ===== 缓存辅助 =====
    def _cache_get(self, cache: Dict, key: str, ttl: int) -> Optional[Any]:
        entry = cache.get(key)
        if entry and time.time() - entry[1] < ttl:
            return entry[0]
        return None

    def _cache_put(self, cache: Dict, key: str, value: Any):
        if len(cache) >= self._MAX_CACHE_ENTRIES:
            # evict oldest (simple FIFO)
            oldest = next(iter(cache))
            del cache[oldest]
        cache[key] = (value, time.time())

    async def entity_guided_search(
        self,
        query: str,
        entities_list: List[str],
        top_k: int = 15,
        trace_id: str = None,
    ) -> Dict[str, Any]:
        """实体引导的召回主入口

        Args:
            query: 原始查询
            entities_list: 少阴提取的实体名称列表（如 ["PA66", "齿轮", "ISO 9001"]）
            top_k: 返回结果数
            trace_id: 链路追踪ID

        Returns:
            {
                "events": [...],         # 召回的 Event 列表
                "chunks": [...],         # 映射后的 Chunk 列表（去重）
                "entity_hits": [...],    # 命中的实体详情
                "path": "entity_guided",
            }
        """
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"[{trace_id or 'PathA'}] 实体引导召回开始, 实体数={len(entities_list)}")
        start_time = asyncio.get_event_loop().time()

        # Step 1：实体精确/模糊匹配
        entity_hits = await self._match_entities(entities_list, threshold=0.9)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"[{trace_id or 'PathA'}] 实体匹配: 命中{len(entity_hits)}/{len(entities_list)}")

        if not entity_hits:
            return {"events": [], "chunks": [], "entity_hits": [], "path": "entity_guided_empty"}

        # Step 2：通过实体查找关联 events
        events = await self._get_events_by_entities(entity_hits)

        if not events:
            return {
                "events": [], "chunks": [],
                "entity_hits": entity_hits, "path": "entity_guided_no_events",
            }

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"[{trace_id or 'PathA'}] 事件关联: 找到{len(events)}个事件")

        # Step 3：Event → Chunk 映射 + 去重
        chunks = await self._events_to_chunks(events, top_k)

        # Step 4：按 event_score 排序（同一 chunk 被多个 event 引用时取最高分）
        chunks = self._deduplicate_and_sort_chunks(chunks, top_k)

        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        logger.info(
            f"[{trace_id or 'PathA'}] 完成: {len(events)} events → "
            f"{len(chunks)} chunks, {duration_ms:.0f}ms"
        )

        return {
            "events": events,
            "chunks": chunks,
            "entity_hits": entity_hits,
            "path": "entity_guided",
            "duration_ms": duration_ms,
        }

    async def _match_entities(
        self, entities_list: List[str], threshold: float = 0.9
    ) -> List[Dict]:
        """实体精确/模糊匹配 — 批量 SQL 查询（无 N+1）

        FIX-03: 改为一次批量 IN 查询 → 内存匹配
        FIX-08: 使用 threshold 判定模糊匹配置信度
        FIX-07: 添加实体匹配缓存
        """
        if not entities_list:
            return []

        # 生成缓存 key
        cache_key = "|".join(sorted(entities_list))
        cached = self._cache_get(self._entity_cache, cache_key, self._ENTITY_CACHE_TTL)
        if cached is not None:
            return cached

        try:
            from src.db.memory_store import get_store

            store = get_store()
            matched = {}

            # ===== 批量精确匹配（一次 SQL 查询）=====
            # P0-3A FIX: 删除双次执行 bug，仅保留 asyncio.to_thread 包装
            placeholders = ",".join("?" * len(entities_list))
            exact_rows = await asyncio.to_thread(
                lambda: store._db_conn.execute(
                    f"SELECT entity_id, name, entity_type, description, chunk_ids_json, event_ids_json "
                    f"FROM entities WHERE name IN ({placeholders}) AND status='active'",
                    tuple(entities_list),
                ).fetchall()
            )

            for row in exact_rows:
                entity_id = row[0]
                if entity_id not in matched:
                    matched[entity_id] = {
                        "entity_id": row[0],
                        "name": row[1],
                        "entity_type": row[2],
                        "description": row[3],
                        "chunk_ids": json.loads(row[4]) if row[4] else [],
                        "event_ids": json.loads(row[5]) if row[5] else [],
                        "_match_score": 1.0,  # 精确匹配 = 1.0
                        "_matched_query_entity": row[1],
                        "_match_type": "exact",
                    }

            # ===== 剩余未匹配的实体做批量 LIKE 查询 =====
            matched_names = {m["name"] for m in matched.values()}
            unmatched = [e for e in entities_list if e not in matched_names]

            for entity_name in unmatched:
                # P0-3B FIX: 删除双次执行 bug，只保留 asyncio.to_thread
                like_rows = await asyncio.to_thread(
                    lambda en=entity_name: store._db_conn.execute(
                        "SELECT entity_id, name, entity_type, description, chunk_ids_json, event_ids_json "
                        "FROM entities WHERE name LIKE ? AND status='active' LIMIT 3",
                        (f"%{en}%",),
                    ).fetchall()
                )

                for row in like_rows:
                    entity_id = row[0]
                    if entity_id not in matched:
                        # 计算匹配分数（基于名称长度比）
                        name_len = len(entity_name)
                        matched_name = row[1]
                        # 简单的 Jaccard 式匹配度
                        if entity_name.lower() == matched_name.lower():
                            score = 1.0
                        elif entity_name.lower() in matched_name.lower():
                            score = 0.85
                        else:
                            score = 0.7

                        if score >= threshold:
                            matched[entity_id] = {
                                "entity_id": row[0],
                                "name": row[1],
                                "entity_type": row[2],
                                "description": row[3],
                                "chunk_ids": json.loads(row[4]) if row[4] else [],
                                "event_ids": json.loads(row[5]) if row[5] else [],
                                "_match_score": score,
                                "_matched_query_entity": entity_name,
                                "_match_type": "fuzzy",
                            }

            result = list(matched.values())
            self._cache_put(self._entity_cache, cache_key, result)
            return result

        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[Path A] 实体匹配失败: {e}")
            return []

    async def _get_events_by_entities(self, entity_hits: List[Dict]) -> List[Dict]:
        """通过实体查找关联 events — 批量 SQL 查询

        FIX-04: 先收集所有 event_ids → 一次 IN 查询
        """
        if not entity_hits:
            return []

        try:
            from src.db.memory_store import get_store

            store = get_store()
            all_events = {}

            # ===== 方式1：收集所有 event_ids =====
            all_event_ids = set()
            entity_name_map = {}  # event_id → matched entity name

            for entity_hit in entity_hits:
                event_ids = entity_hit.get("event_ids", [])
                for eid in event_ids:
                    all_event_ids.add(eid)
                    entity_name_map[eid] = entity_hit["name"]

            # 批量查询
            if all_event_ids:
                placeholders = ",".join("?" * len(all_event_ids))
                # P0-3D FIX: 包装到 asyncio.to_thread 避免阻塞事件循环
                rows = await asyncio.to_thread(
                    lambda: store._db_conn.execute(
                        f"SELECT event_id, title, summary, content, chunk_ids_json, "
                        f"entity_names_json, event_type, level, file_hash, file_name "
                        f"FROM events WHERE event_id IN ({placeholders}) AND status='active'",
                        tuple(all_event_ids),
                    ).fetchall()
                )

                for row in rows:
                    eid = row[0]
                    all_events[eid] = self._row_to_event(
                        row, entity_name_map.get(eid, entity_hits[0]["name"])
                    )

            # ===== 方式2：对每个 entity_name 做反向 LIKE（并行化 + asyncio.to_thread）=====
            # P0-3D + P1-3E FIX: 并行化 LIKE 查询 + 非阻塞线程池
            entity_names = list({e["name"] for e in entity_hits})[:10]

            async def _like_query_one(entity_name: str) -> List[tuple]:
                return await asyncio.to_thread(
                    lambda: store._db_conn.execute(
                        "SELECT event_id, title, summary, content, chunk_ids_json, "
                        "entity_names_json, event_type, level, file_hash, file_name "
                        "FROM events WHERE entity_names_json LIKE ? AND status='active' LIMIT 30",
                        (f"%{entity_name}%",),
                    ).fetchall()
                )

            like_results = await asyncio.gather(
                *[_like_query_one(en) for en in entity_names],
                return_exceptions=True
            )

            for i, rows in enumerate(like_results):
                if isinstance(rows, Exception):
                    continue
                entity_name = entity_names[i]
                for row in rows:
                    eid = row[0]
                    if eid not in all_events:
                        all_events[eid] = self._row_to_event(row, entity_name)

            return list(all_events.values())

        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[Path A] 事件查找失败: {e}")
            return []

    def _row_to_event(self, row, matched_entity: str = None) -> Dict:
        """将 SQL 行转换为 event dict"""
        return {
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
            "_from_entity_channel": True,
            "_matched_entity": matched_entity,
            "_score": 1.0,
        }

    async def _events_to_chunks(
        self, events: List[Dict], top_k: int = 15
    ) -> List[Dict]:
        """Event → Chunk 映射 — 批量 chunk_id 查询

        FIX-05: 先收集所有 chunk_ids → 一次批量 JSON 查询
        FIX-07: chunk 缓存
        P0-3D FIX: SQLite 调用包装到 asyncio.to_thread
        P1-4A FIX: 使用 get_chunks_batch() 替代逐条查询
        """
        if not events:
            return []

        try:
            from src.db.memory_store import get_store

            store = get_store()

            # 限制处理的事件数量
            events_to_process = events[:min(len(events), 30)]

            # 构建 event_score 映射
            event_score_map = {}
            event_title_map = {}
            for event in events_to_process:
                for cid in event.get("chunk_ids", []):
                    score = event.get("_score", 0)
                    if cid not in event_score_map or score > event_score_map[cid]:
                        event_score_map[cid] = score
                        event_title_map[cid] = event.get("title", "")

            if not event_score_map:
                return []

            chunk_ids = list(event_score_map.keys())
            all_chunks = {}
            uncached_ids = []

            # 先查 L2 缓存
            for cid in chunk_ids:
                cached = self._cache_get(self._chunk_cache, cid, self._CHUNK_CACHE_TTL)
                if cached is not None:
                    chunk = dict(cached)
                    chunk["_via_event"] = event_title_map.get(cid, "")
                    chunk["_event_score"] = event_score_map.get(cid, 0)
                    chunk["_source"] = "entity_guided"
                    chunk["_recall_path"] = "Path A"
                    all_chunks[cid] = chunk
                else:
                    uncached_ids.append(cid)

            # 批量获取未缓存的 chunk（1 次 SQL + JSON 缓存）
            if uncached_ids:
                chunk_map = await asyncio.to_thread(
                    lambda: store.get_chunks_batch(uncached_ids)
                )
                for cid, chunk in chunk_map.items():
                    self._cache_put(self._chunk_cache, cid, dict(chunk))
                    chunk["_via_event"] = event_title_map.get(cid, "")
                    chunk["_event_score"] = event_score_map.get(cid, 0)
                    chunk["_source"] = "entity_guided"
                    chunk["_recall_path"] = "Path A"
                    all_chunks[cid] = chunk

            return list(all_chunks.values())

        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"[Path A] Event→Chunk映射失败: {e}")
            return []

    def _deduplicate_and_sort_chunks(
        self, chunks: List[Dict], top_k: int = 15
    ) -> List[Dict]:
        """去重并按 event_score 排序"""
        seen_texts = set()
        unique_chunks = []
        for c in chunks:
            text_key = c.get("text", "")[:50] or c.get("summary", "")[:50]
            if text_key not in seen_texts:
                seen_texts.add(text_key)
                unique_chunks.append(c)

        unique_chunks.sort(
            key=lambda x: x.get("_event_score", 0) + x.get("score", 0) * 0.5,
            reverse=True,
        )
        return unique_chunks[:top_k]


# ========== 全局实例 ==========
_entity_guided_recall_instance: Optional[EntityGuidedRecall] = None


def get_entity_guided_recall() -> EntityGuidedRecall:
    global _entity_guided_recall_instance
    if _entity_guided_recall_instance is None:
        _entity_guided_recall_instance = EntityGuidedRecall()
    return _entity_guided_recall_instance


async def entity_guided_search(
    query: str,
    entities_list: List[str],
    top_k: int = 15,
    trace_id: str = None,
) -> Dict[str, Any]:
    """兼容旧接口"""
    engine = get_entity_guided_recall()
    return await engine.entity_guided_search(
        query=query,
        entities_list=entities_list,
        top_k=top_k,
        trace_id=trace_id,
    )
