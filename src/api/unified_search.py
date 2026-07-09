"""
v2.1 — 统一搜索 API（伏羲令，真实跨服务聚合）
数据来源：搜索 + Wiki + 知识图谱 + 文件索引 聚合查询
"""
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter(tags=["统一搜索"])

# ChromaDB 种子数据标记
_SEED_CONTENT_PREFIXES = (
    "伏羲是一个企业知识认知中枢",
    "ChromaDB 是一个开源的向量数据库",
    "PostgreSQL 的 pgvector 扩展",
    "文档分块是 RAG 管线的关键步骤",
    "HNSW 是一种高效的近似最近邻搜索算法",
    "坤卦 ☷ 负责伏羲系统的记忆存储",
)


def _is_seed_result(item: dict) -> bool:
    """检查搜索结果是否为种子数据"""
    text = (item.get("text", "") or item.get("content", "") or "").strip()
    for prefix in _SEED_CONTENT_PREFIXES:
        if text.startswith(prefix):
            return True
    return False


def _mark_seed_results(results: list) -> list:
    """为种子数据标记 origin 属性"""
    for r in results:
        if _is_seed_result(r):
            r["origin"] = "seed"
            if "note" not in r:
                r["note"] = "示例数据（系统种子向量）"
    return results


@router.get("/api/unified-search")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def unified_search(
    request: Request = None,
    q: str = Query("", description="搜索关键词"),
):
    """伏羲令统一搜索 — v1.50 真实跨服务聚合

    搜索来源：
      1. 知识库语义搜索 (hybrid_search)
      2. Wiki 页面搜索 (wiki_engine)
      3. 知识图谱实体搜索 (graph)

    示例数据自动标记 origin=seed。
    结果为空时返回引导信息。
    """
    t0 = time.time()
    try:
        matches = []
        searched_sources = []

        if not q or not q.strip():
            return _build_response(
                request, q, [], 0, time.time() - t0,
                hint="请输入搜索关键词",
            )

        # 1. 知识库搜索
        try:
            from src.taiyang.retrieval import hybrid_search
            kb_results = await hybrid_search(q, top_k=5)
            searched_sources.append("knowledge_base")
            for r in kb_results:
                matches.append({
                    "source": "knowledge_base",
                    "title": r.get("title", r.get("source", "")),
                    "text": r.get("text", r.get("snippet", ""))[:200],
                    "score": r.get("score", r.get("distance", 0)),
                    "file_name": r.get("file_name", ""),
                    "chunk_id": r.get("chunk_id", r.get("id", "")),
                })
        except ImportError:
            searched_sources.append("knowledge_base (unavailable)")
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"统一搜索 - 知识库查询失败: {e}")
            searched_sources.append(f"knowledge_base (error)")

        # 2. Wiki 搜索
        try:
            from src.taiyang.wiki import get_wiki_engine
            wiki_engine = get_wiki_engine()
            wiki_pages = wiki_engine.search_content(q, limit=5)
            searched_sources.append("wiki")
            for p in wiki_pages:
                matches.append({
                    "source": "wiki",
                    "title": p.get("title", ""),
                    "text": (p.get("summary", "") or p.get("content", ""))[:200],
                    "page_id": p.get("id", ""),
                    "score": 1.0,
                })
        except ImportError:
            searched_sources.append("wiki (unavailable)")
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"统一搜索 - Wiki 查询失败: {e}")
            searched_sources.append(f"wiki (error)")

        # 3. 知识图谱搜索
        try:
            from src.taiyang.graph import query_graph
            graph_results = query_graph(entity=q, limit=5)
            searched_sources.append("knowledge_graph")
            for g in graph_results:
                matches.append({
                    "source": "knowledge_graph",
                    "title": g.get("name", g.get("entity", "")),
                    "text": g.get("description", g.get("relation", ""))[:200],
                    "entity": g.get("name", g.get("entity", "")),
                    "score": g.get("score", g.get("confidence", 0.5)),
                })
        except ImportError:
            searched_sources.append("knowledge_graph (unavailable)")
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"统一搜索 - 图谱查询失败: {e}")
            searched_sources.append(f"knowledge_graph (error)")

        # 标记种子数据
        matches = _mark_seed_results(matches)

        # 按 score 排序
        matches.sort(key=lambda m: m.get("score", 0), reverse=True)

        took_ms = round((time.time() - t0) * 1000, 1)
        hint = None
        if not matches:
            hint = f'未找到与 "{q}" 相关的结果。尝试：上传更多文档、使用不同关键词、在 Wiki 中创建相关页面。'

        return _build_response(request, q, matches, took_ms, hint=hint, sources=searched_sources)

    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"unified_search 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


def _build_response(request, q: str, matches: list, took_ms: float,
                    hint: str = None, sources: list = None) -> dict:
    """构建统一响应"""
    data = {
        "query": q,
        "matches": matches,
        "total": len(matches),
        "took_ms": took_ms,
        "sources": sources or [],
    }
    if hint:
        data["hint"] = hint

    # 统计种子数据
    seed_count = sum(1 for m in matches if m.get("origin") == "seed")
    if seed_count > 0:
        data["seed_count"] = seed_count
        data["seed_note"] = f"其中 {seed_count} 条结果为示例数据（种子向量）"

    _wants_v2 = request and (
        request.query_params.get("format") == "v2"
        or request.headers.get("X-API-Format", "").lower() == "v2"
    )
    if _wants_v2:
        from src.api.response import success
        return success(data=data, message="统一搜索")
    return data
