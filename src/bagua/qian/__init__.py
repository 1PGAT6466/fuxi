"""
qian/ - 乾卦模块
================

乾卦是伏羲 RAG 系统的意识中枢（0 的居所），通过 IntentBus 调度
其他 7 个卦，实现完整的"意图循环"。

模块结构：
- intent_loop.py           # 意图循环（Intent Loop）
- cycle_guard.py           # CycleGuard（循环守护）
- safety_cruise.py         # SafetyCruise（安全巡航）
- degradation.py           # 三层降级
- session_manager.py       # Session 隔离
- llm_dispatcher.py        # LLM 调度
- fallback.py              # 降级和回退
- health_check.py          # 健康检查
- utils.py                 # 工具函数
- qian_gua.py              # 乾卦主类
"""

from .qian_gua import QianGua
from .intent_loop import IntentLoop
from .cycle_guard import CycleGuard
from .safety_cruise import SafetyCruise
from .degradation import DegradationManager
from .session_manager import SessionManager
from .llm_dispatcher import LLMDispatcher
from .fallback import FallbackManager
from .health_check import HealthChecker

__all__ = [
    "QianGua",
    "IntentLoop",
    "CycleGuard",
    "SafetyCruise",
    "DegradationManager",
    "SessionManager",
    "LLMDispatcher",
    "FallbackManager",
    "HealthChecker",
]
