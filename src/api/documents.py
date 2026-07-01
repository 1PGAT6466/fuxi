"""
routers/documents.py — 文档管理路由（v10.0）
负责：/api/documents, /api/raw-store, /api/ingest-batch, /api/reindex,
      /api/view, /api/reset, 文档上传/删除/查看
"""
import logging; logger = logging.getLogger(__name__)
from src.core.http_client import fetch, post
import os
import hashlib as hl_dl, json, hashlib, time, asyncio, urllib.request
from datetime import datetime, timezone
from pathlib import Path
import asyncio
from collections import deque

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Query
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse

from src.config import (
    DATA_DIR, UPLOAD_DIR, MAX_FILE_MB, ALLOWED_EXTENSIONS,
    SENSITIVE_PATTERNS, ADMIN_TOKEN, STATIC_DIR, LOADER_URL
)
from src.db.data_store import load_chunks, log_search, invalidate_chunk_cache
from src.services.ingest import _sanitize_filename, _classify_text, _audit_text, _clean_text, _generate_summary, _smart_chunk, _extract_text, _compute_file_hash
from src.category_registry import match_category, normalize_category
from src.db.memory_store import get_store
from src.db.vector_store import get_vector_store, embed_texts
from pydantic import BaseModel

# ============ 后台向量化队列（v10.1 修复） ============
import asyncio
from collections import deque
import logging
from src.core.http_client import fetch, post
_logger = logging.getLogger(__name__)

_vector_queue = deque()
_vector_lock = asyncio.Lock()
_vector_task = None

async def _background_vectorizer():
    """后台批量向量化，每 3 秒处理一批"""
    global _vector_queue
    while True:
        try:
            batch = []
            async with _vector_lock:
                while _vector_queue:
                    batch.extend(_vector_queue.popleft())
            
            if batch:
                _logger.info(f'[vectorizer] processing {len(batch)} chunks...')
                await _index_vectors_async(batch)
                _logger.info(f'[vectorizer] done ({len(batch)} chunks)')
            
            await asyncio.sleep(3)
        except Exception as e:
            logger.exception("Exception in routers/documents.py")
            _logger.error(f'[vectorizer] error: {e}')
            await asyncio.sleep(10)

def _start_background_vectorizer():
    """启动后台向量化任务（幂等）"""
    global _vector_task
    try:
        loop = asyncio.get_event_loop()
        if _vector_task is None or _vector_task.done():
            _vector_task = loop.create_task(_background_vectorizer())
            _logger.info('[vectorizer] background task started')
    except RuntimeError:
        pass  # event loop not ready yet

router = APIRouter(tags=["文档管理"])


# ============ 数据模型 ============

class IngestBatchRequest(BaseModel):
    file_name: str
    file_hash: str = ""
    category: str = "未分类"
    chunks: list = []
    md_path: str = ""
    loader_path: str = ""


# ============ 辅助函数 ============

def _check_admin_token(request: Request):
    token = request.headers.get("x-admin-token", "")
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="需要管理令牌")


def _audit_wrapper(text: str):
    return _audit_text(text, SENSITIVE_PATTERNS)


# ============ 文档列表 ============

@router.get("/api/documents")
async def documents(page: int = 1, page_size: int = 50):
    """去重后的文件列表"""
    seen = {}
    for c in load_chunks():
        fh = c.get("file_hash", "")
        ct = c.get("created_at", "")
        if fh and fh not in seen:
            seen[fh] = {
                "file_name": c.get("file_name", ""),
                "file_hash": fh,
                "category": c.get("category", ""),
                "chunk_count": 1,
                "created_at": ct,
                "file_type": (c.get("file_name", "") or ".").split(".")[-1].lower() if c.get("file_name") else "",
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
        "files": all_files[start:end], "total": total,
        "page": page, "page_size": page_size, "total_pages": total_pages,
    }


@router.get("/api/documents/{file_hash}")
async def document(file_hash: str):
    """根据 file_hash 获取文档 chunks"""
    docs = get_store().get_by_hash(file_hash)
    if not docs:
        docs = [c for c in load_chunks() if c.get("file_hash") == file_hash]
    if not docs:
        raise HTTPException(status_code=404, detail=f"文档 {file_hash} 不存在")


