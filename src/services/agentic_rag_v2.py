"""
agentic_rag_v2.py — Agentic RAG
FC循环决策 + 8个工具
"""
import logging
from typing import Dict, List

logger = logging.getLogger("services.agentic_rag_v2")


class AgenticRAG:
    """Agentic RAG — FC循环决策"""

    MAX_LOOPS = 3
    TOKEN_BUDGET = 4000

    TOOLS = [
        {"name": "search_knowledge", "description": "搜索知识库"},
        {"name": "read_document", "description": "读取文档"},
        {"name": "query_entity", "description": "查询实体"},
        {"name": "get_events", "description": "获取事件"},
        {"name": "get_relations", "description": "获取关系"},
        {"name": "summarize", "description": "总结"},
        {"name": "validate", "description": "验证"},
        {"name": "done", "description": "完成"},
    ]

    async def run(self, query: str) -> Dict:
        """执行Agentic RAG"""
        loops = 0
        total_tokens = 0
        results = []

        while loops < self.MAX_LOOPS and total_tokens < self.TOKEN_BUDGET:
            loops += 1

            # Plan
            plan = await self._plan(query, results)

            # Execute
            action_result = await self._execute(plan)
            results.append(action_result)
            total_tokens += action_result.get("tokens", 0)

            # Reflect
            if action_result.get("done"):
                break

        return {
            "answer": results[-1].get("answer", "") if results else "",
            "confidence": results[-1].get("confidence", 0) if results else 0,
            "sources": results[-1].get("sources", []) if results else [],
            "loops": loops,
            "total_tokens": total_tokens,
        }

    async def _plan(self, query: str, history: List[Dict]) -> Dict:
        """规划下一步"""
        return {"tool": "search_knowledge", "query": query}

    async def _execute(self, plan: Dict) -> Dict:
        """执行工具"""
        tool = plan.get("tool", "search_knowledge")

        if tool == "search_knowledge":
            from src.taiyang.retrieval import hybrid_search
            results = await hybrid_search(plan.get("query", ""), top_k=10)
            return {"results": results, "tokens": 100, "done": len(results) > 0}

        return {"results": [], "tokens": 0, "done": True}
