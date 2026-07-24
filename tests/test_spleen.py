"""
tests/test_spleen.py — 🩸 脾单元测试
P5: 器官测试覆盖补充
"""
import pytest
from src.hypothalamus import Meridian
from src.hypothalamus.organs.spleen import SpleenAgent


class TestSpleenInit:
    
    def test_spleen_creation(self):
        m = Meridian()
        s = SpleenAgent(m)
        assert s.organ_id == "spleen"
    
    def test_spleen_registered(self):
        m = Meridian()
        SpleenAgent(m)
        organ = m.get_organ("spleen")
        assert organ is not None
        assert "脾" in organ.name


class TestSpleenStats:
    
    def test_initial_stats(self):
        m = Meridian()
        s = SpleenAgent(m)
        stats = s.stats()
        assert isinstance(stats, dict)