# ===== 原始文件下载 =====
from fastapi.responses import FileResponse

@router.get("/api/download/{file_hash}")
async def download_file(file_hash: str):
    """下载原始文件 — 通过装载机代理"""
    import sqlite3, urllib.request, urllib.parse
    
    from src.core.db import connect
    file_name = None
    
    try:
        with connect("chunks") as db:
            row = db.execute(
                "SELECT file_name FROM chunks WHERE file_hash LIKE ? AND status='active' ORDER BY LENGTH(file_name) DESC LIMIT 1",
                (file_hash[:16] + "%",)
            ).fetchone()
            if not row and len(file_hash) > 16:
                row = db.execute(
                    "SELECT file_name FROM chunks WHERE file_hash=? AND status='active' ORDER BY LENGTH(file_name) DESC LIMIT 1",
                    (file_hash,)
                ).fetchone()
            if row:
                file_name = row[0].replace("\\", "/")
    except Exception as e:
        logger.warning(f"DB lookup failed: {e}")
    
    if file_name:
        # Try direct loader proxy
        try:
            loader_url = LOADER_URL + "/api/download?path=" + urllib.parse.quote(file_name)
            data = await fetch(loader_url, timeout=15)
            if data and len(data) > 50:
                return Response(content=data, media_type="application/octet-stream")
        except Exception as e:
            logger.warning(f"Loader direct failed: {e}")
        
        # Fallback: search loader files API by filename
        try:
            simple_name = file_name.split("/")[-1]
            import requests, json as json_mod
            r = requests.get(LOADER_URL + "/api/files", timeout=10)
            for f in r.json().get("files", []):
                if f.get("name", "") == simple_name:
                    lp = f.get("path", "").replace("\\", "/")
                    if lp:
                        loader_url = LOADER_URL + "/api/download?path=" + urllib.parse.quote(lp)
                        data = await fetch(loader_url, timeout=30)
                        if data and len(data) > 50:
                            return Response(content=data, media_type="application/octet-stream")
        except Exception as e:
            logger.warning(f"Loader fallback failed: {e}")
    
    raise HTTPException(status_code=404, detail=f"文件不存在: {file_hash}")

@router.delete("/api/documents/{file_hash}")
async def delete_document(file_hash: str):
    """删除文档"""
    count = get_store().delete_by_hash(file_hash)
    invalidate_chunk_cache()
    return {"deleted": True, "removed_chunks": count}


# ============ 文档查看 ============

