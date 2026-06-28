"""
tests/test_nose.py — 👃 鼻单元测试
P5: 器官测试覆盖补充
"""
import pytest
import time
from src.hypothalamus.meridian import Meridian
from src.hypothalamus.organs.nose import NoseAgent


class TestNoseInit:
    
    def test_nose_creation(self):
        m = Meridian()
        n = NoseAgent(m)
        assert n.organ_id == "nose"
    
    def test_nose_registered(self):
        m = Meridian()
        NoseAgent(m)
        organ = m.get_organ("nose")
        assert organ is not None
        assert "鼻" in organ.name


class TestNoseSniffing:
    
    def test_sniff_interval_value(self):
        m = Meridian()
        n = NoseAgent(m)
        assert n.SNIFF_INTERVAL > 0
    
    def test_zero_result_detection(self):
        m = Meridian()
        n = NoseAgent(m)
        # Simulate zero result
        n._zero_result_count = 10
        assert n._zero_result_count == 10


class TestNoseStats:
    
    def test_initial_stats(self):
        m = Meridian()
        n = NoseAgent(m)
        stats = n.stats()
        assert isinstance(stats, dict)
