# v2.1 双路由开关 — 对话路由（v1 ShaoyinBrain + v2 乾卦意图循环）
# v1.44 Phase 1 Fix: 新增会话管理 + SSE流式 + 历史消息端点
import json
import logging
import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI 对话"])

# ============ 联网搜索检测 ============
# 当用户查询匹配这些关键词时，自动触发联网搜索
_REALTIME_KEYWORDS = [
    "天气",
    "今天",
    "现在",
    "最新",
    "新闻",
    "实时",
    "当前",
    "几度",
    "下雨",
    "温度",
    "股价",
    "汇率",
    "比赛",
    "几号",
    "星期",
    "假期",
    "放假",
    "上映",
    "weather",
    "today",
    "now",
    "latest",
    "news",
]


def _needs_web_search(query: str) -> bool:
    """判断查询是否需要联网搜索"""
    q = query.lower()
    return any(kw in q for kw in _REALTIME_KEYWORDS)


async def _search_and_inject(query: str) -> str:
    """联网搜索并格式化为上下文注入文本"""
    try:
        from src.services.web_search import web_search

        results = await web_search(query, max_results=3)
        if not results:
            return ""
        lines = ["[联网搜索结果] 以下是实时搜索结果，请基于这些信息回答："]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.title}\n   {r.content[:300]}\n   来源: {r.url}")
        return "\n".join(lines)
    except (ImportError, ConnectionError, TimeoutError, OSError, ValueError) as e:
        logger.warning(f"[WebSearch] 联网搜索失败: {e}")
        return ""


# ============ 持久化会话存储（SQLite）============
# v2.1: 使用 SQLite 持久化，重启不丢失会话和消息
# v1.50 R5: 统一使用 data_service.py 的连接管理，消除散落的 sqlite3.connect

from src.data_service import delete_session_from_db as _delete_session_from_db_svc
from src.data_service import ensure_chat_tables as _ensure_chat_tables
from src.data_service import (
    load_all_chat_sessions,
)
from src.data_service import save_message_to_db as _save_message_to_db_svc
from src.data_service import save_session_to_db as _save_session_to_db_svc

# 全局状态说明（MEDIUM-8）：
# _sessions_store 和 _messages_store 是进程级内存缓存，用于加速会话和消息的热点访问。
# 选择全局字典而非依赖 SQLite 的原因：
#   1. 减少频繁的数据库读取（每次请求都查 DB 会成为性能瓶颈）
#   2. 会话数据量可控（单实例部署，用户数有限）
#   3. 启动时从 SQLite 加载，运行时写穿（write-through）到 DB，保证持久性
#   4. 重启后自动从 SQLite 恢复，不会丢失数据
# 风险：多实例部署时此缓存不共享，需改用 Redis 等分布式缓存。
_sessions_store: dict = {}
_messages_store: dict = {}
_MAX_SESSIONS = 1000  # v1.50: 会话缓存上限，防止内存无限增长

# v1.50 R4: 会话和消息存储的线程安全锁
import asyncio as _asyncio

_sessions_lock = _asyncio.Lock()
_messages_lock = _asyncio.Lock()


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
    except (OSError, ValueError, KeyError) as e:
        logger.warning(f"加载持久化会话失败: {e}")


def _save_session_to_db(session: dict):
    """持久化单个会话到 SQLite"""
    try:
        _save_session_to_db_svc(session)
    except (OSError, ValueError, KeyError) as e:
        logger.warning(f"持久化会话失败: {e}")


def _save_message_to_db(session_id: str, msg: dict):
    """持久化单条消息到 SQLite"""
    try:
        _save_message_to_db_svc(session_id, msg)
    except (OSError, ValueError, KeyError) as e:
        logger.warning(f"持久化消息失败: {e}")


