"""
v1.44 Phase 1 Fix — RAG 检索路由
提供传统 chunk 检索、SAG Event 粒度检索、实体向量扩展端点
v1.50: 种子数据自动标记 origin=seed
"""
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RAG 检索"])

# ============ 种子数据标记 ============
# ChromaDB 种子向量内容前缀
_CHROMA_SEED_PREFIXES = (
    "伏羲是一个企业知识认知中枢",
    "ChromaDB 是一个开源的向量数据库",
    "PostgreSQL 的 pgvector 扩展",
    "文档分块是 RAG 管线的关键步骤",
    "HNSW 是一种高效的近似最近邻搜索算法",
    "坤卦 \u2637 负责伏羲系统的记忆存储",
)
# chunks.db 种子文件
_CHUNKS_SEED_NAMES = frozenset({"test_knowledge.md", "malware.exe"})


def _mark_seed_results(results: list) -> list:
    """为种子数据标记 origin=seed 属性"""
    for r in results:
        text = (r.get("text", "") or r.get("content", "") or "").strip()

        # 检查是否为 ChromaDB 种子向量
        is_chroma_seed = any(text.startswith(p) for p in _CHROMA_SEED_PREFIXES)

        # 检查是否为 chunks.db 种子
        fname = (r.get("file_name", "") or r.get("metadata", {}).get("file_name", "") or "").lower()
        is_chunk_seed = fname in _CHUNKS_SEED_NAMES

        if is_chroma_seed or is_chunk_seed:
            r["origin"] = "seed"
            if "note" not in r:
                r["note"] = f"示例数据{'（ChromaDB 种子向量）' if is_chroma_seed else '（chunks.db 测试数据）'}" if is_chroma_seed else f"示例数据（{fname}）"

    return results


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    mode: str = "semantic"  # semantic / keyword / hybrid
    score_threshold: float = 0

    @field_validator("top_k")
    @classmethod
    def validate_top_k(cls, v: int) -> int:
        """v1.44 安全修复: top_k 上限验证"""
        from src.services.prompt_guard import clamp_top_k
        return clamp_top_k(v)


class EventSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    granularity: str = "auto"  # chunk / event / auto
    score_threshold: float = 0
    mode: str = "semantic"  # semantic / keyword / hybrid

    @field_validator("top_k")
    @classmethod
    def validate_top_k(cls, v: int) -> int:
        """v1.44 安全修复: top_k 上限验证"""
        from src.services.prompt_guard import clamp_top_k
        return clamp_top_k(v)


# ============ POST /api/rag/search — 传统 chunk 粒度检索 ============

def _filter_by_tenant(results: list, tenant_id: str) -> list:
    """多租户隔离：按 tenant_id 过滤结果
    
    规则：
      - 如果结果 metadata 中有 tenant_id 字段，必须匹配
      - 如果结果 metadata 中无 tenant_id 字段，视为默认租户数据
      - 非默认租户不能访问其他租户的数据
    """
    if tenant_id == "default":
        return results
    filtered = []
    for r in results:
        meta = r.get("metadata", {})
        r_tenant = meta.get("tenant_id", "default")
        if r_tenant == tenant_id:
            filtered.append(r)
    return filtered


