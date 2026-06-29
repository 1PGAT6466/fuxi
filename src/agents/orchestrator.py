"""
orchestrator.py — 调度 Agent v4.0
拆解问题 → 分配子任务 → 收集结果
"""
import logging
import time
from typing import Dict, List

from src.agents import BaseAgent, AgentContext
from src.agents.retrieval_agent import RetrievalAgent
from src.agents.generation_agent import GenerationAgent
from src.agents.reflection_agent import ReflectionAgent

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """调度 Agent：Plan → Execute → Reflect 循环"""

    def __init__(self):
        super().__init__(agent_id="orchestrator", description="调度多 Agent 协作")
        self.retrieval = RetrievalAgent()
        self.generation = GenerationAgent()
        self.reflection = ReflectionAgent()

    async def run(self, ctx: AgentContext) -> Dict:
        """执行调度"""
        start = time.time()

        # Phase 1: 检索
        retrieval_result = await self.retrieval.run(ctx)
        if not retrieval_result.get("success"):
            return {
                "answer": "检索服务暂时不可用，请稍后重试。",
                "sources": [],
                "mode": "retrieval_error",
                "agent_metrics": self._collect_metrics(),
            }

        ctx.intermediate_results = retrieval_result.get("results", [])

        # Phase 2: 生成
        gen_result = await self.generation.run(ctx)
        if not gen_result.get("success"):
            return {
                "answer": gen_result.get("answer", "生成异常"),
                "sources": ctx.intermediate_results[:5],
                "mode": "generation_error",
                "agent_metrics": self._collect_metrics(),
            }

        answer = gen_result.get("answer", "")
        ctx.metadata["answer"] = answer
        ctx.metadata["sources"] = ctx.intermediate_results[:5]

        # Phase 3: 反思（非流式时）
        if not ctx.metadata.get("stream"):
            try:
                reflect_result = await self.reflection.run(ctx)
                if reflect_result.get("success") and not reflect_result.get("passed"):
                    logger.info(f"[Orchestrator] Reflection flagged: {reflect_result.get('issues')}")
                    answer = reflect_result.get("answer", answer)
            except Exception as e:
                logger.warning(f"[Orchestrator] Reflection failed: {e}")

        duration = (time.time() - start) * 1000

        return {
            "answer": answer,
            "sources": ctx.intermediate_results[:5],
            "mode": "agent_orchestrated",
            "duration_ms": round(duration, 1),
            "retrieval_count": retrieval_result.get("count", 0),
            "agent_metrics": self._collect_metrics(),
        }

    def _collect_metrics(self) -> Dict:
        """收集所有 Agent 指标"""
        return {
            "retrieval": self.retrieval.get_metrics(),
            "generation": self.generation.get_metrics(),
            "reflection": self.reflection.get_metrics(),
        }


# 全局实例
_orchestrator = None

def get_orchestrator() -> OrchestratorAgent:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = OrchestratorAgent()
    return _orchestrator


async def agent_chat(query: str, history: List[Dict] = None, stream: bool = False) -> Dict:
    """Agent 对话入口（替代旧 agentic_rag_v2）"""
    ctx = AgentContext(
        query=query,
        history=history or [],
        metadata={"stream": stream},
    )
    orchestrator = get_orchestrator()
    return await orchestrator.run(ctx)
