# src/shaoyin/__init__.py
"""少阴·炼化 — 决策合成中枢

架构说明 (v2.2):
  本模块为 RAG 问答的权威入口。推理与合成管线分布如下：
    - ShaoyinBrain: 完整 RAG 管线（意图识别→策略选择→检索→Self-RAG→
                     CRAG→合成→L5 CRAG→校验→重试）★ 权威入口
    - AgenticRAG v2: MiMo function calling 驱动的 Agentic Search
                     (Plan→Execute→Reflect, 8 个工具)
    - LiGua (离卦):  知识蒸馏子能力（关键词检索、内容蒸馏、对比、摘要）
                      注意：离卦侧重 local keyword 检索/蒸馏,
                      Self-RAG/CRAG/答案合成由 ShaoyinBrain 承担

  推荐使用方式：
    # 完整 RAG 问答（推荐）
    from src.shaoyin.brain import ShaoyinBrain
    brain = ShaoyinBrain(meridian)
    result = await brain.think(query, history)

    # Agentic Search（复杂多步查询）
    from src.shaoyin.agentic_rag_v2 import agentic_search
    result = await agentic_search(query)

    # 内容蒸馏
    from src.bagua.li import LiGua
    li = LiGua()
    result = li.execute({"action": "distill", "content": "...", "max_length": 200})
"""

# [Bridge v2.2] 推理/决策功能桥接到离卦 li.py（知识蒸馏与推理子能力）
# 注意：离卦侧重 keyword 检索/蒸馏/对比/摘要，不包含完整 Self-RAG/CRAG 管线
# 完整推理链路由 ShaoyinBrain 承担（Intent→Retrieve→Self-RAG→CRAG→Compose→Validate）
from src.bagua.li import LiGua as DistillationBridge

from .brain import ShaoyinBrain  # ★ 权威 RAG 入口
from .agentic_rag_v2 import agentic_search, TOOLS  # Agentic Search v2.0

# 子模块引用（鲁棒导入：子模块可能有不同的导出命名）
from .smart_self_rag import SmartSelfRAG
from .crag_corrector import CRAGCorrector

# 以下子模块的导入可能因命名差异而失败，使用 try/except 保护
try:
    from .composer import AnswerComposer as Composer
except ImportError:
    Composer = None

try:
    from .query_planner import QueryPlanner
except ImportError:
    QueryPlanner = None

try:
    from .query_router import QueryRouter
except ImportError:
    QueryRouter = None

try:
    from .resolver import Resolver
except ImportError:
    Resolver = None

try:
    from .strategy import StrategySelector
except ImportError:
    StrategySelector = None

try:
    from .validator import Validator
except ImportError:
    Validator = None

try:
    from .tools import ToolRegistry
except ImportError:
    ToolRegistry = None

try:
    from .judge import judge_answer as Judge
except ImportError:
    Judge = None

try:
    from .judge_v2 import JudgeV2
except ImportError:
    JudgeV2 = None

try:
    from .fact_check import FactChecker
except ImportError:
    FactChecker = None

__all__ = [
    "DistillationBridge",
    "ShaoyinBrain",     # ★ 权威入口
    "agentic_search",
    "TOOLS",
    "SmartSelfRAG",
    "CRAGCorrector",
    "Composer",
    "Judge",
    "JudgeV2",
    "FactChecker",
    "QueryPlanner",
    "QueryRouter",
    "Resolver",
    "StrategySelector",
    "Validator",
    "ToolRegistry",
]
