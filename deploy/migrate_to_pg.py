# ============================================================================
# 伏羲 RAG 4.0 — 数据迁移脚本（SQLite/ChromaDB → PostgreSQL+pgvector）
# ============================================================================
# 用法:
#   python deploy/migrate_to_pg.py --dry-run                     # 预览
#   python deploy/migrate_to_pg.py --limit 1000                  # 分批
#   python deploy/migrate_to_pg.py --resume                      # 断点续传
#   python deploy/migrate_to_pg.py --all --batch-size 500        # 全量
# ============================================================================

import argparse
import json
import logging
import os
import struct
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migrate")

# ============================================================================
# 配置
# ============================================================================

SQLITE_DB = Path("data/memory.db")
CHROMA_DIR = Path("data/chromadb")

# ======== 安全修复 (CWE-798): 从环境变量读取数据库凭证 ========
PG_CONFIG = {
    "host": os.getenv("FUXI_PG_HOST", "172.25.30.200"),
    "port": int(os.getenv("FUXI_PG_PORT", "5432")),
    "database": os.getenv("FUXI_PG_DATABASE", "fuxi"),
    "user": os.getenv("FUXI_PG_USER", "feng-shaoxuan"),
    "password": os.getenv("FUXI_PG_PASSWORD"),
}

# 启动时检查密码是否已设置
if not PG_CONFIG["password"]:
    logger.error(
        "❌ FUXI_PG_PASSWORD 环境变量未设置！"
        "请设置: export FUXI_PG_PASSWORD='<your_password>'"
    )
    # 不直接退出，允许在 --dry-run 模式下继续（仅生成 JSON 导出）
    logger.warning("⚠️ 将仅生成 JSON 导出文件，不连接 PostgreSQL")


class ProgressTracker:
    """断点续传"""

    def __init__(self, state_file: Path = Path("data/migration_state.json")):
        self.state_file = state_file
        self.state = self._load()

    def _load(self) -> Dict:
        if self.state_file.exists():
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        return {"last_chunk_index": 0, "migrated_chunks": 0, "migrated_events": 0, "errors": []}

    def save(self) -> None:
        self.state_file.write_text(json.dumps(self.state, indent=2, ensure_ascii=False),
                                   encoding="utf-8")

    def mark_chunk(self, idx: int) -> None:
        self.state["last_chunk_index"] = idx
        self.state["migrated_chunks"] += 1

    def mark_event(self):
        self.state["migrated_events"] += 1

    def add_error(self, err: str):
        self.state["errors"].append(err)


# ============================================================================
# 主流程
# ============================================================================

def get_pg_connection() -> Optional[object]:
    """获取 PostgreSQL 连接"""
    try:
        import psycopg2
        conn = psycopg2.connect(**PG_CONFIG)
        logger.info(f"✅ PostgreSQL 连接成功: {PG_CONFIG['host']}:{PG_CONFIG['port']}")
        return conn
    except ImportError:
        logger.warning("⚠️ psycopg2 未安装，将仅生成 JSON 导出文件")
        return None
    except Exception as e:
        logger.warning(f"⚠️ PostgreSQL 连接失败: {e}，将仅生成 JSON 导出文件")
        return None


def get_sqlite_connection() -> Optional[sqlite3.Connection]:
    """获取 SQLite 连接"""
    import sqlite3
    if not SQLITE_DB.exists():
        logger.error(f"❌ SQLite 数据库不存在: {SQLITE_DB}")
        sys.exit(1)
    conn = sqlite3.connect(str(SQLITE_DB))
    conn.row_factory = sqlite3.Row
    return conn


def load_blob_embedding(blob) -> Optional[List[float]]:
    """从 SQLite BLOB 解码 embedding（Phase A 格式: struct.pack('f'*768)）"""
    if not blob:
        return None
    try:
        count = len(blob) // 4
        return list(struct.unpack(f"{count}f", blob))
    except Exception:
        return None


def embedding_to_pg_str(embedding: List[float]) -> str:
    """转为 pgvector 字符串"""
    return f"[{','.join(str(x) for x in embedding)}]"


# ============================================================================
# 迁移阶段
# ============================================================================

