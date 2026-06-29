"""
routers/chat.py — AI 对话路由（v10.0）
负责：/api/chat, /api/chat/agent — 智能问答 + Agentic RAG
"""
import os, json, time, asyncio, logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.db.data_store import load_chunks, log_search, load_graph, load_config

logger = logging.getLogger(__name__)
from src.services.retrieval import hybrid_search
from src.services.llm import call_deepseek, call_deepseek_stream, get_cached_answer
from src.services.graph_router import get_entity_context
from src.services.query_router import route_query
from src.db.memory_store import get_store
from src.services.query_resolver import resolve_query, compress_history
from src.services.security import sanitize_user_input
from src.services.feature_flags import load_flags
from src.hypothalamus.brain import Instinct
from src.config import TERMS_FILE, AI_TIMEOUT_SECONDS

import aiohttp

router = APIRouter(tags=["AI 对话"])


class ChatRequest(BaseModel):
    query: str
    history: List[dict] = []
    stream: bool = False


# ============ 公司知识头构建 ============

def _build_company_knowledge_header() -> str:
    """从术语表 + 知识图谱 + FAQ 构建专属知识前缀"""
    header_parts = ["你是伏羲知识库 AI 助手。你必须了解以下公司专属信息：\n"]
    if TERMS_FILE.exists():
        try:
            terms = json.loads(TERMS_FILE.read_text(encoding="utf-8"))
            for cat, display in [("devices","常用设备"),("materials","常用材料"),
                                 ("models","产品型号"),("suppliers","供应商"),("abbreviations","缩写")]:
                items = terms.get(cat, [])
                if items:
                    names = ", ".join([t["term"] for t in items[:8]])
                    header_parts.append(f"- {display}：{names}")
        except Exception:
            logger.warning("suppressed exception", exc_info=True)
            pass
    try:
        graph = load_graph()
        nodes = graph.get("nodes", {})
        if nodes:
            top_devices = [n for n, v in nodes.items() if v.get("type")=="device"][:5]
            top_materials = [n for n, v in nodes.items() if v.get("type")=="material"][:5]
            if top_devices:
                header_parts.append(f"- 网络/硬件设备：{', '.join(top_devices)}")
            if top_materials:
                header_parts.append(f"- 塑胶材料：{', '.join(top_materials)}")
    except Exception:
        logger.warning("suppressed exception", exc_info=True)
        pass
    try:
        faq = load_config().get("faq", [])
        cats = list(set(f.get("category","") for f in faq if f.get("category")))
        if cats:
            header_parts.append(f"- 知识领域：{', '.join(cats[:8])}")
    except Exception:
        logger.warning("suppressed exception", exc_info=True)
        pass
    header_parts.append("\n")
    return "\n".join(header_parts)


# ============ 领域 Prompt 映射 ============

DOMAIN_PROMPT_MAP = {
    "network": (
        "你是伏羲 IT 网络工程师 AI 助手。\n"
        "专长: VLAN 划分、交换路由配置、ACL 策略、无线网络部署、DHCP/NPS 认证。\n"
        "回答时使用网络专业术语（如 trunk/access/STP/OSPF），引用具体设备型号和端口号。\n"
        "涉及 IP 规划时自动检查网段冲突。"
    ),
    "mechanical": (
        "你是伏羲模具/机械设计 AI 助手。\n"
        "专长: 注塑模具设计（导柱导套/滑块/浇口/冷却系统）、连接器模具、标准件选型。\n"
        "回答时标注材料牌号（如 SKD61/SUJ2/S136）、HRC 硬度、尺寸公差。\n"
        "涉及标准件时注明供应商替代方案（米思米/盘起/国产）。"
    ),
    "electrical": (
        "你是伏羲电气自动化 AI 助手。\n"
        "专长: PLC 控制（西门子 S7-1200）、传感器选型与安装、电气柜布线、伺服驱动。\n"
        "回答时注明传感器型号（欧姆龙/SMC/基恩士）、接线方式（NPN/PNP）、防护等级。"
    ),
    "quality": (
        "你是伏羲品质检测 AI 助手。\n"
        "专长: 三坐标测量（蔡司 CONTURA）、GD&T 公差分析、GR&R 评估、CPK 计算。\n"
        "回答时标注测量标准（ISO 2768/GB/T 1184）、公差等级、采样策略。"
    ),
}