@router.get("/api/view/{file_hash}")
async def view_file(file_hash: str):
    """查看原始文档 - PDF优先返回原文件流，保留图片/表格/版式"""
    store = get_store()
    chunks_data = store.get_by_hash(file_hash)
    if not chunks_data:
        raise HTTPException(status_code=404, detail="文件不存在")
    file_name = chunks_data[0].get("file_name", "")
    file_ext = os.path.splitext(file_name)[1].lower()

    # 对二进制文件 -> 尝试返回原始文件
    is_binary = file_ext in (".pdf", ".docx", ".xlsx", ".pptx",
                              ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
                              ".dwg", ".dxf", ".step", ".stp")
    if is_binary:
        # 策略1: 本机 raw_docs/
        raw_dir = Path("raw_docs")
        if raw_dir.exists():
            for fp in raw_dir.iterdir():
                if fp.is_file() and file_name in fp.name:
                    ext_map = {
                        ".pdf": "application/pdf",
                        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                        ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp",
                    }
                    mt = ext_map.get(file_ext, "application/octet-stream")
                    return FileResponse(path=str(fp), filename=file_name, media_type=mt)

        # 策略2: 装载机代理
        try:
            import urllib.request
            proxy_url = LOADER_URL + "/api/download?path=" + urllib.parse.quote(file_name.replace("\\", "/"))
            raw_bytes = await fetch(proxy_url, timeout=10)
            if raw_bytes and len(raw_bytes) > 100:
                ext_map = {
                    ".pdf": "application/pdf",
                    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp",
                }
                mt = ext_map.get(file_ext, "application/octet-stream")
                return Response(content=raw_bytes, media_type=mt)
        except Exception:
            pass  # 不可达，回退文本

    # 文本文件 or 二进制获取失败 -> HTML 文本预览
    category = chunks_data[0].get("category", "未分类")
    sorted_chunks = sorted(chunks_data, key=lambda x: x.get("chunk_index", 0))
    full_text = "".join(chr(10)+chr(10)+"---"+chr(10)+chr(10)).join(
        c.get("text", "") for c in sorted_chunks if c.get("chunk_index", 0) >= 0
    )

    # Build HTML - avoid f-string issues with special chars
    sorted_count = len([c for c in sorted_chunks if c.get("chunk_index", 0) >= 0])
    safe_text = full_text.replace("<", "&lt;").replace(">", "&gt;")

    html_parts = []
    html_parts.append("<!DOCTYPE html>")
    html_parts.append('<html lang="zh-CN">')
    html_parts.append("<head>")
    html_parts.append('<meta charset="UTF-8">')
    html_parts.append("<title>" + file_name + " - 伏羲·内世界</title>")
    html_parts.append("<style>")
    html_parts.append("body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:900px;margin:40px auto;padding:20px;color:#333;background:#fafafa}")
    html_parts.append("h1{font-size:20px;border-bottom:2px solid #e65100;padding-bottom:10px}")
    html_parts.append(".meta{color:#888;font-size:13px;margin:8px 0 20px}")
    html_parts.append(".content{white-space:pre-wrap;line-height:1.8;font-size:15px;background:#fff;padding:24px;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.08)}")
    html_parts.append("</style>")
    html_parts.append("</head>")
    html_parts.append("<body>")
    html_parts.append("<h1>📄 " + file_name + "</h1>")
    html_parts.append('<div class="meta">分类: ' + category + " | 共 " + str(sorted_count) + " 个段落</div>")
    html_parts.append('<div class="content">' + safe_text + "</div>")
    html_parts.append("</body>")
    html_parts.append("</html>")

    html = "".join(chr(10)).join(html_parts)
    return HTMLResponse(content=html)

# ============ 文档上传与清洗 ============

@router.post("/api/raw-store")
@router.post("/api/upload")  # 兼容旧前端
async def raw_store_proxy(request: Request):
    """代理上传到本机 local_receiver:8090"""
    body = await request.body()
    content_type = request.headers.get("content-type", "")
    try:
        raw_store_url = os.getenv("KB_RAW_STORE_URL", LOADER_URL.replace(":8090", ":8090") + "/api/raw-store")
        status, resp_body = await post(raw_store_url, data=body, timeout=120, headers={"Content-Type": content_type})
        return Response(content=resp_body, status_code=status, media_type="application/json")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"上传代理失败: {str(e)}")

