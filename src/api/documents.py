# v1.50 统一响应格式 — 文档路由
# v1.50 Phase E: 新增文档可见性修改 API（Company Brain 权限隔离）
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pathlib import Path

router = APIRouter(tags=["文档管理"])

@router.get("/api/documents")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def documents(page: int = 1, page_size: int = 50, request: Request = None):
    """文档列表 — v1.50 统一响应格式支持"""
    from src.db.data_store import load_chunks
    from src.api.response import success, paginated, error, server_error
    try:
        chunks = load_chunks()
        seen = {}
        for c in chunks:
            fh = c.get("file_hash", "")
            if fh and fh not in seen:
                seen[fh] = {
                    "file_name": c.get("file_name", ""),
                    "file_hash": fh,
                    "category": c.get("category", ""),
                    "chunk_count": 1,
                }
            elif fh:
                seen[fh]["chunk_count"] += 1
        files = list(seen.values())
        
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            return paginated(items=files, total=len(files), page=page, page_size=page_size, message="获取文档列表成功")
        return {"files": files, "total": len(files), "page": page, "page_size": page_size}
    except Exception as e:
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            return error("获取文档列表失败", status_code=500, detail=str(e))
        return {"files": [], "total": 0, "error": str(e)}

@router.post("/api/upload")
async def upload(file: UploadFile = File(...), request: Request = None):
    """文件上传 — v1.50 统一响应格式支持"""
    from src.shaoyang.pipeline import ShaoyangPipeline
    from src.bagua.intent_bus import IntentBus
    from src.api.response import success, error, server_error
    import tempfile
    
    try:
        # 保存临时文件（使用配置的 UPLOAD_DIR）
        from src.config import UPLOAD_DIR as CONFIG_UPLOAD_DIR
        tmp_dir = Path(CONFIG_UPLOAD_DIR)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / file.filename
        
        content = await file.read()
        tmp_path.write_bytes(content)
        
        # 通过少阳处理
        intent_bus = IntentBus()
        pipeline = ShaoyangPipeline(intent_bus)
        result = await pipeline.digest(str(tmp_path), source="upload")
        
        upload_data = {
            "file_name": file.filename,
            "chunks": len(result.chunks),
            "duration_ms": result.duration_ms,
        }
        
        # 向后兼容: 默认返回旧格式 {status: "ok", file_name, chunks, duration_ms}
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            return success(data=upload_data, message="上传成功")
        # 默认旧格式 — 也加上 status 字段方便统一
        return {
            "status": "ok",
            "file_name": file.filename,
            "chunks": len(result.chunks),
            "duration_ms": result.duration_ms,
        }
    except Exception as e:
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            return error("上传失败", status_code=500, detail=str(e))
        raise HTTPException(500, f"处理失败: {str(e)}")


@router.delete("/api/documents/{file_hash}")
async def delete_document(file_hash: str, request: Request = None):
    """删除文档 — 按 file_hash 删除 chunks、向量和物理文件"""
    from src.db.data_store import load_chunks, save_chunks
    from src.db.vector_store import get_vector_store
    from src.api.response import success, error
    import hashlib
    import os
    import logging
    _logger = logging.getLogger(__name__)

    try:
        chunks = load_chunks()
        if not chunks:
            raise HTTPException(404, f"无数据，无法删除 {file_hash}")

        # 按 file_hash 精确匹配
        matching = [c for c in chunks if c.get("file_hash", "") == file_hash]
        if not matching:
            # 尝试模糊匹配文件名
            matching = [c for c in chunks if file_hash in c.get("file_name", "") or file_hash in c.get("file_hash", "")]
        if not matching:
            raise HTTPException(404, f"文档 {file_hash} 未找到")

        file_name = matching[0].get("file_name", file_hash)
        kept = [c for c in chunks if c.get("file_hash", "") != file_hash and file_hash not in c.get("file_name", "")]
        save_chunks(kept)

        # 删除向量库对应 chunks
        try:
            vs = get_vector_store()
            if vs:
                vs.delete_by_file(file_hash)
        except Exception as e:
            _logger.warning(f"向量库删除失败（非致命）: {e}")

        # 删除物理文件
        from src.config import UPLOAD_DIR as _UPLOAD_DIR
        from pathlib import Path as _Path
        upload_dir = _Path(_UPLOAD_DIR)
        if upload_dir.exists():
            for root, dirs, files in os.walk(str(upload_dir)):
                for fname in files:
                    fpath = _Path(root) / fname
                    try:
                        with open(fpath, "rb") as f:
                            content = f.read()
                        computed_hash = hashlib.sha256(content).hexdigest()[:16]
                        if computed_hash == file_hash[:16] or file_hash in str(fpath):
                            fpath.unlink()
                    except Exception as e:
                        _logger.warning(f"物理文件删除失败: {e}")

        result_data = {
            "file_name": file_name,
            "file_hash": file_hash,
            "chunks_removed": len(matching),
        }

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            return success(data=result_data, message=f"文档 {file_name} 已删除")
        return {"status": "ok", "message": f"文档 {file_name} 已删除", **result_data}

    except HTTPException:
        raise
    except Exception as e:
        _logger.exception(f"delete_document 失败: {e}")
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            return error("删除失败", status_code=500, detail=str(e))
        raise HTTPException(500, f"删除失败: {str(e)}")


