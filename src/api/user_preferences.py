"""
v2.1 — 用户偏好 API（真实持久化版）
数据来源：data/user_preferences/ 目录下每个用户的 JSON 文件
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging
import json
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user", tags=["用户偏好"])

# v1.50 R4: Use config DATA_DIR for consistent path resolution
from src.config import DATA_DIR as _CFG_DATA_DIR
_PREFS_DIR = os.path.join(str(_CFG_DATA_DIR), "user_preferences")


DEFAULT_PREFERENCES = {
    "theme": "system",
    "language": "zh-CN",
    "notifications_enabled": True,
    "sidebar_collapsed": False,
    "default_engine": "v2",
}


def _ensure_prefs_dir():
    os.makedirs(_PREFS_DIR, exist_ok=True)


def _get_prefs_path(username: str) -> str:
    """获取用户偏好文件路径"""
    _ensure_prefs_dir()
    # 防止路径遍历
    safe_name = "".join(c for c in username if c.isalnum() or c in "-_.")
    if not safe_name:
        safe_name = "anonymous"
    return os.path.join(_PREFS_DIR, f"{safe_name}.json")


def _load_preferences(username: str) -> dict:
    """加载用户偏好"""
    path = _get_prefs_path(username)
    if not os.path.exists(path):
        return dict(DEFAULT_PREFERENCES)

    try:
        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        # 合并默认值（确保缺失的 key 有默认值）
        merged = dict(DEFAULT_PREFERENCES)
        merged.update(saved)
        return merged
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"读取用户偏好失败 {username}: {e}")
        return dict(DEFAULT_PREFERENCES)


def _save_preferences(username: str, prefs: dict):
    """保存用户偏好"""
    _ensure_prefs_dir()
    path = _get_prefs_path(username)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(prefs, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"保存用户偏好失败 {username}: {e}")
        raise


@router.get("/preferences")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def get_user_preferences(request: Request = None):
    """获取当前用户偏好 — 从持久化文件读取"""
    try:
        username = getattr(request.state, "user", "anonymous") if request else "anonymous"
        prefs = _load_preferences(username)

        # v1.50 R5: 统一返回格式 {status: "ok", data: {...}}
        return {"status": "ok", "data": {"preferences": prefs}}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"get_user_preferences 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


@router.put("/preferences")
async def update_user_preferences(request: Request):
    """更新用户偏好 — 持久化到文件"""
    try:
        body = await request.json()
        username = getattr(request.state, "user", "anonymous") if request else "anonymous"

        # 加载现有偏好，合并更新
        current = _load_preferences(username)
        # 只接受合法字段
        allowed_keys = set(DEFAULT_PREFERENCES.keys())
        for key, value in body.items():
            if key in allowed_keys:
                current[key] = value

        _save_preferences(username, current)
        logger.info(f"[user_preferences] {username} 更新偏好: {list(body.keys())}")

        return {"preferences": current, "ok": True, "message": "偏好已保存"}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"update_user_preferences 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )
