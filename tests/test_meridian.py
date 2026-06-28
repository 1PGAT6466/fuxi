"""
tests/test_meridian.py — 经络系统单元测试 v4.0
"""
import asyncio
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.hypothalamus.meridian import Meridian, Signal, SignalPriority


@pytest.fixture
def meridian():
    m = Meridian()
    m.register_organ("test_organ", "测试器官", "🧪")
    return m


class TestMeridianBasic:
    """经络基础功能测试"""

    def test_register_organ(self, meridian):
        assert len(meridian.list_organs()) == 1
        assert meridian.get_organ("test_organ").name == "测试器官"

    def test_heartbeat_tracking(self, meridian):
        meridian.heartbeat("test_organ")
        assert meridian.is_alive("test_organ") is True

    def test_unknown_organ_not_alive(self, meridian):
        assert meridian.is_alive("nonexistent") is False

    def test_signal_creation(self):
        signal = Signal(
            source="brain",
            target="limbs",
            signal_type="search",
            payload={"query": "test"},
            priority=SignalPriority.HIGH,
        )
        assert signal.source == "brain"
        assert signal.priority == SignalPriority.HIGH
        assert signal.signal_id  # auto-generated

    def test_signal_persistence_in_history(self, meridian):
        signal = Signal(source="a", target="b", signal_type="ping", payload={})
        meridian.send(signal)
        history = meridian.get_history(limit=50)
        assert len(history) >= 1
        assert history[-1]["source"] == "a"


class TestMeridianPriority:
    """经络优先级测试"""

    def test_priority_ordering(self):
        assert SignalPriority.CRITICAL < SignalPriority.HIGH
        assert SignalPriority.HIGH < SignalPriority.NORMAL
        assert SignalPriority.NORMAL < SignalPriority.LOW

    def test_critical_signal_has_highest_priority(self, meridian):
        signal = Signal(source="heart", target="brain", signal_type="alert",
                       priority=SignalPriority.CRITICAL)
        assert signal.priority == 0  # CRITICAL = 0


class TestMeridianStats:
    """经络统计测试"""

    def test_initial_stats(self, meridian):
        stats = meridian.stats()
        assert stats["organs_registered"] == 1
        assert not stats["running"]

    def test_organs_list(self, meridian):
        meridian.register_organ("liver", "肝", "🛡️")
        organs = meridian.list_organs()
        assert len(organs) == 2
        assert {o.organ_id for o in organs} == {"test_organ", "liver"}
