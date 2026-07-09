"""
lib/db.py — 统一数据库访问层
所有数据库操作集中在这里，router 层禁止直接 sqlite3.connect
"""
import sqlite3, os, json
from pathlib import Path
from contextlib import contextmanager
import logging; logger = logging.getLogger(__name__)

# 从 config 读取路径，避免路径不一致
from src.config import WORLDTREE_DB_PATH, CHUNKS_DB_PATH, LOG_DIR

_WORLDTREE_PATH = Path(WORLDTREE_DB_PATH)
_WIKI_PATH = _WORLDTREE_PATH  # P2-4: wiki.db merged into worldtree.db
_CHUNKS_PATH = Path(CHUNKS_DB_PATH) if CHUNKS_DB_PATH else _WORLDTREE_PATH.parent / "chunks.db"

def get_db_path(name: str) -> Path:
    paths = {
        "worldtree": _WORLDTREE_PATH,
        "wiki": _WIKI_PATH,
        "chunks": _CHUNKS_PATH,
        "kb": _WORLDTREE_PATH.parent / "kb.db",
    }
    return paths.get(name, _WORLDTREE_PATH.parent / f"{name}.db")

@contextmanager
def connect(name: str):
    """上下文管理器，自动关闭"""
    conn = sqlite3.connect(str(get_db_path(name)), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# ===== 世界树统计 =====
def count_worldtree() -> dict:
    with connect("worldtree") as db:
        return {
            "wiki_pages": db.execute("SELECT COUNT(1) FROM wiki_pages").fetchone()[0],
            "entities": db.execute("SELECT COUNT(1) FROM entities").fetchone()[0],
            "entity_relations": db.execute("SELECT COUNT(1) FROM entity_relations").fetchone()[0],
            "terms": db.execute("SELECT COUNT(1) FROM terms").fetchone()[0],
        }

# ===== Wiki 操作 =====
def get_wiki_tree() -> list:
    with connect("worldtree") as db:
        rows = db.execute(
            "SELECT category_path, COUNT(*) as cnt FROM wiki_pages GROUP BY category_path ORDER BY cnt DESC"
        ).fetchall()
    tree = {}
    for row in rows:
        parts = row["category_path"].split(" > ")
        current = tree
        for part in parts:
            if part not in current:
                current[part] = {"_children": {}, "_count": 0}
            current[part]["_count"] += row["cnt"]
            current = current[part]["_children"]
    return tree

def get_wiki_pages(cat: str = "", limit: int = 50, offset: int = 0) -> list:
    with connect("worldtree") as db:
        if cat:
            rows = db.execute(
                "SELECT id, title, summary, category_path, quality_score FROM wiki_pages WHERE category_path=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (cat, limit, offset)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT id, title, summary, category_path, quality_score FROM wiki_pages ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
    return [dict(r) for r in rows]

# ===== 知识图谱 =====
def get_knowledge_graph() -> dict:
    with connect("worldtree") as db:
        entities = db.execute("SELECT id, name, type, category_path FROM entities").fetchall()
        relations = db.execute(
            "SELECT e1.name as from_name, e2.name as to_name, er.relation_type "
            "FROM entity_relations er "
            "LEFT JOIN entities e1 ON er.from_id=e1.id "
            "LEFT JOIN entities e2 ON er.to_id=e2.id"
        ).fetchall()
    
    nodes = {r["name"]: {"id": r["id"], "type": r["type"], "label": r["type"], "category_path": r["category_path"] or ""} for r in entities}
    edges = [[r["from_name"], r["to_name"], r["relation_type"]] for r in relations if r["from_name"] and r["to_name"]]
    
    return {"nodes": nodes, "edges": edges}

# ===== 搜索日志 =====
def log_search_to_db(query: str, result_count: int, latency_ms: float, mode: str = "search"):
    try:
        import json
        today = __import__('datetime').datetime.now().strftime("%Y%m%d")
        log_dir = Path(LOG_DIR) if LOG_DIR else _WORLDTREE_PATH.parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"search_{today}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "query": query,
                "results": result_count,
                "latency_ms": round(latency_ms, 1),
                "mode": mode,
                "timestamp": __import__('datetime').datetime.now().isoformat()
            }, ensure_ascii=False) + "\n")
    except Exception:
        logger.warning(f"[db] 搜索日志写入失败", exc_info=True)

logger.info("lib/db.py 加载完成")
