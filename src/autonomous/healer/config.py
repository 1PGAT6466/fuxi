"""
自修复配置模块 (Healer Configuration)
====================================
修复引擎的全局配置参数
"""

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class HealerConfig:
    """自修复引擎配置"""

    # === 频率限制 ===
    default_cooldown: int = 300  # 默认冷却期（秒）
    high_risk_cooldown: int = 600  # 高危动作冷却期（秒）

    # === 回滚配置 ===
    snapshot_dir: str = "data/healer/snapshots"  # 快照存储路径
    max_snapshots: int = 50  # 最大快照数量
    rollback_timeout: int = 60  # 回滚超时（秒）

    # === 审计日志 ===
    audit_log_path: str = "data/healer/audit.log"  # 审计日志路径
    history_max: int = 1000  # 最大历史记录数

    # === 人工审批 ===
    approval_timeout: int = 300  # 审批超时（秒）
    auto_approve_low_risk: bool = True  # 低危动作自动批准

    # === 执行控制 ===
    max_concurrent_repairs: int = 3  # 最大并发修复数
    action_timeout: int = 120  # 单个动作超时（秒）
    max_retries: int = 2  # 最大重试次数
    retry_delay: int = 10  # 重试间隔（秒）

    # === 服务端点 ===
    chromadb_url: str = os.getenv("CHROMADB_URL", "http://localhost:8000")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:8000")

    # === 磁盘清理阈值 ===
    disk_cleanup_threshold: float = 90.0  # 触发清理的磁盘使用率（%）
    disk_cleanup_target: float = 80.0  # 清理目标使用率（%）
    cache_dirs: List[str] = field(
        default_factory=lambda: [
            "/tmp/fuxi",
            "data/cache",
            "data/temp",
        ]
    )
