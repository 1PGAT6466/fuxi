"""
test_infra_components.py — 基础设施组件测试
测试新增的基础设施组件
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRetry:
    """重试机制测试"""

    def test_retry_async_import(self):
        from src.infra.retry import retry_async
        assert callable(retry_async)

    def test_retry_sync_success(self):
        from src.infra.retry import retry_sync

        def success():
            return "ok"

        result = retry_sync(success)
        assert result == "ok"


class TestConnectionPool:
    """连接池测试"""

    def test_pool_init(self):
        from src.infra.connection_pool import SQLiteConnectionPool
        pool = SQLiteConnectionPool(":memory:")
        assert pool is not None


class TestValidation:
    """验证测试"""

    def test_validate_query(self):
        from src.infra.validation import validate_query, ValidationError
        assert validate_query("test query") == "test query"
        with pytest.raises(ValidationError):
            validate_query("")

    def test_validate_top_k(self):
        from src.infra.validation import validate_top_k
        assert validate_top_k(10) == 10
        assert validate_top_k("invalid") == 10
        assert validate_top_k(200) == 100

    def test_sanitize_input(self):
        from src.infra.validation import sanitize_input
        assert sanitize_input("normal text") == "normal text"
        assert "<script>" not in sanitize_input("<script>alert(1)</script>")


class TestCacheStats:
    """缓存统计测试"""

    def test_record_hit(self):
        from src.infra.cache_stats import CacheStats
        stats = CacheStats()
        stats.record_hit(10.0)
        assert stats._hits == 1

    def test_record_miss(self):
        from src.infra.cache_stats import CacheStats
        stats = CacheStats()
        stats.record_miss(20.0)
        assert stats._misses == 1

    def test_get_stats(self):
        from src.infra.cache_stats import CacheStats
        stats = CacheStats()
        stats.record_hit(10.0)
        stats.record_miss(20.0)
        result = stats.get_stats()
        assert result["hits"] == 1
        assert result["misses"] == 1
        assert result["hit_rate"] == 0.5


class TestRequestMetrics:
    """请求指标测试"""

    def test_record_request(self):
        from src.infra.request_metrics import RequestMetrics
        metrics = RequestMetrics()
        metrics.record_request(100.0, True)
        assert metrics._requests == 1

    def test_get_stats(self):
        from src.infra.request_metrics import RequestMetrics
        metrics = RequestMetrics()
        metrics.record_request(100.0, True)
        metrics.record_request(200.0, False)
        result = metrics.get_stats()
        assert result["requests"] == 2
        assert result["errors"] == 1

    def test_get_percentiles(self):
        from src.infra.request_metrics import RequestMetrics
        metrics = RequestMetrics()
        for i in range(100):
            metrics.record_request(float(i), True)
        result = metrics.get_percentiles()
        assert "p50" in result
        assert "p95" in result


class TestHealthChecker:
    """健康检查测试"""

    def test_check_all_import(self):
        from src.infra.health_check import get_health_checker
        checker = get_health_checker()
        assert checker is not None


class TestRateLimiter:
    """限速器测试"""

    def test_sliding_window(self):
        from src.infra.rate_limiter import SlidingWindowRateLimiter
        limiter = SlidingWindowRateLimiter(5, 60)
        for _ in range(5):
            assert limiter.acquire() == True
        assert limiter.acquire() == False


class TestCircuitBreaker:
    """断路器测试"""

    def test_closed_state(self):
        from src.infra.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() == True

    def test_open_state(self):
        from src.infra.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() == False


class TestTimeout:
    """超时测试"""

    def test_with_timeout_import(self):
        from src.infra.timeout import with_timeout
        assert callable(with_timeout)


class TestMetricsCollector:
    """指标收集测试"""

    def test_increment_counter(self):
        from src.infra.metrics_collector import MetricsCollector
        collector = MetricsCollector()
        collector.increment_counter("test", 5)
        assert collector.get_counter("test") == 5

    def test_set_gauge(self):
        from src.infra.metrics_collector import MetricsCollector
        collector = MetricsCollector()
        collector.set_gauge("cpu", 0.5)
        assert collector.get_gauge("cpu") == 0.5

    def test_record_histogram(self):
        from src.infra.metrics_collector import MetricsCollector
        collector = MetricsCollector()
        for i in range(10):
            collector.record_histogram("latency", float(i))
        result = collector.get_histogram_stats("latency")
        assert result["count"] == 10


class TestErrorTracker:
    """错误追踪测试"""

    def test_record_error(self):
        from src.infra.error_tracker import ErrorTracker
        tracker = ErrorTracker()
        tracker.record_error("test_error", "test message")
        assert len(tracker._errors) == 1

    def test_get_error_stats(self):
        from src.infra.error_tracker import ErrorTracker
        tracker = ErrorTracker()
        tracker.record_error("type1", "msg1")
        tracker.record_error("type2", "msg2")
        result = tracker.get_error_stats()
        assert result["total_errors"] == 2


class TestConfigValidator:
    """配置验证测试"""

    def test_validate(self):
        from src.infra.config_validation import ConfigValidator
        validator = ConfigValidator()
        result = validator.validate()
        assert "valid" in result
        assert "errors" in result
        assert "warnings" in result


class TestSystemMonitor:
    """系统监控测试"""

    def test_get_system_stats(self):
        from src.infra.system_monitor import SystemMonitor
        monitor = SystemMonitor()
        result = monitor.get_system_stats()
        assert "uptime_seconds" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
