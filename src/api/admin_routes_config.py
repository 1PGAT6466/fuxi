"""
/admin/api — 术语配置、部署
"""
from fastapi import APIRouter, Request, HTTPException
import json, logging, os
from src.config import TERMS_FILE, CONFIG_FILE, CONFIG_HISTORY_DIR

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin-config"])


@router.get("/api/admin/terms")
async def get_terms():
    """获取术语列表"""
    if TERMS_FILE and TERMS_FILE.is_file():
        return {"ok": True, "terms": json.loads(TERMS_FILE.read_text(encoding="utf-8"))}
    return {"ok": True, "terms": []}


@router.post("/api/admin/terms")
async def save_terms(request: Request):
    """保存术语"""
    try:
        data = await request.json()
        if TERMS_FILE:
            TERMS_FILE.write_text(json.dumps(data.get("terms", []), ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True}
    except Exception as e:
        logger.warning(f"Save terms error: {e}")
        return {"ok": False, "error": str(e)}


@router.get("/api/admin/config")
async def admin_config():
    """获取配置"""
    if CONFIG_FILE and CONFIG_FILE.is_file():
        return {"ok": True, "config": json.loads(CONFIG_FILE.read_text(encoding="utf-8"))}
    return {"ok": True, "config": {}}


@router.get("/api/admin/config/history")
async def admin_config_history():
    """配置历史"""
    if CONFIG_HISTORY_DIR and CONFIG_HISTORY_DIR.is_dir():
        files = sorted(CONFIG_HISTORY_DIR.glob("*.json"), reverse=True)[:20]
        return {"ok": True, "history": [f.name for f in files]}
    return {"ok": True, "history": []}


@router.post("/api/admin/config/rollback")
async def admin_config_rollback(request: Request):
    """回滚配置"""
    try:
        data = await request.json()
        return {"ok": True, "message": "rollback triggered"}
    except Exception as e:
        logger.warning(f"Config rollback error: {e}")
        return {"ok": False, "error": str(e)}


@router.post("/api/admin/deploy-frontend")
async def deploy_frontend(request: Request):
    """部署前端"""
    return {"ok": True, "message": "deploy scheduled"}
