"""
routers/metadata.py — 元数据中心路由
提供元数据文件的搜索、列表、下载、查看功能
元数据文件：CAD/压缩包/二进制/多媒体等无法提取文本结构的文件
"""
import logging; logger = logging.getLogger(__name__)
import os, hashlib
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import FileResponse, HTMLResponse, Response, JSONResponse
from src.db.data_store import get_store

router = APIRouter(tags=["元数据中心"])

# 元数据模式标记字段
META_FLAG = "metadata_only"
ADMIN_TOKEN = os.environ.get("KB_ADMIN_TOKEN", "")


def _check_admin_token(request: Request):
    token = request.headers.get("x-admin-token", "")
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="需要管理令牌")


@router.get("/api/metadata")
async def metadata_files(
    request: Request,
    page: int = 1,
    page_size: int = 50,
    search: str = "",
    category: str = "",
):
    """
    元数据文件列表（支持搜索和分页）
    - 搜索：按文件名模糊匹配
    - 分类过滤：按 category 字段
    - 分页：默认 50 条/页
    """
    store = get_store()
    all_chunks = store.get_all() if hasattr(store, 'get_all') else []

    # 收集元数据文件
    seen = {}
    for c in all_chunks:
        meta_flag = c.get(META_FLAG, False)
        # 通过 text 内容判断是否为元数据（[元数据文件] / [CAD/工程文件] 等前缀）
        text = c.get("text", "")
        is_meta = (
            meta_flag or
            text.startswith("[元数据文件]") or
            text.startswith("[CAD/工程文件]") or
            text.startswith("[无解析器]") or
            text.startswith("[内容为空]") or
            text.startswith("[元数据")
        )
        if not is_meta:
            continue

        fh = c.get("file_hash", "")
        ct = c.get("created_at", "")
        cat = c.get("category", "元数据")
        fn = c.get("file_name", "")

        # 搜索过滤
        if search and search.lower() not in fn.lower():
            continue
        if category and category != cat:
            continue

        if fh and fh not in seen:
            ext = (fn or ".").split(".")[-1].lower() if "." in fn else ""
            size_mb = 0
            # 尝试从 text 中提取大小信息
            import re
            size_match = re.search(r"大小:\s*([\d.]+)MB", text)
            if size_match:
                size_mb = float(size_match.group(1))
            seen[fh] = {
                "file_name": fn,
                "file_hash": fh,
                "category": cat,
                "chunk_count": 1,
                "created_at": ct,
                "file_type": ext,
                "size_mb": round(size_mb, 1),
            }
        elif fh:
            seen[fh]["chunk_count"] += 1
            if ct > seen[fh].get("created_at", ""):
                seen[fh]["created_at"] = ct

    all_files = list(seen.values())
    all_files.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    total = len(all_files)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "files": all_files[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get("/api/metadata/categories")
async def metadata_categories():
    """返回所有元数据文件的分类统计"""
    store = get_store()
    all_chunks = store.get_all() if hasattr(store, 'get_all') else []

    cat_count = {}
    seen_hashes = set()
    for c in all_chunks:
        meta_flag = c.get(META_FLAG, False)
        text = c.get("text", "")
        is_meta = (
            meta_flag or
            text.startswith("[元数据文件]") or
            text.startswith("[CAD/工程文件]") or
            text.startswith("[无解析器]") or
            text.startswith("[内容为空]") or
            text.startswith("[元数据")
        )
        if not is_meta:
            continue

        fh = c.get("file_hash", "")
        if fh in seen_hashes:
            continue
        seen_hashes.add(fh)

        cat = c.get("category", "元数据")
        cat_count[cat] = cat_count.get(cat, 0) + 1

    return {"categories": cat_count, "total": len(seen_hashes)}


@router.get("/api/metadata/view/{file_hash}")
async def metadata_view(file_hash: str):
    """获取元数据文件的详细信息"""
    store = get_store()
    chunks = store.get_by_hash(file_hash)
    if not chunks:
        # 在 load_chunks 中查找
        from src.db.data_store import load_chunks
        chunks = [c for c in load_chunks() if c.get("file_hash") == file_hash]
    if not chunks:
        raise HTTPException(status_code=404, detail="文件不存在")

    c = chunks[0]
    file_name = c.get("file_name", "")
    ext = (file_name or ".").split(".")[-1].lower()
    text = c.get("text", "")

    # 从 text 提取元数据信息
    import re
    size_mb = 0
    size_match = re.search(r"大小:\s*([\d.]+)MB", text)
    if size_match:
        size_mb = float(size_match.group(1))

    return {
        "file_name": file_name,
        "file_hash": file_hash,
        "category": c.get("category", "元数据"),
        "created_at": c.get("created_at", ""),
        "file_type": ext,
        "size_mb": round(size_mb, 1),
        "chunk_count": len(chunks),
        "format": ext.upper(),
        "can_download": True,
        "can_search": False,
        "raw_text_preview": text[:500],
    }
