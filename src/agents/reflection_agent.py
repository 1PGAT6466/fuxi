"""
reflection_agent.py — 反思 Agent v4.0
质量评估 + 改写重试
"""
import logging
import time
from typing import Dict

from src.agents import BaseAgent, AgentContext

logger = logging.getLogger(__name__)


class ReflectionAgent(BaseAgent):
    """反思 Agent：质量评估 + 改写重试"""

    def __init__(self):
        super().__init__(agent_id="reflection", description="回答质量评估 + 反思")

    async def run(self, ctx: AgentContext) -> Dict:
        """评估回答质量"""
        start = time.time()
        try:
            from src.services.judge import judge_and_decide

            answer = ctx.metadata.get("answer", "")
            sources = ctx.metadata.get("sources", [])

            judge_contexts = [
                {"text": r.get("text", ""), "file_name": r.get("file_name", "?")}
                for r in sources[:5]
            ]

            result = await judge_and_decide(answer, judge_contexts)
            duration = (time.time() - start) * 1000
            self._record_run(duration)

            return {
                "success": True,
                "passed": result.get("passed", True),
                "answer": result.get("answer", answer),
                "issues": result.get("judge_result", {}).get("issues", []),
                "duration_ms": round(duration, 1),
            }
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._record_run(duration, error=True)
            return {"success": True, "passed": True, "answer": ctx.metadata.get("answer", ""), "error": str(e)}
