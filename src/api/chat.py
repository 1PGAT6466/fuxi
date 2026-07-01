# 兼容层 - 对话路由
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(tags=["AI 对话"])

class ChatRequest(BaseModel):
    query: str
    history: List[dict] = []
    stream: bool = False

@router.post("/api/chat")
async def chat(body: ChatRequest, request: Request):
    """对话端点"""
    try:
        from src.shaoyin.brain import ShaoyinBrain
        from src.hypothalamus.meridian import Meridian
        
        meridian = Meridian()
        brain = ShaoyinBrain(meridian)
        result = await brain.think(body.query, body.history)
        
        return {
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "mode": "shaoyin",
            "confidence": result.get("confidence", 0),
        }
    except Exception as e:
        return {"answer": f"处理失败: {str(e)}", "sources": [], "mode": "error"}

@router.post("/api/chat/agent")
async def chat_agent(body: ChatRequest):
    """Agent对话端点"""
    return await chat(body, None)
