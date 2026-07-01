# 兼容层 - 评测路由
from fastapi import APIRouter

router = APIRouter(tags=["评测"])

@router.get("/api/evaluation/overview")
async def evaluation_overview():
    """评测概览"""
    return {"search_stats": {}, "rag_eval": {}, "test_cases_count": 0}
