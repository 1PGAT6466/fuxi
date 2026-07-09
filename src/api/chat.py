# v2.1 双路由开关 — 对话路由（v1 ShaoyinBrain + v2 乾卦意图循环）
# v1.44 Phase 1 Fix: 新增会话管理 + SSE流式 + 历史消息端点
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, field_validator
from typing import List, Optional
import uuid
import json
import time
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI 对话"])

# ============ 持久化会话存储（SQLite）============
# v2.1: 使用 SQLite 持久化，重启不丢失会话和消息
# v1.50 R5: 统一使用 data_service.py 的连接管理，消除散落的 sqlite3.connect

from src.data_service import (
    ensure_chat_tables as _ensure_chat_tables,
    load_all_chat_sessions,
    save_session_to_db as _save_session_to_db_svc,
    save_message_to_db as _save_message_to_db_svc,
    delete_session_from_db as _delete_session_from_db_svc,
)

# 内存缓存层（加速热点访问）
_sessions_store: dict = {}
_messages_store: dict = {}


def _load_sessions_from_db():
    """从 SQLite 加载所有会话到内存缓存"""
    try:
        _ensure_chat_tables()
        sessions, messages = load_all_chat_sessions()
        _sessions_store.clear()
        _sessions_store.update(sessions)
        _messages_store.clear()
        _messages_store.update(messages)
        logger.info(f"已从 SQLite 加载 {len(_sessions_store)} 个会话")
    except Exception as e:
        logger.warning(f"加载持久化会话失败: {e}")


def _save_session_to_db(session: dict):
    """持久化单个会话到 SQLite"""
    try:
        _save_session_to_db_svc(session)
    except Exception as e:
        logger.warning(f"持久化会话失败: {e}")


def _save_message_to_db(session_id: str, msg: dict):
    """持久化单条消息到 SQLite"""
    try:
        _save_message_to_db_svc(session_id, msg)
    except Exception as e:
        logger.warning(f"持久化消息失败: {e}")


def _delete_session_from_db(session_id: str):
    """从 SQLite 删除会话及其消息"""
    try:
        _delete_session_from_db_svc(session_id)
    except Exception as e:
        logger.warning(f"删除持久化会话失败: {e}")




# 启动时加载持久化数据
_load_sessions_from_db()


class ChatRequest(BaseModel):
    query: str = ""
    history: List[dict] = []
    stream: bool = False
    granularity: Optional[str] = "chunk"  # 任务 4: chunk/event/auto

    # 兼容前端发送 message 字段
    message: Optional[str] = None

    class Config:
        # 允许使用额外字段
        extra = "ignore"

    def model_post_init(self, __context):
        # 如果前端发送了 message 但没有 query，使用 message 的值
        if self.message and not self.query:
            self.query = self.message

    @field_validator("history")
    @classmethod
    def validate_history(cls, v: List[dict]) -> List[dict]:
        if len(v) > 50:
            raise ValueError("对话历史条目数不能超过50条")
        return v

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("查询内容不能为空")
        if len(v) > 4000:
            raise ValueError("查询内容长度不能超过4000字符")
        return v


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
    except Exception as e:  # TODO: Narrow exception type
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
    except Exception as e:  # TODO: Narrow exception type
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


# ============ v1.44 Phase 1 Fix: 会话管理端点 ============

class CreateSessionRequest(BaseModel):
    title: Optional[str] = "新对话"


class ChatSendRequest(BaseModel):
    session_id: Optional[str] = None
    query: str
    history: List[dict] = []
    stream: bool = False
    granularity: Optional[str] = "chunk"

    # 兼容前端发送 sessionId 字段（camelCase）
    sessionId: Optional[str] = None

    class Config:
        # 允许使用 camelCase 字段名（前端使用 sessionId）
        populate_by_name = True

    def model_post_init(self, __context):
        # 如果前端发送了 sessionId 但没有 session_id，使用 sessionId 的值
        if self.sessionId is not None and self.session_id is None:
            self.session_id = self.sessionId

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("查询内容不能为空")
        if len(v) > 4000:
            raise ValueError("查询内容长度不能超过4000字符")
        return v

    @field_validator("history")
    @classmethod
    def validate_history(cls, v: List[dict]) -> List[dict]:
        if len(v) > 50:
            raise ValueError("对话历史条目数不能超过50条")
        return v


def _get_user_id(request: Request) -> str:
    """从请求中获取当前用户ID"""
    return getattr(request.state, "user", "anonymous")


@router.get("/api/chat/sessions")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def chat_sessions(request: Request):
    """获取当前用户的会话列表"""
    try:
        user_id = _get_user_id(request)
        user_sessions = [
            s for s in _sessions_store.values()
            if s.get("user_id") == user_id
        ]
        user_sessions.sort(key=lambda s: s.get("updated_at", 0), reverse=True)
        return {
            "sessions": user_sessions,
            "total": len(user_sessions),
        }
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"chat_sessions 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)}
        )


@router.post("/api/chat/sessions")
async def create_session(body: CreateSessionRequest, request: Request):
    """创建新会话"""
    try:
        user_id = _get_user_id(request)
        session_id = str(uuid.uuid4())
        now = time.time()
        session = {
            "id": session_id,
            "title": body.title or "新对话",
            "user_id": user_id,
            "last_message": "",
            "created_at": now,
            "updated_at": now,
            "message_count": 0,
        }
        _sessions_store[session_id] = session
        _messages_store[session_id] = []
        _save_session_to_db(session)  # v2.1: 持久化
        return {
            "id": session_id,
            "title": session["title"],
            "last_message": session["last_message"],
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
            "message_count": session["message_count"],
        }
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"create_session 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)}
        )


