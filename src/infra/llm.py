"""
infra/llm.py — 重导出壳（v1.50 合并后）
=====================================
本文件是纯粹的重导出壳（re-export shell），不包含任何业务逻辑。
所有 LLM 调用逻辑已统一到 src.services.llm 模块。

设计意图：
  - 保持向后兼容：旧代码中 `from src.infra.llm import call_llm` 不会报错
  - 单一职责：services/llm.py 负责业务逻辑，infra/llm.py 仅做路径转发
  - 新代码应直接使用 `from src.services.llm import ...`

v1.50: 合并完成，本文件从实现层降级为重导出壳
"""

# flake8: noqa: F403, F401
from src.services.llm import *  # noqa: F403
