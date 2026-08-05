"""
伏羲 v1.50 — 反馈 API

提供用户反馈的提交、查询、更新功能。

API 端点：
  GET    /api/feedback         — 返回反馈列表
  POST   /api/feedback         — 提交反馈
  PUT    /api/feedback/{id}    — 更新反馈状态

数据存储：data/feedback.json
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from src.config import DATA_DIR

logger = logging.getLogger(__name__)

router = APIRouter(tags=["反馈"])

FEEDBACK_FILE = os.path.join(str(DATA_DIR), "feedback.json")


def _ensure_data_dir():
    """确保数据目录存在"""
    os.makedirs(os.path.dirname(FEEDBACK_FILE), exist_ok=True)


def _load_feedback() -> List[Dict]:
    """加载反馈数据"""
    if not os.path.exists(FEEDBACK_FILE):
        return []
    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_feedback(entries: List[Dict]):
    """保存反馈数据"""
    _ensure_data_dir()
    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


@router.get("/api/feedback")
async def get_feedback(
    status: str = Query(None),
    type: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """返回反馈列表"""
    try:
        entries = _load_feedback()
        # 按时间倒序
        entries.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        # 过滤
        if status:
            entries = [e for e in entries if e.get("status") == status]
        if type:
            entries = [e for e in entries if e.get("type") == type]
        total = len(entries)
        # 分页
        start = (page - 1) * page_size
        items = entries[start : start + page_size]
        return {"status": "success", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}
    except (OSError, IOError, ValueError) as e:
        logger.exception(f"获取反馈列表失败: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@router.post("/api/feedback")
async def submit_feedback(request: Request):
    """提交反馈"""
    try:
        data = await request.json()
        entry = {
            "id": str(uuid.uuid4()),
            "user": data.get("user", "admin"),
            "type": data.get("type", "feature"),
            "title": data.get("title", ""),
            "content": data.get("content", ""),
            "status": "open",
            "created_at": datetime.now().isoformat(),
        }
        entries = _load_feedback()
        entries.append(entry)
        _save_feedback(entries)
        return {"status": "success", "data": {"id": entry["id"]}}
    except (OSError, IOError, json.JSONDecodeError, ValueError) as e:
        logger.exception(f"提交反馈失败: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@router.put("/api/feedback/{feedback_id}")
async def update_feedback(feedback_id: str, request: Request):
    """更新反馈状态"""
    try:
        data = await request.json()
        entries = _load_feedback()
        found = False
        for entry in entries:
            if entry.get("id") == feedback_id:
                if "status" in data:
                    entry["status"] = data["status"]
                if "type" in data:
                    entry["type"] = data["type"]
                if "title" in data:
                    entry["title"] = data["title"]
                if "content" in data:
                    entry["content"] = data["content"]
                entry["updated_at"] = datetime.now().isoformat()
                found = True
                break
        if not found:
            return JSONResponse(status_code=404, content={"status": "error", "message": "反馈不存在"})
        _save_feedback(entries)
        return {"status": "success", "message": "反馈已更新"}
    except (OSError, IOError, json.JSONDecodeError, ValueError) as e:
        logger.exception(f"更新反馈失败: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@router.get("/api/feedback/weekly")
async def get_weekly_feedback():
    """返回每周反馈汇总"""
    return {"status": "success", "data": {"items": [], "total": 0}}


logger.info("[feedback] 反馈 API 已加载")
