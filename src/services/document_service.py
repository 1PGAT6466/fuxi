"""
伏羲 v1.50 — 文档服务层
=====================
Service layer for document operations: list, upload, delete, visibility management.
Abstracts away db/vector_store/pipline details from API routes.
"""
import logging
import hashlib
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def list_documents(page: int = 1, page_size: int = 50) -> List[Dict[str, Any]]:
    """获取文档列表（按 file_hash 去重）"""
    from src.db.data_store import load_chunks

    chunks = load_chunks()
    seen: Dict[str, Dict] = {}
    for c in chunks:
        fh = c.get("file_hash", "")
        if fh and fh not in seen:
            seen[fh] = {
                "file_name": c.get("file_name", ""),
                "file_hash": fh,
                "category": c.get("category", ""),
                "chunk_count": 1,
                "created_at": c.get("created_at", ""),
                "owner_id": c.get("owner_id", ""),
                "visibility": c.get("visibility", "public"),
            }
        elif fh:
            seen[fh]["chunk_count"] += 1

    return list(seen.values())


def upload_document(file_name: str, file_content: bytes, source: str = "upload") -> Dict[str, Any]:
    """上传并处理文档"""
    from src.shaoyang.pipeline import ShaoyangPipeline
    from src.bagua.intent_bus import IntentBus
    from src.config import UPLOAD_DIR as CONFIG_UPLOAD_DIR

    tmp_dir = Path(CONFIG_UPLOAD_DIR)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / file_name
    tmp_path.write_bytes(file_content)

    intent_bus = IntentBus()
    pipeline = ShaoyangPipeline(intent_bus)
    result = pipeline.digest(str(tmp_path), source=source)

    return {
        "file_name": file_name,
        "chunks": len(result.chunks),
        "duration_ms": result.duration_ms,
    }


def delete_document(file_hash: str, current_user: str = "anonymous", current_role: str = "user") -> Dict[str, Any]:
    """删除文档，返回删除结果。AUTHZ: 需传入当前用户信息进行权限检查。"""
    from src.db.data_store import load_chunks, save_chunks
    from src.db.vector_store import get_vector_store
    from src.config import UPLOAD_DIR as _UPLOAD_DIR

    chunks = load_chunks()
    if not chunks:
        raise FileNotFoundError(f"无数据，无法删除 {file_hash}")

    matching = [c for c in chunks if c.get("file_hash", "") == file_hash]
    if not matching:
        matching = [
            c for c in chunks
            if file_hash in c.get("file_name", "") or file_hash in c.get("file_hash", "")
        ]

    if not matching:
        raise FileNotFoundError(f"文档 {file_hash} 未找到")

    # 所有权检查
    is_admin = current_role == "admin"
    if not is_admin:
        doc_owner = matching[0].get("owner_id") or matching[0].get("uploader", "")
        if doc_owner and doc_owner != current_user and current_user != "anonymous":
            raise PermissionError("无权删除他人文档")

    file_name = matching[0].get("file_name", file_hash)
    kept = [
        c for c in chunks
        if c.get("file_hash", "") != file_hash and file_hash not in c.get("file_name", "")
    ]
    save_chunks(kept)

    # 删除向量
    try:
        vs = get_vector_store()
        if vs:
            vs.delete_by_file(file_hash)
    except Exception as e:  # TODO: Narrow exception type
        logger.warning(f"向量库删除失败（非致命）: {e}")

    # 删除物理文件
    upload_dir = Path(_UPLOAD_DIR)
    if upload_dir.exists():
        for root, dirs, files in os.walk(str(upload_dir)):
            for fname in files:
                fpath = Path(root) / fname
                try:
                    with open(fpath, "rb") as f:
                        content = f.read()
                    computed_hash = hashlib.sha256(content).hexdigest()[:16]
                    if computed_hash == file_hash[:16] or file_hash in str(fpath):
                        fpath.unlink()
                except OSError as e:
                    logger.warning(f"物理文件删除失败: {e}")

    return {
        "file_name": file_name,
        "file_hash": file_hash,
        "chunks_removed": len(matching),
    }


def get_document_by_hash(file_hash: str) -> Optional[Dict[str, Any]]:
    """按 file_hash 获取文档信息"""
    from src.db.data_store import load_chunks
    chunks = load_chunks()
    matching = [c for c in chunks if c.get("file_hash", "") == file_hash]
    if not matching:
        return None
    return matching[0]


def update_document_visibility(
    doc_id: str,
    visibility: str,
    team_id: str = "",
    owner_id: str = "",
) -> Dict[str, Any]:
    """更新文档可见性"""
    from src.api.permissions import PermissionManager
    from src.db.data_store import load_chunks, save_chunks
    from src.db.vector_store import get_vector_store

    visibility = PermissionManager.validate_visibility(visibility)

    chunks = load_chunks()
    updated_count = 0
    for c in chunks:
        if c.get("file_hash", "") == doc_id:
            c["visibility"] = visibility
            if team_id:
                c["team_id"] = team_id
            if not c.get("owner_id"):
                c["owner_id"] = owner_id
            updated_count += 1

    if updated_count > 0:
        save_chunks(chunks)

    # 更新向量库 metadata
    try:
        vs = get_vector_store()
        if vs:
            vs.update_metadata_by_file(doc_id, {
                "visibility": visibility,
                "team_id": team_id or "",
            })
    except Exception as e:  # TODO: Narrow exception type
        logger.warning(f"向量库 metadata 更新失败（非致命）: {e}")

    return {
        "doc_id": doc_id,
        "visibility": visibility,
        "team_id": team_id or "",
        "chunks_updated": updated_count,
    }
