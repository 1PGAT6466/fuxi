"""
results_postprocess.py — 太阳·结果后处理
上下文扩展 + 去重 + 格式化
"""
import logging
from typing import List, Dict

logger = logging.getLogger("taiyang.results_postprocess")


def expand_context(results: List[Dict]) -> List[Dict]:
    """上下文扩展：为每个结果补充相邻chunk的上下文"""
    if not results:
        return results

    try:
        from src.db.memory_store import get_store
        store = get_store()

        expanded = []
        for r in results:
            # 如果已有足够文本，不扩展
            text = r.get("text", "")
            if len(text) > 500:
                expanded.append(r)
                continue

            # 尝试获取相邻chunk
            file_hash = r.get("file_hash", "")
            chunk_index = r.get("chunk_index", -1)

            if file_hash and chunk_index >= 0:
                prev_chunk = _get_adjacent_chunk(store, file_hash, chunk_index - 1)
                next_chunk = _get_adjacent_chunk(store, file_hash, chunk_index + 1)

                context_parts = []
                if prev_chunk:
                    context_parts.append(prev_chunk.get("text", "")[-200:])
                context_parts.append(text)
                if next_chunk:
                    context_parts.append(next_chunk.get("text", "")[:200])

                r["text"] = "\n".join(context_parts)
                r["_expanded"] = True

            expanded.append(r)

        return expanded

    except Exception as e:
        logger.warning(f"[结果后处理] 上下文扩展失败: {e}")
        return results


def _get_adjacent_chunk(store, file_hash: str, chunk_index: int) -> Dict:
    """获取相邻chunk"""
    try:
        rows = store._db_conn.execute(
            "SELECT doc FROM chunks WHERE file_hash = ? AND chunk_index = ?",
            (file_hash, chunk_index)
        ).fetchall()
        if rows:
            import json
            return json.loads(rows[0][0])
    except Exception:
        pass
    return None


def deduplicate_results(results: List[Dict]) -> List[Dict]:
    """去重"""
    seen = set()
    deduped = []

    for r in results:
        # 优先用chunk_id去重
        key = r.get("chunk_id") or r.get("file_hash", "")
        if key:
            if key in seen:
                continue
            seen.add(key)
        else:
            # 用文本前50字去重
            text_key = r.get("text", "")[:50]
            if text_key in seen:
                continue
            seen.add(text_key)

        deduped.append(r)

    return deduped


def format_results(results: List[Dict], max_results: int = 10) -> List[Dict]:
    """格式化结果"""
    formatted = []

    for i, r in enumerate(results[:max_results]):
        formatted.append({
            "rank": i + 1,
            "text": r.get("text", "")[:1000],
            "file_name": r.get("file_name", ""),
            "file_hash": r.get("file_hash", ""),
            "score": r.get("score", 0),
            "source": r.get("_source", "unknown"),
            "via_event": r.get("_via_event", ""),
            "rerank_score": r.get("_rerank_score", 0),
        })

    return formatted


def merge_search_results(
    bm25_results: List[Dict],
    vector_results: List[Dict],
    multi_hop_results: List[Dict] = None,
) -> List[Dict]:
    """合并多路检索结果"""
    all_results = []

    # 标记来源
    for r in bm25_results:
        r["_source"] = "bm25"
        all_results.append(r)

    for r in vector_results:
        r["_source"] = "vector"
        all_results.append(r)

    if multi_hop_results:
        for r in multi_hop_results:
            r["_source"] = "multi_hop"
            all_results.append(r)

    # 去重
    all_results = deduplicate_results(all_results)

    # 按分数排序
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)

    return all_results
