"""
v1.44 Phase 1 Fix — RAG 检索路由
提供传统 chunk 检索、SAG Event 粒度检索、实体向量扩展端点
"""
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RAG 检索"])


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    mode: str = "semantic"  # semantic / keyword / hybrid
    score_threshold: float = 0


class EventSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    granularity: str = "auto"  # chunk / event / auto
    score_threshold: float = 0
    mode: str = "semantic"  # semantic / keyword / hybrid


# ============ POST /api/rag/search — 传统 chunk 粒度检索 ============

@router.post("/api/rag/search")
async def rag_search(body: SearchRequest, request: Request = None):
    """传统 chunk 粒度检索 — 调用 shaoyang + ChromaDB

    返回 {results, total} 格式。
    """
    try:
        # 尝试使用 taiyang 检索模块
        try:
            from src.taiyang.retrieval import search_chunks
            results = search_chunks(
                query=body.query,
                top_k=body.top_k,
                mode=body.mode,
                score_threshold=body.score_threshold,
            )
            return {
                "results": results,
                "total": len(results),
            }
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"taiyang.retrieval 调用失败，回退到基本搜索: {e}")

        # 回退：使用 db/vector_store 直接检索
        try:
            from src.db.vector_store import get_vector_store
            vs = get_vector_store()
            if vs:
                results = vs.search(body.query, top_k=body.top_k)
                formatted = []
                for r in results:
                    formatted.append({
                        "id": r.get("id", ""),
                        "text": r.get("text", r.get("content", "")),
                        "score": r.get("score", r.get("distance", 0)),
                        "metadata": r.get("metadata", {}),
                        "source": r.get("metadata", {}).get("source", ""),
                    })
                return {
                    "results": formatted,
                    "total": len(formatted),
                }
        except Exception as e2:
            logger.warning(f"vector_store 回退也失败: {e2}")

        # 最终回退：返回空结果
        return {
            "results": [],
            "total": 0,
        }
    except Exception as e:
        logger.exception(f"rag_search 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)}
        )


# ============ POST /api/rag/sag-search — SAG Event 粒度检索 ============

@router.post("/api/rag/sag-search")
async def rag_sag_search(body: EventSearchRequest, request: Request = None):
    """SAG Event 粒度检索 — 支持 chunk/event/auto 三种粒度

    返回 {results, events, total, granularity} 格式。
    """
    try:
        granularity = body.granularity or "auto"

        results = []
        events = []

        try:
            from src.taiyang.sag_pipeline import search_sag
            sag_results = search_sag(
                query=body.query,
                top_k=body.top_k,
                granularity=granularity,
                score_threshold=body.score_threshold,
            )
            if sag_results:
                if isinstance(sag_results, dict):
                    results = sag_results.get("results", sag_results.get("chunks", []))
                    events = sag_results.get("events", sag_results.get("sag_events", []))
                elif isinstance(sag_results, list):
                    results = sag_results
                return {
                    "results": results,
                    "events": events,
                    "total": len(results),
                    "granularity": granularity,
                }
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"sag_pipeline 调用失败，回退: {e}")

        # 回退：使用标准 chunk 检索
        try:
            from src.taiyang.retrieval import search_chunks
            results = search_chunks(
                query=body.query,
                top_k=body.top_k,
                mode=body.mode,
                score_threshold=body.score_threshold,
            )
            return {
                "results": results,
                "events": events,
                "total": len(results),
                "granularity": "chunk",
            }
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"retrieval 回退失败: {e}")

        # 最终回退
        return {
            "results": [],
            "events": [],
            "total": 0,
            "granularity": granularity,
        }
    except Exception as e:
        logger.exception(f"rag_sag_search 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)}
        )


# ============ POST /api/rag/sag-trace — SAG 检索追踪 SSE ============

class SAGTraceRequest(BaseModel):
    session_id: str


@router.post("/api/rag/sag-trace")
async def rag_sag_trace(body: SAGTraceRequest, request: Request = None):
    """SAG 检索追踪 — SSE 流式返回三阶段流水线数据

    当前为占位实现：返回一个空追踪流。
    完整实现需要从 SAG Pipeline 获取实时 trace 数据。
    """
    try:
        import json
        import asyncio
        from fastapi.responses import StreamingResponse

        async def trace_generator():
            yield f"data: {json.dumps({'type': 'start', 'session_id': body.session_id, 'message': 'SAG 追踪已启动'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.5)
            yield f"data: {json.dumps({'type': 'stage', 'stage': 'stage1_retrieval', 'message': '阶段1: 检索完成（占位）'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.3)
            yield f"data: {json.dumps({'type': 'stage', 'stage': 'stage2_rerank', 'message': '阶段2: 重排序完成（占位）'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.3)
            yield f"data: {json.dumps({'type': 'stage', 'stage': 'stage3_generation', 'message': '阶段3: 生成完成（占位）'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.2)
            yield f"data: [DONE]\n\n"

        return StreamingResponse(
            trace_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        logger.exception(f"rag_sag_trace 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)}
        )


# ============ GET /api/rag/entity-expand — 实体向量扩展 ============

@router.get("/api/rag/entity-expand")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def rag_entity_expand(
    entity_name: str = Query(..., description="实体名称"),
    request: Request = None,
):
    """实体向量扩展 — 输入实体名，返回向量相似度排序的扩展实体

    当前占位实现：返回空扩展列表。
    完整实现需要调用嵌入模型 + ChromaDB 查找相似实体。
    """
    try:
        if not entity_name or not entity_name.strip():
            return JSONResponse(
                status_code=400,
                content={"error": "缺少 entity_name 参数"}
            )

        # 尝试使用 taiyang 实体扩展
        try:
            from src.taiyang.expand import expand_entity
            expanded = expand_entity(entity_name, top_k=10)
            return {
                "entity_name": entity_name,
                "expanded_entities": expanded,
                "total": len(expanded),
            }
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"expand_entity 失败: {e}")

        # 占位返回
        return {
            "entity_name": entity_name,
            "expanded_entities": [],
            "total": 0,
        }
    except Exception as e:
        logger.exception(f"rag_entity_expand 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)}
        )
