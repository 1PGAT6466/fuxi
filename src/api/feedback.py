"""
routers/feedback.py — 反馈与用户偏好路由（v10.0）
负责：/api/feedback, /api/feedback/v2, /api/behavior,
      /api/user/preferences
"""
import os, json, time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.config import LOG_DIR, FEEDBACK_DIR, DATA_DIR
from src.db.data_store import log_behavior, get_user_preferences, save_user_preferences
import logging; logger = logging.getLogger(__name__)

router = APIRouter(tags=["反馈与用户"])


class FeedbackRequest(BaseModel):
    query: str = ""
    answer_preview: str = ""
    useful: bool = True
    timestamp: str = ""


def _get_user_id(request: Request) -> str:
    uid = request.headers.get("x-user-id", "")
    if not uid:
        uid = request.client.host if request.client else "unknown"
    return uid


# ============ 用户偏好 ============

@router.get("/api/user/preferences")
async def get_user_prefs(request: Request):
    uid = _get_user_id(request)
    prefs = get_user_preferences(uid)
    return {"user_id": uid[:16], "preferences": prefs}


@router.post("/api/user/preferences")
async def save_user_prefs(request: Request):
    uid = _get_user_id(request)
    body = await request.json()
    save_user_preferences(uid, body.get("preferences", {}))
    return {"status": "ok"}


# ============ 行为日志 ============

@router.post("/api/behavior")
async def behavior_log(request: Request):
    """用户行为日志（点击/复制/展开）"""
    try:
        body = await request.json()
    except Exception:
        return {"status": "ignored"}
    log_behavior(body)
    return {"status": "ok"}


# ============ 反馈（旧版）============

@router.post("/api/feedback")
async def feedback(req: FeedbackRequest):
    """用户反馈（有用/无用）"""
    fb_file = LOG_DIR / f"feedback_{datetime.now().strftime('%Y%m%d')}.jsonl"
    with open(fb_file, "a", encoding="utf-8") as f:
        json.dump(req.dict(), f, ensure_ascii=False)
        f.write("\n")
    # 反馈学习闭环
    try:
        from src.services.learner import log_feedback as lf
        action = req.dict().get("action", "like")
        query = req.dict().get("query", "")
        fhash = req.dict().get("file_hash", "")
        cid = req.dict().get("chunk_index", 0)
        correction = req.dict().get("correction", "")
        lf(query, fhash, cid, action, correction)
    except Exception:
        logger.warning(f"[feedback] suppressed exception", exc_info=True)
        pass
    return {"status": "ok", "learned": True}


# ============ 反馈（增强版 v2）============


@router.get("/api/feedback/daily")
async def feedback_daily():
    try:
        from src.services.feedback_loop import daily_feedback_report
        return daily_feedback_report()
    except ModuleNotFoundError:
        return {"feedbacks": [], "message": "feedback_loop service not available"}

@router.get("/api/feedback/weekly")
async def feedback_weekly():
    try:
        from src.services.feedback_loop import analyze_search_quality
        return analyze_search_quality(days=7)
    except ModuleNotFoundError:
        return {"feedbacks": [], "message": "feedback_loop service not available"}

@router.get("/api/feedback/monthly")
async def feedback_monthly():
    try:
        from src.services.feedback_loop import analyze_search_quality
        return analyze_search_quality(days=30)
    except ModuleNotFoundError:
        return {"feedbacks": [], "message": "feedback_loop service not available"}

@router.post("/api/feedback/v2")
async def feedback_v2(request: Request):
    """增强反馈：记录搜索上下文、隐式反馈、纠错"""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")

    query = body.get("query", "")
    action = body.get("action", "click")
    fhash = body.get("file_hash", "")
    chunk_index = body.get("chunk_index", 0)
    correction = body.get("correction", "")
    chunk_preview = body.get("chunk_preview", "")
    search_results = body.get("search_results", [])
    implicit = body.get("implicit", False)

    # 日志
    log_entry = {
        "time": datetime.now(timezone.utc).isoformat(),
        "query": query[:300],
        "action": action,
        "file_hash": fhash,
        "chunk_index": chunk_index,
        "correction": correction[:500],
        "chunk_preview": chunk_preview[:300],
        "search_results": search_results,
        "implicit": implicit,
    }

    fb_file = FEEDBACK_DIR / f"feedback_v2_{datetime.now().strftime('%Y%m%d')}.jsonl"
    with open(fb_file, "a", encoding="utf-8") as f:
        json.dump(log_entry, f, ensure_ascii=False)
        f.write("\n")

    # 反馈学习
    if not implicit:
        try:
            from src.services.learner import log_feedback as lf
            lf(query, fhash, chunk_index, action, correction)
            for sr in search_results[:5]:
                lf(query, sr.get("hash", ""), sr.get("idx", 0),
                   "relevance_" + action, "", "search")
        except Exception:
            logger.warning(f"[feedback] suppressed exception", exc_info=True)
            pass

    # 纠错存档
    if action == "correct" and correction:
        corr_file = FEEDBACK_DIR / "corrections.jsonl"
        with open(corr_file, "a", encoding="utf-8") as f:
            json.dump({
                "time": datetime.now(timezone.utc).isoformat(),
                "query": query, "file_hash": fhash,
                "chunk_index": chunk_index,
                "original": chunk_preview[:300],
                "correction": correction,
            }, f, ensure_ascii=False)
            f.write("\n")

    # P6: 记录反馈到记忆系统
    try:
        from src.services.memory_system import record_experience
        record_experience(
            action=f"feedback_{action}",
            detail=f"query={query[:80]} hash={fhash} correction={correction[:50]}",
            outcome="ok",
            tags=["feedback", action]
        )
    except Exception:
        logger.warning(f"[feedback] suppressed exception", exc_info=True)
        pass
    
    return {"status": "ok", "action": action, "implicit": implicit}


# ============ 任务状态 ============

@router.get("/api/task/{task_id}")
async def task_status(task_id: str):
    return {"status": "not_found"}
