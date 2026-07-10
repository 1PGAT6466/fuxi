"""
P0 修复：/api/files 路由别名 → 前端 Files.vue 调用 /api/files/*
将 documents 和 upload 端点的 /api/documents 和 /api/upload 映射到 /api/files 前缀。
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

# ── GET /api/files ── 文件列表（转发到 documents 逻辑）
@router.get("/api/files")
async def files_list(request: Request, page: int = 1, page_size: int = 50):
    """文件列表 — 别名 /api/documents"""
    from src.api.documents import documents
    return await documents(request=request, page=page, page_size=page_size)


# ── POST /api/files/upload ── 文件上传（转发到 upload 逻辑） ──
@router.post("/api/files/upload")
async def files_upload(request: Request):
    """文件上传 — 别名 /api/upload"""
    from fastapi import File as FastAPIFile
    # 尝试读取 multipart form
    from src.api.documents import upload
    form = await request.form()
    file = form.get("file")
    if file is None:
        raise HTTPException(400, "缺少 file 字段")
    return await upload(file=file, request=request)


# ── DELETE /api/files/{id} ── 删除文件 ──
@router.delete("/api/files/{file_id}")
async def files_delete(file_id: str, request: Request):
    """删除文件 — 按 file_hash 删除文档及关联 chunks"""
    try:
        from src.db.data_store import load_chunks, save_chunks
        from src.db.vector_store import get_vector_store

        chunks = await asyncio.to_thread(load_chunks)
        if not chunks:
            raise HTTPException(404, f"无数据，无法删除 {file_id}")

        # 按 file_hash 匹配
        matching = [c for c in chunks if c.get("file_hash", "") == file_id]
        if not matching:
            # 尝试模糊匹配文件名
            matching = [c for c in chunks if file_id in c.get("file_name", "") or file_id in c.get("file_hash", "")]
        if not matching:
            raise HTTPException(404, f"文件 {file_id} 未找到")

        file_name = matching[0].get("file_name", file_id)
        kept = [c for c in chunks if c.get("file_hash", "") != file_id and file_id not in c.get("file_name", "")]
        await asyncio.to_thread(save_chunks, kept)

        # 删除向量库对应 chunks
        try:
            vs = get_vector_store()
            if vs:
                vs.delete_by_file(file_id)
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"向量库删除失败（非致命）: {e}")

        # 删除物理文件（异步化避免阻塞事件循环）
        if UPLOAD_DIR.exists():
            def _delete_physical_files():
                for root, dirs, files in os.walk(str(UPLOAD_DIR)):
                    for fname in files:
                        fpath = Path(root) / fname
                        try:
                            content = await asyncio.to_thread(lambda: open(fpath, "rb").read())
                            computed_hash = hashlib.sha256(content).hexdigest()[:16]
                            if computed_hash == file_id[:16] or file_id in str(fpath):
                                fpath.unlink()
                                logger.info(f"[files_alias] 物理文件已删除: {fpath}")
                        except Exception as e:  # TODO: Narrow exception type
                            logger.warning(f"物理文件删除失败: {e}")
            await asyncio.to_thread(_delete_physical_files)

        return {
            "status": "ok",
            "message": f"文件 {file_name} 已删除",
            "chunks_removed": len(matching),
        }
    except HTTPException:
        raise
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"files_delete 失败: {e}")
        raise HTTPException(500, f"删除失败: {str(e)}")


# ── GET /api/files/{id}/download ── 文件下载 ──
@router.get("/api/files/{file_id}/download")
async def files_download(file_id: str, request: Request):
    """文件下载 — 别名 /api/download/{file_hash}"""
    from src.api.files_view import download_document
    return await download_document(file_hash=file_id, request=request)


# ── v1.44 Phase 1 Fix: PUT /api/files/{file_id} ── 更新文件元数据 ──
@router.put("/api/files/{file_id}")
async def files_update(file_id: str, request: Request):
    """更新文件元数据"""
    try:
        body = await request.json()

        from src.db.data_store import load_chunks, save_chunks
        chunks = await asyncio.to_thread(load_chunks)
        if not chunks:
            raise HTTPException(404, f"文件 {file_id} 未找到")

        # 匹配文件
        matching = [c for c in chunks if c.get("file_hash", "") == file_id]
        if not matching:
            matching = [c for c in chunks if file_id in c.get("file_name", "")]
        if not matching:
            raise HTTPException(404, f"文件 {file_id} 未找到")

        # 更新匹配的 chunks 中允许的字段
        updated_count = 0
        for c in matching:
            changed = False
            for key in ("file_name", "category", "tags"):
                if key in body:
                    c[key] = body[key]
                    changed = True
            if changed:
                updated_count += 1

        if updated_count > 0:
            await asyncio.to_thread(save_chunks, chunks)

        return {
            "ok": True,
            "message": f"文件 {file_id} 元数据已更新",
            "chunks_updated": updated_count,
        }
    except HTTPException:
        raise
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"files_update 失败: {e}")
        raise HTTPException(500, f"更新失败: {str(e)}")
