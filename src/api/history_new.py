"""
伏羲 v1.44 — History API 模块

实现：
- GET /api/history - 获取历史记录
- POST /api/history/visit - 记录访问
- DELETE /api/history - 清空历史记录
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

logger = logging.getLogger("api.history")

router = APIRouter()


def _get_history_file(username: str) -> Path:
    """获取用户历史记录文件路径"""
    from src.config import DATA_DIR

    history_dir = Path(DATA_DIR) / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    return history_dir / f"{username}.json"


def _load_history(username: str) -> List[Dict]:
    """加载用户历史记录"""
    history_file = _get_history_file(username)
    if history_file.exists():
        return json.loads(history_file.read_text(encoding="utf-8"))
    return []


def _save_history(username: str, history: List[Dict]):
    """保存用户历史记录"""
    history_file = _get_history_file(username)
    history_file.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("/api/history")
@require_role("user")
async def get_history(request: Request):
    """获取历史记录"""
    try:
        username = get_current_username(request)
        history = _load_history(username)

        return success(data={"items": history, "total": len(history)})
    except Exception as e:
        logger.error(f"获取历史记录失败: {e}")
        return server_error(detail=str(e))


@router.post("/api/history/visit")
@require_role("user")
async def record_visit(request: Request):
    """记录访问"""
    try:
        username = get_current_username(request)
        body = await request.json()

        history = _load_history(username)

        new_visit = {
            "id": f"visit_{len(history) + 1}",
            "url": body.get("url", ""),
            "title": body.get("title", ""),
            "visited_at": datetime.now().isoformat(),
        }

        history.append(new_visit)
        _save_history(username, history)

        return success(data=new_visit, status_code=201)
    except Exception as e:
        logger.error(f"记录访问失败: {e}")
        return server_error(detail=str(e))


@router.delete("/api/history")
@require_role("user")
async def clear_history(request: Request):
    """清空历史记录"""
    try:
        username = get_current_username(request)
        _save_history(username, [])

        return success(message="历史记录已清空")
    except Exception as e:
        logger.error(f"清空历史记录失败: {e}")
        return server_error(detail=str(e))
