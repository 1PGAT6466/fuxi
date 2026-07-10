"""
feedback.py - 反馈路由
数据来源: feedback_store.py + 文件持久化
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
        except (OSError, IOError) as e:
            logger.warning(f"读取反馈文件失败 {fname}: {e}")
    return entries


@router.get("/api/feedback/weekly")
async def get_weekly_feedback():
    """获取最近一周的反馈数据"""
    try:
        entries = _load_feedback_files(days=7)
        return {
            "status": "success",
            "data": {
                "entries": entries,
                "count": len(entries),
                "period_days": 7
            }
        }
    except (OSError, IOError, ValueError) as e:
        logger.exception(f"获取反馈数据失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@router.post("/api/feedback")
async def submit_feedback(request: Request):
    """提交用户反馈"""
    try:
        data = await request.json()
        entry = {
            "timestamp": time.time(),
            "query": data.get("query", ""),
            "answer": data.get("answer", ""),
            "rating": data.get("rating", 0),
            "comment": data.get("comment", ""),
            "user": data.get("user", "anonymous"),
        }
        os.makedirs(FEEDBACK_DIR, exist_ok=True)
        fname = f"feedback_{time.strftime('%Y%m%d')}.jsonl"
        fpath = os.path.join(FEEDBACK_DIR, fname)
        with open(fpath, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return {"status": "success", "message": "反馈已提交"}
    except (OSError, IOError, json.JSONDecodeError, ValueError) as e:
        logger.exception(f"提交反馈失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )
