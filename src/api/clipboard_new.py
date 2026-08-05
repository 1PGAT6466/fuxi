"""
伏羲 v1.44 — Clipboard API 模块

实现：
- POST /api/clipboard/sync - 同步剪贴板
- GET /api/clipboard/history - 获取历史
- DELETE /api/clipboard/batch-delete - 批量删除
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from src.api.response import error, not_found, server_error, success
from src.auth.rbac import get_current_username, require_role

logger = logging.getLogger("api.clipboard")

router = APIRouter()


def _get_clipboard_file(username: str) -> Path:
    """获取用户剪贴板文件路径"""
    from src.config import DATA_DIR

    clipboard_dir = Path(DATA_DIR) / "clipboard"
    clipboard_dir.mkdir(parents=True, exist_ok=True)
    return clipboard_dir / f"{username}.json"


def _load_clipboard(username: str) -> List[Dict]:
    """加载用户剪贴板历史"""
    clipboard_file = _get_clipboard_file(username)
    if clipboard_file.exists():
        return json.loads(clipboard_file.read_text(encoding="utf-8"))
    return []


def _save_clipboard(username: str, clipboard: List[Dict]):
    """保存用户剪贴板历史"""
    clipboard_file = _get_clipboard_file(username)
    clipboard_file.write_text(json.dumps(clipboard, ensure_ascii=False, indent=2), encoding="utf-8")


@router.post("/api/clipboard/sync")
@require_role("user")
async def sync_clipboard(request: Request):
    """同步剪贴板"""
    try:
        username = get_current_username(request)
        body = await request.json()

        clipboard = _load_clipboard(username)

        new_item = {
            "id": f"clip_{len(clipboard) + 1}",
            "content": body.get("content", ""),
            "type": body.get("type", "text"),
            "created_at": datetime.now().isoformat(),
        }

        clipboard.append(new_item)
        _save_clipboard(username, clipboard)

        return success(data=new_item, status_code=201)
    except Exception as e:
        logger.error(f"同步剪贴板失败: {e}")
        return server_error(detail=str(e))


@router.get("/api/clipboard/history")
@require_role("user")
async def get_clipboard_history(request: Request):
    """获取剪贴板历史"""
    try:
        username = get_current_username(request)
        clipboard = _load_clipboard(username)

        return success(data={"items": clipboard, "total": len(clipboard)})
    except Exception as e:
        logger.error(f"获取剪贴板历史失败: {e}")
        return server_error(detail=str(e))


@router.delete("/api/clipboard/batch-delete")
@require_role("user")
async def batch_delete_clipboard(request: Request):
    """批量删除剪贴板"""
    try:
        username = get_current_username(request)
        body = await request.json()

        ids_to_delete = body.get("ids", [])

        clipboard = _load_clipboard(username)
        clipboard = [item for item in clipboard if item.get("id") not in ids_to_delete]
        _save_clipboard(username, clipboard)

        return success(message=f"已删除 {len(ids_to_delete)} 条记录")
    except Exception as e:
        logger.error(f"批量删除剪贴板失败: {e}")
        return server_error(detail=str(e))