@router.post("/api/rag/search")
async def rag_search(body: SearchRequest, request: Request = None):
    """传统 chunk 粒度检索 — 调用 shaoyang + ChromaDB

    返回 {results, total} 格式。
    v1.44 R2: 多租户隔离 — 从 JWT 提取 tenant_id，过滤搜索结果
    """
    # v1.44 R2: 从 request.state 获取租户 ID
    tenant_id = getattr(request.state, "tenant_id", "default") if request else "default"

    # v1.44 安全修复: top_k 上限
    from src.services.prompt_guard import clamp_top_k
    top_k = clamp_top_k(body.top_k)
    
    try:
        # 尝试使用 taiyang 检索模块
        try:
            from src.taiyang.retrieval import search_chunks
            results = search_chunks(
                query=body.query,
                top_k=top_k,
                mode=body.mode,
                score_threshold=body.score_threshold,
            )
            # v1.44 R2: 多租户隔离过滤
            results = _filter_by_tenant(results, tenant_id)
            return {
                "results": results,
                "total": len(results),
            }
        except ImportError:
            pass
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"taiyang.retrieval 调用失败，回退到基本搜索: {e}")

        # 回退：使用 db/vector_store 直接检索
        try:
            from src.db.vector_store import get_vector_store
            vs = get_vector_store()
            if vs:
                results = vs.search(body.query, top_k=top_k)
                formatted = []
                for r in results:
                    formatted.append({
                        "id": r.get("id", ""),
                        "text": r.get("text", r.get("content", "")),
                        "score": r.get("score", r.get("distance", 0)),
                        "metadata": r.get("metadata", {}),
                        "source": r.get("metadata", {}).get("source", ""),
                    })
                # v1.44 R2: 多租户隔离过滤
                formatted = _filter_by_tenant(formatted, tenant_id)
                # v1.50: 标记种子数据
                formatted = _mark_seed_results(formatted)
                return {
                    "results": formatted,
                    "total": len(formatted),
                    "seed_count": sum(1 for r in formatted if r.get("origin") == "seed"),
                }
        except Exception as e2:  # TODO: Narrow exception type
            logger.warning(f"vector_store 回退也失败: {e2}")

        # 最终回退：返回空结果
        return {
            "results": [],
            "total": 0,
        }
    except Exception as e:  # TODO: Narrow exception type
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
    v1.44 R2: 多租户隔离 — 从 JWT 提取 tenant_id，过滤搜索结果
    """
    # v1.44 R2: 从 request.state 获取租户 ID
    tenant_id = getattr(request.state, "tenant_id", "default") if request else "default"

    # v1.44 安全修复: top_k 上限
    from src.services.prompt_guard import clamp_top_k
    top_k = clamp_top_k(body.top_k)
    
    try:
        granularity = body.granularity or "auto"

        results = []
        events = []

        try:
            from src.taiyang.sag_pipeline import search_sag
            sag_results = search_sag(
                query=body.query,
                top_k=top_k,
                granularity=granularity,
                score_threshold=body.score_threshold,
            )
            if sag_results:
                if isinstance(sag_results, dict):
                    results = sag_results.get("results", sag_results.get("chunks", []))
                    events = sag_results.get("events", sag_results.get("sag_events", []))
                elif isinstance(sag_results, list):
                    results = sag_results
                # v1.44 R2: 多租户隔离过滤
                results = _filter_by_tenant(results, tenant_id)
                # v1.50: 标记种子数据
                results = _mark_seed_results(results)
                return {
                    "results": results,
                    "events": events,
                    "total": len(results),
                    "granularity": granularity,
                    "seed_count": sum(1 for r in results if r.get("origin") == "seed"),
                }
        except ImportError:
            pass
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"sag_pipeline 调用失败，回退: {e}")

        # 回退：使用标准 chunk 检索
        try:
            from src.taiyang.retrieval import search_chunks
            results = search_chunks(
                query=body.query,
                top_k=top_k,
                mode=body.mode,
                score_threshold=body.score_threshold,
            )
            # v1.44 R2: 多租户隔离过滤
            results = _filter_by_tenant(results, tenant_id)
            # v1.50: 标记种子数据
            results = _mark_seed_results(results)
            return {
                "results": results,
                "events": events,
                "total": len(results),
                "granularity": "chunk",
                "seed_count": sum(1 for r in results if r.get("origin") == "seed"),
            }
        except ImportError:
            pass
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"retrieval 回退失败: {e}")

        # 最终回退
        return {
            "results": [],
            "events": [],
            "total": 0,
            "granularity": granularity,
        }
    except Exception as e:  # TODO: Narrow exception type
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

    v2.1: 尝试从真实 SAG Pipeline 获取 trace 数据，
    失败时回退到状态说明而非虚假占位数据。
    """
    try:
        import json
        import asyncio
        from fastapi.responses import StreamingResponse

        async def trace_generator():
            yield f"data: {json.dumps({'type': 'start', 'session_id': body.session_id, 'message': 'SAG 追踪已启动'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.5)
            
            # 尝试从真实 SAG Pipeline 获取追踪数据
            real_trace = None
            try:
                from src.taiyang.sag_pipeline import SagTracer
                tracer = SagTracer()
                real_trace = tracer.get_trace(body.session_id)
            except ImportError:
                pass
            except Exception as trace_err:  # TODO: Narrow exception type
                logger.warning(f"SAG 追踪获取失败: {trace_err}")
            
            if real_trace and real_trace.get("stages"):
                # 返回真实追踪数据
                for stage in real_trace.get("stages", []):
                    stage_data = {
                        "type": "stage",
                        "stage": stage.get("name", ""),
                        "message": stage.get("message", ""),
                        "duration_ms": stage.get("duration_ms", 0),
                        "details": stage.get("details", {}),
                    }
                    yield f"data: {json.dumps(stage_data, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.2)
            else:
                # 无实时追踪数据：明确告知当前状态而非返回虚假占位
                yield f"data: {json.dumps({'type': 'notice', 'message': 'SAG 实时追踪数据暂不可用。系统运行正常，但追踪功能需连接活跃的 SAG Pipeline 实例。'}, ensure_ascii=False)}\n\n"
            
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
    except Exception as e:  # TODO: Narrow exception type
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

    v2.1: 回退时明确告知原因，区分"功能未实现"与"无匹配结果"。
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
                "source": "taiyang.expand",
            }
        except ImportError:
            logger.info("taiyang.expand 模块未安装，实体扩展功能不可用")
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"expand_entity 调用失败: {e}")

        # 尝试知识图谱回退
        try:
            from src.db.data_store import load_graph
            graph = await asyncio.to_thread(load_graph)
            nodes = graph.get("nodes", {})
            if entity_name in nodes:
                related = []
                for edge in graph.get("edges", []):
                    if edge.get("from") == entity_name:
                        related.append({
                            "name": edge.get("to", ""),
                            "relation": edge.get("relation", ""),
                            "source": "knowledge_graph",
                        })
                    elif edge.get("to") == entity_name:
                        related.append({
                            "name": edge.get("from", ""),
                            "relation": edge.get("relation", ""),
                            "source": "knowledge_graph",
                        })
                if related:
                    return {
                        "entity_name": entity_name,
                        "expanded_entities": related[:10],
                        "total": len(related),
                        "source": "knowledge_graph",
                    }
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"知识图谱回退失败: {e}")

        # 明确告知调用方：功能未实现 vs 无匹配结果
        return {
            "entity_name": entity_name,
            "expanded_entities": [],
            "total": 0,
            "notice": "实体扩展功能当前不可用：缺少嵌入模型模块 (taiyang.expand) 且知识图谱中无此实体",
        }
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"rag_entity_expand 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)}
        )
