"""
services/retrieval.py — 混合检索服务（v10.0）
负责：BM25 + 向量双路召回 → RRF 融合 → 精排 → 去重 → 上下文扩展
"""
import logging; logger = logging.getLogger(__name__)
import re, asyncio
from typing import List, Dict

# v11: Concurrent control for ChromaDB
_VECTOR_SEM = asyncio.Semaphore(2)

try:
    import jieba
    jieba.setLogLevel(20)
except ImportError:
    jieba = None

from src.db.memory_store import get_store
from src.db.vector_store import get_vector_store, embed_texts
from src.services.graph_router import route_to_categories, expand_query_with_synonyms, get_entity_context
from src.config import EMBEDDER_URL
from src.services.query_expansion import expand_query, llm_rewrite_query, hyde_expand_query
from src.services.fusion import rrf_fusion, weighted_fusion_adjust, exact_match_boost, dynamic_category_weight, personalized_boost
from src.services.results_postprocess import mmr_dedup, expand_context, _split_sentences_zh, _expand_parent_child, _find_best_sentence
from src.services.synonym_loader import load_synonyms
# 兼容别名
_SYNONYM_MAP = load_synonyms()



def _merge_vector_results(hyde_results: list, orig_results: list) -> list:
    """合并 HyDE + 原始向量结果，去重"""
    seen = set()
    merged = []
    for r in hyde_results + orig_results:
        key = r.get("file_hash", "") + "|" + str(r.get("chunk_index", 0))
        if key not in seen:
            seen.add(key)
            merged.append(r)
    return merged


async def vector_recall(query: str, n_results: int = 30, category: str = "") -> list:
    """L2-路2: 向量语义召回"""
    results = []
    try:
        q_emb = await embed_texts([query])
        if not q_emb or not q_emb[0]:
            return results
        vs = get_vector_store()
        if not vs or vs.count <= 0:
            return results  # count=0 空库 / count=-1 ChromaDB 故障
        # 分类过滤（v10.1: Chroma where clause）
        chroma_filter = {"category": category} if category else None
        async with _VECTOR_SEM:
            loop = asyncio.get_running_loop()
            vr = await loop.run_in_executor(
                None, 
                lambda: vs.query(q_emb[0], n_results=n_results, where=chroma_filter)
            )
        if vr.get("error"):
            logger.warning(f"Vector query failed: {vr.get('reason')}")
            return results
        if not vr.get("ids") or not vr["ids"][0]:
            return results
        for i, vid in enumerate(vr["ids"][0]):
            meta = vr["metadatas"][0][i] if i < len(vr["metadatas"][0]) else {}
            dist = vr["distances"][0][i] if i < len(vr["distances"][0]) else 0
            sim = 1.0 - float(dist)
            if sim > 0.15:
                results.append({
                    "file_hash": meta.get("file_hash", ""),
                    "text": meta.get("text", ""),
                    "file_name": meta.get("file_name", ""),
                    "category": meta.get("category", ""),
                    "chunk_index": meta.get("chunk_index", 0),
                    "score": round(sim * 10, 2),
                    "_source": "vector",
                    "_similarity": round(sim, 4),
                })
    except Exception:
        logger.warning(f"[retrieval] suppressed exception", exc_info=True)
        pass
    return results