@router.delete("/api/chat/sessions/{session_id}")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def delete_session(session_id: str, request: Request):
    """删除指定会话"""
    try:
        user_id = _get_user_id(request)
        session = _sessions_store.get(session_id)
        if not session:
            return JSONResponse(
                status_code=404,
                content={"error": "会话未找到", "detail": f"会话 {session_id} 不存在"}
            )
        if session.get("user_id") != user_id:
            return JSONResponse(
                status_code=403,
                content={"error": "无权限删除此会话"}
            )
        del _sessions_store[session_id]
        _messages_store.pop(session_id, None)
        _delete_session_from_db(session_id)  # v2.1: 持久化删除
        return {"ok": True, "message": f"会话 {session_id} 已删除"}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"delete_session 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)}
        )


@router.post("/api/chat/send")
async def chat_send(body: ChatSendRequest, request: Request):
    """发送消息（支持SSE流式 + 非流式）

    与 POST /api/chat 逻辑一致，额外支持 session_id 关联。
    通过 stream 参数控制返回格式：
      - stream=true → SSE 流式响应
      - stream=false → 普通 JSON 响应
    """
    try:
        user_id = _get_user_id(request)

        # 如果有 session_id，验证会话存在并更新
        session_id = body.session_id
        if session_id:
            session = _sessions_store.get(session_id)
            if not session:
                # 自动创建会话
                session_id = str(uuid.uuid4())
                session = {
                    "id": session_id,
                    "title": body.query[:30] + ("..." if len(body.query) > 30 else ""),
                    "user_id": user_id,
                    "last_message": body.query[:100],
                    "created_at": time.time(),
                    "updated_at": time.time(),
                    "message_count": 0,
                }
                _sessions_store[session_id] = session
                _messages_store[session_id] = []
                _save_session_to_db(session)  # v2.1: 持久化
            else:
                session["last_message"] = body.query[:100]
                session["updated_at"] = time.time()
                _save_session_to_db(session)  # v2.1: 持久化更新
                session["message_count"] = session.get("message_count", 0) + 1

        # 保存用户消息
        if session_id:
            user_msg = {
                "role": "user",
                "content": body.query,
                "timestamp": time.time(),
            }
            _messages_store.setdefault(session_id, []).append(user_msg)
            _save_message_to_db(session_id, user_msg)  # v2.1: 持久化
            # 持久化会话更新
            if session_id in _sessions_store:
                _save_session_to_db(_sessions_store[session_id])

        # 如果请求流式响应
        if body.stream:
            async def sse_generator():
                try:
                    # 调用实际的对话逻辑
                    chat_body = ChatRequest(
                        query=body.query,
                        history=body.history,
                        granularity=body.granularity
                    )
                    result = await chat(chat_body, request)

                    answer = result.get("answer", "")
                    sources = result.get("sources", [])

                    # 逐字符流式输出 (兼容前端 delta/content 两种字段名)
                    for char in answer:
                        chunk = {"type": "content", "delta": char, "content": char}
                        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                        await asyncio_sleep(0.01)

                    # 发送引用 (兼容前端 references 字段)
                    if sources:
                        ref_chunk = {
                            "type": "references",
                            "references": [
                                {"id": f"ref-{i}", "title": s.get("title", s.get("source", "")), "type": "document", "snippet": s.get("snippet", s.get("text", ""))[:200]}
                                for i, s in enumerate(sources[:5])
                            ]
                        }
                        yield f"data: {json.dumps(ref_chunk, ensure_ascii=False)}\n\n"

                    # 完成标记 (兼容前端两种格式)
                    done_chunk = {'type': 'done', 'done': True, 'sources': sources}
                    yield f"data: {json.dumps(done_chunk, ensure_ascii=False)}\n\n"

                    # 保存助手回复
                    if session_id:
                        asst_msg = {
                            "role": "assistant",
                            "content": answer,
                            "sources": sources,
                            "timestamp": time.time(),
                        }
                        _messages_store.setdefault(session_id, []).append(asst_msg)
                        _save_message_to_db(session_id, asst_msg)  # v2.1: 持久化

                except Exception as e:  # TODO: Narrow exception type
                    logger.exception(f"SSE 生成失败: {e}")
                    error_chunk = {"type": "error", "content": str(e)}
                    yield f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n"

            return StreamingResponse(
                sse_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                }
            )
        else:
            # 非流式：直接复用现有 /api/chat 逻辑
            chat_body = ChatRequest(
                query=body.query,
                history=body.history,
                granularity=body.granularity
            )
            result = await chat(chat_body, request)

            # 保存助手回复
            if session_id:
                asst_msg = {
                    "role": "assistant",
                    "content": result.get("answer", ""),
                    "sources": result.get("sources", []),
                    "timestamp": time.time(),
                }
                _messages_store.setdefault(session_id, []).append(asst_msg)
                _save_message_to_db(session_id, asst_msg)  # v2.1: 持久化

            return result

    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"chat_send 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)}
        )


@router.get("/api/chat/sessions/{session_id}/messages")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def chat_session_messages(session_id: str, request: Request):
    """获取指定会话的历史消息"""
    try:
        user_id = _get_user_id(request)
        session = _sessions_store.get(session_id)
        if not session:
            return JSONResponse(
                status_code=404,
                content={"error": "会话未找到", "detail": f"会话 {session_id} 不存在"}
            )
        if session.get("user_id") != user_id:
            return JSONResponse(
                status_code=403,
                content={"error": "无权限查看此会话"}
            )
        messages = _messages_store.get(session_id, [])
        return {
            "session_id": session_id,
            "messages": messages,
            "total": len(messages),
        }
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"chat_session_messages 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)}
        )


# 异步 sleep 辅助（用于 SSE 流式输出）
import asyncio

async def asyncio_sleep(seconds: float):
    await asyncio.sleep(seconds)
