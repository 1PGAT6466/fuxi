"""
tests/test_heart.py — 🫀 心单元测试
P5: 器官测试覆盖补充
"""
import pytest
import time
from unittest.mock import MagicMock, AsyncMock, patch
from src.hypothalamus import Meridian
from src.hypothalamus.organs.heart import HeartAgent


class TestHeartInit:
    """心脏初始化"""
    
    def test_heart_creation(self):
        m = Meridian()
        h = HeartAgent(m)
        assert h.organ_id == "heart"
        assert h._beat_count == 0
        assert h._running is False
        assert h._anomalies == []
    
    def test_heart_registered_in_meridian(self):
        m = Meridian()
        HeartAgent(m)
        organ = m.get_organ("heart")
        assert organ is not None
        assert organ.name == "心"
        assert organ.emoji == "🫀"


class TestHeartStats:
    """心脏统计"""
    
    def test_initial_stats(self):
        m = Meridian()
        h = HeartAgent(m)
        stats = h.stats()
        assert stats["beat_count"] == 0
        assert stats["running"] is False
        assert stats["alive"] is True
    
    def test_stats_after_beat(self):
        m = Meridian()
        h = HeartAgent(m)
        # Simulate a beat update
        h._beat_count = 5
        h._last_health = {"timestamp": time.time()}
        h._anomalies = [{"time": time.time(), "message": "test"}]
        stats = h.stats()
        assert stats["beat_count"] == 5
        assert stats["anomalies_24h"] == 1


class TestHeartAnomaly:
    """异常检测与自愈"""
    
    def test_anomaly_collection(self):
        m = Meridian()
        h = HeartAgent(m)
        h._anomalies.append({"time": time.time(), "message": "Test anomaly"})
        assert len(h._anomalies) == 1
        assert h._anomalies[0]["message"] == "Test anomaly"
    
    def test_anomaly_24h_filter(self):
        m = Meridian()
        h = HeartAgent(m)
        # Add old anomaly (>24h)
        h._anomalies.append({"time": time.time() - 100000, "message": "old"})
        h._anomalies.append({"time": time.time(), "message": "recent"})
        stats = h.stats()
        assert stats["anomalies_24h"] == 1  # only recent one
