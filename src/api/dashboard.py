# 兼容层 - 仪表板路由
from fastapi import APIRouter

router = APIRouter(tags=["仪表板"])

@router.get("/api/dashboard")
async def dashboard():
    """仪表板"""
    return {"dashboard": {}}
