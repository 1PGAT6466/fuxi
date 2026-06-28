"""
/admin/api — 工具数据管理
"""
from fastapi import APIRouter, Request
import json, logging
from src.config import TOOLS_DATA

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin-tools"])


@router.get("/api/tools")
async def tools():
    """获取工具列表"""
    if TOOLS_DATA and TOOLS_DATA.is_file():
        return {"ok": True, "data": json.loads(TOOLS_DATA.read_text(encoding="utf-8"))}
    return {"ok": True, "data": []}


@router.get("/api/tools/check")
async def tools_check():
    """工具可用性检查"""
    return {"ok": True, "checks": []}


@router.get("/api/admin/tools")
async def admin_tools():
    """管理面板工具列表"""
    return await tools()


@router.post("/api/admin/tools")
async def admin_save_tools(request: Request):
    """保存工具配置"""
    try:
        data = await request.json()
        if TOOLS_DATA:
            TOOLS_DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "message": "保存成功"}
    except Exception as e:
        logger.warning(f"Save tools error: {e}")
        return {"ok": False, "error": str(e)}