def _delete_session_from_db(session_id: str):
    """从 SQLite 删除会话及其消息"""
    try:
        _delete_session_from_db_svc(session_id)
    except (OSError, ValueError, KeyError) as e:
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
            # v2.0: 超过 50 条时自动保留最近 30 条（而非报错）
            v = v[-30:]
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
async def chat(body: ChatRequest, request: Request = None) -> JSONResponse:
    """对话端点 — v2.0 智能路由

    自动路由策略：
      - 简单查询（短文本、无历史）→ v1（ShaoyinBrain，快速响应）
      - 复杂查询（长文本、多轮、含关键词）→ v2（乾卦意图循环，深度推理）
    """
    engine = request.query_params.get("engine", "auto") if request else "auto"

    # v2.0 智能路由：自动选择最优引擎
    if engine == "auto":
        query = body.query.strip()
        history_len = len(body.history) if body.history else 0
        # 复杂度评分
        complexity = 0
        if len(query) > 200:
            complexity += 2
        if history_len > 3:
            complexity += 2
        # 复杂查询关键词
        _complex_keywords = {
            "分析",
            "对比",
            "总结",
            "归纳",
            "为什么",
            "怎么",
            "如何",
            "区别",
            "优缺点",
            "方案",
            "建议",
            "评估",
        }
        if any(kw in query for kw in _complex_keywords):
            complexity += 1
        # 自动决策
        engine = "v2" if complexity >= 2 else "v1"

    if engine == "v2":
        return await _chat_v2(body, request)
    else:
        return await _chat_v1(body, request)


