"""
bagua — 八卦层 · 伏羲 v2.1 重构

八卦是系统的 8 大功能模块，每个卦对应一类核心能力：
  乾 ☰ — 知识检索与搜索
  坤 ☷ — 记忆存储与管理
  震 ☳ — 主动推送与通知
  巽 ☴ — 数据接入与管道
  坎 ☵ — 风险控制与安全
  离 ☲ — 知识蒸馏与推理
  艮 ☶ — 稳定性与自我修复
  兑 ☱ — 对话与交互

所有卦继承自 GuaBase，拥有统一的健康管理、降级矩阵和断路器。
"""

from src.bagua.base_gua import (
    GuaBase,
    CircuitState,
    HealthLevel,
    FallbackAction,
    DegradationRule,
)

from src.infra.circuit_breaker import DependencyStatus

__all__ = [
    "GuaBase",
    "CircuitState",
    "HealthLevel",
    "FallbackAction",
    "DegradationRule",
    "DependencyStatus",
]
