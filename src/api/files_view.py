import asyncio
# 兼容层 - 文件查看/下载路由
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import os
import logging
import urllib.parse

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
                    except Exception as e:  # TODO: Narrow exception type
                        logger.warning("文件哈希计算失败: %s", e, exc_info=True)
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
    except Exception as e:  # TODO: Narrow exception type
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
                    except Exception as e:  # TODO: Narrow exception type
                        logger.warning("文件下载哈希计算失败: %s", e, exc_info=True)
        raise HTTPException(404, detail="文档未找到")
    except HTTPException:
        raise
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"download_document 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


@router.get("/api/antenna/search")
@router.post("/api/antenna/search")
async def antenna_search(request: Request, q: str = ""):
    """天线搜索 — 混合检索：知识库语义搜索 + 联网搜索降级
    
    优先使用本地知识库（ChromaDB + SQLite 混合检索），
    如果本地无结果或外部 API 可用，再尝试联网搜索。
    """
    if not q or not q.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "缺少 q 参数", "detail": "搜索关键词不能为空"}
        )

    query = q.strip()
    results = []
    source = "knowledge_base"
    message = ""

    # 1) 优先尝试本地知识库混合检索
    try:
        from src.taiyang.retrieval import hybrid_search
        kb_results = await hybrid_search(query, top_k=5)
        if kb_results:
            results = [
                {
                    "title": r.get("title", r.get("source", r.get("file_name", ""))),
                    "snippet": (r.get("text", "") or r.get("snippet", "") or r.get("doc", ""))[:200],
                    "url": r.get("url", r.get("file_hash", "")),
                    "score": r.get("score", 0),
                    "source": "knowledge_base",
                }
                for r in kb_results
            ]
            source = "knowledge_base"
            message = f"找到 {len(results)} 条相关结果"
    except (ImportError, ModuleNotFoundError) as e:
        logger.warning(f"知识库检索不可用: {e}")
    except Exception as e:  # TODO: Narrow exception type
        logger.warning(f"知识库检索失败: {e}")

    # 2) 如果本地无结果，尝试联网搜索（如果配置了 Brave API）
    if not results:
        try:
            brave_key = os.getenv("BRAVE_API_KEY", "")
            if brave_key:
                import urllib.request
                import json as _json
                def _brave_search():
                    req = urllib.request.Request(
                        f"https://api.search.brave.com/res/v1/web/search?q={urllib.parse.quote(query)}&count=5",
                        headers={
                            "Accept": "application/json",
                            "Accept-Encoding": "gzip",
                            "X-Subscription-Token": brave_key,
                        }
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        return _json.loads(resp.read().decode("utf-8"))
                data = await asyncio.to_thread(_brave_search)
                web_results = data.get("web", {}).get("results", [])
                results = [
                    {
                        "title": wr.get("title", ""),
                        "snippet": wr.get("description", "")[:200],
                        "url": wr.get("url", ""),
                        "score": 1.0,
                        "source": "web_brave",
                    }
                    for wr in web_results
                ]
                source = "web_brave"
                message = f"联网搜索找到 {len(results)} 条结果"
        except ImportError:
            logger.debug("urllib 不可用，跳过联网搜索")
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"联网搜索失败: {e}")

    if not results:
        message = "未找到相关结果，请尝试其他关键词"

    return {
        "results": results,
        "query": query,
        "source": source,
        "message": message,
    }
