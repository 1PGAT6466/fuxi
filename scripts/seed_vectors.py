#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/seed_vectors.py — 伏羲 v1.50 Phase 2: 向量数据入库验证
=================================================================
用示例文本做 embedding 入库，验证 ChromaDB 写入链路从 embedder → vector_store.add() → ChromaDB 正常。

用法:
    cd E:\easyclaw\伏羲-v1.44\repo
    python scripts/seed_vectors.py

验证标准：
    - py_compile 0 错误 ✅
    - 运行后 embeddings 表行数 > 0 ✅
    - ChromaDB 路径统一为 data/chromadb ✅
"""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import sys
import time
from pathlib import Path

# 确保项目根在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 设置环境变量确保使用统一路径
os.environ.setdefault("KB_CHROMA_DIR", "data/chromadb")
# 禁用 embedder URL（会用模拟向量）
os.environ.setdefault("KB_EMBEDDER_URL", "http://localhost:8081")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("seed_vectors")


def _get_chroma_db_path() -> Path:
    """获取统一 ChromaDB 路径"""
    fuxi_data = os.getenv("FUXI_DATA_DIR", str(PROJECT_ROOT / "data"))
    chroma_dir = os.getenv("KB_CHROMA_DIR", "data/chromadb")
    if not os.path.isabs(chroma_dir):
        chroma_dir = os.path.join(PROJECT_ROOT, chroma_dir)
    return Path(chroma_dir)


def check_collections_exist() -> dict:
    """检查现有 collection 配置是否完整"""
    db_path = _get_chroma_db_path() / "chroma.sqlite3"
    result = {"path": str(db_path), "exists": db_path.exists(), "collections": {}, "embeddings": 0}

    if not db_path.exists():
        logger.warning(f"ChromaDB 数据库不存在: {db_path}")
        return result

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # 检查 collections
    rows = conn.execute("SELECT id, name FROM collections").fetchall()
    for row in rows:
        result["collections"][row["name"]] = row["id"]

    # 检查 embeddings
    emb_count = conn.execute("SELECT COUNT(*) as cnt FROM embeddings").fetchone()
    result["embeddings"] = emb_count["cnt"] if emb_count else 0

    conn.close()
    return result


def seed_with_synthetic_embeddings():
    """用模拟向量（128维随机向量）直接写入 ChromaDB，不依赖外部 embedder 服务"""
    logger.info("=" * 60)
    logger.info("伏羲 v1.50 向量种子入库")
    logger.info("=" * 60)

    # 步骤 1: 检查当前状态
    info = check_collections_exist()
    logger.info(f"ChromaDB 路径: {info['path']}")
    logger.info(f"数据库存在: {info['exists']}")
    logger.info(f"已有 collections: {list(info['collections'].keys())}")
    logger.info(f"当前 embeddings 数: {info['embeddings']}")

    # 步骤 2: 导入 VectorStore
    logger.info("\n--- 步骤 2: 初始化 VectorStore ---")
    try:
        from src.db.vector_store import VectorStore, get_vector_store

        # 直接用 VectorStore with data_dir=data
        vs = VectorStore(db_dir=str(PROJECT_ROOT / "data"))
        logger.info(f"VectorStore 初始化成功, collection: {vs.collection_name}")
        logger.info(f"当前向量数: {vs.count}")
    except Exception as e:
        logger.error(f"VectorStore 初始化失败: {e}")
        return False

    # 步骤 3: 准备种子数据（6 条示例文本）
    logger.info("\n--- 步骤 3: 准备种子数据 ---")
    import hashlib
    import random
    random.seed(42)

    seed_texts = [
        "伏羲是一个企业知识认知中枢，服务于伏羲内世界的团队成员。",
        "ChromaDB 是一个开源的向量数据库，专为 AI 应用设计。",
        "PostgreSQL 的 pgvector 扩展支持高效的向量相似度搜索。",
        "文档分块是 RAG 管线的关键步骤，合理的分块策略能显著提升检索质量。",
        "HNSW (Hierarchical Navigable Small World) 是一种高效的近似最近邻搜索算法。",
        "坤卦 ☷ 负责伏羲系统的记忆存储与管理，包括短期记忆和 Wiki 知识库。",
    ]

    # 为每个文本生成 128 维随机向量（模拟 bge-large-zh 的 1024 维，但用 128 维便于测试）
    DIM = 128
    ids = []
    embeddings = []
    metadatas = []
    documents = []

    for i, text in enumerate(seed_texts):
        chunk_id = f"seed_{i+1}"
        # 生成长度归一化的随机向量
        vec = [random.uniform(-1.0, 1.0) for _ in range(DIM)]
        # L2 归一化（cosine 距离需要）
        norm = sum(v * v for v in vec) ** 0.5
        vec = [v / norm for v in vec]

        ids.append(chunk_id)
        embeddings.append(vec)
        documents.append(text)
        metadatas.append({
            "doc_id": "seed_doc",
            "chunk_index": str(i),
            "file_name": "seed_vectors.py",
            "category": "测试",
            "source_file": "scripts/seed_vectors.py",
            "text_preview": text[:100],
        })

    logger.info(f"准备 {len(ids)} 条种子向量 (dim={DIM})")
    for i, (cid, text) in enumerate(zip(ids, seed_texts)):
        logger.info(f"  [{cid}] {text[:60]}...")

    # 步骤 4: 写入 ChromaDB
    logger.info("\n--- 步骤 4: 写入 ChromaDB ---")
    try:
        success = vs.add(
            ids=ids,
            embeddings=embeddings,
            metadata=metadatas,
            documents=documents,
        )
        logger.info(f"vs.add() 返回: {success}")
        logger.info(f"写入后向量数: {vs.count}")
    except Exception as e:
        logger.error(f"写入失败: {e}")
        return False

    # 步骤 5: 验证
    logger.info("\n--- 步骤 5: 验证 ---")
    time.sleep(1)  # 等待 ChromaDB 内部刷新

    # 5a: 通过 VectorStore.count 验证
    final_count = vs.count
    logger.info(f"VectorStore.count = {final_count}")

    # 5b: 直接查询 SQLite embeddings 表
    db_path = _get_chroma_db_path() / "chroma.sqlite3"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    emb_count = conn.execute("SELECT COUNT(*) as cnt FROM embeddings").fetchone()["cnt"]
    logger.info(f"SQLite embeddings 表行数: {emb_count}")

    # 5c: 显示 embedding 样本
    sample = conn.execute(
        "SELECT e.id, s.type, s.scope "
        "FROM embeddings e "
        "LEFT JOIN segments s ON e.segment_id = s.id "
        "LIMIT 5"
    ).fetchall()
    for row in sample:
        emb_id = str(row['id'])[:20] if row['id'] else 'N/A'
        logger.info(f"  embedding: id={emb_id}... segment_type={row['type']}")

    conn.close()

    # 判断结果
    if final_count > 0 and emb_count > 0:
        logger.info("\n" + "=" * 60)
        logger.info("✅ 向量入库验证通过！")
        logger.info(f"   VectorStore.count = {final_count}")
        logger.info(f"   embeddings 表行数 = {emb_count}")
        logger.info("=" * 60)
        return True
    else:
        logger.error("\n" + "=" * 60)
        logger.error("❌ 向量入库验证失败！")
        logger.error(f"   VectorStore.count = {final_count}")
        logger.error(f"   embeddings 表行数 = {emb_count}")
        logger.error("=" * 60)
        return False


def main():
    """主入口"""
    logger.info(f"项目根目录: {PROJECT_ROOT}")
    logger.info(f"KB_CHROMA_DIR: {os.getenv('KB_CHROMA_DIR', '未设置')}")
    logger.info(f"ChromaDB 路径: {_get_chroma_db_path()}")

    success = seed_with_synthetic_embeddings()

    # 打印最终统计
    info = check_collections_exist()
    logger.info(f"\n最终状态: collections={list(info['collections'].keys())}, embeddings={info['embeddings']}")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
