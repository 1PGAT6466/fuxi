"""
graph_agent.py — 图谱 Agent v4.0
实体链接 + 路径推理
"""
import logging
import time
from typing import Dict

from src.agents import BaseAgent, AgentContext

logger = logging.getLogger(__name__)


class GraphAgent(BaseAgent):
    """图谱 Agent：知识图谱推理"""

    def __init__(self):
        super().__init__(agent_id="graph", description="知识图谱实体链接 + 路径推理")
        self.register_tool("entity_link", self._entity_link)
        self.register_tool("graph_route", self._graph_route)

    async def run(self, ctx: AgentContext) -> Dict:
        """执行图谱推理"""
        start = time.time()
        try:
            from src.services.graph_router import get_entity_context, route_to_categories
            entity_ctx = get_entity_context(ctx.query)
            categories = route_to_categories(ctx.query)
            duration = (time.time() - start) * 1000
            self._record_run(duration)
            return {
                "success": True,
                "entity_context": entity_ctx or "",
                "categories": categories or [],
            }
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._record_run(duration, error=True)
            return {"success": False, "entity_context": "", "categories": [], "error": str(e)}

    async def _entity_link(self, query: str) -> Dict:
        """实体链接工具"""
        from src.services.graph_router import get_entity_context
        ctx = get_entity_context(query)
        return {"context": ctx} if ctx else {}

    async def _graph_route(self, query: str) -> Dict:
        """图谱路由工具"""
        from src.services.graph_router import route_to_categories
        cats = route_to_categories(query)
        return {"categories": cats} if cats else {}