DOMAIN_KEYWORDS = {
    "network": ["vlan","ip","网段","dhcp","路由","交换机","端口","ap","ac","acl","拓扑","子网","trunk","stp","802.1x"],
    "mechanical": ["模具","导柱","导套","顶针","滑块","浇口","齿轮","轴承","标准件","收缩率","模温","hrc","硬度","分型面","排气"],
    "electrical": ["plc","传感器","伺服","变频","气缸","电磁阀","接线","电气柜","s7-1200","西门子","欧姆龙","smc","profinet","24v","npn","pnp"],
    "quality": ["三坐标","蔡司","contura","gd&t","gr&r","cpk","平面度","位置度","测量","校准","测头","轮廓度","公差"],
}


def _get_domain_override(query: str, route_name: str) -> str:
    """根据查询内容选择领域 Prompt"""
    if route_name != "default":
        return DOMAIN_PROMPT_MAP.get(route_name, "")
    ql = query.lower()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in ql for kw in keywords):
            return DOMAIN_PROMPT_MAP.get(domain, "")
    return ""


# ============ 核心对话 ============

# ======== v10.1: Query Decomposition ========

DECOMPOSE_DELIMITERS = ["？", "?", "；", ";"]
DECOMPOSE_CONJUNCTIONS = ["和", "与", "分别", "各自", "区别", "差异", "不同", "还有", "以及", "另外"]

def _decompose_query(query: str) -> list:
    q = query.strip()
    sub_queries = [q]
    for delim in DECOMPOSE_DELIMITERS:
        if delim in q:
            parts = [p.strip() for p in q.split(delim) if len(p.strip()) > 3]
            if len(parts) >= 2:
                sub_queries = parts
                break
    if len(sub_queries) == 1:
        for conj in DECOMPOSE_CONJUNCTIONS:
            if conj in q:
                parts = q.split(conj, 1)
                if len(parts) == 2 and len(parts[0]) > 2 and len(parts[1]) > 2:
                    sub_queries = [parts[0].strip(), parts[1].strip()]
                    break
    if len(sub_queries) == 1 and len(q) > 60:
        parts = [p.strip() for p in q.split("，") if len(p.strip()) > 5]
        if len(parts) >= 2:
            sub_queries = parts[:3]
    return sub_queries[:5]




def _record_chat_memory(query: str, result_count: int, mode: str):
    """P6: 记录 AI 对话到记忆系统"""
    try:
        from src.services.memory_system import record_experience
        record_experience(
            action="chat",
            detail=f"query={query[:80]} results={result_count} mode={mode}",
            outcome="ok" if result_count > 0 else "empty",
            tags=["chat", mode]
        )
    except Exception:
        logger.warning("suppressed exception", exc_info=True)
        pass

