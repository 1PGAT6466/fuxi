"""
nose/ — 器官分层结构

分层结构：
├── signal_layer.py      # 信号层：处理经络信号
├── business_layer.py    # 业务层：核心处理逻辑
├── data_layer.py        # 数据层：数据持久化
└── utility_layer.py     # 工具层：辅助函数
"""

from .signal_layer import NoseAgent

__all__ = ["NoseAgent"]
