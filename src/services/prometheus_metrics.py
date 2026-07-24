"""
prometheus_metrics.py — 完整监控告警体系 (v1.44 P1 核心修复)

功能覆盖：
  1. 系统指标：CPU、内存、磁盘
  2. 业务指标：请求量、响应时间、错误率
  3. RAG 指标：检索质量、LLM 调用次数、缓存命中率
  4. 告警规则：阈值告警、趋势告警

架构集成：
  - 复用现有 metrics.py 中的 prometheus 指标定义
  - 与 alerts.py 告警管理联动
  - 异步系统指标采集（基于 psutil）
  - 支持 /api/metrics 端点输出 Prometheus 格式

约束：
  - 不修改现有框架代码
  - 保持与现有架构一致
  - 异步编程模式（async/await）
"""

import asyncio
import logging
import time
import threading
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime, timezone

import psutil
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY

from src.services.metrics import (
    http_requests_total,
    http_request_duration_seconds,
    search_requests_total,
    search_duration_seconds,
    search_result_count,
    cache_hits_total,
    cache_misses_total,
    llm_requests_total,
    llm_duration_seconds,
    token_consumed_total,
    token_cost_total,
    vector_store_chunks,
    vector_store_health,
    sqlite_chunks,
    feedback_total,
    organ_health,
    record_search,
    record_cache,
    record_llm,
    record_feedback,
    update_store_stats,
    get_metrics_response,
)
from src.config import DATA_DIR as CONFIG_DATA_DIR

logger = logging.getLogger(__name__)

# ============ 配置常量 ============
SYSTEM_METRICS_INTERVAL = 10.0
TREND_WINDOW_SIZE = 60
LATENCY_HISTORY_SIZE = 1000
ERROR_HISTORY_SIZE = 500

# ============ 系统级 Prometheus 指标 ============

system_cpu_percent = Gauge(
    "fuxi_system_cpu_percent",
    "CPU 使用率百分比",
    ["core"]
)
system_cpu_load_1m = Gauge("fuxi_system_cpu_load_1m", "系统 1 分钟平均负载")
system_cpu_load_5m = Gauge("fuxi_system_cpu_load_5m", "系统 5 分钟平均负载")
system_cpu_load_15m = Gauge("fuxi_system_cpu_load_15m", "系统 15 分钟平均负载")

system_memory_total_bytes = Gauge("fuxi_system_memory_total_bytes", "系统总内存（字节）")
system_memory_used_bytes = Gauge("fuxi_system_memory_used_bytes", "系统已用内存（字节）")
system_memory_percent = Gauge("fuxi_system_memory_percent", "内存使用率百分比")

system_swap_total_bytes = Gauge("fuxi_system_swap_total_bytes", "交换分区总大小（字节）")
system_swap_used_bytes = Gauge("fuxi_system_swap_used_bytes", "交换分区已用（字节）")
system_swap_percent = Gauge("fuxi_system_swap_percent", "交换分区使用率百分比")

system_disk_total_bytes = Gauge("fuxi_system_disk_total_bytes", "磁盘总大小（字节）", ["mountpoint"])
system_disk_used_bytes = Gauge("fuxi_system_disk_used_bytes", "磁盘已用（字节）", ["mountpoint"])
system_disk_percent = Gauge("fuxi_system_disk_percent", "磁盘使用率百分比", ["mountpoint"])
system_disk_read_bytes = Gauge("fuxi_system_disk_read_bytes", "磁盘读取字节数", ["device"])
system_disk_write_bytes = Gauge("fuxi_system_disk_write_bytes", "磁盘写入字节数", ["device"])

system_net_bytes_sent = Gauge("fuxi_system_net_bytes_sent", "网络发送字节数", ["interface"])
system_net_bytes_recv = Gauge("fuxi_system_net_bytes_recv", "网络接收字节数", ["interface"])
system_net_packets_sent = Gauge("fuxi_system_net_packets_sent", "网络发送包数", ["interface"])
system_net_packets_recv = Gauge("fuxi_system_net_packets_recv", "网络接收包数", ["interface"])

system_process_open_fds = Gauge("fuxi_system_process_open_fds", "进程打开的文件描述符数")
system_process_threads = Gauge("fuxi_system_process_threads", "进程线程数")
system_process_uptime_seconds = Gauge("fuxi_system_process_uptime_seconds", "进程运行时长（秒）")
system_uptime_seconds = Gauge("fuxi_system_uptime_seconds", "系统运行时间（秒）")

