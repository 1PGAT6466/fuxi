"""
cache.py — 语义缓存服务 (RAG 3.0)
两层缓存策略:
  L1: 精确匹配 (query string → results)
  L2: 语义相似匹配 (query embedding 余弦相似度 > 0.92)
"""
import asyncio
import hashlib
import time
from collections import OrderedDict
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# LRU 缓存配置
MAX_CACHE_SIZE = 200
MAX_CACHE_AGE_SECONDS = 3600  # 1小时
SIMILARITY_THRESHOLD = 0.92   # 语义匹配阈值

_l1_cache: OrderedDict = OrderedDict()  # exact match
_l2_cache: list = []  # semantic match: [(embedding, results, timestamp)]
_cache_lock = asyncio.Lock()
_cache_hits = 0
_cache_misses = 0


def _make_key(query: str, category: str, top_k: int) -> str:
    raw = f"{query}|{category}|{top_k}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


async def get_cache(query: str, category: str = "", top_k: int = 15) -> Optional[list]:
    """查询缓存 — L1 精确 → L2 语义"""
    global _cache_hits, _cache_misses
    
    async with _cache_lock:
        # L1: 精确匹配
        key = _make_key(query, category, top_k)
        if key in _l1_cache:
            entry = _l1_cache[key]
            if time.time() - entry["ts"] < MAX_CACHE_AGE_SECONDS:
                _l1_cache.move_to_end(key)
                _cache_hits += 1
                logger.info(f"[Cache] L1 hit: '{query[:40]}...'")
                return entry["results"]
            else:
                del _l1_cache[key]
        
        # L2: 语义匹配
        if _l2_cache:
            try:
                from src.db.vector_store import embed_texts
                q_emb = await embed_texts([query])
                if q_emb and q_emb[0]:
                    q_vec = q_emb[0]
                    now = time.time()
                    valid_count = 0
                    for i, (emb, results, ts) in enumerate(_l2_cache):
                        if now - ts > MAX_CACHE_AGE_SECONDS:
                            continue
                        valid_count += 1
                        sim = _cosine_similarity(q_vec, emb)
                        if sim >= SIMILARITY_THRESHOLD:
                            _cache_hits += 1
                            logger.info(f"[Cache] L2 hit (sim={sim:.3f}): '{query[:40]}...'")
                            return results
                    # 如果大量过期，触发清理
                    if len(_l2_cache) - valid_count > 10:
                        _l2_cache[:] = [(e, r, t) for e, r, t in _l2_cache
                                        if now - t < MAX_CACHE_AGE_SECONDS]
            except Exception as e:  # TODO: Narrow exception type

                logger.warning(f"[cache] suppressed exception", exc_info=True)
    _cache_misses += 1
    return None


async def set_cache(query: str, results: list, category: str = "", top_k: int = 15):
    """写入缓存"""
    async with _cache_lock:
        key = _make_key(query, category, top_k)
        
        # L1 写入
        _l1_cache[key] = {"ts": time.time(), "results": results}
        _l1_cache.move_to_end(key)
        
        # 淘汰最旧的
        while len(_l1_cache) > MAX_CACHE_SIZE:
            _l1_cache.popitem(last=False)
        
        # L2 语义缓存（异步写入 embedding）
        try:
            from src.db.vector_store import embed_texts
            q_emb = await embed_texts([query])
            if q_emb and q_emb[0]:
                now = time.time()
                _l2_cache.append((q_emb[0], results, now))
                # 清理过期条目 + 大小淘汰
                _l2_cache[:] = [(e, r, t) for e, r, t in _l2_cache
                                if now - t < MAX_CACHE_AGE_SECONDS]
                while len(_l2_cache) > MAX_CACHE_SIZE // 2:
                    _l2_cache.pop(0)
        except Exception as e:  # TODO: Narrow exception type

            logger.warning(f"[cache] suppressed exception", exc_info=True)

def _cosine_similarity(a: list, b: list) -> float:
    """余弦相似度"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def get_cache_stats() -> dict:
    return {
        "l1_size": len(_l1_cache),
        "l2_size": len(_l2_cache),
        "hits": _cache_hits,
        "misses": _cache_misses,
        "hit_rate": round(_cache_hits / max(1, _cache_hits + _cache_misses), 3),
    }


def clear_cache():
    global _l1_cache, _l2_cache, _cache_hits, _cache_misses
    _l1_cache = OrderedDict()
    _l2_cache = []
    _cache_hits = 0
    _cache_misses = 0
    logger.info("[Cache] cleared")
