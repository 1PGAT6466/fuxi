# 兼容层 - 重导出到新位置
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY

# 保持旧接口兼容
search_requests_total = Counter('fuxi_search_requests_total', '搜索请求总数', ['status'])
search_duration_seconds = Histogram('fuxi_search_duration_seconds', '搜索延迟')

def record_search(status, duration_s, result_count):
    search_requests_total.labels(status=status).inc()
    search_duration_seconds.observe(duration_s)

def record_cache(hit, level="L1"):
    pass

def get_metrics_response():
    return generate_latest(REGISTRY)

def update_store_stats(sqlite_count=0, vector_count=0):
    pass

def generate_metrics_text():
    return generate_latest(REGISTRY).decode('utf-8')

def generate_health_summary():
    from src.config import START_TIME
    import time
    return {
        "ok": True,
        "chunks": 0,
        "latency_p50_ms": 0,
        "latency_p95_ms": 0,
        "latency_p99_ms": 0,
        "error_rate": 0.0,
        "uptime_hours": round((time.time() - START_TIME) / 3600, 1),
    }

def inc_counter(name, value=1):
    pass

def observe_histogram(name, value):
    pass
