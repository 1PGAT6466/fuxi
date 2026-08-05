"""
伏羲 v1.50 — 知识库管理 API
========================
- /api/knowledge/approval  — 知识库审批
- /api/knowledge/rollback  — 知识库回滚
- /api/knowledge/versions  — 知识库版本
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from src.api.response import error, success
from src.config import DATA_DIR

logger = logging.getLogger("knowledge")

router = APIRouter()

# ── 存储路径 ──


def _get_versions_file() -> Path:
    p = Path(DATA_DIR) / "knowledge_versions.json"
    if not p.exists():
        p.write_text("[]", encoding="utf-8")
    return p


def _get_approvals_file() -> Path:
    p = Path(DATA_DIR) / "knowledge_approvals.json"
    if not p.exists():
        p.write_text("[]", encoding="utf-8")
    return p


def _load_json(path: Path) -> list:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_json(path: Path, data: list):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 版本管理 ──


@router.get("/api/knowledge/versions")
async def list_versions(
    file_name: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """获取知识库版本列表"""
    versions = _load_json(_get_versions_file())
    if file_name:
        versions = [v for v in versions if v.get("file_name") == file_name]
    versions.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return success(data={"items": versions[:limit], "total": len(versions)})


@router.post("/api/knowledge/versions")
async def create_version(request: Request):
    """创建知识库版本快照"""
    body = await request.json()
    file_name = body.get("file_name")
    description = body.get("description", "")
    chunks_snapshot = body.get("chunks_snapshot", [])

    if not file_name:
        return error("file_name 不能为空", status_code=400)

    versions = _load_json(_get_versions_file())
    version_id = f"v{int(time.time())}_{len(versions)}"
    version = {
        "version_id": version_id,
        "file_name": file_name,
        "description": description,
        "chunks_count": len(chunks_snapshot),
        "created_at": time.time(),
    }
    versions.append(version)
    _save_json(_get_versions_file(), versions)

    # 保存快照数据
    snapshot_dir = Path(DATA_DIR) / "version_snapshots"
    snapshot_dir.mkdir(exist_ok=True)
    snapshot_path = snapshot_dir / f"{version_id}.json"
    snapshot_path.write_text(json.dumps(chunks_snapshot, ensure_ascii=False), encoding="utf-8")

    return success(data=version, message="版本创建成功")


# ── 审批流程 ──


@router.get("/api/knowledge/approval")
async def list_approvals(
    status: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """获取审批列表"""
    approvals = _load_json(_get_approvals_file())
    if status:
        approvals = [a for a in approvals if a.get("status") == status]
    approvals.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return success(data={"items": approvals[:limit], "total": len(approvals)})


@router.post("/api/knowledge/approval")
async def create_approval(request: Request):
    """创建审批请求"""
    body = await request.json()
    file_name = body.get("file_name")
    action = body.get("action", "update")  # update / delete
    description = body.get("description", "")
    requested_by = body.get("requested_by", "unknown")

    if not file_name:
        return error("file_name 不能为空", status_code=400)

    approvals = _load_json(_get_approvals_file())
    approval_id = f"app_{int(time.time())}_{len(approvals)}"
    approval = {
        "approval_id": approval_id,
        "file_name": file_name,
        "action": action,
        "description": description,
        "requested_by": requested_by,
        "status": "pending",
        "created_at": time.time(),
        "reviewed_by": None,
        "reviewed_at": None,
    }
    approvals.append(approval)
    _save_json(_get_approvals_file(), approvals)
    return success(data=approval, message="审批请求已创建")


@router.post("/api/knowledge/approval/{approval_id}")
async def review_approval(approval_id: str, request: Request):
    """审批操作（approve / reject）"""
    body = await request.json()
    action = body.get("action")  # approve / reject
    reviewed_by = body.get("reviewed_by", "admin")

    if action not in ("approve", "reject"):
        return error("action 必须为 approve 或 reject", status_code=400)

    approvals = _load_json(_get_approvals_file())
    for a in approvals:
        if a.get("approval_id") == approval_id:
            a["status"] = "approved" if action == "approve" else "rejected"
            a["reviewed_by"] = reviewed_by
            a["reviewed_at"] = time.time()
            _save_json(_get_approvals_file(), approvals)
            return success(data=a, message=f"审批已{a['status']}")

    return error("审批记录不存在", status_code=404)


# ── 回滚 ──


@router.post("/api/knowledge/rollback")
async def rollback_version(request: Request):
    """回滚到指定版本"""
    body = await request.json()
    version_id = body.get("version_id")
    file_name = body.get("file_name")

    if not version_id:
        return error("version_id 不能为空", status_code=400)

    # 查找版本
    versions = _load_json(_get_versions_file())
    target_version = None
    for v in versions:
        if v.get("version_id") == version_id:
            target_version = v
            break

    if not target_version:
        return error("版本不存在", status_code=404)

    # 读取快照
    snapshot_path = Path(DATA_DIR) / "version_snapshots" / f"{version_id}.json"
    if not snapshot_path.exists():
        return error("版本快照数据不存在", status_code=404)

    snapshot_data = json.loads(snapshot_path.read_text(encoding="utf-8"))

    # 执行回滚 — 删除旧 chunks 并写入快照数据
    import sqlite3

    db_path = Path(DATA_DIR) / "chunks.db"
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    fn = file_name or target_version.get("file_name", "")

    # 删除该文件的旧 chunks
    c.execute("DELETE FROM chunks WHERE file_name = ?", (fn,))

    # 写入快照中的 chunks
    for chunk in snapshot_data:
        c.execute(
            "INSERT INTO chunks (doc, file_name, chunk_index, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (chunk.get("doc", ""), fn, chunk.get("chunk_index", 0), "active", time.time()),
        )

    conn.commit()
    conn.close()

    return success(
        data={
            "version_id": version_id,
            "file_name": fn,
            "chunks_restored": len(snapshot_data),
        },
        message="回滚成功",
    )
