"""
文件管理统一 API — 伏羲 v1.50
==============================
统一 /api/files、/api/documents、/api/kb/files 三套端点

端点：
  GET  /api/files          — 文件列表（统一入口）
  POST /api/files/upload   — 文件上传
  DELETE /api/files/{id}   — 删除文件
  GET  /api/files/{id}     — 获取文件详情
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["文件管理"])

# ============ 统一文件列表 ============


@router.get("/api/files")
async def files_list(
    request: Request = None,
    page: int = 1,
    page_size: int = 50,
    category: Optional[str] = None,
    format: Optional[str] = None,
):
    """统一文件列表接口

    整合 /api/documents 和 /api/kb/files 的功能
    支持分页和分类过滤
    """
    from src.api.response import paginated, success
    from src.db.data_store import load_chunks

    try:
        chunks = await asyncio.to_thread(load_chunks)
        if not chunks:
            chunks = []

        # 按 file_hash 聚合
        seen = {}
        for c in chunks:
            fh = c.get("file_hash", "")
            if not fh:
                continue

            # 分类过滤
            if category and c.get("category", "") != category:
                continue

            if fh not in seen:
                seen[fh] = {
                    "id": fh,
                    "file_name": c.get("file_name", ""),
                    "file_hash": fh,
                    "category": c.get("category", ""),
                    "chunk_count": 1,
                    "created_at": c.get("created_at", ""),
                    "owner_id": c.get("owner_id", ""),
                    "visibility": c.get("visibility", "public"),
                }
            else:
                seen[fh]["chunk_count"] += 1

        files = list(seen.values())
        total = len(files)

        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        paginated_files = files[start:end]

        # 响应格式
        _wants_v2 = format == "v2" or (request and request.headers.get("X-API-Format", "").lower() == "v2")

        if _wants_v2:
            return paginated(
                items=paginated_files, total=total, page=page, page_size=page_size, message="获取文件列表成功"
            )

        return {
            "files": paginated_files,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    except Exception as e:
        logger.exception(f"files_list 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


# ============ 文件上传 ============


@router.post("/api/files/upload")
async def files_upload(request: Request):
    """文件上传 — 统一入口

    整合 /api/upload 功能
    """
    from src.api.documents import upload

    try:
        form = await request.form()
        file = form.get("file")
        if file is None:
            raise HTTPException(400, "缺少 file 字段")

        return await upload(file=file, request=request)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"files_upload 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "上传失败", "detail": str(e)})


# ============ 删除文件 ============


@router.delete("/api/files/{file_id}")
async def files_delete(file_id: str, request: Request = None):
    """删除文件 — 统一入口

    整合 /api/documents/{file_hash} 和 /api/files/{file_id} 的删除功能
    """
    from src.api.documents import delete_document

    try:
        return await delete_document(file_hash=file_id, request=request)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"files_delete 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "删除失败", "detail": str(e)})


# ============ 文件详情 ============


@router.get("/api/files/{file_id}")
async def files_detail(file_id: str, request: Request = None):
    """获取文件详情"""
    from src.db.data_store import load_chunks

    try:
        chunks = await asyncio.to_thread(load_chunks)
        if not chunks:
            raise HTTPException(404, "无数据")

        # 查找匹配的文件
        matching = [c for c in chunks if c.get("file_hash", "") == file_id]
        if not matching:
            # 尝试模糊匹配
            matching = [c for c in chunks if file_id in c.get("file_name", "")]

        if not matching:
            raise HTTPException(404, f"文件 {file_id} 未找到")

        # 构建文件详情
        first = matching[0]
        file_detail = {
            "id": first.get("file_hash", file_id),
            "file_name": first.get("file_name", ""),
            "file_hash": first.get("file_hash", ""),
            "category": first.get("category", ""),
            "chunk_count": len(matching),
            "created_at": first.get("created_at", ""),
            "owner_id": first.get("owner_id", ""),
            "visibility": first.get("visibility", "public"),
            "chunks": [
                {
                    "id": c.get("id", ""),
                    "text": c.get("text", "")[:500],  # 截断过长的文本
                    "metadata": c.get("metadata", {}),
                }
                for c in matching[:50]  # 最多返回 50 个 chunks
            ],
        }

        _wants_v2 = request and (
            request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2"
        )

        if _wants_v2:
            from src.api.response import success

            return success(data=file_detail, message="获取文件详情成功")

        return file_detail

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"files_detail 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})