@router.post("/api/ingest-batch")
async def ingest_batch(body: IngestBatchRequest):
    """接收清洗脚本推送的批量 chunk，写入存储并自动向量化"""
    if not body.chunks:
        return {"status": "empty", "file": body.file_name}

    # 安全检查：路径穿越 + 非法文件名
    if '..' in body.file_name or '/' in body.file_name or '\\' in body.file_name:
        return {"status": "blocked", "file": body.file_name, "reason": "非法文件名（路径穿越）"}
    if len(body.file_name) > 255:
        return {"status": "blocked", "file": body.file_name, "reason": "文件名过长"}

    # v11.40 P0.1: 文件扩展名白名单 — 拒绝二进制 CAD/临时文件
    ALLOWED_CHUNK_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt", ".md", ".csv", ".ppt", ".pptx"}
    BLOCKED_EXTS = {".sldprt", ".step", ".sldasm", ".ipt", ".cfg", ".zip", ".rar", ".7z", ".stp", ".igs", ".iges", ".dwg", ".dxf", ".stl", ".obj"}
    ext_lower = os.path.splitext(body.file_name)[1].lower()
    if ext_lower in BLOCKED_EXTS:
        return {"status": "blocked", "file": body.file_name, "reason": f"二进制CAD文件 ({ext_lower})，不入库"}
    if ext_lower not in ALLOWED_CHUNK_EXTS and ext_lower:
        return {"status": "blocked", "file": body.file_name, "reason": f"不支持的文件类型 ({ext_lower})"}
    
    # 拒绝草稿/上传中文件
    _fn_lower = body.file_name.lower()
    if '.uploading.' in _fn_lower or '.baiduyun.' in _fn_lower or _fn_lower.endswith('.cfg'):
        return {"status": "blocked", "file": body.file_name, "reason": "草稿/临时文件"}

    
    # v10.0: MD5 去重 — 检查文件是否已存在
    if body.file_hash:
        existing = get_store().get_by_hash(body.file_hash)
        if existing:
            return {"status": "duplicate", "file": body.file_name, 
                    "message": f"文件已存在（{len(existing)} chunks），跳过"}
    
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # 用服务器端 match_category 重新精确分类（覆盖装载机粗略分类）
    _re_cat = body.category
    # v11.40: WIKI文件分类不参与自动修正，保留原始标记用于后续提炼
    if "WIKI" not in body.category:
        try:
            from src.category_registry import match_category, normalize_category
            all_text = " ".join(ch.get("text", "") for ch in body.chunks[:10])
            ext = os.path.splitext(body.file_name)[1].lower()
            _re_cat = match_category(all_text, file_ext=ext, file_name=body.file_name) or body.category
            if _re_cat != body.category:
                logger.info(f"[rerank] 分类修正: {body.category} → {_re_cat}")
        except Exception:
            logger.warning(f"[documents] suppressed exception", exc_info=True)
            pass
    new_chunks = []
    # v11.40 P0.3: 元数据注入 — 提取文件来源页码和章节信息
    _page_info = ""
    _section_info = ""
    for ch in body.chunks:
        raw_text = ch.get("text", "")
        # P0.1: 空内容/极短内容过滤（<30字拒绝入库）
        if not raw_text or len(raw_text.strip()) < 30:
            continue
        # P0.1: 草稿标记检测
        if raw_text.strip().startswith("[内容为空]") or raw_text.strip().startswith("[元数据文件]"):
            continue
        
        safe, audit = _audit_text(raw_text, SENSITIVE_PATTERNS)
        
        # P0.2: 长文本自动分块（>1500字用 smart_chunk 二次分块）
        if len(safe) > 1500:
            sub_chunks = _smart_chunk(safe, size=1200, overlap=100)
            for si, sc in enumerate(sub_chunks):
                # P0.3: 注入元数据标签 [文档名 | 来源]
                tagged_text = sc  # [来源] metadata is in file_name field
                new_chunks.append({
                    "file_name": body.file_name,
                    "file_hash": body.file_hash,
                    "text": tagged_text,
                    "category": _re_cat,
                    "chunk_index": ch.get("index", 0) * 100 + si,
                    "created_at": now,
                    "tags": [],
                    "trust": "unverified",
                    "audit_note": audit or "",
                    "images": ch.get("images", []),
                })
        else:
            tagged_text = safe  # [来源] metadata is in file_name field
            new_chunks.append({
                "file_name": body.file_name,
                "file_hash": body.file_hash,
                "loader_path": body.loader_path,
                "text": tagged_text,
                "category": _re_cat,
                "chunk_index": ch.get("index", 0),
                "created_at": now,
                "tags": [],
                "trust": "unverified",
                "audit_note": audit or "",
                "images": ch.get("images", []),
            })
    if not new_chunks:
        return {"status": "blocked", "file": body.file_name, "reason": "all chunks filtered", "chunks": 0}
    get_store().insert_many(new_chunks)
    invalidate_chunk_cache()

    # 自动向量化 → 放入后台队列，不阻塞响应
    try:
        _start_background_vectorizer()
        async with _vector_lock:
            _vector_queue.append(new_chunks)
    except Exception:
        logger.warning(f"[documents] suppressed exception", exc_info=True)
        pass

    # 知识图谱自动进化
    try:
        from src.services.evolver import discover_entities, evolve_graph
        full_text = " ".join(ch.get("text", "") for ch in body.chunks[:50])
        entities = discover_entities(full_text)
        if entities:
            added = evolve_graph(entities, body.file_name)
            if added > 0:
                logger.info(f"[graph] +{added} entities from {body.file_name}")
    except Exception:
        logger.warning(f"[documents] suppressed exception", exc_info=True)
        pass

    # 第八章：WIKI 上传链路 — 自动提炼入库 wiki.db
    if _re_cat == "WIKI文件" or "WIKI" in (body.file_name or ""):
        try:
            from src.services.wiki_upload_handler import refine_with_llm
            full_text = " ".join(ch.get("text", "") for ch in body.chunks[:30])
            if len(full_text.strip()) >= 50:
                refined = refine_with_llm(full_text)
                if refined:
                    from src.services.wiki_engine import get_wiki_engine
                    engine = get_wiki_engine()
                    title = body.file_name.rsplit(".", 1)[0][:80]
                    tags = []
                    for line in refined.split("\n"):
                        if line.strip().startswith("## "):
                            title = line.strip().replace("## ", "")[:80]; break
                        if line.strip().startswith("#") and not line.strip().startswith("##"):
                            tags = [t.strip().replace("#", "") for t in line.split() if t.startswith("#")]
                    engine.create_page(
                        title=title, content=refined,
                        category="Wiki上传 > 自动提炼",
                        tags=tags,
                        sources=[body.file_name],
                    )
                    logger.info(f"[wiki] 自动提炼入库: {title}")
        except Exception as e:
            logger.warning(f"[wiki] 自动提炼失败: {e}")

    # 表格结构化索引
    try:
        from src.services.feature_flags import load_flags as _lf
        if _lf().get("table_structured_search", False):
            from src.services.table_parser import parse_table_to_rows
            table_chunks = [c for c in new_chunks if "|" in c.get("text", "") and "---" in c.get("text", "")]
            if table_chunks:
                logger.info(f"[table] 发现 {len(table_chunks)} 个表格 chunk")
    except Exception as e:
        logger.warning(f"[table] 表格索引失败: {e}")

    # 知识生命周期注册
    try:
        from src.services.knowledge_lifecycle import register_knowledge
        for c in new_chunks[:5]:
            register_knowledge(
                entity_id=c.get("file_hash", "") + "_" + str(c.get("chunk_index", 0)),
                source=body.file_name,
                confidence=0.7
            )
    except Exception as e:
        logger.warning(f"[lifecycle] 注册失败: {e}")

    return {"status": "ok", "file": body.file_name, "chunks": len(new_chunks)}


