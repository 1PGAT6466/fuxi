"""
伏羲 v1.50 — 缺失 API 补全
========================
- /api/notifications/vapid  — VAPID 公钥（Web Push）
- /api/webhooks/verify      — Webhook 验签
- /api/graph/nodes           — 图节点查询
- /api/graph/auto            — 自动图构建
- /api/clipboard/batch       — 剪贴板批量操作
"""

import hashlib
import hmac
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from src.api.response import error, success
from src.config import DATA_DIR

logger = logging.getLogger("extra_api")

router = APIRouter()


# ══════════════════════════════════════════════
#  /api/notifications/vapid — VAPID 公钥
# ══════════════════════════════════════════════

_VAPID_KEYS_FILE = Path(DATA_DIR) / "vapid_keys.json"


def _get_or_create_vapid_keys() -> dict:
    """获取或创建 VAPID 密钥对"""
    if _VAPID_KEYS_FILE.exists():
        try:
            return json.loads(_VAPID_KEYS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    # 生成模拟 VAPID 密钥（生产环境应用 py_vapid）
    import base64
    import os

    public_key = base64.urlsafe_b64encode(os.urandom(65)).rstrip(b"=").decode("utf-8")
    private_key = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("utf-8")

    keys = {
        "public_key": public_key,
        "private_key": private_key,
        "created_at": time.time(),
    }
    _VAPID_KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _VAPID_KEYS_FILE.write_text(json.dumps(keys, indent=2), encoding="utf-8")
    return keys


@router.get("/api/notifications/vapid")
async def get_vapid_public_key():
    """获取 VAPID 公钥（用于 Web Push 订阅）"""
    keys = _get_or_create_vapid_keys()
    return success(data={"publicKey": keys["public_key"]})


# ══════════════════════════════════════════════
#  /api/webhooks/verify — Webhook 验签
# ══════════════════════════════════════════════


@router.post("/api/webhooks/verify")
async def verify_webhook(request: Request):
    """验证 Webhook 签名"""
    body = await request.json()
    payload = body.get("payload", "")
    secret = body.get("secret", "")
    signature = body.get("signature", "")

    if not payload or not secret:
        return error("payload 和 secret 不能为空", status_code=400)

    # HMAC-SHA256 验签
    expected = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    is_valid = hmac.compare_digest(expected, signature)

    return success(
        data={
            "valid": is_valid,
            "algorithm": "hmac-sha256",
        },
        message="验签完成",
    )


# ══════════════════════════════════════════════
#  /api/graph/nodes — 图节点查询
# ══════════════════════════════════════════════


def _read_kg_data() -> tuple:
    """读取知识图谱数据"""
    kg_path = Path(DATA_DIR) / "knowledge_graph.json"
    if not kg_path.exists():
        return {}, []
    try:
        data = json.loads(kg_path.read_text(encoding="utf-8"))
        nodes = data.get("nodes", data.get("entities", {}))
        edges = data.get("edges", data.get("relations", []))
        if isinstance(nodes, list):
            nodes = {n.get("id", n.get("name", str(i))): n for i, n in enumerate(nodes)}
        return nodes, edges
    except Exception:
        return {}, []


@router.get("/api/graph/nodes")
async def list_graph_nodes(
    q: str = Query("", description="搜索关键词"),
    type: str = Query(None, description="节点类型过滤"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """查询图谱节点"""
    nodes, edges = _read_kg_data()

    if not isinstance(nodes, dict):
        return success(data={"items": [], "total": 0})

    # 过滤
    result = []
    for node_id, node_info in nodes.items():
        if q and q.lower() not in node_id.lower():
            continue
        if type:
            node_type = node_info.get("type", "") if isinstance(node_info, dict) else ""
            if node_type != type:
                continue
        item = {"id": node_id}
        if isinstance(node_info, dict):
            item.update(node_info)
        result.append(item)

    total = len(result)
    result = result[offset : offset + limit]
    return success(data={"items": result, "total": total})


@router.post("/api/graph/nodes")
async def create_graph_node(request: Request):
    """创建图谱节点"""
    body = await request.json()
    node_id = body.get("id") or body.get("name")
    node_type = body.get("type", "entity")
    properties = body.get("properties", {})

    if not node_id:
        return error("节点 id 或 name 不能为空", status_code=400)

    nodes, edges = _read_kg_data()
    if not isinstance(nodes, dict):
        nodes = {}

    nodes[node_id] = {
        "type": node_type,
        "properties": properties,
        "created_at": time.time(),
    }

    # 保存
    kg_path = Path(DATA_DIR) / "knowledge_graph.json"
    kg_data = {"nodes": nodes, "edges": edges}
    kg_path.write_text(json.dumps(kg_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return success(data={"id": node_id, "type": node_type}, message="节点创建成功")


# ══════════════════════════════════════════════
#  /api/graph/auto — 自动图构建
# ══════════════════════════════════════════════


@router.post("/api/graph/auto")
async def auto_build_graph(request: Request):
    """自动构建知识图谱（从 chunks 中提取实体和关系）"""
    body = await request.json()
    file_name = body.get("file_name")
    limit = body.get("limit", 100)

    import sqlite3

    db_path = Path(DATA_DIR) / "chunks.db"
    if not db_path.exists():
        return error("chunks.db 不存在", status_code=404)

    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    if file_name:
        c.execute("SELECT doc FROM chunks WHERE file_name = ? LIMIT ?", (file_name, limit))
    else:
        c.execute("SELECT doc FROM chunks LIMIT ?", (limit,))

    chunks = [row[0] for row in c.fetchall()]
    conn.close()

    if not chunks:
        return error("没有找到 chunks 数据", status_code=404)

    # 简单实体提取（基于规则）
    import re

    entities = set()
    relations = []

    for chunk in chunks:
        if not chunk:
            continue
        # 提取中文名词短语
        nouns = re.findall(r"[\u4e00-\u9fff]{2,8}", chunk[:2000])
        for noun in nouns[:10]:
            entities.add(noun)

    # 构建图
    nodes, edges = _read_kg_data()
    if not isinstance(nodes, dict):
        nodes = {}

    new_count = 0
    for entity in entities:
        if entity not in nodes:
            nodes[entity] = {
                "type": "auto_extracted",
                "source": file_name or "auto",
                "created_at": time.time(),
            }
            new_count += 1

    # 保存
    kg_path = Path(DATA_DIR) / "knowledge_graph.json"
    kg_data = {"nodes": nodes, "edges": edges}
    kg_path.write_text(json.dumps(kg_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return success(
        data={
            "entities_extracted": len(entities),
            "new_nodes_added": new_count,
            "total_nodes": len(nodes),
        },
        message="自动图构建完成",
    )


# ══════════════════════════════════════════════
#  /api/clipboard/batch — 剪贴板批量操作
# ══════════════════════════════════════════════


def _get_clipboard_file() -> Path:
    return Path(DATA_DIR) / "clipboard.json"


def _load_clipboard() -> list:
    p = _get_clipboard_file()
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_clipboard(records: list):
    p = _get_clipboard_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


@router.post("/api/clipboard/batch")
async def clipboard_batch(request: Request):
    """剪贴板批量操作（删除、收藏、导出）"""
    body = await request.json()
    action = body.get("action")  # delete / favorite / export
    entry_ids = body.get("entry_ids", [])

    if not action or not entry_ids:
        return error("action 和 entry_ids 不能为空", status_code=400)

    records = _load_clipboard()
    affected = 0

    if action == "delete":
        new_records = [r for r in records if r.get("id") not in entry_ids]
        affected = len(records) - len(new_records)
        _save_clipboard(new_records)

    elif action == "favorite":
        for r in records:
            if r.get("id") in entry_ids:
                r["favorite"] = True
                affected += 1
        _save_clipboard(records)

    elif action == "export":
        exported = [r for r in records if r.get("id") in entry_ids]
        return success(data={"items": exported, "count": len(exported)}, message="导出成功")

    else:
        return error(f"不支持的操作: {action}", status_code=400)

    return success(data={"affected": affected}, message=f"批量{action}完成")
