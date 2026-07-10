"""
graph_traversal.py — Phase 8.1: 图遍历推理引擎
支持多跳实体遍历 + SQLite 邻接表加速
"""
import json, os, logging, sqlite3
from typing import List, Dict, Optional
from collections import deque
from pathlib import Path

logger = logging.getLogger("graph_traversal")
GRAPH_FILE = os.path.join(os.path.dirname(__file__), "../../data/knowledge_graph.json")
DB_PATH = Path(os.path.join(os.path.dirname(__file__), "../../data/chunks.db"))


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS graph_adjacency (
            entity_id   TEXT NOT NULL,
            neighbor_id TEXT NOT NULL,
            relation    TEXT NOT NULL,
            direction   TEXT NOT NULL,
            weight      REAL DEFAULT 1.0,
            PRIMARY KEY (entity_id, neighbor_id, relation, direction)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_adj_entity ON graph_adjacency(entity_id)")
    conn.commit()
    return conn


def build_adjacency():
    """从 knowledge_graph.json 构建 SQLite 邻接表"""
    graph = load_graph()
    edges = graph.get("edges", [])
    if not edges:
        logger.warning("[GraphTraversal] 无边数据，跳过邻接表构建")
        return 0

    conn = _get_conn()
    conn.execute("DELETE FROM graph_adjacency")

    # Batch: executemany 替代循环 INSERT
    adj_rows = []
    for e in edges:
        src = e.get("source", "")
        tgt = e.get("target", "")
        rel = e.get("relation", "related_to")
        if src and tgt:
            adj_rows.append((src, tgt, rel, "out", 1.0))
            adj_rows.append((tgt, src, rel, "in", 1.0))
    if adj_rows:
        conn.executemany("INSERT OR IGNORE INTO graph_adjacency VALUES (?,?,?,?,1.0)", adj_rows)

    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM graph_adjacency").fetchone()[0]
    conn.close()
    logger.info(f"[GraphTraversal] 邻接表构建完成: {count} 条")
    return count


def load_graph() -> dict:
    if os.path.exists(GRAPH_FILE):
        with open(GRAPH_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"nodes": [], "edges": []}


def _build_adj_from_graph(graph: dict, relation_filter: Optional[str] = None) -> dict:
    """从 JSON 构建内存邻接表"""
    adj = {}
    for e in graph.get("edges", []):
        s, t = e.get("source", ""), e.get("target", "")
        rel = e.get("relation", "related_to")
        if relation_filter and rel != relation_filter:
            continue
        adj.setdefault(s, []).append((t, rel))
        adj.setdefault(t, []).append((s, rel))
    return adj


def _get_neighbors_from_db(entity_id: str) -> List[tuple]:
    """从 SQLite 邻接表获取邻居（更快）"""
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT neighbor_id, relation FROM graph_adjacency WHERE entity_id=?",
            (entity_id,)
        ).fetchall()
        conn.close()
        return rows
    except Exception as e:  # TODO: Narrow exception type
        logger.warning("Exception 失败: %s", e, exc_info=True)
        return []


def multi_hop_traverse(
    start_entity: str,
    target_type: Optional[str] = None,
    max_hops: int = 3,
    relation_filter: Optional[str] = None
) -> Dict:
    """
    多跳图遍历引擎
    优先使用 SQLite 邻接表，fallback 到 JSON
    """
    graph = load_graph()
    nodes = {n["id"]: n for n in graph.get("nodes", [])}

    # 尝试 SQLite 邻接表
    db_neighbors = _get_neighbors_from_db(start_entity)
    use_db = len(db_neighbors) > 0

    if use_db:
        adj = {}  # 按需加载
        def get_neighbors(entity):
            return _get_neighbors_from_db(entity)
    else:
        adj = _build_adj_from_graph(graph, relation_filter)
        def get_neighbors(entity):
            return adj.get(entity, [])

    if start_entity not in nodes and not use_db:
        return {"paths": [], "entities": [], "error": f"Entity not found: {start_entity}"}

    # BFS 多跳遍历
    visited = {start_entity}
    queue = deque([(start_entity, [start_entity], 0)])
    found_paths = []
    found_entities = set()
    max_depth_reached = 0

    while queue:
        current, path, depth = queue.popleft()
        if depth >= max_hops:
            continue
        max_depth_reached = max(max_depth_reached, depth)

        for neighbor, rel in get_neighbors(current):
            if relation_filter and rel != relation_filter:
                continue
            if neighbor in visited:
                continue
            new_path = path + [neighbor]
            visited.add(neighbor)

            node = nodes.get(neighbor, {})
            ntype = node.get("type", "")

            if target_type and ntype == target_type:
                found_paths.append({
                    "path": new_path,
                    "hops": depth + 1,
                    "target_type": ntype,
                    "relations": [rel]
                })
                found_entities.add(neighbor)
            elif not target_type:
                found_paths.append({
                    "path": new_path,
                    "hops": depth + 1,
                    "target_type": ntype,
                    "relations": [rel]
                })
                found_entities.add(neighbor)

            queue.append((neighbor, new_path, depth + 1))

    return {
        "paths": found_paths[:20],
        "entities": list(found_entities),
        "start": start_entity,
        "hops_traversed": max_depth_reached,
        "source": "sqlite" if use_db else "json"
    }


def find_paths(entity_a: str, entity_b: str, max_hops: int = 4) -> List[Dict]:
    """找两个实体之间的所有路径"""
    graph = load_graph()
    nodes = {n["id"]: n for n in graph.get("nodes", [])}
    adj = _build_adj_from_graph(graph)

    if entity_a not in nodes or entity_b not in nodes:
        return []

    visited = {entity_a}
    queue = deque([(entity_a, [entity_a], 0)])
    found = []

    while queue:
        current, path, depth = queue.popleft()
        if depth >= max_hops:
            continue
        for neighbor, rel in adj.get(current, []):
            if neighbor in visited:
                continue
            new_path = path + [neighbor]
            if neighbor == entity_b:
                found.append({"path": new_path, "hops": depth + 1})
            else:
                visited.add(neighbor)
                queue.append((neighbor, new_path, depth + 1))

    return found[:10]


def subgraph(center_entity: str, radius: int = 2) -> Dict:
    """提取以 center_entity 为中心的子图"""
    graph = load_graph()
    nodes = {n["id"]: n for n in graph.get("nodes", [])}
    adj = _build_adj_from_graph(graph)

    visited = {center_entity}
    queue = deque([(center_entity, 0)])
    sub_nodes = [center_entity]
    sub_edges = []

    while queue:
        current, depth = queue.popleft()
        if depth >= radius:
            continue
        for neighbor, rel in adj.get(current, []):
            sub_edges.append({"from": current, "to": neighbor, "relation": rel})
            if neighbor not in visited:
                visited.add(neighbor)
                sub_nodes.append(neighbor)
                queue.append((neighbor, depth + 1))

    return {"nodes": sub_nodes, "edges": sub_edges, "center": center_entity}


def get_reachable_entities(entity: str, max_hops: int = 2) -> List[str]:
    """获取可达实体（用于 GraphRAG 上下文扩展）"""
    result = multi_hop_traverse(entity, max_hops=max_hops)
    return result.get("entities", [])
