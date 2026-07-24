"""
伏羲 v2.1 — 跨窗口剪贴板 API

提供剪贴板内容同步、历史管理、收藏等后端能力。

API 端点：
  POST   /api/clipboard/sync              — 同步剪贴板内容
  GET    /api/clipboard/history            — 获取历史记录
  GET    /api/clipboard/history/:entryId   — 获取单条记录
  DELETE /api/clipboard/history            — 清空历史
  PATCH  /api/clipboard/:entryId/favorite  — 切换收藏状态
  DELETE /api/clipboard/:entryId           — 删除单条
  POST   /api/clipboard/batch-delete       — 批量删除

数据存储：JSON 文件持久化在 data/clipboard/ 目录下
"""
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
import logging
import time
import os
import json
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(tags=["跨窗口剪贴板"])

# ═══════════════════════════════════════════
# 配置 & 存储路径
# ═══════════════════════════════════════════

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CLIPBOARD_DIR = os.path.join(_BASE_DIR, "data", "clipboard")
_CLIPBOARD_FILE = os.path.join(_CLIPBOARD_DIR, "history.json")
_FAVORITES_FILE = os.path.join(_CLIPBOARD_DIR, "favorites.json")

# 最大缓存条目数
_MAX_HISTORY_SIZE = 200

# 条目过期时间（秒）— 7 天
_EXPIRY_SECONDS = 7 * 24 * 3600


def _ensure_dir():
    """确保数据目录存在"""
    os.makedirs(_CLIPBOARD_DIR, exist_ok=True)


def _load_records() -> list:
    """加载所有剪贴板历史记录"""
    _ensure_dir()
    if os.path.exists(_CLIPBOARD_FILE):
        try:
            with open(_CLIPBOARD_FILE, "r", encoding="utf-8") as f:
                records = json.load(f)
                return records if isinstance(records, list) else []
        except (json.JSONDecodeError, IOError):
            pass
    return []


def _save_records(records: list):
    """保存剪贴板历史记录"""
    _ensure_dir()
    # 限制最大条目数
    if len(records) > _MAX_HISTORY_SIZE:
        records = records[:_MAX_HISTORY_SIZE]
    try:
        with open(_CLIPBOARD_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"保存剪贴板历史失败: {e}")


