"""
feedback_fix.py — 反馈闭环修复
================================
修复内容：
1. learner import 失败时不再静默跳过，记录明确日志
2. 反馈数据结构统一
3. 添加反馈学习的状态追踪
"""

import os
import json
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Optional
from pathlib import Path

from src.config import LOG_DIR, DATA_DIR

logger = logging.getLogger(__name__)

# 反馈学习状态文件
FEEDBACK_STATE_FILE = DATA_DIR / "feedback_state.json"


def _load_state() -> dict:
    if FEEDBACK_STATE_FILE.exists():
        try:
            return json.loads(FEEDBACK_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"total_feedbacks": 0, "last_learned": None, "pending": 0, "errors": []}


def _save_state(state: dict):
    FEEDBACK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    FEEDBACK_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def log_feedback_unified(
    query: str,
    file_hash: str,
    chunk_index: int,
    action: str,  # "like", "dislike", "click", "copy", "correction"
    correction: str = "",
    user_id: str = "",
    search_results: list = None,
) -> Dict:
    """统一反馈记录 + 学习触发"""
    
    state = _load_state()
    state["total_feedbacks"] = state.get("total_feedbacks", 0) + 1
    
    # 1. 写入日志文件（始终成功）
    log_entry = {
        "time": datetime.now(timezone.utc).isoformat(),
        "query": query[:300],
        "action": action,
        "file_hash": file_hash,
        "chunk_index": chunk_index,
        "correction": correction[:500] if correction else "",
        "user_id": user_id,
    }
    
    log_file = LOG_DIR / f"feedback_{datetime.now().strftime('%Y%m%d')}.jsonl"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            json.dump(log_entry, f, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        logger.error(f"[Feedback] log write failed: {e}")
    
    # 2. 触发学习（关键修复点）
    learned = False
    try:
        from src.services.learner import log_feedback as lf
        lf(query, file_hash, chunk_index, action, correction)
        learned = True
        logger.info(f"[Feedback] learned: action={action} query='{query[:50]}'")
    except ImportError:
        logger.error(
            "[Feedback] learner module NOT INSTALLED — "
            "feedback logged but NOT learned. "
            "Install: pip install <learner module> or check src/services/learner.py"
        )
        state["pending"] = state.get("pending", 0) + 1
        state["errors"].append({
            "time": datetime.now().isoformat(),
            "error": "learner module not installed",
            "query": query[:100],
        })
        # 只保留最近 20 条错误
        state["errors"] = state["errors"][-20:]
    except Exception as e:
        logger.error(f"[Feedback] learning failed: {e}", exc_info=True)
        state["pending"] = state.get("pending", 0) + 1
        state["errors"].append({
            "time": datetime.now().isoformat(),
            "error": str(e)[:200],
            "query": query[:100],
        })
        state["errors"] = state["errors"][-20:]
    
    state["last_learned"] = datetime.now().isoformat() if learned else state.get("last_learned")
    _save_state(state)
    
    return {
        "logged": True,
        "learned": learned,
        "pending_learning": state.get("pending", 0),
    }


def get_feedback_stats() -> Dict:
    """获取反馈学习状态"""
    state = _load_state()
    
    # 统计今天的反馈数
    today_file = LOG_DIR / f"feedback_{datetime.now().strftime('%Y%m%d')}.jsonl"
    today_count = 0
    if today_file.exists():
        try:
            with open(today_file, "r", encoding="utf-8") as f:
                today_count = sum(1 for _ in f)
        except Exception:
            pass
    
    return {
        "total_feedbacks": state.get("total_feedbacks", 0),
        "today_feedbacks": today_count,
        "pending_learning": state.get("pending", 0),
        "last_learned": state.get("last_learned"),
        "recent_errors": state.get("errors", [])[-5:],
    }


# ============================================================
# 反馈路由修复（替换 feedback.py 中的 feedback 函数）
# ============================================================

def feedback_handler_fixed(req_body: dict) -> dict:
    """修复版反馈处理 — 不再静默失败"""
    query = req_body.get("query", "")
    action = req_body.get("action", "like")
    file_hash = req_body.get("file_hash", "")
    chunk_index = req_body.get("chunk_index", 0)
    correction = req_body.get("correction", "")
    user_id = req_body.get("user_id", "")
    
    result = log_feedback_unified(
        query=query,
        file_hash=file_hash,
        chunk_index=chunk_index,
        action=action,
        correction=correction,
        user_id=user_id,
    )
    
    return {
        "status": "ok",
        "learned": result["learned"],
        "pending_learning": result["pending_learning"],
        "message": "反馈已记录" + ("，学习模块不可用，待处理" if not result["learned"] else "，已学习"),
    }
