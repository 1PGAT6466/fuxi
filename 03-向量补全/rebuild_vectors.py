"""
rebuild_vectors.py — 向量索引重建脚本
=====================================
用途：补全缺失的向量索引（当前 9937 chunks 只有 4985 个向量）

运行方式：
    cd /home/feng-shaoxuan/kb-server
    python scripts/rebuild_vectors.py

可选参数：
    --batch-size 50    # 每批处理的 chunk 数
    --dry-run          # 只统计不执行
"""

import os
import sys
import time
import asyncio
import logging
import argparse

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import DATA_DIR
from src.db.data_store import load_chunks
from src.db.vector_store import get_vector_store, embed_texts

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("rebuild_vectors")


async def rebuild(batch_size: int = 50, dry_run: bool = False):
    """全量重建向量索引"""
    
    # 1. 加载所有 chunks
    logger.info("Loading chunks...")
    chunks = load_chunks()
    logger.info(f"Total chunks: {len(chunks)}")
    
    # 2. 获取已有向量
    vs = get_vector_store()
    if not vs:
        logger.error("VectorStore unavailable!")
        return
    
    existing_count = vs.count
    logger.info(f"Existing vectors: {existing_count}")
    
    # 3. 找出缺失向量的 chunks
    # ChromaDB 的 get_all 不太好用，我们换个思路：
    # 对每个 chunk 尝试 upsert，ChromaDB 会自动处理去重
    
    total = len(chunks)
    processed = 0
    failed = 0
    skipped = 0
    
    if dry_run:
        logger.info(f"[DRY RUN] Would process {total} chunks in batches of {batch_size}")
        logger.info(f"[DRY RUN] Estimated batches: {(total + batch_size - 1) // batch_size}")
        return
    
    t0 = time.time()
    
    for i in range(0, total, batch_size):
        batch = chunks[i:i + batch_size]
        texts = []
        ids = []
        metas = []
        
        for j, chunk in enumerate(batch):
            text = chunk.get("text", "")
            if not text or len(text.strip()) < 10:
                skipped += 1
                continue
            
            file_hash = chunk.get("file_hash", "")
            chunk_idx = chunk.get("chunk_index", j)
            chunk_id = f"{file_hash}:{chunk_idx}"
            
            texts.append(text)
            ids.append(chunk_id)
            metas.append({
                "file_hash": file_hash,
                "file_name": chunk.get("file_name", ""),
                "category": chunk.get("category", ""),
                "chunk_index": chunk_idx,
                "text": text[:1000],  # ChromaDB metadata 截断
            })
        
        if not texts:
            continue
        
        # 批量 embedding
        try:
            embeddings = await embed_texts(texts)
            if not embeddings or len(embeddings) != len(texts):
                logger.warning(f"Batch {i//batch_size}: embed returned {len(embeddings) if embeddings else 0} vectors, expected {len(texts)}")
                failed += len(texts)
                continue
            
            # 写入 ChromaDB
            success = vs.add(ids=ids, embeddings=embeddings, metadata=metas)
            if success:
                processed += len(texts)
            else:
                failed += len(texts)
                
        except Exception as e:
            logger.error(f"Batch {i//batch_size} failed: {e}")
            failed += len(texts)
        
        # 进度
        done = min(i + batch_size, total)
        pct = done / total * 100
        elapsed = time.time() - t0
        eta = elapsed / max(done, 1) * (total - done)
        logger.info(f"Progress: {done}/{total} ({pct:.1f}%) | OK={processed} FAIL={failed} SKIP={skipped} | ETA={eta:.0f}s")
        
        # 避免 embedder 过载
        await asyncio.sleep(0.5)
    
    elapsed = time.time() - t0
    logger.info(f"\n{'='*50}")
    logger.info(f"Rebuild complete in {elapsed:.1f}s")
    logger.info(f"  Processed: {processed}")
    logger.info(f"  Failed: {failed}")
    logger.info(f"  Skipped: {skipped}")
    logger.info(f"  Final vector count: {vs.count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rebuild vector index")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    asyncio.run(rebuild(batch_size=args.batch_size, dry_run=args.dry_run))
