# 兼容层 - v2路由
from fastapi import APIRouter

router = APIRouter(tags=["v2"])

@router.get("/api/v2/status")
async def v2_status():
    """v2状态"""
    return {"status": "ok"}
