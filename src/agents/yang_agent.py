"""
yang_agent.py — 太极·阳 Agent v4.0
执行层：MiMo 2.5 Pro + FC 工具调用 + 多步推理
"""
import json
import logging
import time
from typing import Dict, List, Optional

from src.agents import BaseAgent, AgentContext

logger = logging.getLogger(__name__)

MAX_STEPS = 5
TOKEN_BUDGET = 15000

YANG_SYSTEM_PROMPT = """你是伏羲知识库的执行智能体。

## 工作原则
1. 先搜索，再回答。绝不凭空编造。
2. 搜索结果不足时，主动扩大搜索范围（换关键词、查图谱、查Wiki）。
3. 涉及数字、规格、价格时，必须引用来源。
4. 不确定时说"根据现有资料无法确定"，不要猜测。

## 工具使用策略
- 简单问题（是什么/怎么用）→ 1次 search_knowledge + done
- 比较问题（A vs B）→ 分别搜索 A 和 B，再比较
- 分析问题（为什么/怎么办）→ 搜索 + 读取相关文档 + 综合分析
- 信息不足 → 尝试 2-3 种不同关键词，仍不足则如实告知

## 输出格式
调用 done 工具时，answer 字段必须是完整的中文回答，包含：
- 直接回答用户问题
- 引用来源（[Ref 1] 格式）
- 如有不确定之处，明确标注"""

YANG_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "搜索企业知识库（文档+Wiki+图谱融合检索）",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "scope": {
                        "type": "string",
                        "enum": ["all", "documents", "wiki", "graph"],
                        "default": "all",
                        "description": "检索范围"
                    },
                    "top_k": {"type": "integer", "default": 5, "description": "返回结果数"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": "读取指定文档的完整内容（用于深入理解某个文档）",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_hash": {"type": "string", "description": "文件哈希"},
                    "chunk_index": {"type": "integer", "description": "指定段落，-1 表示全文", "default": -1}
                },
                "required": ["file_hash"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_entity",
            "description": "查询知识图谱中的实体信息（参数、关系、相关文档）",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {"type": "string", "description": "实体名称，如 PLC、S7-1200"},
                    "relation_type": {"type": "string", "description": "关系类型，如 参数、供应商、替代品"}
                },
                "required": ["entity_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": "完成任务，输出最终答案",
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string", "description": "最终回答"},
                    "confidence": {"type": "number", "description": "置信度 0-1"},
                    "sources": {"type": "array", "items": {"type": "string"}, "description": "引用来源列表"}
                },
                "required": ["answer"]
            }
        }
    }
]


