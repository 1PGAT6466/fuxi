# v2.1 双路由开关 — 对话路由（v1 ShaoyinBrain + v2 乾卦意图循环）
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
import uuid

router = APIRouter(tags=["AI 对话"])


class ChatRequest(BaseModel):
    query: str
    history: List[dict] = []
    stream: bool = False
    granularity: Optional[str] = "chunk"  # 任务 4: chunk/event/auto


@router.post("/api/chat")
async def chat(body: ChatRequest, request: Request = None):
    """对话端点 — v2.1 双路由开关

    查询参数 engine：
      - 不传 / engine=v1 → 旧路径（ShaoyinBrain）
      - engine=v2       → 乾卦意图循环路径（QianGua.think）
    """
    engine = request.query_params.get("engine", "v1") if request else "v1"

    if engine == "v2":
        return await _chat_v2(body, request)
    else:
        return await _chat_v1(body, request)


async def _chat_v1(body: ChatRequest, request: Optional[Request] = None):
    """v1 路径：ShaoyinBrain（保留现有逻辑）"""
    from src.api.response import success, error
    try:
        from src.shaoyin.brain import ShaoyinBrain
        # v2.1: Meridian 已废弃，v1 fallback 使用 IntentBus 兼容接口
        from src.bagua.intent_bus import IntentBus

        intent_bus = IntentBus()
        brain = ShaoyinBrain(intent_bus)
        result = await brain.think(body.query, body.history)

        answer_data = {
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "mode": "shaoyin",
            "confidence": result.get("confidence", 0),
        }

        # 向后兼容: 默认返回旧格式 {answer, sources, mode, confidence}
        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            return success(data=answer_data, message="对话完成")
        return answer_data
    except Exception as e:
        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            return error("对话失败", status_code=500, detail=str(e))
        return {"answer": f"处理失败: {str(e)}", "sources": [], "mode": "error"}


async def _chat_v2(body: ChatRequest, request: Optional[Request] = None):
    """v2 路径：乾卦意图循环路径

    通过 QianGua.think() 执行完整的意图循环：
    LLM 决策 → IntentBus 派发 → 目标卦执行 → 结果回收 → 再决策 → DONE
    """
    try:
        from src.bagua.qian import QianGua
        from src.bagua.intent_bus import get_intent_bus

        bus = get_intent_bus()
        qian = QianGua(intent_bus=bus)
        qian.start()

        result = await qian.think(
            query=body.query,
            history=body.history,
            session_id=str(uuid.uuid4()),
        )

        return {
            "answer": result.get("answer", ""),
            "sources": result.get("intents_used", []),
            "mode": "qian",
            "confidence": _compute_qian_confidence(result),
        }
    except Exception as e:
        return {
            "answer": f"乾卦路径处理失败: {str(e)}",
            "sources": [],
            "mode": "qian-error",
            "confidence": 0,
        }


def _compute_qian_confidence(result: dict) -> float:
    """从乾卦 think() 结果中估算置信度

    规则（按优先级从高到低）：
      - 执行了搜索且轮数 ≤ 4 且无降级 → 0.9
      - 轮数过多 (> 6) 且降级 → 0.2
      - 执行了搜索但使用了降级 → 0.6
      - 无搜索 → 0.3
      - 其他 → 0.5
    """
    intents = result.get("intents_used", [])
    rounds = result.get("rounds", 0)
    fallback = result.get("fallback_used", False)

    has_search = any(i in ("SEARCH", "SEARCH_X") for i in intents)

    if has_search and not fallback and rounds <= 4:
        return 0.9
    elif rounds > 6 and fallback:
        return 0.2
    elif has_search and fallback:
        return 0.6
    elif not has_search:
        return 0.3
    return 0.5

@router.post("/api/chat/agent")
async def chat_agent(body: ChatRequest):
    """Agent对话端点"""
    return await chat(body, None)
