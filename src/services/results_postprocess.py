"""
results_postprocess — 从 retrieval.py 拆分
1.40 天梯计划 P2：上帝类拆分
"""

"""
services/retrieval.py — 混合检索服务（v10.0）
负责：BM25 + 向量双路召回 → RRF 融合 → 精排 → 去重 → 上下文扩展
"""
import logging; logger = logging.getLogger(__name__)
import re, asyncio
from typing import List, Dict

# v11: Concurrent control for ChromaDB
_VECTOR_SEM = asyncio.Semaphore(8)

try:
    import jieba
    jieba.setLogLevel(20)
except ImportError:
    jieba = None

from src.db.memory_store import get_store
from src.db.vector_store import get_vector_store, embed_texts
from src.services.graph_router import route_to_categories, expand_query_with_synonyms, get_entity_context
from src.config import EMBEDDER_URL
from src.services.synonym_loader import load_synonyms
# 兼容别名
_SYNONYM_MAP = load_synonyms()




def mmr_dedup(results: list, diversity_weight: float = 0.25, top_k: int = 15) -> list:
    """H5: MMR 多样性去重"""
    if len(results) <= 1:
        return results
    scores = [r.get("score", 0) for r in results]
    max_s, min_s = max(scores), min(scores)
    if max_s == min_s:
        return results[:top_k]
    normalized = [(s - min_s) / (max_s - min_s) for s in scores]
    selected, selected_texts, candidates = [], [], list(range(len(results)))
    lam = 1.0 - diversity_weight
    for _ in range(min(top_k, len(results))):
        if not candidates:
            break
        if not selected:
            best = max(candidates, key=lambda i: normalized[i])
        else:
            best_score, best = -float("inf"), candidates[0]
            for i in candidates:
                text_i = (results[i].get("text", "") or "").lower()
                max_overlap = max((len(set(text_i) & set(st)) / max(len(set(text_i) | set(st)), 1)
                                   for st in selected_texts), default=0)
                mmr = lam * normalized[i] - diversity_weight * max_overlap
                if mmr > best_score:
                    best_score, best = mmr, i
        selected.append(results[best])
        selected_texts.append((results[best].get("text", "") or "").lower())
        candidates.remove(best)
    return selected


def expand_context(hits: list, all_chunks: list = None, before: int = 2, after: int = 2,
                   max_chars: int = 3000, sentence_window: int = 3) -> list:
    """H1: Sentence Window 上下文扩展"""
    if not hits or before + after == 0:
        return hits
    expanded, seen = [], set()
    store = get_store()
    for hit in hits:
        fh = hit.get("file_hash", "")
        ci = hit.get("chunk_index", 0)
        same_file = store.get_by_hash(fh)
        if not same_file:
            expanded.append(hit)
            continue
        same_file.sort(key=lambda x: x.get("chunk_index", 0))
        pos = next((i for i, c in enumerate(same_file) if c.get("chunk_index") == ci), -1)
        if pos < 0:
            expanded.append(hit)
            continue
        start = max(0, pos - before)
        end = min(len(same_file), pos + after + 1)
        context_chunks = same_file[start:end]
        big_text = ""
        for cc in context_chunks:
            big_text += cc.get("text", "") + "\n"
            if len(big_text) > max_chars * 2:
                big_text = big_text[:max_chars * 2] + "..."
                break
        query = hit.get("_query", "")
        if query and big_text:
            sentences = _split_sentences_zh(big_text)
            if len(sentences) >= 3:
                anchor_idx = _find_best_sentence(query, sentences)
                sw_start = max(0, anchor_idx - sentence_window)
                sw_end = min(len(sentences), anchor_idx + sentence_window + 1)
                window_text = "".join(sentences[sw_start:sw_end])
                if len(window_text) > max_chars:
                    window_text = window_text[:max_chars] + "..."
                big_text = window_text
        hit_key = f"{fh}:{start}-{end}"
        if hit_key in seen:
            continue
        seen.add(hit_key)
        expanded.append({**hit, "text": big_text.strip(), "text_preview": big_text[:500].strip()})
    return expanded


def _split_sentences_zh(text: str) -> list:
    import re as _re
    parts = _re.split(r'(?<=[.！？；;!?\n])', text)
    return [p.strip() for p in parts if p.strip() and len(p.strip()) >= 2]


def _expand_parent_child(hits: list, all_chunks: list) -> list:
    """P1-3: Parent-Child chunk expansion.
    When a chunk has parent_idx metadata (from parent_child_chunk),
    attach sibling child chunks to enrich context.
    """
    if not all_chunks:
        return hits
    # Build index: parent_idx → list of child chunks
    parent_to_children = {}
    child_by_parent = {}
    for c in all_chunks:
        pi = c.get("parent_idx")
        if pi is not None:
            ct = c.get("chunk_type", "")
            if ct == "child":
                parent_to_children.setdefault(pi, []).append(c)
    if not parent_to_children:
        return hits  # no parent-child metadata, skip
    
    expanded = []
    seen_keys = set()
    for hit in hits:
        key = f"{hit.get('file_hash','')}:{hit.get('chunk_index',0)}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        expanded.append(hit)
        
        # Check if this hit is part of a parent-child structure
        parent_idx = hit.get("parent_idx")
        if parent_idx is not None and parent_idx in parent_to_children:
            children = parent_to_children[parent_idx]
            for child in children[:5]:  # max 5 children per parent
                child_key = f"{child.get('file_hash','')}:{child.get('chunk_index',0)}"
                if child_key in seen_keys:
                    continue
                seen_keys.add(child_key)
                expanded.append({
                    **hit,  # inherit parent metadata
                    "text": child.get("text", ""),
                    "chunk_index": child.get("chunk_index", 0),
                    "chunk_type": "child",
                    "parent_idx": parent_idx,
                    "_source": hit.get("_source", "") + "+child",
                    "score": hit.get("score", 0) * 0.85,  # slight penalty for child chunks
                })
    return expanded


def _find_best_sentence(query: str, sentences: list) -> int:
    q_lower = query.lower()
    q_words = [w for w in q_lower.split() if len(w) >= 2 and w not in
               ('的','是','在','和','与','或','了','吗','呢','吧','有','不','也','都','就','要','会','可以','这个','那个','什么','怎么','哪个','一个')]
    if not q_words:
        return 0
    best_idx, best_score = 0, 0
    for i, s in enumerate(sentences):
        s_lower = s.lower()
        score = sum(s_lower.count(w) for w in q_words)
        if score > best_score:
            best_score, best_idx = score, i
    return best_idx