# ============ RAG 专用指标 ============

rag_retrieval_precision = Gauge("fuxi_rag_retrieval_precision", "检索精度 (Precision)")
rag_retrieval_recall = Gauge("fuxi_rag_retrieval_recall", "检索召回率 (Recall)")
rag_retrieval_f1 = Gauge("fuxi_rag_retrieval_f1", "检索 F1 分数")
rag_retrieval_mrr = Gauge("fuxi_rag_retrieval_mrr", "检索平均倒数排名 (MRR)")
rag_retrieval_ndcg = Gauge("fuxi_rag_retrieval_ndcg", "检索 NDCG@10")

rag_llm_calls_total = Counter("fuxi_rag_llm_calls_total", "RAG 场景 LLM 调用总数", ["stage"])
rag_llm_tokens_total = Counter("fuxi_rag_llm_tokens_total", "RAG 场景 LLM Token 消耗", ["stage", "direction"])
rag_llm_latency_seconds = Histogram(
    "fuxi_rag_llm_latency_seconds", "RAG 场景 LLM 调用延迟",
    ["stage"], buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 30.0]
)

rag_cache_hit_rate = Gauge("fuxi_rag_cache_hit_rate", "RAG 缓存命中率 (0.0-1.0)")
rag_query_cache_hits = Counter("fuxi_rag_query_cache_hits", "查询级缓存命中数", ["cache_type"])
rag_embedding_cache_hits = Counter("fuxi_rag_embedding_cache_hits", "Embedding 缓存命中数")

rag_pipeline_duration_seconds = Histogram(
    "fuxi_rag_pipeline_duration_seconds", "RAG 管线端到端延迟",
    buckets=[1.0, 2.0, 5.0, 10.0, 15.0, 30.0, 60.0]
)
rag_pipeline_stages = Histogram(
    "fuxi_rag_pipeline_stages_seconds", "RAG 各阶段耗时",
    ["stage"], buckets=[0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)
rag_query_complexity = Histogram(
    "fuxi_rag_query_complexity", "查询复杂度（0=简单, 1=复杂）",
    buckets=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
)

rag_hallucination_score = Gauge("fuxi_rag_hallucination_score", "幻觉检测分数 (0=无幻觉, 1=严重幻觉)")
rag_answer_relevance = Gauge("fuxi_rag_answer_relevance", "回答相关性评分 (0.0-1.0)")
rag_source_attribution_rate = Gauge("fuxi_rag_source_attribution_rate", "来源归因率 (0.0-1.0)")

# ============ 告警相关指标 ============

alert_active_total = Gauge("fuxi_alert_active_total", "当前活跃告警数量", ["severity"])
alert_fired_total = Counter("fuxi_alert_fired_total", "累计触发的告警总数", ["alert_name", "severity"])
alert_resolved_total = Counter("fuxi_alert_resolved_total", "累计解决的告警总数", ["alert_name", "severity"])
system_error_rate_total = Counter("fuxi_system_error_rate_total", "系统错误总数", ["error_type"])

# ============ 数据结构 ============

@dataclass
class AlertRule:
    """告警规则定义"""
    name: str
    description: str
    severity: str
    metric_name: str
    condition: str
    threshold: float
    duration_seconds: float = 60.0
    cooldown_seconds: float = 300.0
    enabled: bool = True
    labels: Dict[str, str] = field(default_factory=dict)
    last_fired_at: float = 0.0
    first_breach_at: float = 0.0
    breach_count: int = 0
    is_active: bool = False


@dataclass
class TrendSample:
    """趋势分析样本"""
    timestamp: float
    value: float


@dataclass
class SystemSnapshot:
    """系统快照"""
    timestamp: float = field(default_factory=time.time)
    cpu_percent: float = 0.0
    cpu_per_core: List[float] = field(default_factory=list)
    memory_percent: float = 0.0
    memory_used_gb: float = 0.0
    memory_total_gb: float = 0.0
    swap_percent: float = 0.0
    disk_percent: float = 0.0
    disk_used_gb: float = 0.0
    disk_total_gb: float = 0.0
    open_fds: int = 0
    thread_count: int = 0
