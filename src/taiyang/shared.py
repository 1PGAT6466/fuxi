"""
shared.py — 太阳·筑基 共享工具函数

从 sag_pipeline、entity_guided_recall、retrieval 中提取的重复代码。

M-2: _events_to_chunks — Event → Chunk 映射（批量查询 + 去重排序）
M-3: _deduplicate_chunks — 按 chunk_id/id/text 去重
"""
import logging
from typing import List, Dict

logger = logging.getLogger("taiyang.shared")


def _events_to_chunks(
    events: List[Dict],
    top_k: int = 30,
    max_events: int = 30,
    store=None,
) -> List[Dict]:
    """Event → Chunk 映射 — 批量 chunk_id 查询 + 按 event_score 排序

    从 events 的 chunk_ids 字段反查 chunk 文本，用于 ADR-003 粒度切换点。

    P0-3C FIX: 从 Round 2 退化恢复 → 使用 get_chunks_batch() 批量查询。
    原来每个 cid 一次 SQL（150 次），现在一次批量 IN 查询。

    Args:
        events: 包含 chunk_ids 字段的事件列表
        top_k: 返回 chunk 数量上限
        max_events: 处理的事件数量上限
        store: MemoryStore 实例（必传）

    Returns:
        排序后的 chunk dict 列表
    """
    if not events:
        return []
    if store is None:
        from src.db.memory_store import get_store
        store = get_store()

    events_to_process = events[: min(len(events), max_events)]

    # 构建 chunk_id → (event_score, event_title) 映射（取最高分）
    chunk_score_map: Dict[str, float] = {}
    chunk_title_map: Dict[str, str] = {}
    for event in events_to_process:
        score = event.get("_score", 0)
        title = event.get("title", "")
        for cid in event.get("chunk_ids", []):
            if cid not in chunk_score_map or score > chunk_score_map[cid]:
                chunk_score_map[cid] = score
                chunk_title_map[cid] = title

    if not chunk_score_map:
        return []

    # 批量查询所有 chunk_ids（1 次 SQL + JSON 缓存）
    all_cids = list(chunk_score_map.keys())
    chunk_map = store.get_chunks_batch(all_cids)

    # 组装结果
    all_chunks = {}
    for cid, chunk in chunk_map.items():
        chunk["_via_event"] = chunk_title_map.get(cid, "")
        chunk["_event_score"] = chunk_score_map.get(cid, 0)
        chunk["_source"] = "event_recall"
        chunk["_recall_path"] = "SAG Multi-Hop"
        all_chunks[cid] = chunk

    chunks = list(all_chunks.values())
    chunks.sort(key=lambda x: x.get("_event_score", 0), reverse=True)
    return chunks[:top_k]


def _deduplicate_chunks(chunks: List[Dict]) -> List[Dict]:
    """去重：按 chunk_id、id 或 text 前 50 字符去重

    Args:
        chunks: 待去重的 chunk 列表

    Returns:
        去重后的 chunk 列表
    """
    seen = set()
    unique = []
    for c in chunks:
        cid = c.get("chunk_id") or c.get("id") or c.get("text", "")[:50]
        if cid not in seen:
            seen.add(cid)
            unique.append(c)
    return unique
