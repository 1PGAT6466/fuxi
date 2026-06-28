"""
tests/test_limbs.py — 🦾 四肢单元测试
P5: 器官测试覆盖补充
"""
import pytest
from src.hypothalamus.meridian import Meridian
from src.hypothalamus.organs.limbs import LimbsAgent


class TestLimbsInit:
    
    def test_limbs_creation(self):
        m = Meridian()
        l = LimbsAgent(m)
        assert l.organ_id == "limbs"
    
    def test_limbs_registered(self):
        m = Meridian()
        LimbsAgent(m)
        organ = m.get_organ("limbs")
        assert organ is not None


class TestLimbsStats:
    
    def test_initial_stats(self):
        m = Meridian()
        l = LimbsAgent(m)
        stats = l.stats()
        assert isinstance(stats, dict)
