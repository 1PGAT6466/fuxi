"""
table_agent.py — 表格 Agent v4.0
结构化数据查询 + SQL 生成
"""
import logging
import time
from typing import Dict, List

from src.agents import BaseAgent, AgentContext

logger = logging.getLogger(__name__)


class TableAgent(BaseAgent):
    """表格 Agent：结构化数据查询"""

    def __init__(self):
        super().__init__(agent_id="table", description="表格/结构化数据查询")
        self.register_tool("query_table", self._query_table)
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

    async def run(self, ctx: AgentContext) -> Dict:
        """查询表格数据"""
        start = time.time()
        try:
            from src.services.table_view import table_view_recall
            results = table_view_recall(ctx.query, top_k=5)
            duration = (time.time() - start) * 1000
            self._record_run(duration)
            return {"success": True, "results": results, "count": len(results)}
        except Exception as e:  # TODO: Narrow exception type
            duration = (time.time() - start) * 1000
            self._record_run(duration, error=True)
            return {"success": False, "results": [], "error": str(e)}
    # FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行

    async def _query_table(self, query: str, top_k: int = 5) -> List[Dict]:
        """表格查询工具"""
        from src.services.table_view import table_view_recall
        return table_view_recall(query, top_k=top_k)