def _load_favorites() -> dict:
    """加载收藏列表 (entryId -> bool)"""
    _ensure_dir()
    if os.path.exists(_FAVORITES_FILE):
        try:
            with open(_FAVORITES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_favorites(favorites: dict):
    """保存收藏列表"""
    _ensure_dir()
    try:
        with open(_FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump(favorites, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"保存收藏列表失败: {e}")


def _clean_expired_records(records: list) -> tuple:
    """清理过期记录，返回 (有效记录, 移除数量)"""
    now = time.time()
    valid = []
    removed = 0
    for r in records:
        created = r.get("createdAt") or r.get("timestamp", 0)
        if isinstance(created, str):
            try:
                # ISO format → timestamp
                from datetime import datetime
                created = datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp()
            except (ValueError, AttributeError):
                created = 0
        if now - created > _EXPIRY_SECONDS:
            removed += 1
        else:
            valid.append(r)
    return valid, removed


# ═══════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════


@router.post("/api/clipboard/sync")
async def sync_clipboard(request: Request):
    """
    同步剪贴板内容到服务端

    POST /api/clipboard/sync
    Body: {
      windowId: str,
      serviceName?: str,
      entry: {
        format: 'text'|'html'|'json'|'image-ref'|'file-ref',
        plainText: str,
        formattedContent?: str,
        referencePath?: str,
        sourceWindowId?: str,
        sourceService?: str,
        size?: int,
        metadata?: dict
      }
    }
    """
    try:
        body = await request.json()
        window_id = body.get("windowId", "unknown")
        service_name = body.get("serviceName", "")
        entry_data = body.get("entry", {})

        if not entry_data.get("plainText"):
            return JSONResponse(
                content={"success": False, "message": "plainText 不能为空"},
                status_code=400,
            )

        # 生成条目 ID
        entry_id = f"clip-server-{uuid.uuid4().hex[:12]}"

        # 创建完整条目
        entry = {
            "id": entry_id,
            "format": entry_data.get("format", "text"),
            "plainText": entry_data.get("plainText", ""),
            "formattedContent": entry_data.get("formattedContent"),
            "referencePath": entry_data.get("referencePath"),
            "sourceWindowId": entry_data.get("sourceWindowId", window_id),
            "sourceService": entry_data.get("sourceService", service_name),
            "isFavorite": False,
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "size": entry_data.get("size", len(entry_data.get("plainText", "").encode("utf-8"))),
            "metadata": entry_data.get("metadata"),
        }

        # 读取现有记录
        records = _load_records()

        # 清理过期记录
        records, removed = _clean_expired_records(records)
        if removed:
            logger.info(f"已清理 {removed} 条过期剪贴板记录")

        # 插入到最前
        records.insert(0, entry)

        # 限制最大条目数
        if len(records) > _MAX_HISTORY_SIZE:
            records = records[:_MAX_HISTORY_SIZE]

        _save_records(records)

        logger.info(f"剪贴板同步: window={window_id}, entry={entry_id}, total={len(records)}")
        return JSONResponse(
            content={
                "success": True,
                "entryId": entry_id,
                "totalCount": len(records),
            }
        )

    except Exception as e:
        logger.error(f"剪贴板同步失败: {e}")
        return JSONResponse(
            content={"success": False, "message": str(e)},
            status_code=500,
        )


@router.get("/api/clipboard/history")
async def get_clipboard_history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    format: str = Query(default=None),
    favoritesOnly: bool = Query(default=False),
    search: str = Query(default=None),
):
    """
    获取剪贴板历史记录

    GET /api/clipboard/history?limit=50&offset=0&format=text&favoritesOnly=false&search=keyword
    """
    try:
        records = _load_records()

        # 清理过期记录
        records, removed = _clean_expired_records(records)
        if removed:
            _save_records(records)
            logger.info(f"查询时清理了 {removed} 条过期记录")

        # 加载收藏状态
        favorites = _load_favorites()
        for r in records:
            r["isFavorite"] = favorites.get(r["id"], False)

        # 过滤
        filtered = records

        if favoritesOnly:
            filtered = [r for r in filtered if r.get("isFavorite", False)]

        if format:
            filtered = [r for r in filtered if r.get("format") == format]

        if search:
            q = search.lower().strip()
            filtered = [
                r for r in filtered
                if q in (r.get("plainText", "") or "").lower()
                or q in (r.get("formattedContent", "") or "").lower()
                or q in (r.get("sourceService", "") or "").lower()
            ]

        total = len(filtered)

        # 分页
        page = filtered[offset:offset + limit]

        return JSONResponse(
            content={
                "entries": page,
                "total": total,
                "cached": len(records),
            }
        )

    except Exception as e:
        logger.error(f"获取剪贴板历史失败: {e}")
        return JSONResponse(
            content={"entries": [], "total": 0, "cached": 0, "error": str(e)},
            status_code=500,
        )


@router.patch("/api/clipboard/{entry_id}/favorite")
async def toggle_clipboard_favorite(entry_id: str, request: Request):
    """
    切换条目收藏状态

    PATCH /api/clipboard/:entryId/favorite
    Body: { "isFavorite": true|false }
    """
    try:
        body = await request.json()
        is_fav = body.get("isFavorite", False)

        favorites = _load_favorites()

        if is_fav:
            favorites[entry_id] = True
            logger.info(f"收藏条目: {entry_id}")
        else:
            favorites.pop(entry_id, None)
            logger.info(f"取消收藏条目: {entry_id}")

        _save_favorites(favorites)

        # 同时更新历史记录中的状态
        records = _load_records()
        updated = False
        for r in records:
            if r["id"] == entry_id:
                r["isFavorite"] = is_fav
                updated = True
                break
        if updated:
            _save_records(records)

        return JSONResponse(
            content={"success": True, "entryId": entry_id}
        )

    except Exception as e:
        logger.error(f"切换收藏状态失败: {e}")
        return JSONResponse(
            content={"success": False, "message": str(e)},
            status_code=500,
        )


@router.delete("/api/clipboard/{entry_id}")
async def delete_clipboard_entry(entry_id: str):
    """
    删除单条剪贴板条目

    DELETE /api/clipboard/:entryId
    """
    try:
        records = _load_records()
        original_len = len(records)

        records = [r for r in records if r["id"] != entry_id]

        if len(records) == original_len:
            return JSONResponse(
                content={"success": False, "message": "条目不存在"},
                status_code=404,
            )

        _save_records(records)

        # 同时清理收藏
        favorites = _load_favorites()
        favorites.pop(entry_id, None)
        _save_favorites(favorites)

        logger.info(f"已删除剪贴板条目: {entry_id}")
        return JSONResponse(
            content={"success": True, "entryId": entry_id}
        )

    except Exception as e:
        logger.error(f"删除剪贴板条目失败: {e}")
        return JSONResponse(
            content={"success": False, "message": str(e)},
            status_code=500,
        )


@router.post("/api/clipboard/batch-delete")
async def batch_delete_clipboard_entries(request: Request):
    """
    批量删除剪贴板条目

    POST /api/clipboard/batch-delete
    Body: { "entryIds": ["id1", "id2", ...] }
    """
    try:
        body = await request.json()
        entry_ids = body.get("entryIds", [])

        if not entry_ids:
            return JSONResponse(
                content={"success": False, "message": "entryIds 不能为空"},
                status_code=400,
            )

        id_set = set(entry_ids)
        records = _load_records()
        original_len = len(records)

        records = [r for r in records if r["id"] not in id_set]
        affected = original_len - len(records)

        _save_records(records)

        # 清理收藏
        favorites = _load_favorites()
        for eid in entry_ids:
            favorites.pop(eid, None)
        _save_favorites(favorites)

        logger.info(f"批量删除剪贴板条目: {affected} 条")
        return JSONResponse(
            content={"success": True, "affectedCount": affected}
        )

    except Exception as e:
        logger.error(f"批量删除剪贴板条目失败: {e}")
        return JSONResponse(
            content={"success": False, "message": str(e)},
            status_code=500,
        )


@router.delete("/api/clipboard/history")
async def clear_clipboard_history():
    """
    清空所有剪贴板历史

    DELETE /api/clipboard/history
    """
    try:
        _save_records([])
        _save_favorites({})
        logger.info("剪贴板历史已清空")
        return JSONResponse(
            content={"success": True, "totalCount": 0}
        )

    except Exception as e:
        logger.error(f"清空剪贴板历史失败: {e}")
        return JSONResponse(
            content={"success": False, "message": str(e)},
            status_code=500,
        )
