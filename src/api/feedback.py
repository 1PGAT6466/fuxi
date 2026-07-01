# 兼容层 - 反馈路由
from fastapi import APIRouter

router = APIRouter(tags=["反馈"])

@router.get("/api/feedback/weekly")
async def feedback_weekly():
    """每周反馈"""
    return {"feedbacks": []}

@router.post("/api/feedback")
async def feedback():
    """提交反馈"""
    return {"ok": True}