@router.post("/api/chat")
async def chat(body: ChatRequest, request: Request):
    """智能问答：混合检索 + AI 生成"""
    q = body.query.strip()
    if not q:
        raise HTTPException(status_code=400, detail="查询不能为空")

    # Phase 3.5: Prompt 注入防御
    safe_q = sanitize_user_input(q)
    if safe_q is None:
        raise HTTPException(status_code=400, detail="请求包含不安全内容")

    # 检查缓存
    cached = get_cached_answer(q)
    if cached:
        results = await hybrid_search(q, load_chunks(), top_k=5)
        log_search(q, len(results), 0)
        _record_chat_memory(q, len(results), 'cached')
        return {"answer": cached, "sources": results, "mode": "cached"}

    # 1. 混合检索（Query Planner + 自动拆解）
    results = []
    _flags = load_flags()
    if _flags.get("query_planner", False):
        try:
            from src.services.query_planner import plan_query_async
            plan = await plan_query_async(q)
            if plan:
                all_results = []
                seen = set()
                for step in plan:
                    r = await hybrid_search(step.query, load_chunks(), top_k=5)
                    for item in r:
                        key = item.get("file_hash","") + str(item.get("chunk_index",0))
                        if key not in seen:
                            seen.add(key)
                            all_results.append(item)
                results = all_results[:10]
                logger.info(f"[chat] Query Planner: {len(plan)} steps → {len(results)} results")
        except Exception as e:
            logger.warning(f"[chat] Query Planner fallback: {e}")
    if not results:
        sub_queries = _decompose_query(q)
        if len(sub_queries) > 1:
            all_results = []
            seen = set()
            for sq in sub_queries[:3]:
                r = await hybrid_search(sq, load_chunks(), top_k=5)
                for item in r:
                    key = item.get("file_hash","") + str(item.get("chunk_index",0))
                    if key not in seen:
                        seen.add(key)
                        all_results.append(item)
            results = all_results[:10]
        else:
            results = await hybrid_search(q, load_chunks(), top_k=5)

    # 1.5: Wiki 优先搜索（精炼知识优先，命中则替换同主题 chunk）
    wiki_pages = []
    try:
        from src.services.wiki import get_wiki_engine
        we = get_wiki_engine()
        wiki_pages = we.search_content(q, limit=3)
        if wiki_pages:
            logger.info(f'[chat] Wiki hit: {len(wiki_pages)} pages for query')
            # 去重：Wiki 命中时，移除主题高度重叠的 chunk
            wiki_titles = {p.get('title', '').strip() for p in wiki_pages}
            results = [r for r in results if not any(
                title[:6] in r.get('file_name', '') or title[:6] in r.get('text', '')[:100]
                for title in wiki_titles if len(title) >= 4
            )]
    except Exception as e:
        logger.warning(f'[chat] Wiki search failed: {e}')

    # 2a. 检索质量熔断检查
    retrieval_scores = [float(r.get("_rerank_score", r.get("score", 0))) for r in results[:5]]
    avg_score = sum(retrieval_scores) / max(len(retrieval_scores), 1) if retrieval_scores else 0
    low_quality = avg_score < 0.3 and len(results) < 3
    if low_quality:
        logger.info(f"[chat] Low retrieval quality (avg={avg_score:.2f}), considering skin external search fallback")

    # 2. 构建上下文（Wiki 优先 + Token 预算）
    MAX_CTX_CHARS = 6000
    ctx_parts = []
    char_count = 0
    if wiki_pages:
        for i, p in enumerate(wiki_pages[:3]):
            if char_count >= MAX_CTX_CHARS: break
            title = p.get('title', 'Unknown')
            category = p.get('category', '')
            limit = min(800, MAX_CTX_CHARS - char_count)
            if limit < 100: break
            content = p.get('content', '')[:limit]
            part = f'[Wiki {i+1}] {title} ({category})\
{content}'
            ctx_parts.append(part)
            char_count += len(part)
    if results and char_count < MAX_CTX_CHARS:
        for i, r in enumerate(results[:5]):
            if char_count >= MAX_CTX_CHARS: break
            limit = min(600, MAX_CTX_CHARS - char_count)
            if limit < 100: break
            part = f"[Ref {i+1}] 来源:{r.get('file_name','?')}\n{r.get('text','')[:limit]}"
            ctx_parts.append(part)
            char_count += len(part)
    ctx = "\n\n---\n\n".join(ctx_parts) if ctx_parts else "知识库中暂无相关文档."

    # v10.0: 图谱上下文注入
    graph_ctx = get_entity_context(q)
    if graph_ctx:
        ctx += graph_ctx
    
    # 2b. Context Compression（v1.42）: 超预算时智能提炼，替代暴力截断
    if len(ctx) > 4000:
        try:
            from src.services.context_compressor import compress_context
            ctx_parts_list = ctx.split('\n\n---\n\n')
            compressed_parts = await compress_context(ctx_parts_list, q, total_budget=4000)
            ctx = '\n\n---\n\n'.join(compressed_parts)
            logger.info(f'[chat] Context compressed: {len(ctx)} chars')
        except Exception as e:
            logger.warning(f'[chat] Context compression failed, using raw: {e}')
            ctx = ctx[:5000]

    # 3. 构建系统 Prompt
    company_header = _build_company_knowledge_header()
    sys_prompt = (
        company_header +
        "规则:\n"
        "1. 仅依据文档内容作答，不要编造信息。\n"
        "2. 引用文档时使用 [Ref N] 标注。\n"
        "3. 用 Markdown 格式输出。\n"
        "4. 如果信息不足，明确说根据现有知识库未找到相关信息。\n"
        "\n文档:\n" + ctx
    )

    # 4. 领域 Prompt 注入
    try:
        route_info = route_query(q)
        route_name = route_info.get("name", "default") if route_info else "default"
    except Exception:
        logger.exception("Exception in routers/chat.py")
        route_name = "default"
    domain_override = _get_domain_override(q, route_name)
    if domain_override:
        sys_prompt = domain_override + "\n\n规则:\n" + sys_prompt[sys_prompt.index("规则:"):] if "规则:" in sys_prompt else sys_prompt

    # 5. 构建消息
    messages = [{"role": "system", "content": sys_prompt}, {"role": "user", "content": q}]
    if body.history:
        for h in body.history[-6:]:
            messages.insert(1, h)

    llm_prompt = sys_prompt + "\n\n用户问题: " + q + "\n\n请根据以上文档内容回答用户问题:"

    # 6. 流式响应
    # P0-1: 父子分块 — 补充父块上下文到搜索结果
    for sr in results:
        if sr.get('chunk_type') == 'child' and sr.get('parent_idx') is not None:
            try:
                for pc in get_store().get_by_hash(sr.get('file_hash', '')):
                    if pc.get('chunk_type') == 'parent' and pc.get('parent_idx') == sr.get('parent_idx'):
                        sr['parent_context'] = pc.get('text', '')[:3000]
                        break
            except Exception:
                logger.warning("suppressed exception", exc_info=True)
                pass
    
    async def _stream_response(prompt_text: str, search_results: list):
        yield f"data: {json.dumps({'sources': search_results})}\n\n"
        async for token in call_deepseek_stream(prompt_text):
            if token:
                yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"

    if body.stream:
        return StreamingResponse(
            _stream_response(llm_prompt, results),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )

    # 7. 非流式：DeepSeek Chat
    llm_answer = await call_deepseek(llm_prompt)
    if llm_answer:
        log_search(q, len(results), 0)
        # v5.3: 裁判模型质检（非流式）
        try:
            from src.services.judge import judge_and_decide
            j_ctxs = [{"text": r.get("text", ""), "file_name": r.get("file_name", "?")} for r in results[:5]]
            j_result = await judge_and_decide(llm_answer, j_ctxs)
            llm_answer = j_result["answer"]
            if not j_result.get("passed"):
                logger.warning(f"[chat] Judge flagged: {j_result.get('judge_result', {}).get('issues', [])}")
        except Exception as e:
            logger.warning(f"[chat] Judge unavailable: {e}")
        # v5: 追加引用溯源
        source_refs = []
        for i, r in enumerate(results[:8]):
            wiki_title = r.get("wiki_title") or r.get("title") or r.get("file_name", "?")
            if wiki_title and wiki_title != "?":
                source_refs.append(f"[Ref {i+1}] {wiki_title[:60]}")
        if source_refs and "Ref " not in llm_answer:
            llm_answer += "\n\n---\n**📚 参考来源：**\n" + "\n".join(source_refs)
        # v5.1: 自动外探 — 知识库未找到时尝试联网
        no_result_markers = [
            "未找到相关", "知识库中未找到", "知识库中暂无", "未检索到",
            "没有找到", "暂无相关", "根据现有知识库未找到", "知识库中暂无相关"
        ]
        if any(marker in llm_answer for marker in no_result_markers):
            try:
                brave_key = os.getenv("BRAVE_API_KEY", "")
                if brave_key:
                    import urllib.request as _ur, urllib.parse as _up
                    _search_url = "https://api.search.brave.com/res/v1/web/search?q=" + _up.quote(q) + "&count=3"
                    _search_req = _ur.Request(_search_url, headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": brave_key
                    })
                    _search_resp = _ur.urlopen(_search_req, timeout=8)
                    _web_data = json.loads(_search_resp.read())
                    _web_items = []
                    for _wr in (_web_data.get("web", {}).get("results", []) or [])[:3]:
                        _web_items.append("🌐 **{}**\n{}".format(_wr.get("title",""), _wr.get("description","")[:250]))
                    if _web_items:
                        llm_answer += "\n\n---\n🐙 **发·外探（联网搜索补充）:**\n" + "\n\n".join(_web_items)
                        _record_chat_memory(q, len(results), "ai_skin_external")
                        return {"answer": llm_answer, "sources": results, "mode": "ai_antenna"}
            except Exception:
                pass
        return {"answer": llm_answer, "sources": results, "mode": "deepseek_chat", "retrieval_mode": "hybrid"}

    # 8. DeepSeek 不可用：先返回搜索结果
    if not body.stream:
        api_key = request.headers.get("X-Mimo-Key", "") or os.getenv("MIMO_API_KEY", "") or os.getenv("DEEPSEEK_API_KEY", "")
        pass  # mimo async removed, now using DeepSeek directly
        return {
            "answer": "🔍 正在生成 AI 回答，请稍后刷新或重新搜索...\n\n**关键词搜索结果:**\n\n" + ctx[:3000],
            "sources": results, "mode": "search_first"
        }

    # 9. 流式降级到 MIMO
    try:
        api_key = request.headers.get("X-Mimo-Key", "") or os.getenv("MIMO_API_KEY", "") or os.getenv("DEEPSEEK_API_KEY", "")
        if not api_key:
            return {"answer": "⚠️ 本地模型和云端 API 均不可用,以下为关键词搜索结果:\n\n" + ctx[:3000],
                    "sources": results, "mode": "keyword_only"}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.xiaomimimo.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": "mimo-v2-omni", "messages": messages, "temperature": 0.1, "max_tokens": 2048},
                timeout=aiohttp.ClientTimeout(total=AI_TIMEOUT_SECONDS)
            ) as resp:
                data = await resp.json()
            if resp.status != 200:
                return {"answer": f"AI 服务异常: {data.get('error',{}).get('message','未知错误')}",
                        "sources": results, "mode": "error"}
            answer = data["choices"][0]["message"]["content"]
            log_search(q, len(results), 0)
            _record_chat_memory(q, len(results), 'ai')
            return {"answer": answer, "sources": results, "mode": "ai"}
    except asyncio.TimeoutError:
        return {"answer": "⏱️ AI 服务响应超时,以下为关键词搜索结果:\n\n" + ctx[:3000],
                "sources": results, "mode": "timeout_fallback"}
    except Exception as e:
        return {"answer": f"请求异常: {str(e)[:100]}", "sources": results, "mode": "error"}


