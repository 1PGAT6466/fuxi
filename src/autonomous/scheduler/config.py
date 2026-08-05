"""
调度器配置 (Scheduler Config)
=============================
所有调度器相关的配置常量，集中管理。
"""

import os
from pathlib import Path

# ── 存储路径 ──
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = os.getenv("FUXI_SCHEDULER_DB", str(_DATA_DIR / "scheduler.db"))

# ── 调度引擎 ──
MAX_INSTANCES = int(os.getenv("FUXI_SCHEDULER_MAX_INSTANCES", "1"))
JOB_DEFAULTS = {
    "coalesce": True,  # 合并错过的执行
    "max_instances": MAX_INSTANCES,
    "misfire_grace_time": 60,  # 错过触发窗口（秒）
}

# ── 重试策略 ──
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY = 5  # 初始退避（秒）
DEFAULT_RETRY_MAX_DELAY = 300  # 最大退避（秒）
DEFAULT_RETRY_MULTIPLIER = 2.0  # 指数退避倍数

# ── 优先级（数值越小优先级越高）──
PRIORITY_CRITICAL = 0  # 健康检查、资源监控
PRIORITY_HIGH = 10  # 指标采集、日志分析
PRIORITY_NORMAL = 50  # 缓存清理、配置热更新
PRIORITY_LOW = 80  # 知识库更新、报表生成
PRIORITY_BACKGROUND = 100  # 后台任务

# ── 执行历史 ──
MAX_HISTORY_PER_JOB = 500  # 每个任务保留最大历史记录数
