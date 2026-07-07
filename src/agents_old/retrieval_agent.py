"""
retrieval_agent.py — 检索 Agent v4.0
封装多路召回 + RRF 融合 + 精排为独立 Agent
"""
import logging
import time
from typing import Dict, List

from src.agents import BaseAgent, AgentContext, ToolResult

logger = logging.getLogger(__name__)


class RetrievalAgent(BaseAgent):
    """检索 Agent：多路召回 + RRF 融合"""

    def __init__(self):
        super().__init__(agent_id="retrieval", description="多路检索 + RRF 融合 + 精排")
        self.register_tool("hybrid_search", self._hybrid_search)
        self.register_tool("wiki_search", self._wiki_search)
        self.register_tool("graph_search", self._graph_search)

    async def run(self, ctx: AgentContext) -> Dict:
        """执行检索"""
        start = time.time()
        try:
            from src.services.retrieval import hybrid_search
            from src.db.data_store import load_chunks

            results = await hybrid_search(ctx.query, load_chunks(), top_k=10)
            duration = (time.time() - start) * 1000
            self._record_run(duration)

            return {
                "success": True,
                "results": results,
                "count": len(results),
                "duration_ms": round(duration, 1),
            }
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._record_run(duration, error=True)
            return {"success": False, "results": [], "error": str(e)}

    async def _hybrid_search(self, query: str, top_k: int = 10) -> List[Dict]:
        """混合检索工具"""
        from src.services.retrieval import hybrid_search
        from src.db.data_store import load_chunks
        return await hybrid_search(query, load_chunks(), top_k=top_k)
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

    async def _wiki_search(self, query: str) -> List[Dict]:
        """Wiki 检索工具"""
        try:
            from src.services.wiki import get_wiki_engine
            we = get_wiki_engine()
            return we.search_content(query, limit=3)
        except Exception as e:
            logger.warning("Exception 失败: %s", e, exc_info=True)
            return []
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

    async def _graph_search(self, query: str) -> Dict:
        """知识图谱检索工具"""
        try:
            from src.services.graph_router import get_entity_context
            ctx = get_entity_context(query)
            return {"context": ctx} if ctx else {}
        except Exception as e:
            logger.warning("Exception 失败: %s", e, exc_info=True)
            return {}
