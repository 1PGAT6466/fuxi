"""
本地 Embedding 服务
使用 sentence-transformers 实现本地 Embedding，避免远程调用延迟
"""

import asyncio
import logging
import time
from typing import List, Optional

logger = logging.getLogger(__name__)

# 全局模型实例
_model = None
_model_name = "paraphrase-multilingual-MiniLM-L12-v2"  # 多语言模型，支持中文


def _get_model():
    """获取模型实例（延迟加载）"""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"加载本地 Embedding 模型: {_model_name}")
            _model = SentenceTransformer(_model_name)
            logger.info("本地 Embedding 模型加载完成")
        except Exception as e:
            logger.error(f"加载本地 Embedding 模型失败: {e}")
            raise
    return _model


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    本地 Embedding 服务
    
    Args:
        texts: 文本列表
        
    Returns:
        Embedding 向量列表
    """
    if not texts:
        return []
    
    try:
        # 获取模型
        model = _get_model()
        
        # 批量处理
        start_time = time.time()
        
        # 使用线程池执行 CPU 密集型任务
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: model.encode(texts, convert_to_numpy=True).tolist()
        )
        
        duration = (time.time() - start_time) * 1000
        logger.info(f"本地 Embedding 完成: {len(texts)} 个文本, 耗时 {duration:.2f}ms")
        
        return embeddings
    except Exception as e:
        logger.error(f"本地 Embedding 失败: {e}")
        raise


async def embed_query(query: str) -> List[float]:
    """
    单条查询 Embedding
    
    Args:
        query: 查询文本
        
    Returns:
        Embedding 向量
    """
    embeddings = await embed_texts([query])
    return embeddings[0] if embeddings else []


def get_model_info() -> dict:
    """获取模型信息"""
    return {
        "model_name": _model_name,
        "loaded": _model is not None,
        "type": "local"
    }
