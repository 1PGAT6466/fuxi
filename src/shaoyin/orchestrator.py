"""
orchestrator.py — 少阴·调度器
Plan→Execute→Reflect 循环
"""
import logging
from typing import Dict, List

logger = logging.getLogger("shaoyin.orchestrator")


class Orchestrator:
    """调度器 — Plan→Execute→Reflect"""

    MAX_LOOPS = 3
    TOKEN_BUDGET = 4000

    async def run(self, query: str, strategy: str = "deep") -> Dict:
        """执行 Plan→Execute→Reflect 循环"""
        plan = await self._plan(query, strategy)
        result = await self._execute(plan)
        reflection = await self._reflect(query, result)

        if not reflection["passed"] and reflection.get("should_retry"):
            result = await self._execute(plan)
            reflection = await self._reflect(query, result)

        return {
            "answer": result.get("answer", ""),
            "confidence": reflection.get("confidence", 0.5),
            "sources": result.get("sources", []),
            "loops": 1,
        }

    async def _plan(self, query: str, strategy: str) -> Dict:
        return {"query": query, "strategy": strategy, "steps": ["search", "compose", "validate"]}

    async def _execute(self, plan: Dict) -> Dict:
        from src.taiyang.retrieval import hybrid_search
        results = await hybrid_search(plan["query"], top_k=10)
        return {"answer": "", "sources": results, "results": results}

    async def _reflect(self, query: str, result: Dict) -> Dict:
        sources = result.get("sources", [])
        if not sources:
            return {"passed": False, "confidence": 0.0, "should_retry": True}
        max_score = max([s.get("score", 0) for s in sources], default=0)
        return {"passed": max_score > 0.3, "confidence": max_score, "should_retry": max_score < 0.3}
