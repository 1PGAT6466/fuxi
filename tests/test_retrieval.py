"""tests/test_retrieval.py — 检索测试"""
import pytest
import logging
import time
from unittest.mock import patch, AsyncMock, MagicMock
from src.taiyang.retrieval import hybrid_search

@pytest.mark.asyncio
async def test_hybrid_search_returns_list():
    with patch('src.db.vector_store.embed_texts', new_callable=AsyncMock, return_value=None):
        result = await hybrid_search('test', top_k=5)
        assert isinstance(result, list)

@pytest.mark.asyncio
async def test_hybrid_search_empty_query():
    with patch('src.db.vector_store.embed_texts', new_callable=AsyncMock, return_value=None):
        result = await hybrid_search('', top_k=5)
        assert isinstance(result, list)

@pytest.mark.asyncio
async def test_slow_query_logged(caplog):
    from src.taiyang.retrieval import TaiyangRetrieval

    meridian = MagicMock()
    retrieval = TaiyangRetrieval(meridian)

    async def fake_refine(query, **kwargs):
        retrieval._set_status("processing")
        start = time.time()
        time.sleep(0.01)
        retrieval._search_count += 1
        duration = (time.time() - start) * 1000
        if duration > 3000:
            logger.warning(f"[SlowQuery] query={query[:80]!r} duration_ms={duration:.0f} result_count=0")
        retrieval._set_status("idle")
        return []

    with caplog.at_level(logging.WARNING, logger="taiyang.retrieval"):
        await fake_refine("短查询")
        assert "SlowQuery" not in caplog.text
