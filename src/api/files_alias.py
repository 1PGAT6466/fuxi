"""
files_alias.py - /api/files 路由别名
将 documents 和 upload 端点映射到 /api/files 前缀
"""
import asyncio
from fastapi import APIRouter, HTTPException, Request
from pathlib import Path
import os
import hashlib
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["文件管理别名"])

from src.config import UPLOAD_DIR as CONFIG_UPLOAD_DIR

UPLOAD_DIR = Path(CONFIG_UPLOAD_DIR)


@router.get("/api/files")
async def files_list(request: Request, page: int = 1, page_size: int = 50):
    """文件列表 - 别名 /api/documents"""
    from src.api.documents import documents
    return await documents(request=request, page=page, page_size=page_size)


@router.post("/api/files/upload")
async def files_upload(request: Request):
    """文件上传 - 别名 /api/upload"""
    from src.api.documents import upload
    form = await request.form()
    file = form.get("file")
    if file is None:
        raise HTTPException(400, "缺少 file 字段")
    return await upload(file=file, request=request)


@router.delete("/api/files/{file_id}")
async def files_delete(file_id: str, request: Request):
    """删除文件 - 按 file_hash 删除文档及关联 chunks"""
    try:
        from src.db.data_store import load_chunks, save_chunks
        from src.db.vector_store import get_vector_store

        chunks = await asyncio.to_thread(load_chunks)
        if not chunks:
            raise HTTPException(404, f"无数据，无法删除 {file_id}")

        matching = [c for c in chunks if c.get("file_hash", "") == file_id]
        if not matching:
            matching = [c for c in chunks if file_id in c.get("file_name", "")]
        if not matching:
            raise HTTPException(404, f"文件 {file_id} 未找到")

        kept = [c for c in chunks if c.get("file_hash", "") != file_id]
        await asyncio.to_thread(save_chunks, kept)

        try:
            vs = get_vector_store()
            if vs:
                vs.delete_by_file(file_id)
        except (OSError, RuntimeError) as e:
            logger.warning(f"向量库删除失败(非致命): {e}")

        return {"status": "success", "message": f"文件 {file_id} 已删除"}
    except HTTPException:
        raise
    except (OSError, IOError, ValueError) as e:
        logger.exception(f"删除文件失败: {e}")
        return HTTPException(500, str(e))
