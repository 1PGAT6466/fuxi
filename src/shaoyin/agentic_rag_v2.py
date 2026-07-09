"""
agentic_rag_v2.py — 太极 · 主 Agent v2.0
Plan → Execute → Reflect 循环，8 个工具，由 MiMo function calling 驱动
"""
import json, logging, asyncio, time
from typing import Dict, List

logger = logging.getLogger(__name__)

MAX_STEPS = 5
MAX_TOTAL_TOKENS = 4000

# ============ 8 个工具定义 ============
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "在知识库中检索相关文档片段。用于查找一般性信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索查询"},
                    "top_k": {"type": "integer", "description": "返回结果数", "default": 5}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_wiki",
            "description": "在 Wiki 知识库中搜索结构化知识。Wiki 包含提炼后的精炼知识，适合查找定义、概述、对比总结。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索查询"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_graph",
            "description": "查询知识图谱，获取实体关系。支持模式：direct=直接关系，traverse=多跳遍历。",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "description": "实体名称"},
                    "mode": {
                        "type": "string",
                        "enum": ["direct", "traverse"],
                        "default": "direct",
                        "description": "查询模式"
                    }
                },
                "required": ["entity"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_doc",
            "description": "读取指定文档的完整内容。当你需要查看某个文档的详细信息时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string", "description": "文件名或文件名片段"},
                    "chunk_index": {"type": "integer", "description": "段落索引（可选）", "default": 0}
                },
                "required": ["file_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_table",
            "description": "提取和查询文档中的表格数据。适合查找参数表、对比矩阵、规格清单。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "表格查询（如 'PA66 参数'、'PLC 对比'）"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "describe_image",
            "description": "描述文档中的图片内容。用于理解图表、流程图、示意图。",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "图片路径或描述"}
                },
                "required": ["image_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "clarify",
            "description": "向用户追问以澄清需求。当问题模糊或有多种理解时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "追问的问题"}
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": "已完成所有检索，可以生成最终答案。",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "判断依据：为什么认为信息已充分"}
                },
                "required": ["reason"]
            }
        }
    }
]

SYSTEM_PROMPT = """你是伏羲知识库的执行智能体。

## 工作原则
1. 先搜索，再回答。绝不凭空编造。
2. 搜索结果不足时，主动扩大搜索范围（换关键词、查图谱、查Wiki）。
3. 涉及数字、规格、价格时，必须引用来源。
4. 不确定时说"根据现有资料无法确定"。

## 工具使用策略
- 简单问题（是什么/怎么用）→ search_knowledge + done
- 比较问题（A vs B）→ 分别搜索 A 和 B，再 extract_table 对比
- 分析问题（为什么/怎么办）→ search_knowledge + read_doc 详细阅读
- 实体关系问题 → query_graph 查图谱
- 参数/规格查询 → extract_table 查表格
- 信息不足 → 换关键词重试 2-3 次，仍不足则 clarify 追问"""


async def _call_mimo_with_tools(query: str, context: List[Dict], step: int) -> Dict:
    """调用 MiMo API with function calling"""
    from src.config import MIMO_API_KEY, MIMO_BASE_URL, MIMO_MODEL, MIMO_TIMEOUT

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if step == 0:
        messages.append({"role": "user", "content": query})
    else:
        messages.append({"role": "user", "content": query})
        for ctx in context:
            messages.append({"role": "assistant", "content": None, "tool_calls": ctx.get("tool_calls", [])})
            for tc_result in ctx.get("tool_results", []):
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_result.get("id", ""),
                    "content": tc_result.get("content", "")
                })

    import aiohttp
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MIMO_API_KEY}",
    }
    payload = {
        "model": MIMO_MODEL,
        "messages": messages,
        "tools": TOOLS,
        "max_tokens": 1024,
        "temperature": 0.2,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{MIMO_BASE_URL}/chat/completions",
            json=payload, headers=headers,
            timeout=aiohttp.ClientTimeout(total=MIMO_TIMEOUT),
        ) as resp:
            if resp.status != 200:
                return {"error": f"API {resp.status}"}
            data = await resp.json()
            choice = data["choices"][0]
            return {
                "message": choice["message"],
                "tool_calls": choice["message"].get("tool_calls", []),
                "finish_reason": choice.get("finish_reason", ""),
            }


# ============================================================
# v3.0: _execute_tool 调度字典重构 — 每个工具独立 handler
# ============================================================


async def _tool_search_knowledge(args: dict) -> str:
    """工具: 知识库关键词搜索"""
    from src.services.retrieval import hybrid_search
    results = await hybrid_search(args.get("query", ""), top_k=args.get("top_k", 5))
    snippets = []
    for r in results[:5]:
        snippets.append({
            "text": r.get("text", "")[:300],
            "file": r.get("file_name", "?"),
            "score": round(r.get("score", 0), 2)
        })
    return json.dumps(snippets, ensure_ascii=False)


async def _tool_search_wiki(args: dict) -> str:
    """工具: Wiki 知识库搜索"""
    from src.services.wiki import search_wiki_pages
    results = await search_wiki_pages(args.get("query", ""))
    return json.dumps([{
        "title": r.get("title", ""),
        "summary": r.get("summary", "")[:200]
    } for r in results[:3]], ensure_ascii=False)


def _tool_query_graph(args: dict) -> str:
    """工具: 知识图谱查询（direct / traverse）"""
    from src.services.graph_router import get_entity_context
    from src.services.graph_traversal import multi_hop_traverse
    entity = args.get("entity", "")
    mode = args.get("mode", "direct")
    if mode == "traverse":
        result = multi_hop_traverse(entity, max_hops=3)
        return json.dumps(result, ensure_ascii=False)
    else:
        ctx = get_entity_context(entity)
        return ctx if ctx else f"图谱中未找到 '{entity}' 的关系"


