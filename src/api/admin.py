"""
routers/admin.py — 管理面板路由（v1.41）
仅负责：静态页面路由 + 子路由挂载。API 实现在各个 admin_routes_*.py 中。
"""
import os, json, hashlib
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse

from src.config import STATIC_DIR, ADMIN_DIR, VERSION

router = APIRouter(tags=["admin"])

# ============ v1.41: 子路由挂载（各模块使用独立路径，无冲突） ============
from src.api.admin_routes_health import router as health_router
from src.api.admin_routes_organs import router as organs_router
from src.api.admin_routes_tools import router as tools_router
from src.api.admin_routes_faq import router as faq_router
from src.api.admin_routes_config import router as config_router
from src.api.admin_routes_data import router as data_router

router.include_router(health_router)
router.include_router(organs_router)
router.include_router(tools_router)
router.include_router(faq_router)
router.include_router(config_router)
router.include_router(data_router)


# ============ 主平台前端页面 ============

@router.get("/")
async def root():
    """伏羲主平台首页"""
    p = STATIC_DIR / "index.html"
    if p.exists():
        content = p.read_text(encoding="utf-8")
        etag = hashlib.md5(content.encode()).hexdigest()
        return HTMLResponse(content, headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0, private",
            "Pragma": "no-cache", "Expires": "0",
            "ETag": f'"{etag}"', "X-Content-Version": etag[:8],
        })
    return HTMLResponse(f"<h1>伏羲 · 企业知识生命体 v{VERSION}</h1>")


@router.get("/admin", response_class=HTMLResponse)
async def admin_home():
    """管理面板首页"""
    p = ADMIN_DIR / "index.html"
    if p.exists():
        content = p.read_text(encoding="utf-8")
        return HTMLResponse(content, headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache", "Expires": "0",
        })
    return HTMLResponse("<h1>管理面板未部署</h1>")


@router.get("/admin/{path:path}")
async def admin_files(path: str):
    """管理面板静态资源"""
    full = ADMIN_DIR / path
    if not os.path.realpath(full).startswith(os.path.realpath(str(ADMIN_DIR))):
        raise HTTPException(status_code=403)
    import mimetypes
    if full.is_file():
        mime, _ = mimetypes.guess_type(str(full))
        return FileResponse(str(full), media_type=mime)
    p = ADMIN_DIR / "index.html"
    if p.exists():
        return HTMLResponse(p.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404)
"""v1.42 管理 API 路由 — 真皮层数据接口"""
from fastapi import APIRouter
from typing import Dict, Any


@router.get("/data")
async def admin_data() -> Dict[str, Any]:
    """返回管理仪表盘数据"""
    import sys
    sys.path.insert(0, '/home/feng-shaoxuan/伏羲·内世界')
    from src.hypothalamus.meridian import Meridian
    # 获取全局 meridian 实例
    try:
        from src.server import _fuxi
        if _fuxi and _fuxi.meridian:
            m = _fuxi.meridian
            organs_status = {}
            for oid, info in m._organs.items():
                organs_status[oid] = {
                    "alive": m.is_alive(oid),
                    "signals_received": info.signals_received,
                    "last_heartbeat_ago": round(__import__('time').time() - info.last_heartbeat, 1),
                }
            return {
                "ok": True,
                "organs": organs_status,
                "organs_alive": sum(1 for o in organs_status.values() if o["alive"]),
                "version": "1.42",
                "timestamp": __import__('datetime').datetime.now().isoformat(),
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.get("/organs")
async def admin_organs() -> Dict[str, Any]:
    """返回器官详细信息"""
    try:
        from src.server import _fuxi
        if _fuxi and _fuxi.meridian:
            m = _fuxi.meridian
            organs = []
            for oid, info in m._organs.items():
                organs.append({
                    "id": oid,
                    "name": info.name if hasattr(info, 'name') else oid,
                    "alive": m.is_alive(oid),
                    "signals_received": info.signals_received,
                    "last_heartbeat_ago": round(__import__('time').time() - info.last_heartbeat, 1),
                })
            return {"ok": True, "organs": organs, "total": len(organs)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
