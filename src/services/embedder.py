"""
kb-embedder v10.1 — 多 worker 文本向量化
端口 8081，仅内网访问
改进：ThreadPoolExecutor 多线程并发编码 + 批量排队
"""
import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [embedder] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger('embedder')

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
# sentence_transformers imported lazily in _get_model()

EMBEDDING_MODEL = os.getenv("KB_MODEL", "BAAI/bge-small-zh-v1.5")
MAX_WORKERS = int(os.getenv("KB_EMBEDDER_WORKERS", "4"))  # 4 个并行 worker

_model = None

def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info(f"模型就绪 (维度={_model.get_sentence_embedding_dimension()})")
    return _model

# v10.1: 单线程 + 大批量 — ThreadPoolExecutor 因 GIL 无加速，用大 batch 硬件优化
app = FastAPI(title="kb-embedder", docs_url=None, redoc_url=None)

class EmbedRequest(BaseModel):
    texts: list[str]

class EmbedResponse(BaseModel):
    vectors: list[list[float]]

@app.post("/embed", response_model=EmbedResponse)
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def embed(req: EmbedRequest):
    """文本批量向量化（单线程大批量，利用 numpy C 扩展释放 GIL）"""
    if not req.texts:
        return EmbedResponse(vectors=[])
    
    # 直接用主线程编码 — numpy C 扩展运算时自动释放 GIL，大 batch 效率最高
    vecs = _get_model().encode(
        req.texts,
        normalize_embeddings=True,
        batch_size=64,           # 大批量提升硬件吞吐
        show_progress_bar=False,
    )
    return EmbedResponse(vectors=vecs.tolist())

class RerankRequest(BaseModel):
    query: str
    documents: List[str]
    top_k: int = 10

class RerankResponse(BaseModel):
    scores: List[float]
    indices: List[int]

@app.post("/rerank", response_model=RerankResponse)
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def rerank(body: RerankRequest):
    """基于 BGE 模型的精度重排（semantic similarity rerank）"""
    import numpy as np
    if not body.documents:
        return RerankResponse(scores=[], indices=[])
    
    # Embed query + documents
    query_vec = _get_model().encode([body.query], normalize_embeddings=True)[0]
    doc_vecs = _get_model().encode([d[:2000] for d in body.documents], normalize_embeddings=True)
    
    # Cosine similarity
    query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-8)
    scores = [float(np.dot(query_norm, dv / (np.linalg.norm(dv) + 1e-8))) for dv in doc_vecs]
    
    indexed = sorted(enumerate(scores), key=lambda x: -x[1])
    top = indexed[:body.top_k]
    return RerankResponse(
        scores=[s for _, s in top],
        indices=[i for i, _ in top]
    )

@app.get("/health")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def health():
    import threading
    return {
        "status": "ready",
        "model": EMBEDDING_MODEL,
        "workers": MAX_WORKERS,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8081, log_level="info")

# === merged from embed.py ===
"""
services/embed.py — 向量嵌入服务（v10.0）
负责：调用 embedder_server 进行文本向量化
"""
import os, aiohttp
from typing import List
import logging; logger = logging.getLogger(__name__)


from src.config import EMBEDDER_URL


async def embed_text(text: str) -> list:
    """单文本向量化"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{EMBEDDER_URL}/embed",
                json={"texts": [text]},
                timeout=aiohttp.ClientTimeout(total=3)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("vectors", data.get("embeddings", [[]]))[0]
    except Exception as e:
        logger.warning("embed_text 操作失败: %s", e, exc_info=True)
    return []


async def batch_embed(texts: list) -> list:
    """批量文本向量化"""
    if not texts:
        return []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{EMBEDDER_URL}/embed",
                json={"texts": texts},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("vectors", data.get("embeddings", []))
    except Exception as e:
        logger.warning("batch_embed 操作失败: %s", e, exc_info=True)
    return [[]] * len(texts)


def cosine_sim(a: list, b: list) -> float:
    """余弦相似度"""
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = (sum(x * x for x in a)) ** 0.5
    nb = (sum(x * x for x in b)) ** 0.5
    return dot / (na * nb) if na and nb else 0.0