async def hybrid_search(query: str, chunks: list = None, category: str = "",
                        file_type: str = "", date_from: str = "", date_to: str = "",
                        top_k: int = 15, skip_cache: bool = False) -> list:
    """
    完整混合检索管线 (RAG 3.0):
    L0: 语义缓存 → L1: Query 扩展(分词+同义词+LLM改写) → L1.5: HyDE → L2: BM25+向量双路 → 
    L3: RRF 融合 + 动态 alpha → L4: 精排(精确/分类/个性化/MMR) → 
    L5: Rerank → L6: Parent-Child + Sentence Window 上下文扩展
    """
    # L-1: QA对匹配（v1.42）— 口语化问题桥接，命中时跳过缓存
    try:
        from src.db.memory_store import get_store
        store_inst = get_store()
        if hasattr(store_inst, 'search_qa_pairs'):
            qa_results = store_inst.search_qa_pairs(query, top_k=3)
            if qa_results:
                qa_chunk_ids = [r.get("source_chunk_id") for r in qa_results if r.get("source_chunk_id")]
                if qa_chunk_ids:
                    skip_cache = True  # QA匹配命中时跳过缓存直接走全文检索
                    logger.info(f"[Retrieval] QA pair match: {len(qa_chunk_ids)} source chunks for '{query[:30]}...'")
    except Exception:
        pass

    # L0: 语义缓存（精确+相似查询命中直接返回）
    if not skip_cache:
        cached = await _check_cache(query, category, top_k)
        if cached is not None:
            return cached
    
    if chunks is None:
        from src.db.data_store import load_chunks
        chunks = load_chunks()

    # L0: 图谱驱动路由 — 识别实体 → 锁定分类范围
    graph_categories = route_to_categories(query)
    if graph_categories and not category:
        # 图谱命中了分类 → 优先在相关分类中检索
        category = graph_categories[0]  # 主分类
        logger.info(f"[graph-router] Query '{query}' → categories: {graph_categories}, main: {category}")
    
    # L1: Query 扩展（+ 同义词 + LLM 改写）
    expanded_q = expand_query_with_synonyms(query)
    rewritten = expand_query(expanded_q)
    # L1-P2: LLM 驱动查询改写（与 HyDE 并行）
    llm_rewrite_task = asyncio.create_task(llm_rewrite_query(query))

    # L1.5 + L2: HyDE + BM25 + 向量三路并行 (v10.1)
    async def _bm25_search():
        store = get_store()
        r = store.hierarchical_search(rewritten, category, file_type, date_from, date_to,
                                      summary_top_k=5, chunk_top_k=top_k * 3)
        if not r:
            r = store.keyword_search(rewritten, category, file_type, date_from, date_to, top_k)
        return r
    
    async def _hyde_and_vector():
        hyde_t = await hyde_expand_query(query)
        sq = hyde_t if hyde_t else query
        vec_r = await vector_recall(sq, top_k * 2)
        if hyde_t:
            hyde_vec_r = await vector_recall(query, top_k)
            vec_r = _merge_vector_results(vec_r, hyde_vec_r)
        return vec_r
    
    hyde_task = asyncio.create_task(_hyde_and_vector())
    
    # L1.75: Wiki summary vector recall (with worldtree fallback)
    async def _wiki_recall():
        wiki_hits = []
        try:
            q_emb = await embed_texts([query])
            if q_emb and q_emb[0]:
                try:
                    from src.services.wiki import get_wiki_engine
                    we = get_wiki_engine()
                    wiki_hits = we.vector_search_wiki(q_emb[0], top_k=3)
                except ModuleNotFoundError:
                    # Fallback: keyword search in worldtree.db wiki_pages
                    import sqlite3
                    from src.config import WORLDTREE_DB_PATH
                    wt_db = sqlite3.connect(str(WORLDTREE_DB_PATH))
                    wt_db.row_factory = sqlite3.Row
                    rows = wt_db.execute(
                        "SELECT id, title, summary, category_path FROM wiki_pages WHERE title LIKE ? OR summary LIKE ? LIMIT 5",
                        (f"%{query}%", f"%{query}%")
                    ).fetchall()
                    wt_db.close()
                    for r in rows:
                        d = dict(r)
                        wiki_hits.append({
                            "wiki_id": d["id"],
                            "title": d["title"],
                            "category": d.get("category_path", "") or "",
                            "similarity": 0.7
                        })
        except Exception as e:
            logger.warning(f"[Wiki recall] {e}")
        return wiki_hits
    
    wiki_task = asyncio.create_task(_wiki_recall())
    
    # L1-P2: 等待 LLM Rewrite 结果，若有改写则双路检索
    try:
        llm_rewritten = await asyncio.wait_for(llm_rewrite_task, timeout=10.0)
    except (asyncio.TimeoutError, Exception):
        llm_rewritten = None
    if llm_rewritten and llm_rewritten != query:
        _rewritten_for_bm25 = expand_query(expand_query_with_synonyms(llm_rewritten))
        async def _retrieve_with_rewrite():
            store = get_store()
            r = store.hierarchical_search(_rewritten_for_bm25, category, file_type, date_from, date_to,
                                           summary_top_k=5, chunk_top_k=top_k * 3)
            if not r:
                r = store.keyword_search(_rewritten_for_bm25, category, file_type, date_from, date_to, top_k)
            return r
        results = await _retrieve_with_rewrite()
    else:
        results = await _bm25_search()
    for i, r in enumerate(results):
        r["_bm25_rank"] = i + 1
        r["_source"] = "bm25"
    
    try:
        vector_results = await asyncio.wait_for(hyde_task, timeout=15.0)
    except asyncio.TimeoutError:
        logger.warning("[Retrieval] HyDE task timeout, continuing without it")
        vector_results = []
    for i, r in enumerate(vector_results):
        r["_vector_rank"] = i + 1
        r["_source"] = "vector"

    # L3: RRF 融合
    merged = rrf_fusion(results, vector_results, k=60)

    # RAG 3.0: Multi-View 表格视图 (第四路召回)
    table_task = asyncio.create_task(_table_recall(query, chunks, top_k))

    # Wiki results injection
    wiki_hits = await wiki_task
    if wiki_hits:
        for wh in wiki_hits:
            merged.append({
                "file_hash": "wiki:" + wh["wiki_id"],
                "text": "[Wiki] " + wh["title"],
                "file_name": "[Wiki]",
                "category": wh.get("category", ""),
                "chunk_index": 0,
                "score": round(wh.get("similarity", 0.5) * 12, 2),
                "_source": "wiki",
                "_wiki_id": wh["wiki_id"],
                "_wiki_title": wh["title"],
            })
    
    # RAG 3.0: Table view results injection
    table_results = await table_task
    if table_results:
        for tr in table_results:
            merged.append({**tr, "_source": "table_view"})
        logger.info(f"[TableView] injected {len(table_results)} table results")
    
    merged.sort(key=lambda x: float(x.get("score", 0)), reverse=True)
    merged = weighted_fusion_adjust(query, merged, results, vector_results)
    if not merged:
        merged = results[:top_k * 3]

    # L4: 三阶段精排
    merged = exact_match_boost(query, merged)
    merged = dynamic_category_weight(query, merged)
    merged = personalized_boost(query, merged)
    merged = mmr_dedup(merged, diversity_weight=0.25, top_k=top_k * 2)

    # L5: Rerank（同步优先 + 异步回退）
    # 先尝试同步获取精排结果；超时/失败则异步后台完成
    for r in merged:
        r["_query"] = query
    merged = expand_context(merged, None, 2, 2, 3000)
    
    # P1-3: Parent-Child expansion — when a parent chunk is hit, attach its child chunks
    merged = _expand_parent_child(merged, chunks)
    
    rerank_result = await _rerank_layer(query, list(merged), top_k * 2)
    if rerank_result:
        merged = rerank_result
    # 注意：rerank_layer 内部已有完整的降级链，不再需要额外的异步重试
    # 如果 rerank 失败，merged 保持 RRF+精排的结果直接返回

    result = merged[:top_k]
    
    # P1.1.1: 统一返回格式 — 添加 context 和 meta 字段
    context_parts = []
    for r in result:
        text = r.get("text", "") or r.get("chunk_text", "")
        if text:
            context_parts.append(text[:500])
    
    meta = {
        "query": query,
        "total_candidates": len(merged),
        "returned": len(result),
        "sources": list(set(r.get("_source", "unknown") for r in result)),
        "pipeline": "hybrid_v3",
    }
    
    # 在每个结果中注入统一字段
    for r in result:
        r["context"] = context_parts
        r["meta"] = meta
    
    # RAG 3.0: 写入语义缓存
    try:
        from src.services.cache import set_cache as _set_cache_sync
        await _set_cache_sync(query, result, category, top_k)
    except Exception as e:

        logger.warning("suppressed exception", exc_info=True)
    return result


