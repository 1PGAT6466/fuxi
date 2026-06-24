"""
vector_store_patch.py — 向量存储补丁
======================================
修复内容：
1. 统一信号量定义（解决 retrieval.py 和 fusion.py 不一致问题）
2. 添加 embed_texts 重试机制

使用方式：
    在 vector_store.py 末尾添加此代码
"""

import asyncio
import logging
from typing import List, Optional

import aiohttp

logger = logging.getLogger(__name__)

# ============================================================
# 统一信号量 — 全局唯一定义
# ============================================================

# 所有模块共享同一个信号量，控制 ChromaDB 并发
CHROMA_SEMAPHORE = asyncio.Semaphore(4)  # 4 并发是合理值

# embedder HTTP 请求信号量
EMBEDDER_SEMAPHORE = asyncio.Semaphore(8)


async def embed_texts_patched(texts: List[str], max_retries: int = 2) -> Optional[List[List[float]]]:
    """带重试和统一信号量的向量嵌入"""
    if not texts:
        return None
    
    from src.config import EMBEDDER_URL
    
    for attempt in range(max_retries):
        try:
            async with EMBEDDER_SEMAPHORE:
                async with aiohttp.ClientSession() as sess:
                    async with sess.post(
                        f"{EMBEDDER_URL}/embed",
                        json={"texts": texts},
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            vectors = data.get("vectors")
                            if vectors:
                                return vectors
                            logger.warning("[embed] no vectors in response")
                            return None
                        logger.warning(f"[embed] HTTP {resp.status}")
        except aiohttp.ClientError as e:
            logger.warning(f"[embed] attempt {attempt + 1}/{max_retries} failed: {e}")
        except Exception as e:
            logger.error(f"[embed] unexpected error: {e}", exc_info=True)
        
        if attempt < max_retries - 1:
            await asyncio.sleep(0.5 * (attempt + 1))
    
    return None


# 在 retrieval.py 和 fusion.py 中使用：
# from src.db.vector_store import CHROMA_SEMAPHORE, embed_texts_patched as embed_texts
