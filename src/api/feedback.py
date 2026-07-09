"""
伏羲 v1.50 — 反馈路由（真实数据版）
数据来源：feedback_store.py（去重 + 文件持久化 + 批量学习）
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging
import json
import os
import time
from typing import Dict, List

logger = logging.getLogger(__name__)

router = APIRouter(tags=["反馈"])

from src.config import FEEDBACK_DIR as CONFIG_FEEDBACK_DIR

FEEDBACK_DIR = os.path.abspath(CONFIG_FEEDBACK_DIR)


def _load_feedback_files(days: int = 7) -> List[Dict]:
    """从反馈日志文件加载反馈条目"""
    entries = []
    cutoff = time.time() - days * 86400
    if not os.path.isdir(FEEDBACK_DIR):
        return entries

    for fname in sorted(os.listdir(FEEDBACK_DIR), reverse=True):
        if not fname.startswith("feedback_") or not fname.endswith(".jsonl"):
            continue
        fpath = os.path.join(FEEDBACK_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("timestamp", 0) >= cutoff:
                            entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"读取反馈文件 {fname} 失败: {e}")

    entries.sort(key=lambda e: e.get("timestamp", 0), reverse=True)
    return entries


@router.get("/api/feedback/weekly")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def feedback_weekly(request: Request = None):
    """每周反馈 — v1.50 真实数据版

    从 feedback/*.jsonl 文件读取真实反馈数据，
    如果没有反馈记录则返回空列表 + 引导信息。
    """
    try:
        from src.services.feedback_store import get_feedback_stats
        stats = get_feedback_stats()

        feedbacks = _load_feedback_files(days=7)

        data = {
            "feedbacks": feedbacks,
            "total": len(feedbacks),
            "stats": stats,
            "hint": None if feedbacks else '暂无用户反馈。通过聊天页面的"踩"按钮提交反馈。',
        }

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data=data, message="每周反馈")
        return data
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"feedback_weekly 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


@router.post("/api/feedback")
async def feedback_submit(request: Request):
    """提交反馈 — v1.50 真实数据版

    请求体:
      {"content": "反馈内容", "rating": 1-5, "category": "搜索|对话|wiki|其他"}

    写入反馈日志文件，触发去重 + 批量学习。
    """
    try:
        body = await request.json()
        user_id = getattr(request.state, "user", "anonymous")

        content = body.get("content", "")
        rating = body.get("rating")
        category = body.get("category", "其他")
        query = body.get("query", "")

        # 写入反馈存储
        from src.services.feedback_store import log_feedback_unified
        action = f"rate_{rating}" if rating else "feedback"

        result = await log_feedback_unified(
            user_id=user_id,
            query=query or content,
            action=action,
            metadata={
                "content": content,
                "rating": rating,
                "category": category,
            },
        )

        logger.info(
            f"[feedback] 用户 {user_id} 提交反馈: "
            f"action={action}, dedup={result.get('dedup')}, "
            f"learn_triggered={result.get('learn_triggered')}"
        )

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(
                data={"ok": True, "dedup": result.get("dedup", False), "learn_triggered": result.get("learn_triggered", False)},
                message="反馈提交成功" if not result.get("dedup") else "重复反馈已忽略"
            )
        return {"ok": True}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"feedback_submit 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )
