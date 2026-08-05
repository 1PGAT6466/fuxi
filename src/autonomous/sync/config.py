"""
数据同步配置 (Sync Config)
============================
集中管理同步模块的所有配置常量。
"""

import os
from pathlib import Path

# ── 存储路径 ──
_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
SYNC_DB_PATH = os.getenv("FUXI_SYNC_DB", str(_DATA_DIR / "sync.db"))
SYNC_STATE_DIR = Path(os.getenv("FUXI_SYNC_STATE_DIR", str(_DATA_DIR / "sync_state")))

# ── 插件源同步 ──
PLUGIN_SYNC_SOURCES = {
    "npm": {
        "registry": os.getenv("NPM_REGISTRY", "https://registry.npmjs.org"),
        "search_endpoint": "/-/v1/search",
        "timeout": 30,
    },
    "github": {
        "api_base": os.getenv("GITHUB_API", "https://api.github.com"),
        "token": os.getenv("GITHUB_TOKEN", ""),
        "org": os.getenv("GITHUB_ORG", ""),
        "timeout": 30,
    },
    "pypi": {
        "api_base": os.getenv("PYPI_API", "https://pypi.org/pypi"),
        "timeout": 30,
    },
}

# 同步频率（秒）
PLUGIN_SYNC_INTERVAL = int(os.getenv("PLUGIN_SYNC_INTERVAL", "3600"))  # 1小时
KNOWLEDGE_SYNC_INTERVAL = int(os.getenv("KNOWLEDGE_SYNC_INTERVAL", "21600"))  # 6小时
CACHE_CLEANUP_INTERVAL = int(os.getenv("CACHE_CLEANUP_INTERVAL", "86400"))  # 24小时

# ── 知识库同步 ──
KNOWLEDGE_WATCH_DIRS = [
    str(_DATA_DIR / "knowledge"),
    str(_DATA_DIR / "documents"),
]
KNOWLEDGE_HASH_ALGORITHM = "sha256"
KNOWLEDGE_BATCH_SIZE = int(os.getenv("KNOWLEDGE_BATCH_SIZE", "50"))

# ── 缓存管理 ──
CACHE_MAX_SIZE_MB = int(os.getenv("CACHE_MAX_SIZE_MB", "512"))
CACHE_MAX_AGE_HOURS = int(os.getenv("CACHE_MAX_AGE_HOURS", "24"))
CACHE_CLEANUP_THRESHOLD = float(os.getenv("CACHE_CLEANUP_THRESHOLD", "0.8"))  # 80% 时触发清理
CACHE_WARMUP_BATCH_SIZE = int(os.getenv("CACHE_WARMUP_BATCH_SIZE", "100"))

# ── 重试策略 ──
SYNC_MAX_RETRIES = int(os.getenv("SYNC_MAX_RETRIES", "3"))
SYNC_RETRY_DELAY = float(os.getenv("SYNC_RETRY_DELAY", "10.0"))

# ── 日志 ──
SYNC_LOG_FILE = str(_DATA_DIR / "sync.log")
