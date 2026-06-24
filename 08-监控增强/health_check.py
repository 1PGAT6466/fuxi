"""
health_check.py — 健康检查增强
================================
替换原有 /api/health 端点，提供各组件独立探活
"""

import time
import asyncio
import logging
from typing import Dict

import aiohttp

from src.config import EMBEDDER_URL, OLLAMA_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)


async def check_memory_store() -> Dict:
    """检查 BM25 存储"""
    try:
        from src.db.memory_store import get_store
        store = get_store()
        count = store.count_chunks() if hasattr(store, 'count_chunks') else -1
        return {"ok": True, "chunks": count, "type": "sqlite_fts5"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def check_vector_store() -> Dict:
    """检查向量存储"""
    try:
        from src.db.vector_store import get_vector_store
        vs = get_vector_store()
        if not vs:
            return {"ok": False, "error": "VectorStore init failed"}
        count = vs.count
        return {"ok": count >= 0, "vectors": count, "type": "chromadb"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def check_embedder() -> Dict:
    """检查 Embedder 服务"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{EMBEDDER_URL}/embed",
                json={"texts": ["test"]},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    dim = len(data.get("vectors", [[]])[0]) if data.get("vectors") else 0
                    return {"ok": True, "url": EMBEDDER_URL, "dimension": dim}
                return {"ok": False, "url": EMBEDDER_URL, "status": resp.status}
    except Exception as e:
        return {"ok": False, "url": EMBEDDER_URL, "error": str(e)}


async def check_ollama() -> Dict:
    """检查 Ollama 服务"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{OLLAMA_URL}/api/tags",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = [m["name"] for m in data.get("models", [])]
                    has_model = any(OLLAMA_MODEL in m for m in models)
                    return {
                        "ok": True,
                        "url": OLLAMA_URL,
                        "model": OLLAMA_MODEL,
                        "model_available": has_model,
                        "all_models": models[:5],
                    }
                return {"ok": False, "url": OLLAMA_URL, "status": resp.status}
    except Exception as e:
        return {"ok": False, "url": OLLAMA_URL, "error": str(e)}


async def check_deepseek() -> Dict:
    """检查 DeepSeek API"""
    import os
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        return {"ok": False, "error": "DEEPSEEK_API_KEY not set"}
    
    # 只检查 key 格式，不实际调用
    if len(api_key) < 10:
        return {"ok": False, "error": "DEEPSEEK_API_KEY too short"}
    
    return {"ok": True, "key_prefix": api_key[:8] + "..."}


async def check_graph() -> Dict:
    """检查知识图谱"""
    try:
        from src.config import GRAPH_PATH
        import json
        if not GRAPH_PATH.exists():
            return {"ok": False, "error": "knowledge_graph.json not found"}
        graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
        return {
            "ok": True,
            "entities": len(graph.get("nodes", {})),
            "edges": len(graph.get("edges", [])),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def check_cache() -> Dict:
    """检查缓存状态"""
    try:
        from src.services.cache import get_cache_stats
        stats = get_cache_stats()
        return {"ok": True, **stats}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def full_health_check() -> Dict:
    """完整健康检查"""
    t0 = time.time()
    
    # 并行检查所有组件
    results = await asyncio.gather(
        check_memory_store(),
        check_vector_store(),
        check_embedder(),
        check_ollama(),
        check_deepseek(),
        check_graph(),
        check_cache(),
        return_exceptions=True,
    )
    
    checks = {}
    check_names = ["memory_store", "vector_store", "embedder", "ollama", "deepseek", "graph", "cache"]
    for name, result in zip(check_names, results):
        if isinstance(result, Exception):
            checks[name] = {"ok": False, "error": str(result)}
        else:
            checks[name] = result
    
    # 总体状态
    all_ok = all(c.get("ok", False) for c in checks.values())
    critical_ok = all(
        checks.get(k, {}).get("ok", False)
        for k in ["memory_store", "vector_store"]
    )
    
    if all_ok:
        status = "healthy"
    elif critical_ok:
        status = "degraded"
    else:
        status = "unhealthy"
    
    return {
        "status": status,
        "checks": checks,
        "duration_ms": round((time.time() - t0) * 1000, 1),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