@router.post("/api/chat/agent")
async def chat_agent(body: ChatRequest):
    """Agentic RAG: Brain Instinct 路由 + 太极 Agent 深度推理"""
    q = body.query.strip()
    if not q:
        raise HTTPException(status_code=400, detail="查询不能为空")

    # 安全检查
    safe_q = sanitize_user_input(q)
    if safe_q is None:
        raise HTTPException(status_code=400, detail="请求包含不安全内容")

    flags = load_flags()
    t0 = time.time()

    # Step 1: Brain Instinct 意图分类（零延迟）
    intent = Instinct.classify_intent(q, [h.get("content", "") for h in body.history[-4:]])
    complexity = Instinct.estimate_complexity(q, intent)
    primary_intent = intent.get("intent", "general_search")

    # Step 2: 路由决策
    SIMPLE_INTENTS = {"definition", "numeric_lookup", "material_selector", "table_query"}
    use_brain_direct = (
        flags.get("brain_direct_route", True)
        and primary_intent in SIMPLE_INTENTS
        and complexity <= 2
    )

    if use_brain_direct:
        # 简单查询 → Brain 直接路由（0.1-0.3s）
        try:
            from src.services.retrieval import hybrid_search
            from src.services.llm import call_deepseek
            results = await hybrid_search(q, load_chunks(), top_k=5)
            ctx = "\n".join([r.get("text", "")[:300] for r in results[:3]])
            prompt = f"基于以下信息简洁回答：\n{ctx}\n\n问题：{q}"
            answer = await call_deepseek(prompt)
            latency = int((time.time() - t0) * 1000)
            return {
                "answer": answer or "未能生成回答",
                "mode": "instinct",
                "intent": primary_intent,
                "complexity": complexity,
                "sources": results[:3],
                "latency_ms": latency,
            }
        except Exception as e:
            logger.warning(f"Brain direct route failed: {e}, falling back to agent")

    # 复杂查询 → 太极 Agent 深度推理
    try:
        from src.services.agentic_rag_v2 import agentic_search as agentic_rag_main
        result = await agentic_rag_main(query=q)
        latency = int((time.time() - t0) * 1000)
        result["mode"] = "agent"
        result["intent"] = primary_intent
        result["complexity"] = complexity
        result["latency_ms"] = latency
        return result
    except Exception as e:
        return {"answer": f"Agent 执行异常: {str(e)[:200]}", "mode": "agent_error"}