def _tool_read_doc(args: dict) -> str:
    """工具: 读取指定文档的完整内容"""
    from src.db.memory_store import get_store
    file_name = args.get("file_name", "")
    chunk_idx = args.get("chunk_index", 0)
    store = get_store()
    all_chunks = store.get_all() if hasattr(store, 'get_all') else []
    matched = [c for c in all_chunks if file_name.lower() in c.get("file_name", "").lower()]
    if matched:
        target = matched[0] if chunk_idx == 0 else next(
            (c for c in matched if c.get("chunk_index") == chunk_idx), matched[0]
        )
        return f"[{target.get('file_name', '?')} #{target.get('chunk_index', 0)}]\n{target.get('text', '')[:1500]}"
    return f"未找到文件 '{file_name}'"


async def _tool_extract_table(args: dict) -> str:
    """工具: 提取和查询文档中的表格数据"""
    from src.services.table_view import search_tables
    results = search_tables(args.get("query", ""))
    if results:
        return json.dumps(results[:3], ensure_ascii=False)
    # fallback: 从 chunk 中搜索表格内容
    from src.services.retrieval import hybrid_search
    results = await hybrid_search(args.get("query", ""), top_k=3)
    table_hits = [r for r in results if "|" in r.get("text", "") or "表格" in r.get("text", "")]
    if table_hits:
        return table_hits[0].get("text", "")[:800]
    return "未找到相关表格数据"


async def _tool_describe_image(args: dict) -> str:
    """工具: 描述文档中的图片内容（多模态 → 知识库 fallback）"""
    image_path = args.get("image_path", "")
    try:
        from src.services.multimodal import transcribe_image
        result = transcribe_image(image_path)
        if result:
            return f"图片描述: {result}"
        from src.services.retrieval import hybrid_search
        results = await hybrid_search(image_path, top_k=3)
        img_results = [r for r in results if r.get("result_type") == "image" or "图片" in r.get("text", "")]
        if img_results:
            return img_results[0].get("text", "")[:500]
        return f"无法描述图片。路径: {image_path}"
    except Exception as e:  # TODO: Narrow exception type
        return f"图片描述失败: {str(e)[:200]}"


def _tool_clarify(args: dict) -> str:
    """工具: 向用户追问以澄清需求"""
    return f"需要用户澄清: {args.get('question', '?')}"


def _tool_done(args: dict) -> str:
    """工具: 标记检索完成"""
    return "DONE: " + args.get("reason", "信息已充分")


# 工具名 → handler 函数的调度字典
_TOOL_HANDLERS = {
    "search_knowledge": _tool_search_knowledge,
    "search_wiki": _tool_search_wiki,
    "query_graph": _tool_query_graph,
    "read_doc": _tool_read_doc,
    "extract_table": _tool_extract_table,
    "describe_image": _tool_describe_image,
    "clarify": _tool_clarify,
    "done": _tool_done,
}


async def _execute_tool(tool_call: Dict) -> str:
    """
    执行单个工具调用 — v3.0 调度字典重构。

    通过 _TOOL_HANDLERS 字典将工具名映射到对应的 handler 函数，
    消除巨型 if-elif 链。保持与外部调用者的完全兼容。

    Args:
        tool_call: MiMo function calling 返回的工具调用对象

    Returns:
        工具执行结果的 JSON 字符串或描述文本
    """
    func = tool_call.get("function", {})
    func_name = func.get("name", "")
    try:
        args = json.loads(func.get("arguments", "{}"))
    except json.JSONDecodeError:
        args = {}

    handler = _TOOL_HANDLERS.get(func_name)
    if handler is None:
        return f"未知工具: {func_name}"

    try:
        # 所有 handler 都接受 args dict，部分为 async
        if asyncio.iscoroutinefunction(handler):
            return await handler(args)
        else:
            return handler(args)
    except Exception as e:  # TODO: Narrow exception type
        logger.warning(f"Tool {func_name} error: {e}")
        return f"工具执行失败: {str(e)[:200]}"


async def agentic_search(query: str) -> Dict:
    """
    太极 Agent 主循环：Plan → Execute → Reflect
    返回: {"answer": str, "sources": list, "steps": int, "tool_calls": list}
    """
    t0 = time.time()
    context = []
    all_sources = []
    steps = 0

    for step in range(MAX_STEPS):
        steps = step + 1

        result = await _call_mimo_with_tools(query, context, step)

        if "error" in result:
            logger.error(f"Agentic step {step} error: {result['error']}")
            break

        tool_calls = result.get("tool_calls", [])

        if not tool_calls or result.get("finish_reason") == "stop":
            break

        done_call = None
        execute_calls = []
        for tc in tool_calls:
            if tc["function"]["name"] == "done":
                done_call = tc
            else:
                execute_calls.append(tc)

        if done_call:
            break

        # 并行执行工具
        tool_results = []
        if execute_calls:
            tasks = [_execute_tool(tc) for tc in execute_calls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for tc, res in zip(execute_calls, results):
                content = str(res) if not isinstance(res, Exception) else f"错误: {res}"
                tool_results.append({"id": tc.get("id", ""), "content": content})
                all_sources.append({
                    "tool": tc["function"]["name"],
                    "query": tc["function"].get("arguments", ""),
                    "result": content[:300]
                })

        context.append({"tool_calls": tool_calls, "tool_results": tool_results})

    duration_ms = int((time.time() - t0) * 1000)
    return {
        "steps": steps,
        "duration_ms": duration_ms,
        "sources": all_sources,
        "context": context,
    }
