"""tests/test_retrieval.py — 检索测试"""
import pytest
from unittest.mock import patch, AsyncMock
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
