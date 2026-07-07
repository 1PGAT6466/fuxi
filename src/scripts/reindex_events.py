#!/usr/bin/env python
"""
reindex_events.py — Phase A 全量回灌脚本
===============================
从已有 chunks 表读取数据，对每个 chunk 调用 SAGExtractor，
将提取的 events 和 entities 写入数据库。

用法：
  python -m src.scripts.reindex_events --limit 100
  python -m src.scripts.reindex_events --limit 50 --offset 100
  python -m src.scripts.reindex_events --limit 10 --dry-run

参数：
  --limit N    每批处理数量（默认 50）
  --offset M   从第 M 条 chunk 开始（默认 0）
  --dry-run    仅打印而不实际执行
  --delay D    两个 chunk 之间的延迟（秒，默认 1.0，用于 LLM 速率限制）
  --db PATH    SQLite 数据库路径（默认 data/chunks.db）
"""
import sys
import os
import json
import asyncio
import argparse
import logging
import time
import struct
from pathlib import Path

# Ensure repo root is on path
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))
os.environ.setdefault('FUXI_JWT_SECRET', os.environ.get('FUXI_JWT_SECRET', 'reindex_phase_a_default_secret'))

from src.db.memory_store import MemoryStore, get_store
from src.shaoyang.extractor import SAGExtractor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger("reindex_events")


async def vectorize_event(store: MemoryStore, row_id: int, event_id: str, content: str) -> bool:
    """为单个事件生成 embedding 并存入 BLOB"""
    try:
        from src.db.vector_store import embed_texts
        embeddings = await embed_texts([content])
        if embeddings and embeddings[0]:
            emb = embeddings[0]
            blob = struct.pack(f'{len(emb)}f', *emb)
            store._db_conn.execute(
                "UPDATE events SET embedding=? WHERE id=?",
                (blob, row_id)
            )
            store._db_conn.commit()
            return True
    except Exception as e:
        logger.warning(f"  向量化失败 event_id={event_id}: {e}")
    return False


async def reindex(args) -> None:
    """主回灌逻辑"""
    store = MemoryStore(db_path=args.db) if args.db else get_store()
    extractor = SAGExtractor()

    # 获取 chunk 总数
    total_chunks = store.total_chunks
    logger.info(f"总 chunks: {total_chunks}，limit={args.limit}，offset={args.offset}")

    # 分批获取 chunks
    chunks = store.get_all(limit=args.limit, offset=args.offset)
    if not chunks:
        logger.info("没有 chunk 需要处理")
        return

    logger.info(f"本批处理 {len(chunks)} 个 chunk (offset={args.offset})")

    total_events = 0
    total_entities = 0
    total_vectorized = 0
    failed_count = 0

    for i, chunk in enumerate(chunks):
        chunk_text = chunk.get("text", "")
        file_hash = chunk.get("file_hash", "")
        file_name = chunk.get("file_name", "")
        chunk_index = chunk.get("chunk_index", i)
        chunk_id = f"{file_hash}_{chunk_index}"

        if not chunk_text or len(chunk_text) < 50:
            logger.info(f"  [{i+1}/{len(chunks)}] 跳过 (文本太短: {len(chunk_text)} chars)")
            continue

        progress = f"[{i+1}/{len(chunks)}]"
        chunk_preview = chunk_text[:50].replace('\n', ' ')
        logger.info(f"  {progress} chunk={chunk_id[:30]}... text=\"{chunk_preview}...\"")

        if args.dry_run:
            logger.info(f"  {progress} [DRY RUN] 跳过实际调用")
            continue

        try:
            extraction = await extractor.extract(
                chunk_text,
                chunk_meta={
                    "chunk_id": chunk_id,
                    "file_hash": file_hash,
                    "file_name": file_name,
                    "category": chunk.get("category", ""),
                }
            )

            chunk_events = len(extraction.events)
            chunk_entities = len(extraction.entities)
            total_events += chunk_events
            total_entities += chunk_entities

            if chunk_events > 0 or chunk_entities > 0:
                logger.info(f"  {progress} 提取: {chunk_events} events, {chunk_entities} entities")

            # 为每个新入库的 event 生成向量
            for event_data in extraction.events:
                event_data["chunk_id"] = chunk_id
                event_data["file_hash"] = file_hash
                event_data["file_name"] = file_name
                event_data["event_type"] = event_data.get("action", "")
                event_data.setdefault("entities", event_data.get("participants", []))
                row_id = store.add_event(event_data)
                if row_id:
                    content = event_data.get("content") or event_data.get("summary", "") or event_data.get("title", "")
                    if content:
                        vec_ok = await vectorize_event(
                            store, row_id, event_data.get("event_id", ""), content
                        )
                        if vec_ok:
                            total_vectorized += 1

            for entity_data in extraction.entities:
                entity_data.setdefault("chunk_ids", [chunk_id])
                entity_data["file_hash"] = file_hash
                entity_data["file_name"] = file_name
                entity_data["source"] = "reindex_events"
                store.add_entity(entity_data)

        except Exception as e:
            failed_count += 1
            error_msg = str(e)
            logger.warning(f"  {progress} 提取失败: {error_msg}")
            # 写入 pending 标记
            try:
                store.add_event({
                    "event_id": f"evt_reindex_pending_{chunk_id[:50]}",
                    "chunk_id": chunk_id,
                    "title": "[REINDEX PENDING]",
                    "content": f"Reindex pending. Error: {error_msg[:200]}",
                    "entities": [],
                    "event_type": "pending",
                    "file_hash": file_hash,
                    "file_name": file_name,
                    "status": "pending",
                })
            except Exception:
                pass

        # 速率限制
        if i < len(chunks) - 1 and args.delay > 0:
            await asyncio.sleep(args.delay)

    # 输出汇总
    logger.info("=" * 50)
    logger.info(f"回灌完成！")
    logger.info(f"  处理: {len(chunks)} chunks")
    logger.info(f"  提取: {total_events} events, {total_entities} entities")
    logger.info(f"  向量化: {total_vectorized} events")
    logger.info(f"  失败: {failed_count} chunks")
    logger.info(f"  DB事件总数: {store.get_event_count()}")
    logger.info(f"  DB实体总数: {store.get_entity_count()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase A 全量回灌：从 chunks 提取 events/entities")
    parser.add_argument("--limit", type=int, default=50, help="每批处理数量（默认 50）")
    parser.add_argument("--offset", type=int, default=0, help="起始偏移（默认 0）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印，不实际执行")
    parser.add_argument("--delay", type=float, default=1.0, help="chunk 间延迟秒数（默认 1.0）")
    parser.add_argument("--db", type=str, default=None, help="SQLite 数据库路径")
    args = parser.parse_args()

    # ======== 安全修复 (CWE-22): 路径遍历防护 ========
    if args.db:
        db_path = Path(args.db).resolve()
        # 拒绝路径遍历攻击（../、~/、绝对路径写入系统目录）
        allowed_base = Path(__file__).resolve().parent.parent.parent
        allowed_dirs = [
            allowed_base / "data",
            allowed_base / "temp",
            allowed_base,
            Path.home() / "kb-server" / "data",
        ]
        if not any(str(db_path).startswith(str(d.resolve())) for d in allowed_dirs):
            logger.error(f"❌ 拒绝路径遍历: {args.db} (仅允许项目 data/ 目录)")
            sys.exit(1)
        args.db = str(db_path)

    asyncio.run(reindex(args))


if __name__ == "__main__":
    main()