async def _index_vectors_async(chunks: list):
    """将 chunk 文本向量化并写入 VectorStore，处理后立即释放内存"""
    import gc
    try:
        valid = [(i, c) for i, c in enumerate(chunks)
                 if c.get("text", "") and len(c["text"]) >= 50]
        if not valid:
            return
        BATCH = 32  # 降低批次大小减少内存峰值
        vs = get_vector_store()
        for start in range(0, len(valid), BATCH):
            batch = valid[start:start + BATCH]
            texts = [c["text"] for _, c in batch]
            vecs = await embed_texts(texts)
            if not vecs:
                break
            ids, metas = [], []
            for idx, (orig_idx, ch) in enumerate(batch[:len(vecs)]):
                chunk_id = f"{ch.get('file_hash','')}:{ch.get('chunk_index',0)}-{orig_idx}"
                ids.append(chunk_id)
                metas.append({
                    "file_hash": ch.get("file_hash", ""),
                    "file_name": ch.get("file_name", ""),
                    "chunk_index": ch.get("chunk_index", 0),
                    "category": ch.get("category", ""),
                    "text": ch.get("text", "")[:1000],
                })
            # 传入 documents 参数确保文本写入 ChromaDB
            docs = [c["text"] for _, c in batch[:len(vecs)]]
            if not vs.add(ids, vecs, metas, docs):
                logger.warning(f"Vector add failed for batch (size={len(ids)})")
            # 每个 batch 后强制释放内存
            del batch, texts, vecs, ids, metas
            gc.collect()
    except Exception:
        logger.error("Vector indexing failed", exc_info=True)