# ============ ☲ 触角·外探 ============
# 当知识库内无结果时，外探网络信息

@router.post("/api/antenna/search")
async def antenna_search(body: ChatRequest):
    """联网搜索：用 Brave Search API 外探网络信息"""
    q = body.query.strip()
    if not q:
        raise HTTPException(status_code=400, detail="查询不能为空")

    brave_key = os.getenv("BRAVE_API_KEY", "")
    if not brave_key:
        return {"answer": "☲ 触角·外探未配置 Brave Search API Key，暂时无法联网搜索。请在环境变量中设置 BRAVE_API_KEY。", "sources": [], "mode": "antenna_unavailable"}

    try:
        import urllib.request, urllib.parse
        url = "https://api.search.brave.com/res/v1/web/search?q=" + urllib.parse.quote(q) + "&count=5"
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": brave_key
        })
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())

        web_results = []
        for r in (data.get("web", {}).get("results", []) or [])[:5]:
            web_results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "description": r.get("description", "")
            })

        if not web_results:
            return {"answer": "☲ 触角·外探未找到相关信息。", "sources": [], "mode": "antenna_empty"}

        web_ctx = "\n\n".join([
            f"[Web {i+1}] {r['title']}\n{r['description'][:300]}"
            for i, r in enumerate(web_results)
        ])
        sys_prompt = (
            "你是伏羲知识库 AI 助手。用户的问题在内部知识库中未找到答案，"
            "你通过联网搜索获取了以下外部信息。请基于这些信息回答用户问题，并标注 [Web N] 来源。\n"
            "如果没有足够信息回答，请如实说明。\n\n"
            "联网搜索结果：\n" + web_ctx
        )
        llm_prompt = sys_prompt + "\n\n用户问题: " + q + "\n\n请基于以上联网搜索结果回答："

        llm_answer = await call_deepseek(llm_prompt)

        if llm_answer:
            formatted_sources = [{"title": r["title"], "url": r["url"], "file_name": "☲ 触角·外探 · " + r["title"]} for r in web_results]
            return {"answer": llm_answer, "sources": formatted_sources, "mode": "antenna_search"}

        answer = "🐙 **发·外探 联网搜索结果**\n\n"
        for i, r in enumerate(web_results):
            answer += f"**{i+1}. [{r['title']}]({r['url']})**\n{r['description'][:200]}\n\n"
        formatted_sources = [{"title": r["title"], "url": r["url"], "file_name": "☲ 触角·外探 · " + r["title"]} for r in web_results]
        return {"answer": answer, "sources": formatted_sources, "mode": "antenna_raw"}

    except Exception as e:
        logger.error(f"[Hair] Web search failed: {e}")
        return {"answer": f"☲ 触角·外探失败：{str(e)[:200]}", "sources": [], "mode": "antenna_error"}
