"""
自修复模块 (Healer Module)
===========================
伏羲自运转 Phase 2：自修复引擎
  - 接收告警信号，自动触发修复
  - 修复前快照，失败自动回滚
  - 频率限制、审计日志、人工审批
  - 8个预置修复动作

用法:
    from src.autonomous.healer import HealerEngine, HealerConfig

    engine = HealerEngine()
    result = await engine.execute_action("clear_cache")
"""

from .actions import PRESET_ACTIONS, ActionResult, BaseAction, RepairAction
from .config import HealerConfig
from .engine import HealerEngine
from .safety import RepairStatus, RiskLevel

__all__ = [
    "HealerEngine",
    "HealerConfig",
    "RepairAction",
    "BaseAction",
    "ActionResult",
    "RiskLevel",
    "RepairStatus",
    "PRESET_ACTIONS",
]