class YangAgent(BaseAgent):
    """太极·阳 Agent：执行层"""

    def __init__(self):
        super().__init__(agent_id="yang", description="太极·阳 执行层")

    async def run(self, ctx: AgentContext) -> Dict:
        """阳·执行主循环"""
        start = time.time()
        messages = [{"role": "system", "content": YANG_SYSTEM_PROMPT}]
        if ctx.history:
            messages.extend(ctx.history[-6:])
        messages.append({"role": "user", "content": ctx.query})

        all_sources = []
        total_tokens = 0

        for step in range(MAX_STEPS):
            try:
                response = await self._call_mimo_fc(messages)
                total_tokens += getattr(getattr(response, 'usage', None), 'total_tokens', 0) or 0

                # token 预算检查
                if total_tokens > TOKEN_BUDGET:
                    duration = (time.time() - start) * 1000
                    self._record_run(duration, total_tokens)
                    return {
                        "answer": "查询过于复杂，请简化问题后重试。",
                        "mode": "token_limit",
                        "steps": step,
                        "tokens": total_tokens,
                    }

                choice = response.choices[0]

                # 无工具调用 → 直接返回文本
                if not getattr(choice.message, 'tool_calls', None):
                    duration = (time.time() - start) * 1000
                    self._record_run(duration, total_tokens)
                    return {
                        "answer": choice.message.content or "",
                        "sources": all_sources[:5],
                        "mode": "direct",
                        "steps": step,
                        "tokens": total_tokens,
                    }

                # 执行工具调用
                tool_call = choice.message.tool_calls[0]
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                # done → Agent 主动结束
                if tool_name == "done":
                    duration = (time.time() - start) * 1000
                    self._record_run(duration, total_tokens)
                    return {
                        "answer": tool_args.get("answer", ""),
                        "confidence": tool_args.get("confidence", 0.8),
                        "sources": tool_args.get("sources", []) or all_sources[:5],
                        "mode": "agent",
                        "steps": step + 1,
                        "tokens": total_tokens,
                    }

                # 执行检索/读取工具
                result = await self._execute_tool(tool_name, tool_args)
                if tool_name == "search_knowledge":
                    all_sources.extend(result.get("results", [])[:3])

                # 将结果加入消息历史
                messages.append({
                    "role": "assistant",
                    "tool_calls": [tool_call],
                    "content": None,
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False)[:3000],
                })

            except Exception as e:
                logger.error(f"[Yang] Step {step} failed: {e}")
                duration = (time.time() - start) * 1000
                self._record_run(duration, total_tokens, error=True)
                return {
                    "answer": f"执行异常: {str(e)[:200]}",
                    "sources": all_sources[:5],
                    "mode": "error",
                    "steps": step,
                }

        # 超过 max_steps
        duration = (time.time() - start) * 1000
        self._record_run(duration, total_tokens)
        return {
            "answer": "查询需要更多步骤，请尝试简化问题。",
            "sources": all_sources[:5],
            "mode": "max_steps",
            "steps": MAX_STEPS,
            "tokens": total_tokens,
        }

    async def _call_mimo_fc(self, messages: List[Dict]):
        """调用 MiMo 2.5 Pro FC"""
        from src.services.llm import _call_api
        from src.config import MIMO_API_KEY, MIMO_BASE_URL, MIMO_MODEL, MIMO_TIMEOUT

        return await _call_api(
            base_url=MIMO_BASE_URL,
            api_key=MIMO_API_KEY,
            model=MIMO_MODEL,
            messages=messages,
            tools=YANG_TOOLS,
            tool_choice="auto",
            temperature=0.1,
            max_tokens=2048,
            timeout=MIMO_TIMEOUT,
        )

    async def _execute_tool(self, tool_name: str, tool_args: Dict) -> Dict:
        """路由执行工具"""
        if tool_name == "search_knowledge":
            return await self._search_knowledge(
                query=tool_args.get("query", ""),
                scope=tool_args.get("scope", "all"),
                top_k=tool_args.get("top_k", 5),
            )
        elif tool_name == "read_document":
            return await self._read_document(
                file_hash=tool_args.get("file_hash", ""),
                chunk_index=tool_args.get("chunk_index", -1),
            )
        elif tool_name == "query_entity":
            return await self._query_entity(
                entity_name=tool_args.get("entity_name", ""),
                relation_type=tool_args.get("relation_type", ""),
            )
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    async def _search_knowledge(self, query: str, scope: str = "all", top_k: int = 5) -> Dict:
        """统一检索：文档+Wiki+图谱"""
        results = []

        if scope in ("all", "documents"):
            try:
                from src.services.retrieval import hybrid_search
                from src.db.data_store import load_chunks
                doc_results = await hybrid_search(query, load_chunks(), top_k=top_k)
                results.extend(doc_results)
            except Exception as e:
                logger.warning(f"[Yang] doc search failed: {e}")

        if scope in ("all", "wiki"):
            try:
                from src.services.wiki import get_wiki_engine
                we = get_wiki_engine()
                wiki_results = we.search_content(query, limit=3)
                results.extend(wiki_results)
            except Exception as e:
                logger.warning(f"[Yang] wiki search failed: {e}")

        if scope in ("all", "graph"):
            try:
                from src.services.graph_router import get_entity_context
                graph_ctx = get_entity_context(query)
                if graph_ctx:
                    results.append({"text": graph_ctx, "file_name": "知识图谱", "source": "graph"})
            except Exception as e:
                logger.warning(f"[Yang] graph search failed: {e}")

        return {"results": results[:top_k], "count": len(results)}

    async def _read_document(self, file_hash: str, chunk_index: int = -1) -> Dict:
        """读取文档"""
        try:
            from src.db.memory_store import get_store
            store = get_store()
            chunks = store.get_by_hash(file_hash)
            if not chunks:
                return {"error": "Document not found"}
            if chunk_index >= 0:
                chunks = [c for c in chunks if c.get("chunk_index") == chunk_index]
            return {"chunks": chunks[:10], "count": len(chunks)}
        except Exception as e:
            return {"error": str(e)}

    async def _query_entity(self, entity_name: str, relation_type: str = "") -> Dict:
        """查询知识图谱实体"""
        try:
            from src.services.graph_router import get_entity_context
            ctx = get_entity_context(entity_name)
            return {"context": ctx} if ctx else {"error": "Entity not found"}
        except Exception as e:
            return {"error": str(e)}