async def _chat_v1(body: ChatRequest, request: Optional[Request] = None):
    """v1 路径：ShaoyinBrain（保留现有逻辑）"""
    from src.api.response import error, success

    try:
        # v2.1: Meridian 已废弃，v1 fallback 使用 IntentBus 兼容接口
        from src.bagua.intent_bus import IntentBus
        from src.shaoyin.brain import ShaoyinBrain

        # P2 指代消解：在多轮对话中消解代词和省略
        resolved_query = body.query
        if body.history and len(body.history) > 0:
            try:
                from src.services.coreference_resolver import resolve_coreference

                resolved_query = await resolve_coreference(body.query, body.history)
                if resolved_query != body.query:
                    logger.info(f"[coref] v1 指代消解: '{body.query[:40]}...' → '{resolved_query[:60]}...'")
            except (ImportError, ConnectionError, TimeoutError, ValueError) as e:
                logger.warning(f"[coref] v1 指代消解失败，使用原始查询: {e}")

        # 联网搜索：检测实时信息需求
        if _needs_web_search(resolved_query):
            _web_ctx = await _search_and_inject(resolved_query)
            if _web_ctx:
                logger.info(f"[WebSearch] v1 联网搜索: '{resolved_query[:50]}...'")
                resolved_query = _web_ctx + "\n\n用户问题: " + resolved_query

        intent_bus = IntentBus()
        brain = ShaoyinBrain(intent_bus)
        result = await brain.think(resolved_query, body.history)

        answer_data = {
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "mode": "shaoyin",
            "confidence": result.get("confidence", 0),
        }

        # 统一返回格式：默认返回 {success, data, message}
        return success(data=answer_data, message="对话完成")
    except (ImportError, ModuleNotFoundError) as e:
        logger.exception(f"_chat_v1 失败: {e}")
        # v1.50 R3: 生产环境不暴露内部错误详情
        _wants_v2 = request and (
            request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            return error("对话失败", status_code=500, detail="服务异常，请稍后重试")
        return {"answer": "对话服务暂时不可用，请稍后重试", "sources": [], "mode": "error"}


async def _chat_v2(body: ChatRequest, request: Optional[Request] = None):
    """v2 路径：乾卦意图循环路径

    通过 QianGua.think() 执行完整的意图循环：
    LLM 决策 → IntentBus 派发 → 目标卦执行 → 结果回收 → 再决策 → DONE
    """
    try:
        from src.bagua.intent_bus import get_intent_bus
        from src.bagua.qian import QianGua

        # P2 指代消解：在多轮对话中消解代词和省略
        resolved_query = body.query
        if body.history and len(body.history) > 0:
            try:
                from src.services.coreference_resolver import resolve_coreference

                resolved_query = await resolve_coreference(body.query, body.history)
                if resolved_query != body.query:
                    logger.info(f"[coref] v2 指代消解: '{body.query[:40]}...' → '{resolved_query[:60]}...'")
            except (ImportError, ConnectionError, TimeoutError, ValueError) as e:
                logger.warning(f"[coref] v2 指代消解失败，使用原始查询: {e}")

        # 联网搜索：检测实时信息需求
        if _needs_web_search(resolved_query):
            _web_ctx = await _search_and_inject(resolved_query)
            if _web_ctx:
                logger.info(f"[WebSearch] v2 联网搜索: '{resolved_query[:50]}...'")
                resolved_query = _web_ctx + "\n\n用户问题: " + resolved_query

        bus = get_intent_bus()
        qian = QianGua(intent_bus=bus)
        qian.start()

        result = await qian.think(
            query=resolved_query,
            history=body.history,
            session_id=str(uuid.uuid4()),
        )

        answer = result.get("answer", "")
        sources = result.get("intents_used", [])
        confidence = _compute_qian_confidence(result)

        # v2.0 自进化: 检测回答质量，触发自校正
        try:
            from src.services.self_correction import detect_error

            error = detect_error(resolved_query, answer)
            if error:
                from src.services.self_correction import analyze_root_cause, record_correction

                root_cause = analyze_root_cause(error)
                record_correction(resolved_query, error, root_cause, "auto_detected")
                logger.warning(f"[自校正] 检测到问题: {error['type']} (原因: {root_cause['cause']})")
        except (ImportError, AttributeError, KeyError, ValueError) as e:
            logger.debug(f"[自校正] 检测失败（非致命）: {e}", exc_info=True)

        return {
            "answer": answer,
            "sources": sources,
            "mode": "qian",
            "confidence": confidence,
        }
    except (ImportError, ModuleNotFoundError, ValueError, TypeError) as e:
        logger.exception(f"_chat_v2 失败: {e}")
        # v1.50 R3: 生产环境不暴露内部错误详情
        return {
            "answer": "对话服务暂时不可用，请稍后重试",
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
async def chat_agent(body: ChatRequest) -> JSONResponse:
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
            v = v[-30:]
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
        user_sessions = [s for s in _sessions_store.values() if s.get("user_id") == user_id]
        user_sessions.sort(key=lambda s: s.get("updated_at", 0), reverse=True)
        return {
            "sessions": user_sessions,
            "total": len(user_sessions),
        }
    except (KeyError, AttributeError, TypeError) as e:
        logger.exception(f"chat_sessions 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


@router.post("/api/chat/sessions")
async def create_session(body: CreateSessionRequest, request: Request) -> JSONResponse:
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
        # v1.50: 会话缓存淘汰 — 超过上限时删除最旧的会话
        if len(_sessions_store) >= _MAX_SESSIONS:
            oldest_id = min(_sessions_store, key=lambda k: _sessions_store[k].get("updated_at", 0))
            del _sessions_store[oldest_id]
            _messages_store.pop(oldest_id, None)
        _sessions_store[session_id] = session
        _messages_store[session_id] = []
        await asyncio.to_thread(_save_session_to_db, session)  # v2.1: 持久化
        return {
            "id": session_id,
            "title": session["title"],
            "last_message": session["last_message"],
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
            "message_count": session["message_count"],
        }
    except (KeyError, AttributeError, ValueError) as e:
        logger.exception(f"create_session 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


@router.delete("/api/chat/sessions/{session_id}")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def delete_session(session_id: str, request: Request):
    """删除指定会话"""
    try:
        user_id = _get_user_id(request)
        session = _sessions_store.get(session_id)
        if not session:
            return JSONResponse(status_code=404, content={"error": "会话未找到", "detail": f"会话 {session_id} 不存在"})
        if session.get("user_id") != user_id:
            return JSONResponse(status_code=403, content={"error": "无权限删除此会话"})
        del _sessions_store[session_id]
        _messages_store.pop(session_id, None)
        await asyncio.to_thread(_delete_session_from_db, session_id)  # v2.1: 持久化删除
        return {"ok": True, "message": f"会话 {session_id} 已删除"}
    except (KeyError, AttributeError, ValueError) as e:
        logger.exception(f"delete_session 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


# ============ chat_send 辅助函数（重构 v1.50）============


async def _validate_or_create_session(
    session_id: Optional[str],
    user_id: str,
    query: str,
) -> tuple:
    """验证或创建会话，返回 (session_id, session)"""
    if not session_id:
        return None, None

    session = _sessions_store.get(session_id)
    if not session:
        # 自动创建会话
        session_id = str(uuid.uuid4())
        session = {
            "id": session_id,
            "title": query[:30] + ("..." if len(query) > 30 else ""),
            "user_id": user_id,
            "last_message": query[:100],
            "created_at": time.time(),
            "updated_at": time.time(),
            "message_count": 0,
        }
        _sessions_store[session_id] = session
        _messages_store[session_id] = []
        await asyncio.to_thread(_save_session_to_db, session)
    else:
        # 更新现有会话
        session["last_message"] = query[:100]
        session["updated_at"] = time.time()
        session["message_count"] = session.get("message_count", 0) + 1
        await asyncio.to_thread(_save_session_to_db, session)

    # 自动生成会话标题
    if session.get("title") == "新对话" and query:
        session["title"] = query[:30] + ("..." if len(query) > 30 else "")
        await asyncio.to_thread(_save_session_to_db, session)

    return session_id, session


async def _save_user_message(session_id: Optional[str], query: str):
    """保存用户消息到会话"""
    if not session_id:
        return
    user_msg = {
        "role": "user",
        "content": query,
        "timestamp": time.time(),
    }
    _messages_store.setdefault(session_id, []).append(user_msg)
    await asyncio.to_thread(_save_message_to_db, session_id, user_msg)
    if session_id in _sessions_store:
        await asyncio.to_thread(_save_session_to_db, _sessions_store[session_id])


async def _resolve_reference(query: str, history: list) -> str:
    """指代消解预处理"""
    if not history or len(history) == 0:
        return query
    try:
        from src.services.coreference_resolver import resolve_coreference

        resolved = await resolve_coreference(query, history)
        if resolved != query:
            logger.info(f"[coref] 指代消解: '{query[:40]}...' → '{resolved[:60]}...'")
        return resolved
    except (ImportError, ConnectionError, TimeoutError, ValueError) as e:
        logger.warning(f"[coref] 指代消解失败，使用原始查询: {e}")
        return query


def _build_llm_messages(query: str, history: list, system_prompt: str = None) -> list:
    """构建 LLM 消息列表"""
    _system = (
        system_prompt
        or "你是伏羲，企业知识认知中枢。请严格依据知识库资料回答，资料中不存在时请说明。回答专业、精准、有来源。"
    )
    _msgs = [{"role": "system", "content": _system}]

    # 添加历史消息
    for h in history[-10:]:
        _msgs.append({"role": h.get("role", "user"), "content": h.get("content", "")})

    # 联网搜索注入
    _web_context = ""
    if _needs_web_search(query):
        # 注意：这里不能 await，需要在调用处处理
        _msgs.append({"role": "user", "content": query})
    else:
        _msgs.append({"role": "user", "content": query})

    return _msgs


async def _inject_web_context(msgs: list, query: str) -> list:
    """注入联网搜索结果到消息列表"""
    if not _needs_web_search(query):
        return msgs

    _web_context = await _search_and_inject(query)
    if not _web_context:
        return msgs

    logger.info(f"[WebSearch] 触发联网搜索: '{query[:50]}...'")
    # 修改最后一条用户消息
    msgs[-1] = {"role": "user", "content": _web_context + "\n\n用户问题: " + query}
    return msgs


async def _save_assistant_reply(session_id: Optional[str], answer: str, sources: list):
    """保存助手回复到会话"""
    if not session_id:
        return
    asst_msg = {
        "role": "assistant",
        "content": answer,
        "sources": sources,
        "timestamp": time.time(),
    }
    _messages_store.setdefault(session_id, []).append(asst_msg)
    await asyncio.to_thread(_save_message_to_db, session_id, asst_msg)


# ============ chat_send 主函数（重构后）============


@router.post("/api/chat/send")
async def chat_send(body: ChatSendRequest, request: Request) -> JSONResponse:
    """发送消息（支持SSE流式 + 非流式）

    重构 v1.50: 拆分为多个辅助函数，提高可读性和可维护性。
    """
    try:
        user_id = _get_user_id(request)

        # 1. 会话管理
        session_id, session = await _validate_or_create_session(body.session_id, user_id, body.query)

        # 2. 保存用户消息
        await _save_user_message(session_id, body.query)

        # 3. 指代消解
        resolved_query = await _resolve_reference(body.query, body.history)

        # 4. 根据 stream 参数选择响应方式
        if body.stream:
            return await _handle_stream_response(resolved_query, body.history, session_id)
        else:
            return await _handle_non_stream_response(
                resolved_query, body.history, body.granularity, request, session_id
            )

    except (ImportError, ModuleNotFoundError, ValueError, TypeError, KeyError) as e:
        logger.exception(f"chat_send 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


async def _handle_stream_response(
    query: str,
    history: list,
    session_id: Optional[str],
) -> StreamingResponse:
    """处理流式响应"""

    async def sse_generator():
        try:
            # 构建消息列表
            _msgs = _build_llm_messages(query, history)
            _msgs = await _inject_web_context(_msgs, query)

            # 检查语义缓存
            from src.services.llm import get_cached_response

            cached = await get_cached_response(_msgs)
            if cached:
                chunk = {"type": "content", "delta": cached, "content": cached}
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                done_chunk = {"type": "done", "done": True, "sources": []}
                yield f"data: {json.dumps(done_chunk, ensure_ascii=False)}\n\n"
                return

            # 缓存未命中，调用 LLM 流式 API
            from src.services.llm import cache_response, call_llm_stream_messages

            full_answer = ""
            async for token in call_llm_stream_messages(_msgs):
                if token:
                    full_answer += token
                    chunk = {"type": "content", "delta": token, "content": token}
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

            # 缓存完整响应
            if full_answer:
                await cache_response(_msgs, full_answer)

            # RAG 检索补充引用
            sources = await _retrieve_sources(query)

            # 发送引用
            if sources:
                ref_chunk = {
                    "type": "references",
                    "references": [
                        {
                            "id": f"ref-{i}",
                            "title": s.get("title", s.get("source", "")),
                            "type": "document",
                            "snippet": s.get("snippet", s.get("text", ""))[:200],
                        }
                        for i, s in enumerate(sources[:5])
                    ],
                }
                yield f"data: {json.dumps(ref_chunk, ensure_ascii=False)}\n\n"

            # 完成标记
            done_chunk = {"type": "done", "done": True, "sources": sources}
            yield f"data: {json.dumps(done_chunk, ensure_ascii=False)}\n\n"

            # 保存助手回复
            await _save_assistant_reply(session_id, full_answer, sources)

        except (
            ImportError,
            ModuleNotFoundError,
            ValueError,
            TypeError,
            KeyError,
            asyncio.TimeoutError,
            TimeoutError,
            ConnectionError,
            OSError,
        ) as e:
            logger.exception(f"SSE 生成失败: {e}")
            error_chunk = {"type": "error", "content": "服务异常，请稍后重试"}
            yield f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _handle_non_stream_response(
    query: str,
    history: list,
    granularity: Optional[str],
    request: Request,
    session_id: Optional[str],
) -> JSONResponse:
    """处理非流式响应"""
    # 构建消息列表（用于缓存检查）
    _msgs = _build_llm_messages(query, history)
    _msgs = await _inject_web_context(_msgs, query)

    # 调用 chat 端点
    chat_body = ChatRequest(query=query, history=history, granularity=granularity)
    result = await chat(chat_body, request)

    # 解析结果
    if hasattr(result, "body"):
        import json as _json

        result_dict = _json.loads(result.body)
    else:
        result_dict = result

    # 保存助手回复
    answer_data = result_dict.get("data", result_dict)
    if isinstance(answer_data, dict):
        await _save_assistant_reply(session_id, answer_data.get("answer", ""), answer_data.get("sources", []))

    return result


async def _retrieve_sources(query: str) -> list:
    """RAG 检索引用来源"""
    try:
        from src.services.search_service import search_chunks

        rag_results = await search_chunks(query, top_k=3)
        if rag_results:
            sources = [
                {
                    "title": r.get("file_name", r.get("source", "")),
                    "snippet": r.get("text", "")[:200],
                    "score": r.get("score", 0),
                }
                for r in rag_results
            ]
            logger.info(f"RAG检索成功: {len(sources)} sources")
            return sources
    except (ImportError, ConnectionError, TimeoutError, OSError, ValueError) as e:
        logger.warning(f"RAG检索失败（非致命）: {e}", exc_info=True)
    return []


@router.get("/api/chat/sessions/{session_id}/messages")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def chat_session_messages(session_id: str, request: Request):
    """获取指定会话的历史消息"""
    try:
        user_id = _get_user_id(request)
        session = _sessions_store.get(session_id)
        if not session:
            return JSONResponse(status_code=404, content={"error": "会话未找到", "detail": f"会话 {session_id} 不存在"})
        if session.get("user_id") != user_id:
            return JSONResponse(status_code=403, content={"error": "无权限查看此会话"})
        messages = _messages_store.get(session_id, [])
        return {
            "session_id": session_id,
            "messages": messages,
            "total": len(messages),
        }
    except (KeyError, AttributeError, TypeError) as e:
        logger.exception(f"chat_session_messages 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


# 异步 sleep 辅助（用于 SSE 流式输出）
import asyncio


async def asyncio_sleep(seconds: float):
    await asyncio.sleep(seconds)
