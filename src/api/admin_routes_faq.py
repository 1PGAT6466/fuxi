"""
/admin/api — FAQ 数据管理
"""
from fastapi import APIRouter, Request
import json, logging
from src.config import FAQ_DATA

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin-faq"])


@router.get("/api/faq")
async def faq():
    """获取 FAQ"""
    if FAQ_DATA and FAQ_DATA.is_file():
        return {"ok": True, "data": json.loads(FAQ_DATA.read_text(encoding="utf-8"))}
    return {"ok": True, "data": []}


@router.get("/api/admin/faq")
async def admin_faq():
    """管理面板 FAQ"""
    return await faq()


@router.post("/api/admin/faq")
async def admin_save_faq(request: Request):
    """保存 FAQ"""
    try:
        data = await request.json()
        if FAQ_DATA:
            FAQ_DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "message": "保存成功"}
    except Exception as e:
        logger.warning(f"Save FAQ error: {e}")
        return {"ok": False, "error": str(e)}
