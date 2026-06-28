"""
tests/test_lung.py — 肺 v4.1 单元测试
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.hypothalamus.meridian import Meridian
from src.hypothalamus.organs.lung import LungAgent

class TestLungInit:
    def test_lung_creation(self):
        m = Meridian()
        lung = LungAgent(m)
        assert lung.organ_id == "lung"
        assert lung._dirty is True
        assert lung._running is False

    def test_lung_registered(self):
        m = Meridian()
        LungAgent(m)
        organ = m.get_organ("lung")
        assert organ is not None
        assert organ.name == "肺"

class TestLungDirtyMark:
    def test_initial_dirty(self):
        m = Meridian()
        lung = LungAgent(m)
        assert lung._dirty is True

    def test_clean_after_mark(self):
        m = Meridian()
        lung = LungAgent(m)
        lung._dirty = False
        assert lung._dirty is False

    @pytest.mark.asyncio
    async def test_nutrition_sets_dirty(self):
        m = Meridian()
        lung = LungAgent(m)
        lung._dirty = False
        from src.hypothalamus.meridian import Signal
        # mock _exhale to avoid calling distiller
        with patch.object(lung, '_exhale', return_value={"ok": True}):
            await lung._handle_new_nutrition(Signal(
                source="stomach", target="lung",
                signal_type="new_nutrition",
                payload={"chunks": [{"text": "test"}]},
            ))
        assert lung._dirty is True

class TestLungStats:
    def test_initial_stats(self):
        m = Meridian()
        lung = LungAgent(m)
        stats = lung.stats()
        assert stats["breathe_count"] == 0
        assert stats["exhale_count"] == 0

    def test_stats_after_breathe(self):
        m = Meridian()
        lung = LungAgent(m)
        lung._breathe_count = 3
        lung._exhale_count = 2
        stats = lung.stats()
        assert stats["breathe_count"] == 3

class TestLungBreathInterval:
    def test_breath_interval(self):
        m = Meridian()
        lung = LungAgent(m)
        assert lung.BREATH_INTERVAL == 300

class TestLungInhale:
    @pytest.mark.asyncio
    async def test_inhale_empty(self):
        m = Meridian()
        lung = LungAgent(m)
        with patch("src.db.data_store.load_chunks", return_value=[]):
            count, fp = await lung._inhale()
            assert count == 0

    @pytest.mark.asyncio
    async def test_inhale_fingerprint(self):
        m = Meridian()
        lung = LungAgent(m)
        fake = [{"file_name": "a.pdf", "mtime": 100}]
        with patch("src.db.data_store.load_chunks", return_value=fake):
            count, fp = await lung._inhale()
            assert count == 1
            assert len(fp) == 32