def migrate_chunks(sqlite_conn, pg_conn, args, tracker: ProgressTracker) -> int:
    """迁移 chunks 表"""
    offset = args.resume and tracker.state["last_chunk_index"] or 0

    rows = sqlite_conn.execute(
        "SELECT * FROM chunks ORDER BY rowid LIMIT ? OFFSET ?",
        (args.limit or -1, offset),
    ).fetchall()

    if not rows:
        logger.info("没有待迁移的 chunks")
        return 0

    count = 0
    for row in rows:
        data = dict(row)
        embedding = load_blob_embedding(data.get("embedding"))

        if pg_conn and not args.dry_run:
            cur = pg_conn.cursor()
            emb_str = embedding_to_pg_str(embedding) if embedding else None
            try:
                cur.execute(
                    """INSERT INTO chunks (chunk_id, document_id, document_name, content, 
                       chunk_index, token_count, metadata, embedding)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (chunk_id) DO NOTHING""",
                    (data.get("id") or data.get("chunk_id"),
                     data.get("document_id", ""),
                     data.get("document_name") or data.get("source_doc", ""),
                     data.get("content", ""),
                     data.get("chunk_index", 0),
                     data.get("token_count", 0),
                     json.dumps(data.get("metadata") or {}),
                     emb_str),
                )
                pg_conn.commit()
            except Exception as e:
                logger.error(f"写入 chunk {data.get('id')} 失败: {e}")
                tracker.add_error(str(e))

        count += 1
        tracker.mark_chunk(count + offset)

        if count % 100 == 0:
            tracker.save()
            logger.info(f"  进度: {count} chunks")

    if pg_conn:
        pg_conn.commit()

    logger.info(f"✅ chunks 迁移: {count} 条")
    return count


def migrate_events(sqlite_conn, pg_conn, args, tracker: ProgressTracker) -> int:
    """迁移 events 表"""
    try:
        rows = sqlite_conn.execute("SELECT * FROM events").fetchall()
    except Exception:
        logger.info("events 表为空或不存在，跳过")
        return 0

    count = 0
    for row in rows:
        data = dict(row)
        embedding = load_blob_embedding(data.get("embedding"))

        if pg_conn and not args.dry_run:
            cur = pg_conn.cursor()
            emb_str = embedding_to_pg_str(embedding) if embedding else None
            try:
                cur.execute(
                    """INSERT INTO events (event_id, chunk_id, content, event_type,
                       entities_json, confidence, status, embedding)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (event_id) DO NOTHING""",
                    (data.get("id") or data.get("event_id"),
                     data.get("chunk_id", ""),
                     data.get("content", ""),
                     data.get("event_type", "general"),
                     data.get("entities_json", "[]"),
                     data.get("confidence", 0.0),
                     data.get("status", "active"),
                     emb_str),
                )
                pg_conn.commit()
            except Exception as e:
                logger.error(f"写入 event {data.get('id')} 失败: {e}")

        count += 1
        tracker.mark_event()

    logger.info(f"✅ events 迁移: {count} 条")
    return count


def export_standalone(sqlite_conn: sqlite3.Connection, args) -> None:
    """PG 不可用时的 JSON 导出"""
    out_dir = Path("data/export")
    out_dir.mkdir(parents=True, exist_ok=True)

    tables = ["chunks", "events", "entities"]
    for table in tables:
        try:
            rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
        except Exception:
            continue

        data = []
        for row in rows:
            d = dict(row)
            emb = load_blob_embedding(d.pop("embedding", None))
            if emb:
                d["embedding"] = emb
            data.append(d)

        out_file = out_dir / f"{table}.json"
        out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"📦 导出: {out_file} ({len(data)} 条)")

    logger.info(f"✅ 导出完成 → {out_dir}/")


# ============================================================================
# CLI
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="伏羲数据迁移: SQLite → PostgreSQL+pgvector")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际写入")
    parser.add_argument("--limit", type=int, help="限制迁移条数")
    parser.add_argument("--resume", action="store_true", help="断点续传")
    parser.add_argument("--all", action="store_true", help="全量迁移")
    parser.add_argument("--batch-size", type=int, default=500, help="批量大小")
    args = parser.parse_args()

    if not any([args.dry_run, args.limit, args.all, args.resume]):
        parser.print_help()
        print("\n示例:")
        print("  python deploy/migrate_to_pg.py --dry-run          # 预览")
        print("  python deploy/migrate_to_pg.py --limit 1000       # 首批 1000 条")
        print("  python deploy/migrate_to_pg.py --resume           # 续传")
        print("  python deploy/migrate_to_pg.py --all              # 全量")
        return

    logger.info("=" * 60)
    logger.info("伏羲数据迁移工具 v1.0")
    logger.info(f"SQLite: {SQLITE_DB} (存在: {SQLITE_DB.exists()})")
    logger.info(f"ChromaDB: {CHROMA_DIR} (存在: {CHROMA_DIR.exists()})")
    logger.info(f"Dry-run: {args.dry_run}")
    logger.info("=" * 60)

    tracker = ProgressTracker()
    sqlite_conn = get_sqlite_connection()
    pg_conn = get_pg_connection()

    start = time.time()

    try:
        n_chunks = migrate_chunks(sqlite_conn, pg_conn, args, tracker)
        n_events = migrate_events(sqlite_conn, pg_conn, args, tracker)

        if not pg_conn:
            export_standalone(sqlite_conn, args)
    finally:
        sqlite_conn.close()
        if pg_conn:
            pg_conn.close()
        tracker.save()

    elapsed = time.time() - start
    logger.info("=" * 60)
    logger.info(f"迁移完成! chunks: {n_chunks}, events: {n_events}, 耗时: {elapsed:.1f}s")
    if tracker.state["errors"]:
        logger.warning(f"错误数: {len(tracker.state['errors'])}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