# ============ 重建索引 ============

@router.post("/api/reindex")
async def reindex(request: Request):
    """清空库并重新扫描 uploads/ 下所有文件"""
    _check_admin_token(request)
    files = list(UPLOAD_DIR.glob("*"))
    if not files:
        return {"status": "ok", "message": "无文件可重建", "reindexed": 0}
    store = get_store()
    with store._conn() as conn:
        conn.execute("DELETE FROM chunks")
        conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
        conn.commit()
    all_chunks = []
    total_files = 0
    seen_hashes = set()  # v10.0: MD5 去重
    skipped_dupes = 0
    for fp in files:
        if fp.is_dir():
            continue
        safe_name = fp.name
        ext = os.path.splitext(safe_name)[1].lower()
        if not ext:
            continue
        try:
            text = _extract_text(str(fp), ext)
            clean = _clean_text(text)
            if not clean.strip():
                continue
            chunks_text = _smart_chunk(clean)
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            cat = match_category(clean, file_ext=ext, file_name=safe_name) or "通用办公"
            raw_bytes = fp.read_bytes()
            file_hash = hashlib.sha256(raw_bytes).hexdigest()
            
            # v10.0: MD5 去重 — 跳过了重复文件
            if file_hash in seen_hashes:
                skipped_dupes += 1
                continue
            seen_hashes.add(file_hash)
            
            summary = _generate_summary(clean)
            all_chunks.append({
                "file_name": safe_name, "file_hash": file_hash, "file_type": ext,
                "file_size_kb": round(len(raw_bytes) / 1024, 1),
                "text": summary, "category": cat,
                "chunk_index": -1, "created_at": now,
                "tags": ["summary"], "trust": "unverified", "audit_note": ""
            })
            for i, ct in enumerate(chunks_text):
                safe_ct, _ = _audit_wrapper(ct)
                all_chunks.append({
                    "file_name": safe_name, "file_hash": file_hash, "file_type": ext,
                    "file_size_kb": round(len(raw_bytes) / 1024, 1),
                    "text": safe_ct, "category": cat, "chunk_index": i, "created_at": now,
                    "tags": [], "trust": "unverified", "audit_note": ""
                })
            total_files += 1
        except Exception as e:
            logger.warning(f"[reindex] skip {fp.name}: {e}")
    store.insert_many(all_chunks)
    invalidate_chunk_cache()
    return {"status": "ok", "message": f"重建完成 (跳过 {skipped_dupes} 个重复文件)", "reindexed": total_files, "total_chunks": len(all_chunks), "skipped_dupes": skipped_dupes}


# ============ 重置 ============

@router.post("/api/reset")
async def reset(request: Request):
    """清空全部数据"""
    _check_admin_token(request)
    store = get_store()
    n = store.stats()["total_chunks"]
    # Phase 0: use SQL DELETE instead of clearing in-memory lists
    store._db_conn.execute("DELETE FROM chunks")
    store._db_conn.commit()
    invalidate_chunk_cache()
    # store._save() removed — MemoryStore does not support persist
    return {"message": f"已清空 {n} 条数据", "deleted": n}


# ============ 周天大阵: 统一管线 API ============

@router.post("/api/pipeline/process")
async def pipeline_process(request: Request):
    """统一管线处理文件 — 周天大阵 Phase 2"""
    from src.pipeline.unified import get_pipeline
    from src.pipeline.errors import PipelineError

    body = await request.json()
    file_path = body.get("file_path", "")
    source = body.get("source", "api")

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(400, f"文件不存在: {file_path}")

    try:
        pipeline = get_pipeline()
        result = await pipeline.process(file_path, source=source)
        return {
            "status": "ok",
            "chunks": len(result.chunks),
            "events": len(result.events),
            "entities": len(result.entities),
            "duration_ms": round(result.duration_ms, 1),
            "errors": result.errors,
            "skipped": result.skipped,
        }
    except PipelineError as e:
        raise HTTPException(500, f"管线错误 [{e.code}]: {e.message}")
    except Exception as e:
        raise HTTPException(500, f"处理失败: {str(e)}")
