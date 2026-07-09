"""
v1.44 Phase 1 Fix — 知识库(KB)检索路由
提供 KB 搜索 + KB 文档列表端点
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["知识库"])


class KBSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    mode: str = "semantic"


@router.post("/api/kb/search")
async def kb_search(body: KBSearchRequest, request: Request = None):
    """知识库搜索 — 搜索文档块

    返回 {results, total} 格式。
    调用 ChromaDB 向量检索 + SQLite 全文搜索。
    """
    try:
        results = []

        # 尝试使用 taiyang retrieval
        try:
            from src.taiyang.retrieval import search_chunks
            results = search_chunks(
                query=body.query,
                top_k=body.top_k,
                mode=body.mode,
            )
            return {
                "results": results,
                "total": len(results),
            }
        except ImportError:
            pass
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"retrieval.search_chunks 失败: {e}")

        # 回退：直接使用 ChromaDB
        try:
            from src.db.vector_store import get_vector_store
            vs = get_vector_store()
            if vs:
                raw = vs.search(body.query, top_k=body.top_k)
                for r in raw:
                    results.append({
                        "id": r.get("id", ""),
                        "text": r.get("text", r.get("content", "")),
                        "score": r.get("score", r.get("distance", 0)),
                        "source": r.get("metadata", {}).get("source", r.get("file_name", "")),
                        "metadata": r.get("metadata", {}),
                    })
                return {"results": results, "total": len(results)}
        except Exception as e2:  # TODO: Narrow exception type
            logger.warning(f"vector_store 回退失败: {e2}")

        # 最终回退
        return {
            "results": [],
            "total": 0,
        }
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"kb_search 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)}
        )


@router.get("/api/kb/documents")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def kb_documents(request: Request = None):
    """知识库文档列表"""
    try:
        documents = []
        try:
            from src.db.data_store import load_chunks
            chunks = load_chunks()
            seen = set()
            for c in chunks:
                fhash = c.get("file_hash", "")
                if fhash and fhash not in seen:
                    seen.add(fhash)
                    documents.append({
                        "id": fhash,
                        "name": c.get("file_name", ""),
                        "category": c.get("category", ""),
                        "chunk_count": sum(1 for cc in chunks if cc.get("file_hash") == fhash),
                        "created_at": c.get("created_at", ""),
                    })
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"load_chunks 失败: {e}")

        return {
            "documents": documents,
            "total": len(documents),
        }
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"kb_documents 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)}
        )


@router.get("/api/kb/files")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def kb_files(request: Request = None):
    """知识库文件列表 — kb/documents 的别名端点"""
    return await kb_documents(request)


@router.get("/api/kb/stats")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def kb_stats(request: Request = None):
    """知识库统计信息"""
    try:
        stats = {"total_chunks": 0, "total_files": 0, "categories": {}}
        try:
            from src.db.data_store import load_chunks
            chunks = load_chunks()
            if chunks:
                stats["total_chunks"] = len(chunks)
                seen_files = set()
                categories = {}
                for c in chunks:
                    fhash = c.get("file_hash", "")
                    if fhash:
                        seen_files.add(fhash)
                    cat = c.get("category", "未分类")
                    categories[cat] = categories.get(cat, 0) + 1
                stats["total_files"] = len(seen_files)
                stats["categories"] = categories
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"load_chunks 统计失败: {e}")

        return stats
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"kb_stats 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)}
        )
