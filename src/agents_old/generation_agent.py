"""
generation_agent.py — 生成 Agent v4.0
封装 LLM 调用 + 引用标注 + 上下文压缩
"""
import logging
import time
from typing import Dict, List

from src.agents import BaseAgent, AgentContext

logger = logging.getLogger(__name__)


class GenerationAgent(BaseAgent):
    """生成 Agent：上下文合成 + 引用标注"""

    def __init__(self):
        super().__init__(agent_id="generation", description="LLM 生成 + 引用标注")
        self.register_tool("call_llm", self._call_llm)
        self.register_tool("compress_context", self._compress_context)

    async def run(self, ctx: AgentContext) -> Dict:
        """执行生成"""
        start = time.time()
        try:
            from src.services.llm import call_deepseek

            # 构建上下文
            context_parts = []
            for i, r in enumerate(ctx.intermediate_results[:5]):
                context_parts.append(f"[Ref {i+1}] {r.get('file_name', '?')}\n{r.get('text', '')[:500]}")
            context = "\n\n---\n\n".join(context_parts) or "知识库中暂无相关文档."

            prompt = (
                f"你是伏羲知识库 AI 助手。请根据以下文档回答用户问题。\n"
                f"规则：1. 仅依据文档作答 2. 引用时使用 [Ref N] 标注 3. Markdown 格式\n\n"
                f"文档：\n{context}\n\n用户问题：{ctx.query}\n\n请回答："
            )

            answer = await call_deepseek(prompt)
            duration = (time.time() - start) * 1000
            self._record_run(duration)

            return {
                "success": True,
                "answer": answer or "AI 服务暂时不可用",
                "sources": ctx.intermediate_results[:5],
                "duration_ms": round(duration, 1),
            }
        except Exception as e:  # TODO: Narrow exception type
            duration = (time.time() - start) * 1000
            self._record_run(duration, error=True)
            return {"success": False, "answer": f"生成异常: {str(e)[:200]}", "error": str(e)}

    async def _call_llm(self, prompt: str) -> str:
        """LLM 调用工具"""
        from src.services.llm import call_deepseek
        return await call_deepseek(prompt)

    async def _compress_context(self, context_parts: List[str], query: str, budget: int = 4000) -> List[str]:
        """上下文压缩工具"""
        try:
            from src.services.context_compressor import compress_context
            return await compress_context(context_parts, query, total_budget=budget)
        except Exception:  # TODO: Narrow exception type
            return context_parts
