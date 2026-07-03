"""
metrics.py — Prometheus 指标暴露 (v1.50)
提供 /api/metrics 端点，输出：
  - 请求计数、延迟分布、错误率
  - 缓存命中率、搜索延迟
  - 向量存储状态、chunk 计数
  - Token 消耗统计
"""
import time
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY


def _get_or_create(metric_class, name, documentation, labelnames=None, **kwargs):
    """获取或创建 Prometheus 指标（避免重复注册）"""
    try:
        if labelnames:
            return metric_class(name, documentation, labelnames, **kwargs)
        else:
            return metric_class(name, documentation, **kwargs)
    except ValueError:
        # 指标已存在，从注册表中获取
        for collector in REGISTRY._names_to_collectors.values():
            if hasattr(collector, '_name') and collector._name == name:
                return collector
        # 如果找不到，创建一个新的（不注册）
        if labelnames:
            return metric_class(name, documentation, labelnames, registry=None, **kwargs)
        else:
            return metric_class(name, documentation, registry=None, **kwargs)


# ── 请求级指标 ──
http_requests_total = _get_or_create(
    Counter, 'fuxi_http_requests_total', 'HTTP 请求总数',
    ['method', 'endpoint', 'status']
)
http_request_duration_seconds = _get_or_create(
    Histogram, 'fuxi_http_request_duration_seconds', 'HTTP 请求延迟',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
)

# ── 搜索指标 ──
search_requests_total = _get_or_create(
    Counter, 'fuxi_search_requests_total', '搜索请求总数',
    ['status']
)
search_duration_seconds = _get_or_create(
    Histogram, 'fuxi_search_duration_seconds', '搜索延迟',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)
search_result_count = _get_or_create(
    Histogram, 'fuxi_search_result_count', '搜索结果数',
    buckets=[0, 1, 3, 5, 10, 20, 50]
)

# ── 缓存指标 ──
cache_hits_total = _get_or_create(Counter, 'fuxi_cache_hits_total', '缓存命中数', ['level'])
cache_misses_total = _get_or_create(Counter, 'fuxi_cache_misses_total', '缓存未命中数')

# ── 向量存储指标 ──
vector_store_chunks = _get_or_create(Gauge, 'fuxi_vector_store_chunks', '向量库 chunk 数')
sqlite_chunks = _get_or_create(Gauge, 'fuxi_sqlite_chunks', 'SQLite chunk 数')
vector_store_health = _get_or_create(Gauge, 'fuxi_vector_store_health', '向量库健康状态 (1=正常, 0=异常)')

# ── Token 消耗 ──
token_consumed_total = _get_or_create(
    Counter, 'fuxi_token_consumed_total', 'Token 消耗总数',
    ['model', 'type']
)
token_cost_total = _get_or_create(
    Counter, 'fuxi_token_cost_total', 'Token 累计费用(USD)',
    ['model']
)

# ── LLM 调用指标 ──
llm_requests_total = _get_or_create(
    Counter, 'fuxi_llm_requests_total', 'LLM 调用总数',
    ['model', 'status']
)
llm_duration_seconds = _get_or_create(
    Histogram, 'fuxi_llm_duration_seconds', 'LLM 调用延迟',
    ['model'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0]
)

# ── 反馈指标 ──
feedback_total = _get_or_create(
    Counter, 'fuxi_feedback_total', '用户反馈总数',
    ['action']
)

# ── 器官健康指标 ──
organ_health = _get_or_create(Gauge, 'fuxi_organ_health', '器官健康状态 (1=正常, 0=异常)', ['organ'])


def record_search(status: str, duration_s: float, result_count: int):
    """记录一次搜索"""
    search_requests_total.labels(status=status).inc()
    search_duration_seconds.observe(duration_s)
    search_result_count.observe(result_count)


def record_cache(hit: bool, level: str = "L1"):
    """记录缓存命中/未命中"""
    if hit:
        cache_hits_total.labels(level=level).inc()
    else:
        cache_misses_total.inc()


def record_llm(model: str, status: str, duration_s: float, tokens_in: int = 0, tokens_out: int = 0):
    """记录 LLM 调用"""
    llm_requests_total.labels(model=model, status=status).inc()
    llm_duration_seconds.labels(model=model).observe(duration_s)
    if tokens_in:
        token_consumed_total.labels(model=model, type='input').inc(tokens_in)
    if tokens_out:
        token_consumed_total.labels(model=model, type='output').inc(tokens_out)


def record_feedback(action: str):
    """记录用户反馈"""
    feedback_total.labels(action=action).inc()


def update_store_stats(sqlite_count: int = 0, vector_count: int = 0):
    """更新存储统计"""
    sqlite_chunks.set(sqlite_count)
    vector_store_chunks.set(vector_count)
    vector_store_health.set(1 if vector_count > 0 else 0)


def get_metrics_response() -> bytes:
    """获取 Prometheus 格式的指标数据"""
    return generate_latest(REGISTRY)


# ── 兼容旧调用接口 ──
_counter_map = {
    "kb_search_requests_total": search_requests_total,
    "kb_crag_degraded_total": None,
}

def inc_counter(name: str, value: int = 1):
    """兼容旧版计数器调用"""
    try:
        if name in _counter_map and _counter_map[name]:
            _counter_map[name].inc(value)
    except Exception:
        pass

def observe_histogram(name: str, value: float):
    """兼容旧版直方图调用"""
    try:
        if name == "kb_search_latency_seconds":
            search_duration_seconds.observe(value)
    except Exception:
        pass


def generate_health_summary():
    """管理面板指标摘要"""
    from src.config import START_TIME
    from src.db.data_store import load_chunks
    try:
        chunks = load_chunks()
    except:
        chunks = []
    uptime_hours = round((time.time() - START_TIME) / 3600, 1)
    chunk_count = len(chunks) if chunks else 0
    return {
        "ok": True,
        "chunks": chunk_count,
        "latency_p50_ms": 0,
        "latency_p95_ms": 0,
        "latency_p99_ms": 0,
        "error_rate": 0.0,
        "uptime_hours": uptime_hours,
    }


def generate_metrics_text() -> str:
    """生成 Prometheus 格式的指标文本"""
    return generate_latest(REGISTRY).decode('utf-8')
