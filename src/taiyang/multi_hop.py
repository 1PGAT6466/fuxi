"""
multi_hop.py — 太阳·SAG式多跳检索
实体→事件→碎片，顺着线索链破案
三级实体提取策略 + 边界处理
"""
import json
import re
import logging
import asyncio
from typing import List, Dict, Any

logger = logging.getLogger("taiyang.multi_hop")


class SAGMultiHopSearch:
    """SAG 多跳检索 — 基于 Event/Entity 的 SQL 多跳扩展"""

    async def search(self, query: str, top_k: int = 15) -> List[Dict]:
        # 1. 提取查询实体（分层策略）
        entities = await self._extract_entities(query)

        # 2. 边界情况：无实体 → 统一降级策略
        if not entities:
            if logger.isEnabledFor(logging.DEBUG):
                logger.info(f"[SAG多跳] 无实体查询: {query[:30]}..., 降级为向量检索")
            else:
                logger.info(f"[SAG多跳] 无实体查询 (len={len(query)}), 降级为向量检索")
            return await self._fallback_vector_search(query, top_k)

        # 3. 边界情况：单实体 → 单跳扩展
        if len(entities) == 1:
            logger.info(f"[SAG多跳] 单实体查询: {entities[0]}, 使用单跳扩展")
            return await self._single_entity_search(entities[0], query, top_k)

        # 4. 正常多跳流程
        return await self._multi_hop_search(entities, query, top_k)

    async def _extract_entities(self, query: str) -> List[str]:
        """提取查询实体 — 三级策略，按成本递增"""
        entities = []

        # Level 1: 正则 + jieba（< 0.01s）
        regex_entities = re.findall(r'\b[A-Z][a-zA-Z0-9]+\b', query)
        try:
            import jieba.posseg as pseg
            words = pseg.cut(query)
            jieba_entities = [w for w, flag in words if flag in ['nr', 'ns', 'nt', 'nz', 'eng']]
        except Exception as e:
            logger.warning("jieba词性标注失败: %s", e, exc_info=True)
            jieba_entities = []

        entities = list(set(regex_entities + jieba_entities))
        entities = [e for e in entities if len(e) > 1]

        # 如果实体数 >= 2，跳过 LLM
        if len(entities) >= 2:
            return entities

        # Level 2: LLM 提取（< 2s）— 仅在实体不足时调用
        try:
            llm_entities = await asyncio.wait_for(
                self._llm_extract_entities(query), timeout=2.0
            )
            entities.extend(llm_entities)
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"[实体提取] LLM 提取失败: {e}")

        return list(set(e for e in entities if len(e) > 1))

    async def _llm_extract_entities(self, query: str) -> List[str]:
        """LLM 提取实体"""
        try:
            from src.infra.llm import call_ai
            prompt = f"从以下查询中提取实体（人名、地名、组织、产品、技术、型号），用逗号分隔：\n{query}"
            response = await call_ai(prompt)
            if response:
                return [e.strip() for e in response.split(",") if e.strip() and len(e.strip()) > 1]
        except Exception as e:
            logger.warning(f"[实体提取] LLM调用失败: {e}")
        return []

    async def _fallback_vector_search(self, query: str, top_k: int) -> List[Dict]:
        """无实体降级：向量检索"""
        try:
            from src.taiyang.retrieval import hybrid_search
            results = await hybrid_search(query, top_k=top_k)
            for r in results:
                r["_search_mode"] = "vector_fallback"
                r["_reason"] = "no_entities_found"
            return results
        except Exception as e:
            logger.error(f"[SAG多跳] 向量检索降级失败: {e}")
            return []

    async def _single_entity_search(self, entity: str, query: str, top_k: int) -> List[Dict]:
        """单实体搜索：事件关联扩展"""
        # 查找实体关联的事件
        events = await get_events_by_entity(entity)

        if not events:
            # 事件为空，查找实体关联的 chunks
            chunks = await self._get_chunks_by_entity(entity)
            if chunks:
                return chunks[:top_k]
            # 仍为空，降级为向量检索
            return await self._fallback_vector_search(query, top_k)

        # 事件→碎片
        results = []
        for event in events[:10]:
            for cid in event.get("chunk_ids", []):
                chunk = await get_chunk_by_id(cid)
                if chunk:
                    chunk["_via_event"] = event.get("title", "")
                    chunk["_event_score"] = 0.5
                    results.append(chunk)

        results = deduplicate(results)
        return results[:top_k]

# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
    async def _get_chunks_by_entity(self, entity: str) -> List[Dict]:
        """通过实体名查找关联碎片"""
        try:
            from src.db.memory_store import get_store
            store = get_store()
            rows = store._db_conn.execute(
                "SELECT doc FROM chunks WHERE doc LIKE ? LIMIT 20",
                (f'%{entity}%',)
            ).fetchall()
            return [json.loads(r[0]) for r in rows if r[0]]
        except Exception:
            return []

    async def _multi_hop_search(self, entities: List[str], query: str, top_k: int) -> List[Dict]:
        """正常多跳流程：实体→事件→碎片"""
        # 第1跳：种子实体 → 关联事件
        candidate_events = []
        for entity in entities[:5]:
            events = await get_events_by_entity(entity)
            for ev in events:
                ev["_from_entity_channel"] = True
            candidate_events.extend(events)

        # 同时：查询直接向量召回事件
        query_event_hits = await event_vector_recall(query, top_k=20)
        for ev in query_event_hits:
            ev["_from_vector_channel"] = True
        candidate_events.extend(query_event_hits)

        # 去重 + seed_score 排序
        candidate_events = deduplicate(candidate_events)
        for ev in candidate_events:
            ev["_score"] = seed_score(ev, entities, ev.get("_similarity", 0))
        candidate_events.sort(key=lambda x: x["_score"], reverse=True)

        # 第2跳：事件 → 碎片
        results = []
        for event in candidate_events[:10]:
            for cid in event.get("chunk_ids", []):
                chunk = await get_chunk_by_id(cid)
                if chunk:
                    chunk["_via_event"] = event.get("title", "")
                    chunk["_event_score"] = event["_score"]
                    results.append(chunk)

        # 补充直接向量检索
        direct_chunks = await vector_recall(query, top_k=5)
        for c in direct_chunks:
            c["_via_event"] = "direct"
            c["_event_score"] = 0
        results.extend(direct_chunks)

        results = deduplicate(results)
        results.sort(
            key=lambda x: x.get("_event_score", 0) + x.get("_similarity", 0),
            reverse=True,
        )
        return results[:top_k]


def seed_score(candidate: dict, seed_entities: list, vector_similarity: float) -> float:
    """SAG核心打分公式：0.85×向量 + 0.15×实体命中 + 0.05×双通道"""
    vector_score = vector_similarity

    candidate_entities = candidate.get("entity_names", [])
    entity_hit = 1.0 if any(
        e.lower() in [se.lower() for se in seed_entities]
        for e in candidate_entities
    ) else 0.0

    channel_score = 1.0 if (
        candidate.get("_from_entity_channel") and
        candidate.get("_from_vector_channel")
    ) else 0.0

    score = (
        0.85 * vector_score +
        0.15 * entity_hit +
        0.05 * channel_score
    )

    return score


def merge_entities(a: list, b: list) -> list:
    """合并实体列表"""
    seen = set()
    result = []
    for e in a + b:
        key = e.get("name", "").lower()
        if key and key not in seen:
            seen.add(key)
            result.append(e)
    return result


def deduplicate(items: list) -> list:
    """去重"""
    seen = set()
    result = []
    for item in items:
        key = item.get("chunk_id") or item.get("event_id") or item.get("text", "")[:50]
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


# 兼容旧接口
async def multi_hop_search(query: str, max_hops: int = 2, top_k: int = 15) -> list:
    """兼容旧接口"""
    searcher = SAGMultiHopSearch()
    return await searcher.search(query, top_k)


# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def entity_recall(query: str, top_k: int = 10) -> list:
    """从实体表中直接匹配"""
    try:
        from src.db.memory_store import get_store
        store = get_store()
        rows = store._db_conn.execute(
            "SELECT name, entity_type, description FROM entities WHERE ? LIKE '%' || name || '%' LIMIT ?",
            (query, top_k)
        ).fetchall()
        return [{"name": r[0], "type": r[1], "description": r[2]} for r in rows]
    except Exception:
        return []


# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def entity_vector_recall(query: str, top_k: int = 10) -> list:
    """向量检索实体"""
    return []


# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def event_vector_recall(query: str, top_k: int = 20) -> list:
    """向量检索事件"""
    return []


# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def get_events_by_entity(entity_name: str) -> list:
    """通过实体名找到关联事件"""
    try:
        from src.db.memory_store import get_store
        store = get_store()
        rows = store._db_conn.execute(
            "SELECT event_id, title, summary, chunk_ids, entity_names FROM events WHERE entity_names LIKE ? LIMIT 20",
            (f'%{entity_name}%',)
        ).fetchall()
        events = []
        for r in rows:
            events.append({
                "event_id": r[0], "title": r[1], "summary": r[2],
                "chunk_ids": json.loads(r[3]) if r[3] else [],
                "entity_names": json.loads(r[4]) if r[4] else [],
                "_from_entity_channel": True,
            })
        return events
    except Exception:
        return []


# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def get_chunk_by_id(chunk_id: str) -> dict:
    """通过碎片ID获取碎片"""
    try:
        from src.db.memory_store import get_store
        store = get_store()
        rows = store._db_conn.execute(
            "SELECT doc FROM chunks WHERE id = ? OR json_extract(doc, '$.chunk_id') = ?",
            (chunk_id, chunk_id)
        ).fetchall()
        if rows:
            return json.loads(rows[0][0])
    except Exception:
        pass
    return None


async def vector_recall(query: str, top_k: int = 15) -> list:
    """普通向量检索"""
    try:
        from src.taiyang.retrieval import hybrid_search
        return await hybrid_search(query, top_k=top_k)
    except Exception:
        return []
