"""
data_store.py — 数据存储工具（v10.0）
负责：chunks 加载/保存、配置加载/保存、搜索日志、图谱操作
抽取自 server.py，供各 router 模块共享
"""
import os, json, time, threading
from datetime import datetime, timezone

from src.db.memory_store import get_store
from src.config import (
    LOG_DIR,
    CONFIG_FILE,
    CONFIG_HISTORY_DIR,
    GRAPH_PATH,
    TOOLS_DATA,
    FAQ_DATA,
)

# ============ 索引初始化 ============

def _ensure_indexes(conn):
    """确保常用查询有索引"""
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_category ON chunks(category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_created ON chunks(created_at)")
    conn.commit()


def init_db():
    """初始化数据库索引（幂等，可重复调用）"""
    store = get_store()
    _ensure_indexes(store._db_conn)

# ============ Chunks ============

_CHUNK_CACHE = {"data": None, "ts": 0, "access_count": 0, "last_access": 0}
_chunk_cache_lock = threading.Lock()


def _calculate_dynamic_ttl(access_count: int, last_access: float) -> int:
    """根据访问频率动态计算TTL"""
    if access_count > 100:
        return 120
    elif access_count > 10:
        return 60
    else:
        return 30

def load_chunks(filter_junk: bool = True, limit: int = None, offset: int = 0) -> list:
    """从 SQLite 分页加载 chunk（带动态 TTL 缓存，threadsafe）"""
    now = time.time()
    with _chunk_cache_lock:
        if filter_junk and limit is None and offset == 0 and _CHUNK_CACHE["data"] is not None:
            ttl = _calculate_dynamic_ttl(_CHUNK_CACHE["access_count"], _CHUNK_CACHE["last_access"])
            if now - _CHUNK_CACHE["ts"] < ttl:
                _CHUNK_CACHE["access_count"] += 1
                _CHUNK_CACHE["last_access"] = now
                return _CHUNK_CACHE["data"]

    store = get_store()
    chunks = store.get_all(limit=limit, offset=offset)
    if not filter_junk:
        return chunks
    _JUNK_PATTERNS = [
        'draft_meta_info', 'draft_virtual_store', 'draft_content', 'draft_cloud',
        'draft_enterprise', 'key_value.json', 'excanvas.js', 'search.cfg',
        '.step', '.sldprt', '.prt', '.igs', '.dwg', '.stl', '.iges'
    ]
    def _is_junk(fname):
        fn = (fname or '').lower()
        for pat in _JUNK_PATTERNS:
            if pat in fn:
                return True
        return False
    result = [c for c in chunks if not _is_junk(c.get('file_name', ''))]

    if limit is None and offset == 0:
        with _chunk_cache_lock:
            _CHUNK_CACHE["data"] = result
            _CHUNK_CACHE["ts"] = now
            _CHUNK_CACHE["access_count"] = 1
            _CHUNK_CACHE["last_access"] = now

    return result


def invalidate_chunk_cache():
    """在数据写入/删除后调用，清除缓存"""
    with _chunk_cache_lock:
        _CHUNK_CACHE["data"] = None
        _CHUNK_CACHE["ts"] = 0
    _CHUNK_CACHE["access_count"] = 0
    _CHUNK_CACHE["last_access"] = 0


def save_chunks(chunks: list):
    """全量替换保存 chunks：清空现有数据，再批量写入（带缓存失效）
    
    调用方期望：提供完整的 chunk 列表，完全替换数据库中的现有数据。
    实现：通过 MemoryStore 先清空再批量插入，保证原子性。
    """
    store = get_store()
    # 1) 先清空现有数据
    with store._db_conn:
        store._db_conn.execute("DELETE FROM chunks")
        # 重置自增计数器，避免 id 无限增长
        store._db_conn.execute("DELETE FROM sqlite_sequence WHERE name='chunks'")
    # 2) 清除内存缓存
    store._cache_hash.clear()
    store._cache_name.clear()
    store._json_cache.clear()
    store._files_cache = None
    store._files_cache_time = 0
    # 3) 批量写入新数据
    if chunks:
        store.add_batch(chunks)
    # 4) 同步清理 data_store 模块级缓存
    invalidate_chunk_cache()
    logger.info(f"save_chunks: 已保存 {len(chunks)} 条记录")


# ============ Config ============

def load_config() -> dict:
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        logger.warning(f"[data_store] load_config 失败", exc_info=True)
    return {"tools": TOOLS_DATA, "faq": FAQ_DATA}


def save_config(config: dict):
    tmp = str(CONFIG_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False)
    os.replace(tmp, str(CONFIG_FILE))


def save_config_history(config: dict):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    (CONFIG_HISTORY_DIR / f"config_{ts}.json").write_text(
        json.dumps(config, ensure_ascii=False), encoding="utf-8")


# ============ 搜索日志 ============

def log_search(query: str, results: int, ms: float, top_items: list = None):
    try:
        f = LOG_DIR / f"search_{datetime.now().strftime('%Y%m%d')}.jsonl"
        entry = {
            "query": query,
            "results": results,
            "ms": round(ms, 1),
            "time": datetime.now().isoformat(),
        }
        if top_items:
            entry["top_items"] = top_items[:5]
            scores = [it.get("score", 0) for it in top_items]
            if scores:
                entry["top_score"] = max(scores)
                entry["avg_score"] = round(sum(scores) / len(scores), 3)
        with open(f, "a", encoding="utf-8") as fh:
            json.dump(entry, fh, ensure_ascii=False)
            fh.write("\n")
    except Exception:
        logger.warning(f"[data_store] log_search 写入失败", exc_info=True)


def search_history(days: int = 7) -> list:
    hist = []
    cutoff = time.time() - days * 86400
    try:
        for fn in sorted(os.listdir(LOG_DIR), reverse=True):
            if fn.startswith("search_") and fn.endswith(".jsonl"):
                with open(LOG_DIR / fn, encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            e = json.loads(line)
                            if "time" in e:
                                ts = datetime.fromisoformat(e["time"]).timestamp()
                                if ts >= cutoff:
                                    hist.append(e)
                        except Exception:
                            logger.debug(f"[data_store] 搜索日志行解析失败，跳过", exc_info=True)
    except Exception:
        logger.warning(f"[data_store] search_history 读取失败", exc_info=True)(hist, key=lambda x: x.get("time", ""), reverse=True)[:30]


# ============ 知识图谱 ============

def load_graph() -> dict:
    """加载知识图谱，兼容三种来源：
    1. knowledge_graph.json (格式A/B)
    2. worldtree.db entities + entity_relations (fallback)
    统一转换为格式A: {"nodes":{...}, "edges":[...]}
    """
    if GRAPH_PATH.exists():
        raw = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
        if "nodes" in raw or "edges" in raw:
            return {
                "nodes": raw.get("nodes", {}),
                "edges": raw.get("edges", []),
            }
        # 格式B：顶层是实体字典 → 转换
        nodes = {}
        edges = []
        for entity, info in raw.items():
            if not isinstance(info, dict):
                continue
            rels = info.get("relations", [])
            nodes[entity] = info
            for r in rels:
                parts = r.split(":", 1)
                if len(parts) == 2:
                    edges.append({
                        "from": entity,
                        "to": parts[0],
                        "relation": parts[1],
                    })
        if nodes:
            return {"nodes": nodes, "edges": edges}
    
    # Fallback: load from worldtree.db
    try:
        from src.core.db import connect
        with connect("worldtree") as wt_db:
            ents = wt_db.execute("SELECT id, name, type, category_path FROM entities").fetchall()
            if ents:
                nodes = {}
                for r in ents:
                    d = dict(r)
                    nodes[d["name"]] = {
                        "id": d["id"],
                        "type": d["type"],
                        "label": d["type"],
                        "category_path": d.get("category_path", "") or ""
                    }
                edges = []
                rels = wt_db.execute(
                    "SELECT e1.name as from_name, e2.name as to_name, er.relation_type "
                    "FROM entity_relations er "
                    "LEFT JOIN entities e1 ON er.from_id = e1.id "
                    "LEFT JOIN entities e2 ON er.to_id = e2.id"
                ).fetchall()
                for r in rels:
                    d = dict(r)
                    if d["from_name"] and d["to_name"]:
                        edges.append({
                            "from": d["from_name"],
                            "to": d["to_name"],
                            "relation": d["relation_type"]
                        })
                return {"nodes": nodes, "edges": edges}
    except Exception as e:
        logger.warning(f"[data_store] load_graph worldtree 回退失败: {e}", exc_info=True)
    return {"nodes": {}, "edges": []}


def save_graph(graph: dict):
    """保存知识图谱，空图不覆盖已有数据"""
    nodes = graph.get("nodes", graph.get("entities", {}))
    if not nodes and GRAPH_PATH.exists():
        existing = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
        if existing.get("nodes") or existing.get("entities"):
            return  # 拒绝用空图覆盖
    GRAPH_PATH.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")


# ============ 行为日志 ============

def log_behavior(entry: dict):
    f = LOG_DIR / f"behavior_{datetime.now().strftime('%Y%m%d')}.jsonl"
    entry["time"] = datetime.now(timezone.utc).isoformat()
    try:
        with open(f, "a", encoding="utf-8") as fh:
            json.dump(entry, fh, ensure_ascii=False)
            fh.write("\n")
    except Exception:
        logger.warning(f"[data_store] log_behavior 写入失败", exc_info=True)


# ============ 用户偏好 ============

from src.config import USER_PREFERENCES_FILE
import logging; logger = logging.getLogger(__name__)

def get_user_preferences(uid: str) -> dict:
    prefs = {}
    if USER_PREFERENCES_FILE.exists():
        try:
            all_prefs = json.loads(USER_PREFERENCES_FILE.read_text(encoding="utf-8"))
            prefs = all_prefs.get(uid, {})
        except Exception:
            logger.warning(f"[data_store] get_user_preferences 读取失败", exc_info=True)
    return prefs


def save_user_preferences(uid: str, prefs: dict):
    all_prefs = {}
    if USER_PREFERENCES_FILE.exists():
        try:
            all_prefs = json.loads(USER_PREFERENCES_FILE.read_text(encoding="utf-8"))
        except Exception:
            logger.warning(f"[data_store] save_user_preferences 读取失败", exc_info=True)
    all_prefs[uid] = prefs
    USER_PREFERENCES_FILE.write_text(json.dumps(all_prefs, ensure_ascii=False, indent=2), encoding="utf-8")
