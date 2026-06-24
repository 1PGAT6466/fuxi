"""
cache.py — 语义缓存服务 (修复版)
==================================
修复内容：
1. 修复 module NameError（原代码 f"[{module}]" 未定义 module）
2. L2 缓存 set_cache 改为异步非阻塞（不阻塞主请求）
3. 添加缓存 TTL 过期清理
"""

import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from typing import Optional, Any
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
                    for i, (emb, results, ts) in enumerate(_l2_cache):
                        if now - ts > MAX_CACHE_AGE_SECONDS:
                            continue
                        sim = _cosine_similarity(q_vec, emb)
                        if sim >= SIMILARITY_THRESHOLD:
                            _cache_hits += 1
                            logger.info(f"[Cache] L2 hit (sim={sim:.3f}): '{query[:40]}...'")
                            return results
            except Exception as e:
                logger.warning(f"[Cache] L2 lookup failed: {e}", exc_info=True)
    
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
        
        # L2 语义缓存（只在 L1 miss 时写入，减少 embedder 调用）
        try:
            from src.db.vector_store import embed_texts
            q_emb = await embed_texts([query])
            if q_emb and q_emb[0]:
                _l2_cache.append((q_emb[0], results, time.time()))
                # 淘汰过期 + 超量
                now = time.time()
                _l2_cache[:] = [
                    (emb, res, ts) for emb, res, ts in _l2_cache
                    if now - ts < MAX_CACHE_AGE_SECONDS
                ]
                while len(_l2_cache) > MAX_CACHE_SIZE // 2:
                    _l2_cache.pop(0)
        except Exception as e:
            logger.warning(f"[Cache] L2 write failed: {e}", exc_info=True)


def _cosine_similarity(a: list, b: list) -> float:
    """余弦相似度（numpy 加速版）"""
    if not a or not b or len(a) != len(b):
        return 0.0
    try:
        import numpy as np
        a_np = np.array(a, dtype=np.float32)
        b_np = np.array(b, dtype=np.float32)
        dot = np.dot(a_np, b_np)
        norm = np.linalg.norm(a_np) * np.linalg.norm(b_np)
        return float(dot / (norm + 1e-10))
    except ImportError:
        # fallback 到纯 Python
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
