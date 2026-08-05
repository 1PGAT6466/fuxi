import asyncio

"""
v1.44 Phase 1 Fix — 知识库(KB)检索路由
提供 KB 搜索 + KB 文档列表端点
"""
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["知识库"])


class KBSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    mode: str = "semantic"

    @field_validator("top_k")
    @classmethod
    def validate_top_k(cls, v: int) -> int:
        """v1.44 安全修复: top_k 上限验证"""
        from src.services.prompt_guard import clamp_top_k

        return clamp_top_k(v)


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
                    results.append(
                        {
                            "id": r.get("id", ""),
                            "text": r.get("text", r.get("content", "")),
                            "score": r.get("score", r.get("distance", 0)),
                            "source": r.get("metadata", {}).get("source", r.get("file_name", "")),
                            "metadata": r.get("metadata", {}),
                        }
                    )
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
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


@router.get("/api/kb/documents")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def kb_documents(request: Request = None):
    """知识库文档列表"""
    try:
        documents = []
        try:
            from src.db.data_store import load_chunks

            chunks = await asyncio.to_thread(load_chunks)
            seen = set()
            for c in chunks:
                fhash = c.get("file_hash", "")
                if fhash and fhash not in seen:
                    seen.add(fhash)
                    documents.append(
                        {
                            "id": fhash,
                            "name": c.get("file_name", ""),
                            "category": c.get("category", ""),
                            "chunk_count": sum(1 for cc in chunks if cc.get("file_hash") == fhash),
                            "created_at": c.get("created_at", ""),
                        }
                    )
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"load_chunks 失败: {e}")

        return {
            "documents": documents,
            "total": len(documents),
        }
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"kb_documents 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


@router.get("/api/kb/files")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def kb_files(request: Request = None):
    """知识库文件列表 — kb/documents 的别名端点"""
    return await kb_documents(request)


@router.get("/api/kb/collections")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def kb_collections(request: Request = None):
    """知识库集合列表 — 按 category 聚合

    返回每个 category 视为一个 "集合"，包含该分类下的文件数和 chunk 数。
    """
    try:
        from src.api.response import error, success

        collections = []
        try:
            from src.db.data_store import load_chunks

            chunks = await asyncio.to_thread(load_chunks) or []
            if chunks:
                cat_map: dict = {}
                for c in chunks:
                    cat = c.get("category", "未分类")
                    if cat not in cat_map:
                        cat_map[cat] = {"files": set(), "chunk_count": 0}
                    cat_map[cat]["chunk_count"] += 1
                    fhash = c.get("file_hash", "")
                    if fhash:
                        cat_map[cat]["files"].add(fhash)
                for cat_name, info in cat_map.items():
                    collections.append(
                        {
                            "id": cat_name,
                            "name": cat_name,
                            "document_count": len(info["files"]),
                            "chunk_count": info["chunk_count"],
                        }
                    )
        except Exception as e:
            logger.warning(f"kb_collections 读取失败: {e}")

        # ChromaDB 集合信息
        chroma_info = {}
        try:
            from src.db.vector_store import get_vector_store

            vs = get_vector_store()
            if vs and hasattr(vs, "_client"):
                for coll in vs._client.list_collections():
                    try:
                        c = vs._client.get_collection(coll) if isinstance(coll, str) else coll
                        cname = c.name if hasattr(c, "name") else str(coll)
                        chroma_info[cname] = c.count()
                    except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                        pass
        except Exception as e:
            logger.debug(f"ChromaDB 集合列举跳过: {e}")

        return success(
            data={
                "collections": collections,
                "total": len(collections),
                "chromadb_collections": chroma_info,
            },
            message="知识库集合列表",
        )
    except Exception as e:
        logger.exception(f"kb_collections 失败: {e}")
        return JSONResponse(
            status_code=500, content={"status": "error", "message": "获取知识库集合失败", "detail": str(e)}
        )


@router.get("/api/kb/collections/{collection_id}")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def kb_collection_detail(collection_id: str, request: Request = None):
    """集合详情 — 按 category 名称获取"""
    try:
        from src.api.response import error, success

        try:
            from src.db.data_store import load_chunks

            chunks = await asyncio.to_thread(load_chunks) or []
            matched = [c for c in chunks if c.get("category", "未分类") == collection_id]
            if not matched:
                return error(f"集合 '{collection_id}' 不存在或为空", status_code=404)

            seen_files = set()
            for c in matched:
                fhash = c.get("file_hash", "")
                if fhash:
                    seen_files.add(fhash)

            return success(
                data={
                    "id": collection_id,
                    "name": collection_id,
                    "document_count": len(seen_files),
                    "chunk_count": len(matched),
                    "documents": [
                        {
                            "id": fh,
                            "name": next((c.get("file_name", "") for c in matched if c.get("file_hash") == fh), ""),
                        }
                        for fh in seen_files
                    ],
                },
                message="集合详情",
            )
        except Exception as e:
            logger.warning(f"kb_collection_detail 读取失败: {e}")
            return error(f"获取集合详情失败: {e}", status_code=500)
    except Exception as e:
        logger.exception(f"kb_collection_detail 失败: {e}")
        return JSONResponse(
            status_code=500, content={"status": "error", "message": "获取集合详情失败", "detail": str(e)}
        )


@router.get("/api/kb/stats")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def kb_stats(request: Request = None):
    """知识库统计信息"""
    try:
        from src.api.response import success as resp_success

        stats = {"total_chunks": 0, "total_files": 0, "categories": {}, "chromadb_vectors": 0}
        try:
            from src.db.data_store import load_chunks

            chunks = await asyncio.to_thread(load_chunks)
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
        except Exception as e:
            logger.warning(f"load_chunks 统计失败: {e}")

        try:
            from src.db.vector_store import get_vector_store

            vs = get_vector_store()
            if vs:
                stats["chromadb_vectors"] = vs.count
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass

        return resp_success(data=stats, message="知识库统计")
    except Exception as e:
        logger.exception(f"kb_stats 失败: {e}")
        return JSONResponse(
            status_code=500, content={"status": "error", "message": "获取知识库统计失败", "detail": str(e)}
        )