# ============================================================================
# v1.50 Phase E: Company Brain 权限隔离 — 文档可见性 API
# ============================================================================

@router.put("/api/documents/{doc_id}/visibility")
async def update_document_visibility(doc_id: str, request: Request):
    """修改文档可见性

    请求体:
        {
            "visibility": "team"   // 可选: "private" | "team" | "public"
            "team_id": "team-eng"  // 可选: 指定文档所属团队（visibility=team 时建议指定）
        }

    权限要求:
      - 文档所有者可修改
      - 管理员可修改所有文档
    """
    from src.api.response import success, error, unauthorized, bad_request
    import logging
    _logger = logging.getLogger(__name__)

    try:
        body = await request.json()
        visibility = body.get("visibility", "public")
        team_id = body.get("team_id", "")

        # 验证权限字段
        from src.api.permissions import get_permission_manager, PermissionManager
        pm = get_permission_manager()

        visibility = PermissionManager.validate_visibility(visibility)

        # 获取当前用户
        user_id = getattr(request.state, "user", "anonymous") if request else "anonymous"

        # 检查写权限：需要是文档 owner 或 admin
        # 先找到文档的当前 owner
        doc_owner_id = None
        try:
            from src.db.data_store import load_chunks
            chunks = load_chunks()
            for c in chunks:
                if c.get("file_hash", "") == doc_id:
                    doc_owner_id = c.get("owner_id", "")
                    break
        except Exception:
            pass

        if not pm.check_write(user_id, doc_owner_id):
            return unauthorized("无权修改此文档的可见性", "仅文档所有者和管理员可执行此操作")

        # 更新 chunks.db 中文档的 metadata
        updated_count = 0
        try:
            from src.db.data_store import load_chunks, save_chunks
            chunks = load_chunks()
            for c in chunks:
                if c.get("file_hash", "") == doc_id:
                    c["visibility"] = visibility
                    if team_id:
                        c["team_id"] = team_id
                    if not c.get("owner_id"):
                        c["owner_id"] = user_id
                    updated_count += 1
            if updated_count > 0:
                save_chunks(chunks)
        except Exception as e:
            _logger.warning(f"chunks.db metadata 更新失败: {e}")

        # 也尝试更新向量库中的 metadata
        try:
            from src.db.vector_store import get_vector_store
            vs = get_vector_store()
            if vs:
                vs.update_metadata_by_file(doc_id, {
                    "visibility": visibility,
                    "team_id": team_id or "public",
                })
        except Exception as e:
            _logger.warning(f"向量库 metadata 更新失败（非致命）: {e}")

        result_data = {
            "doc_id": doc_id,
            "visibility": visibility,
            "team_id": team_id or "public",
            "chunks_updated": updated_count,
        }

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            return success(data=result_data, message=f"文档 {doc_id} 可见性已更新为 {visibility}")
        return {"status": "ok", **result_data, "message": f"文档可见性已更新为 {visibility}"}

    except Exception as e:
        _logger.exception(f"update_document_visibility 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)}
        )
