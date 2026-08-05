"""
伏羲调度器 (Fuxi Scheduler)
============================
基于 APScheduler 的任务编排引擎：
  - 优先级队列
  - 指数退避重试
  - 任务依赖管理
  - SQLite 持久化
"""

from src.autonomous.scheduler.engine import FuxiScheduler
from src.autonomous.scheduler.jobs import register_preset_jobs

__all__ = ["FuxiScheduler", "register_preset_jobs"]
