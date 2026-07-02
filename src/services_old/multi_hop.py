"""
multi_hop.py — SAG 式多跳检索
实体→事件→碎片 逐跳扩展
"""
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger("multi_hop")


async def multi_hop_search(query: str, max_hops: int = 2, top_k: int = 15) -> list:
    """SAG 式多跳检索"""

    # === 第1跳：实体召回 ===
    matched_entities = await entity_recall(query, top_k=10)
    entity_vector_hits = await entity_vector_recall(query, top_k=10)
    seed_entities = merge_entities(matched_entities, entity_vector_hits)

    if not seed_entities:
        # 无实体命中 → 降级为普通向量检索
        return await vector_recall(query, top_k=top_k)

    # === 第2跳：实体→事件 ===
    candidate_events = []
    for entity in seed_entities[:5]:
        events = await get_events_by_entity(entity["name"])
        candidate_events.extend(events)

    # 同时：查询直接向量召回事件
    query_event_hits = await event_vector_recall(query, top_k=20)
    candidate_events.extend(query_event_hits)

    # 去重 + seed_score 排序
    candidate_events = deduplicate(candidate_events)
    for event in candidate_events:
        event["_score"] = seed_score(
            event,
            [e["name"] for e in seed_entities],
            event.get("_similarity", 0),
        )
    candidate_events.sort(key=lambda x: x["_score"], reverse=True)

    # === 第3跳：事件→碎片 ===
    results = []
    for event in candidate_events[:10]:
        chunk_ids = event.get("chunk_ids", [])
        for cid in chunk_ids:
            chunk = await get_chunk_by_id(cid)
            if chunk:
                chunk["_via_event"] = event.get("title", "")
                chunk["_event_score"] = event["_score"]
                results.append(chunk)

    # 补充：直接向量检索碎片
    direct_chunks = await vector_recall(query, top_k=5)
    for c in direct_chunks:
        c["_via_event"] = "direct"
        c["_event_score"] = 0
    results.extend(direct_chunks)

    # 最终排序
    results = deduplicate(results)
    results.sort(
        key=lambda x: x.get("_event_score", 0) + x.get("_similarity", 0),
        reverse=True,
    )
    return results[:top_k]


def seed_score(candidate: dict, seed_entities: list, vector_similarity: float) -> float:
    """
    SAG 核心打分公式
    综合考虑向量相似度、实体命中、双通道奖励
    """
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


async def entity_recall(query: str, top_k: int = 10) -> list:
    """从实体表中直接匹配查询中出现的实体名"""
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


async def entity_vector_recall(query: str, top_k: int = 10) -> list:
    """向量检索实体"""
    try:
        from src.db.vector_store import get_vector_store, embed_texts
        vs = get_vector_store()
        if not vs:
            return []
        q_emb = await embed_texts([query])
        if not q_emb:
            return []
        result = vs._entities.query(query_embeddings=[q_emb[0]], n_results=top_k)
        entities = []
        for i, eid in enumerate(result.get("ids", [[]])[0]):
            meta = result["metadatas"][0][i]
            entities.append({
                "name": meta.get("name", ""),
                "type": meta.get("entity_type", ""),
                "description": meta.get("description", ""),
                "_similarity": 1.0 - result["distances"][0][i],
            })
        return entities
    except Exception:
        return []


async def event_vector_recall(query: str, top_k: int = 20) -> list:
    """向量检索事件"""
    try:
        from src.db.vector_store import get_vector_store, embed_texts
        vs = get_vector_store()
        if not vs:
            return []
        q_emb = await embed_texts([query])
        if not q_emb:
            return []
        result = vs._events.query(query_embeddings=[q_emb[0]], n_results=top_k)
        events = []
        for i, eid in enumerate(result.get("ids", [[]])[0]):
            meta = result["metadatas"][0][i]
            events.append({
                "event_id": eid,
                "title": meta.get("title", ""),
                "summary": meta.get("summary", ""),
                "chunk_ids": json.loads(meta.get("chunk_ids", "[]")),
                "entity_names": json.loads(meta.get("entity_names", "[]")),
                "_similarity": 1.0 - result["distances"][0][i],
            })
        return events
    except Exception:
        return []


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
    """普通向量检索（降级方案）"""
    try:
        from src.services.retrieval import hybrid_search
        return await hybrid_search(query, top_k=top_k)
    except Exception:
        return []