async def _rerank_layer(query: str, candidates: list, top_k: int = 30) -> list:
    """P1: Cross-encoder 精排
    
    三级降级链:
      1. SiliconFlow Qwen3-Reranker-8B (via proxy <proxy_host>)
      2. embedder_server /rerank 端点
      3. 本地 TF-IDF (jieba)
    """
    if not candidates:
        return candidates
    try:
        from src.services.rerank import rerank
        # 调用统一入口，内部分级降级
        ranked = await rerank(query, candidates, top_k)
        if ranked:
            logger.info(f'intermediate-rerank: {len(ranked)} results via rerank service')
            # 标记精排来源
            first = ranked[0] if ranked else {}
            rr_score = first.get('_rerank_score', 0)
            import json as _json
            logger.debug(f'intermediate-rerank top score: {rr_score:.4f}, source: {first.get("_source", "?")}')
            return ranked
    except Exception as e:
        logger.warning(f'intermediate-rerank fallback: {e}')
    # 最终兜底：返回原始排序
    return candidates[:top_k]


# ============ RAG 3.0: 语义缓存 ============

async def _check_cache(query: str, category: str, top_k: int):
    try:
        from src.services.cache import get_cache
        return await get_cache(query, category, top_k)
    except Exception:
        return None

async def _set_cache(query: str, results: list, category: str, top_k: int):
    try:
        from src.services.cache import set_cache
        await set_cache(query, results, category, top_k)
    except Exception as e:

        logger.warning("suppressed exception", exc_info=True)
# RAG 3.0: Multi-View 表格视图
async def _table_recall(query: str, chunks: list, top_k: int) -> list:
    try:
        from src.services.table_view import table_view_recall
        return await table_view_recall(query, chunks, top_k)
    except Exception:
        return []


# 兼容旧接口
keyword_search = hybrid_search
vector_search = hybrid_search
