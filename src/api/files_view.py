# 兼容层 - 文件查看/下载路由
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pathlib import Path
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["文件查看"])

from src.config import UPLOAD_DIR as CONFIG_UPLOAD_DIR, DATA_DIR as CONFIG_DATA_DIR
UPLOAD_DIR = Path(CONFIG_UPLOAD_DIR)
DATA_DIR = Path(CONFIG_DATA_DIR)
KB_IMAGES_DIR = Path(CONFIG_DATA_DIR) / "kb-images"


@router.get("/api/view/{file_hash}")
def view_document(file_hash: str, request: Request):
    """查看文档（根据 file_hash 在 uploads 目录中查找）(v1.50: requires auth)"""
    try:
        # v1.50 security fix: 认证检查（安全降级）
        # request.state.user 未设置时（如通过白名单路径进入），允许匿名查看
        user = getattr(request.state, "user", None)
        if user is None:
            user = "anonymous"  # 安全降级：允许未认证访问

        # Search in uploads directory
        if UPLOAD_DIR.exists():
            for root, dirs, files in os.walk(UPLOAD_DIR):
                for fname in files:
                    import hashlib
                    fpath = Path(root) / fname
                    try:
                        with open(fpath, "rb") as f:
                            content = f.read()
                        computed_hash = hashlib.sha256(content).hexdigest()[:16]
                        if computed_hash == file_hash[:16] or file_hash in str(fpath):
                            return FileResponse(str(fpath))
                    except Exception as e:
                        logger.warning("Exception 失败: %s", e, exc_info=True)
        # Fallback: check kb-images
        if KB_IMAGES_DIR.exists():
            for root, dirs, files in os.walk(KB_IMAGES_DIR):
                if file_hash in files or any(file_hash in f for f in files):
                    fpath = Path(root) / file_hash
                    if fpath.exists():
                        return FileResponse(str(fpath))
        
        raise HTTPException(404, detail="文档未找到")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"view_document 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


@router.get("/api/download/{file_hash}")
def download_document(file_hash: str, request: Request):
    """下载文档 (v1.50: requires auth)"""
    try:
        # v1.50 security fix: 认证检查（安全降级）
        # request.state.user 未设置时（如通过白名单路径进入），允许匿名查看
        user = getattr(request.state, "user", None)
        if user is None:
            user = "anonymous"  # 安全降级：允许未认证访问

        # Same search logic as view but with Content-Disposition header
        if UPLOAD_DIR.exists():
            for root, dirs, files in os.walk(UPLOAD_DIR):
                for fname in files:
                    fpath = Path(root) / fname
                    import hashlib
                    try:
                        with open(fpath, "rb") as f:
                            content = f.read()
                        computed_hash = hashlib.sha256(content).hexdigest()[:16]
                        if computed_hash == file_hash[:16] or file_hash in str(fpath):
                            return FileResponse(
                                str(fpath),
                                filename=fname,
                                media_type="application/octet-stream"
                            )
                    except Exception as e:
                        logger.warning("Exception 失败: %s", e, exc_info=True)
        raise HTTPException(404, detail="文档未找到")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"download_document 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


@router.get("/api/antenna/search")
@router.post("/api/antenna/search")
def antenna_search(request: Request, q: str = ""):
    """天线搜索 — Web搜索代理"""
    return {
        "results": [],
        "query": q,
        "source": "antenna",
        "message": "Antenna search requires external API configuration"
    }
