"""
agentic_rag.py — 真正的 Agentic RAG 循环 (v1.43)
Plan → Execute → Reflect 循环，由 MiMo 2.5 Pro function calling 驱动
"""
import json, logging, asyncio, time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 最大循环步数
MAX_STEPS = 5
# 成本控制：最大 token 消耗
MAX_TOTAL_TOKENS = 4000

# 工具定义（供 MiMo function calling 使用）
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "在知识库中检索相关文档片段",
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
            "description": "在 Wiki 知识库中搜索结构化知识",
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
            "name": "done",
            "description": "已完成所有检索，可以生成最终答案",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "判断依据"}
                },
                "required": ["reason"]
            }
        }
    }
]

SYSTEM_PROMPT = """你是伏羲知识库的智能检索助手。
用户提问后，你需要：
1. 分析问题，制定检索计划
2. 调用工具检索相关信息
3. 评估检索结果是否足够回答问题
4. 如果不够，调整查询继续检索
5. 信息充分后，调用 done 工具

你可以并行调用多个工具。每次检索后反思结果质量。"""


async def _call_mimo_with_tools(query: str, context: List[Dict], step: int) -> Dict:
    """调用 MiMo API with function calling"""
    from src.services.llm import _call_api
    from src.config import MIMO_API_KEY, MIMO_BASE_URL, MIMO_MODEL, MIMO_TIMEOUT

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # 第一步：用户问题
    if step == 0:
        messages.append({"role": "user", "content": query})
    else:
        # 后续步骤：带上之前的工具调用结果
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


async def _execute_tool(tool_call: Dict) -> str:
    """执行单个工具调用"""
    func_name = tool_call["function"]["name"]
    args = json.loads(tool_call["function"]["get"]("arguments", "{}") if isinstance(tool_call["function"], dict) else tool_call["function"].get("arguments", "{}"))
    
    if func_name == "search_knowledge":
        from src.api.search import search
        query = args.get("query", "")
        top_k = args.get("top_k", 5)
        # 调用内部搜索
        try:
            from src.services.retrieval import hybrid_search
            results = await hybrid_search(query, top_k=top_k)
            snippets = [r.get("text", "")[:200] for r in results[:top_k]]
            return json.dumps(snippets, ensure_ascii=False)
        except Exception as e:
            return f"搜索失败: {e}"
    
    elif func_name == "search_wiki":
        from src.services.wiki import search_wiki_pages
        query = args.get("query", "")
        try:
            results = await search_wiki_pages(query)
            return json.dumps([r.get("title", "") + ": " + r.get("summary", "")[:100] for r in results[:3]], ensure_ascii=False)
        except Exception as e:
            return f"Wiki 搜索失败: {e}"
    
    elif func_name == "done":
        return "DONE: " + args.get("reason", "信息已充分")
    
    return f"未知工具: {func_name}"


async def agentic_search(query: str) -> Dict:
    """
    Agentic RAG 主循环：Plan → Execute → Reflect
    返回: {"answer": str, "sources": list, "steps": int, "tool_calls": list}
    """
    t0 = time.time()
    context = []
    all_sources = []
    steps = 0
    
    for step in range(MAX_STEPS):
        steps = step + 1
        
        # Plan: 让 MiMo 决定下一步
        result = await _call_mimo_with_tools(query, context, step)
        
        if "error" in result:
            logger.error(f"Agentic step {step} error: {result['error']}")
            break
        
        tool_calls = result.get("tool_calls", [])
        
        # 没有工具调用 = 模型认为可以直接回答
        if not tool_calls or result.get("finish_reason") == "stop":
            break
        
        # 检查是否有 done 巡具
        done_call = None
        execute_calls = []
        for tc in tool_calls:
            if tc["function"]["name"] == "done":
                done_call = tc
            else:
                execute_calls.append(tc)
        
        if done_call:
            break
        
        # Execute: 并行执行所有工具
        tool_results = []
        if execute_calls:
            tasks = [_execute_tool(tc) for tc in execute_calls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for tc, res in zip(execute_calls, results):
                content = str(res) if not isinstance(res, Exception) else f"错误: {res}"
                tool_results.append({
                    "id": tc.get("id", ""),
                    "content": content,
                })
                all_sources.append({"tool": tc["function"]["name"], "query": tc["function"].get("arguments", ""), "result": content[:200]})
        
        # 记录上下文
        context.append({
            "tool_calls": tool_calls,
            "tool_results": tool_results,
        })
    
    duration_ms = int((time.time() - t0) * 1000)
    
    return {
        "steps": steps,
        "duration_ms": duration_ms,
        "sources": all_sources,
        "context": context,
    }
