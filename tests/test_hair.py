"""
tests/test_hair.py — 💇 发单元测试
P5: 器官测试覆盖补充
"""
import pytest
from src.hypothalamus.meridian import Meridian
from src.hypothalamus.organs.hair import HairAgent


class TestHairInit:
    
    def test_hair_creation(self):
        m = Meridian()
        h = HairAgent(m)
        assert h.organ_id == "hair"
    
    def test_hair_registered(self):
        m = Meridian()
        HairAgent(m)
        organ = m.get_organ("hair")
        assert organ is not None


class TestHairStats:
    
    def test_initial_stats(self):
        m = Meridian()
        h = HairAgent(m)
        stats = h.stats()
        assert isinstance(stats, dict)
