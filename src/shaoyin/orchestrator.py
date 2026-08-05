"""
orchestrator.py — 少阴·调度器 (🚫 DEPRECATED v2.2)

⚠️ 弃用通知 (2026-08-05):
  本模块的 Plan→Execute→Reflect 循环已被 src.shaoyin.agentic_rag_v2 取代。

  原因：
    - orchestrator.py 实现过于简单（47 行），仅有占位逻辑
    - _plan() 始终返回固定的 3 步计划，无真实推理
    - _execute() 仅调用一次 hybrid_search，无工具编排
    - _reflect() 仅检查最大分数，无真正的质量反思
    - 无 multi-step tool calling、无 function calling 编排

  agentic_rag_v2.py 的优势：
    - MiMo function calling 驱动的 8 工具 Plan→Execute→Reflect 循环
    - 每个工具独立 handler (_TOOL_HANDLERS 调度字典)
    - MAX_STEPS=5 步循环，支持图谱遍历、表格提取、Wiki 搜索
    - 真正的 Plan→Execute→Reflect: MiMo 自主选择工具、并行执行、
      基于执行结果反思下一步

  迁移指南:
    # 旧方式
    from src.shaoyin.orchestrator import Orchestrator
    orch = Orchestrator()
    result = await orch.run(query, strategy="deep")

    # 新方式
    from src.shaoyin.agentic_rag_v2 import agentic_search
    result = await agentic_search(query)

  如需完整的 RAG 问答（非 agentic search），请使用 ShaoyinBrain:
    from src.shaoyin.brain import ShaoyinBrain
    brain = ShaoyinBrain(meridian)
    result = await brain.think(query)

  本文件将在 v3.0 中移除。
"""

import logging
import warnings
from typing import Dict

warnings.warn(
    "shaoyin.orchestrator.Orchestrator 已弃用 (v2.2)。"
    "请迁移到 shaoyin.agentic_rag_v2.agentic_search 或 "
    "shaoyin.brain.ShaoyinBrain。详见模块文档。",
    DeprecationWarning,
    stacklevel=2,
)

logger = logging.getLogger("shaoyin.orchestrator")


class Orchestrator:
    """调度器 — Plan→Execute→Reflect (🚫 DEPRECATED)

    本类已弃用，保留仅为向后兼容。
    新代码请使用 agentic_rag_v2.agentic_search() 或 ShaoyinBrain.think()。
    """

    MAX_LOOPS = 3
    TOKEN_BUDGET = 4000

    async def run(self, query: str, strategy: str = "deep") -> Dict:
        """执行 Plan→Execute→Reflect 循环 (DEPRECATED)

        Args:
            query: 用户查询
            strategy: 策略（"deep" | "fast" | "table"）

        Returns:
            包含 answer、confidence、sources、loops 的结果字典
        """
        logger.warning(
            "[Orchestrator] 使用已弃用的 Orchestrator.run()，"
            "建议迁移到 agentic_search() 或 ShaoyinBrain.think()"
        )

        # ── 委托给 ShaoyinBrain ──
        try:
            from src.shaoyin.brain import ShaoyinBrain

            brain = ShaoyinBrain(None)
            result = await brain.think(query)
            return {
                "answer": result.get("answer", ""),
                "confidence": result.get("confidence", 0.5),
                "sources": result.get("sources", []),
                "loops": 1,
            }
        except Exception:
            pass

        # ── fallback: 保留原逻辑用于极端兼容 ──
        plan = self._plan(query, strategy)
        result = await self._execute(plan)
        reflection = self._reflect(query, result)

        if not reflection["passed"] and reflection.get("should_retry"):
            result = await self._execute(plan)
            reflection = self._reflect(query, result)

        return {
            "answer": result.get("answer", ""),
            "confidence": reflection.get("confidence", 0.5),
            "sources": result.get("sources", []),
            "loops": 1,
        }

    def _plan(self, query: str, strategy: str) -> Dict:
        return {"query": query, "strategy": strategy, "steps": ["search", "compose", "validate"]}

    async def _execute(self, plan: Dict) -> Dict:
        from src.taiyang.retrieval import hybrid_search

        results = await hybrid_search(plan["query"], top_k=10)
        return {"answer": "", "sources": results, "results": results}

    def _reflect(self, query: str, result: Dict) -> Dict:
        sources = result.get("sources", [])
        if not sources:
            return {"passed": False, "confidence": 0.0, "should_retry": True}
        max_score = max([s.get("score", 0) for s in sources], default=0)
        return {"passed": max_score > 0.3, "confidence": max_score, "should_retry": max_score < 0.3}
