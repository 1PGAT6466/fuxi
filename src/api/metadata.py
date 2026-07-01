# 兼容层 - 元数据路由
from fastapi import APIRouter

router = APIRouter(tags=["元数据"])

@router.get("/api/metadata")
async def metadata():
    """元数据"""
    return {"metadata": []}
