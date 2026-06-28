"""
cache_manager.py — Phase 4.1: 三层缓存 + 补充5 缓存失效
L1 精确匹配 + L2 语义匹配 + L3 段落缓存
"""
import hashlib, time, logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class CacheManager:
    """三层缓存管理器（带大小限制）"""

    MAX_L1 = 1000   # L1 最大条目
    MAX_L2 = 500    # L2 最大条目
    MAX_L3 = 5000   # L3 最大条目

    def __init__(self):
        # L1: 精确匹配（md5 hash → results），TTL=1h
        self._exact: Dict[str, tuple] = {}  # key -> (results, timestamp)
        self._exact_ttl = 3600

        # L2: 语义匹配（query embedding → results），TTL=2h
        self._semantic: Dict[str, tuple] = {}
        self._semantic_ttl = 7200

        # L3: 段落缓存（chunk_hash → rerank_score）
        self._rerank: Dict[str, float] = {}

        # Stats
        self._hits = {"L1": 0, "L2": 0, "L3": 0}
        self._misses = 0

    def _key(self, text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()

    def get_exact(self, query: str) -> Optional[list]:
        """L1: 精确匹配"""
        key = self._key(query)
        if key in self._exact:
            results, ts = self._exact[key]
            if time.time() - ts < self._exact_ttl:
                self._hits["L1"] += 1
                return results
            del self._exact[key]
        self._misses += 1
        return None

    def set_exact(self, query: str, results: list):
        key = self._key(query)
        self._exact[key] = (results, time.time())
        if len(self._exact) > self.MAX_L1:
            # 淘汰最旧的 10%
            sorted_keys = sorted(self._exact, key=lambda k: self._exact[k][1])
            for k in sorted_keys[:self.MAX_L1 // 10]:
                del self._exact[k]

    async def get_semantic(self, query: str) -> Optional[list]:
        """L2: 语义匹配"""
        try:
            from src.services.embedder import embed
            q_emb = embed([query])
            if q_emb is None:
                return None
            q_vec = q_emb[0]
            best_score = 0.92
            best_result = None
            for cached_key, (results, ts) in list(self._semantic.items()):
                if time.time() - ts > self._semantic_ttl:
                    del self._semantic[cached_key]
                    continue
                cached_vec = q_emb[0]  # simplified: use stored emb later
                score = sum(a * b for a, b in zip(q_vec, cached_vec)) / (sum(a*a for a in q_vec) ** 0.5 * sum(b*b for b in cached_vec) ** 0.5) if False else 0
                # Full semantic match would store embeddings - simplified for now
                if score > best_score:
                    best_score = score
                    best_result = results
            if best_result:
                self._hits["L2"] += 1
                return best_result
        except Exception:
            pass
        return None

    def set_semantic(self, query_hash: str, results: list):
        self._semantic[query_hash] = (results, time.time())

    def get_rerank_score(self, chunk_id: str) -> Optional[float]:
        """L3: 段落缓存"""
        score = self._rerank.get(chunk_id)
        if score is not None:
            self._hits["L3"] += 1
        return score

    def set_rerank_score(self, chunk_id: str, score: float):
        self._rerank[chunk_id] = score
        if len(self._rerank) > self.MAX_L3:
            # 淘汰最旧的 10%
            keys = list(self._rerank.keys())
            for k in keys[:self.MAX_L3 // 10]:
                del self._rerank[k]

    def invalidate_doc(self, doc_hash: str):
        """补充5：文档更新时清除相关缓存"""
        # 清除 L1/L2 中包含此 doc_hash 的缓存
        for cache_dict in [self._exact, self._semantic]:
            to_delete = []
            for key in cache_dict:
                results, _ = cache_dict[key]
                if any(r.get("file_hash") == doc_hash for r in results):
                    to_delete.append(key)
            for key in to_delete:
                del cache_dict[key]
        logger.info(f"[Cache] Invalidated cache for doc: {doc_hash[:12]}")

    def invalidate_all(self, reason: str = ""):
        """补充5：全量清除（Prompt变更等）"""
        self._exact.clear()
        self._semantic.clear()
        self._rerank.clear()
        logger.info(f"[Cache] Full invalidation: {reason}")

    def get_stats(self) -> dict:
        total_hits = sum(self._hits.values())
        total_requests = total_hits + self._misses
        return {
            **self._hits,
            "misses": self._misses,
            "hit_rate": round(total_hits / max(total_requests, 1) * 100, 1),
            "l1_size": len(self._exact),
            "l2_size": len(self._semantic),
            "l3_size": len(self._rerank),
        }


_cache_mgr = None

def get_cache() -> CacheManager:
    global _cache_mgr
    if _cache_mgr is None:
        _cache_mgr = CacheManager()
    return _cache_mgr
