"""
报告生成器配置 (Reporter Config)
================================
报告模块的全局配置参数。
"""

import os
from pathlib import Path

# ── 存储路径 ──
_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
REPORT_DIR = os.getenv("FUXI_REPORT_DIR", str(_DATA_DIR / "reports"))
REPORT_DB_PATH = os.getenv("FUXI_REPORT_DB", str(_DATA_DIR / "reports.db"))

# ── 报告格式 ──
REPORT_FORMATS = ["markdown", "html"]  # 支持的输出格式

# ── 数据聚合 ──
# 指标名称映射（MetricsCollector 中的 metric name）
METRIC_CPU = "system.cpu.percent"
METRIC_MEMORY = "system.memory.percent"
METRIC_DISK = "system.disk.percent"
METRIC_NET_SENT = "system.net.bytes_sent"
METRIC_NET_RECV = "system.net.bytes_recv"
METRIC_API_LATENCY = "business.latency_avg"
METRIC_API_ERROR_RATE = "business.error_rate"
METRIC_API_REQUEST_COUNT = "business.request_count"

# ── 报告模板变量 ──
TEMPLATE_VARS = {
    "system_name": "伏羲·内世界",
    "version": os.getenv("FUXI_VERSION", "v1.44"),
    "author": "伏羲自运转系统",
}

# ── 存储策略 ──
MAX_REPORTS_PER_TYPE = 100  # 每种类型最大保留报告数
REPORT_RETENTION_DAYS = 90  # 报告保留天数

# ── 聚合优化 ──
AGGREGATION_CACHE_TTL = 300  # 聚合结果缓存 TTL（秒）
