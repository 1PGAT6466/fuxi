"""
伏羲 RAG 4.0 — Entity Frontier 查询时动态超边引擎
====================================================
SAG 论文核心机制: 查询时用 SQL JOIN 动态激活局部超边，
替代离线全局知识图谱。

双后端：PostgreSQL（生产） / SQLite（开发/过渡）

数据流:
    seed_events (种子事件ID列表)
      → expand_seed()    反查关联 entities（Entity Frontier）
      → hop_entities()   H=1 跳 JOIN 发现新 events
      → get_hyperedge()  完整的动态超边子图

性能优化 (Round 1 审计):
- FIX-09: 添加 MAX_NEW_ENTITIES_PER_HOP=50, MAX_TOTAL_EVENTS=500 防止递归爆炸
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ===== 爆炸保护上限 =====
MAX_NEW_ENTITIES_PER_HOP = 50   # 每跳最多 50 个新实体
MAX_TOTAL_EVENTS = 500          # 总事件数硬上限


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class FrontierEntity:
    entity_id: str
    name: str
    type: str
    event_count: int


@dataclass
class HoppedEvent:
    event_id: str
    chunk_id: str
    content: str
    entities: List[dict]
    hop_depth: int = 0


@dataclass
class HyperedgeNode:
    event_id: str
    chunk_id: str
    entity_id: str
    entity_name: str
    entity_type: str
    is_seed: bool = False


# ============================================================================
# SQLite 实现（过渡期，无 PG 可用时使用）
# ============================================================================

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    chunk_id TEXT NOT NULL,
    content TEXT NOT NULL,
    event_type TEXT DEFAULT 'general',
    entities_json TEXT DEFAULT '[]',
    confidence REAL DEFAULT 0.0,
    status TEXT DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    type TEXT NOT NULL,
    aliases_json TEXT DEFAULT '[]',
    chunk_ids_json TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS event_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL REFERENCES events(id),
    entity_id TEXT NOT NULL REFERENCES entities(id),
    role TEXT,
    confidence REAL DEFAULT 1.0,
    UNIQUE(event_id, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_ee_event ON event_entities(event_id);
CREATE INDEX IF NOT EXISTS idx_ee_entity ON event_entities(entity_id);
CREATE INDEX IF NOT EXISTS idx_entities_norm ON entities(normalized_name);
"""


class SQLiteEntityFrontier:
    """SQLite 后端的 Entity Frontier 实现"""

    def __init__(self, db_path: str = "data/memory.db"):
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.executescript(SQLITE_SCHEMA)
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"[EntityFrontier] DDL 初始化失败: {e}")
            raise

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def expand_seed(self, seed_event_ids: List[str]) -> List[FrontierEntity]:
        """从种子事件反查关联实体（Entity Frontier）。"""
        if not seed_event_ids:
            return []

        conn = self._get_conn()
        placeholders = ",".join("?" * len(seed_event_ids))

        rows = conn.execute(f"""
            SELECT 
                ee.entity_id,
                e.name,
                e.type,
                COUNT(DISTINCT ee.event_id) AS event_count
            FROM event_entities ee
            JOIN entities e ON ee.entity_id = e.id
            WHERE ee.event_id IN ({placeholders})
            GROUP BY ee.entity_id, e.name, e.type
            ORDER BY event_count DESC
        """, seed_event_ids).fetchall()

        conn.close()
        return [
            FrontierEntity(
                entity_id=r["entity_id"],
                name=r["name"],
                type=r["type"],
                event_count=r["event_count"],
            )
            for r in rows
        ]

    def hop_entities(
        self,
        entity_ids: List[str],
        exclude_event_ids: Optional[List[str]] = None,
        hop_limit: int = 1,
    ) -> List[HoppedEvent]:
        """从 Entity Frontier 多跳发现新事件，带爆炸保护。

        FIX-09: MAX_NEW_ENTITIES_PER_HOP=50, MAX_TOTAL_EVENTS=500
        """
        if not entity_ids:
            return []

        exclude = exclude_event_ids or []
        conn = self._get_conn()

        placeholders = ",".join("?" * len(entity_ids))
        exclude_placeholders = ",".join("?" * len(exclude)) if exclude else ""

        query = f"""
            SELECT DISTINCT 
                e.id AS event_id,
                e.chunk_id,
                e.content,
                e.entities_json,
                0 AS hop_depth
            FROM event_entities ee
            JOIN events e ON ee.event_id = e.id
            WHERE ee.entity_id IN ({placeholders})
        """
        if exclude:
            query += f" AND e.id NOT IN ({exclude_placeholders})"

        params = entity_ids + exclude
        seen_events = set(exclude)
        results: List[HoppedEvent] = []

        rows = conn.execute(query, params).fetchall()
        for r in rows:
            if r["event_id"] not in seen_events:
                seen_events.add(r["event_id"])
                results.append(HoppedEvent(
                    event_id=r["event_id"],
                    chunk_id=r["chunk_id"],
                    content=r["content"],
                    entities=json.loads(r["entities_json"] or "[]"),
                    hop_depth=0,
                ))
                if len(seen_events) >= MAX_TOTAL_EVENTS:
                    break

        # 后续跳（递归 JOIN）— 带上限
        if hop_limit > 1 and results and len(seen_events) < MAX_TOTAL_EVENTS:
            for depth in range(1, hop_limit):
                if len(seen_events) >= MAX_TOTAL_EVENTS:
                    break

                new_entity_ids = set()
                for evt in results:
                    for ent in evt.entities[:MAX_NEW_ENTITIES_PER_HOP]:
                        name = ent.get("name", "")
                        if name:
                            new_entity_ids.add(name)
                        if len(new_entity_ids) >= MAX_NEW_ENTITIES_PER_HOP:
                            break
                    if len(new_entity_ids) >= MAX_NEW_ENTITIES_PER_HOP:
                        break

                if not new_entity_ids:
                    break

                new_placeholders = ",".join("?" * len(new_entity_ids))
                seen_placeholders = ",".join("?" * len(seen_events))
                new_query = f"""
                    SELECT DISTINCT 
                        e.id AS event_id,
                        e.chunk_id,
                        e.content,
                        e.entities_json,
                        {depth} AS hop_depth
                    FROM event_entities ee
                    JOIN events e ON ee.event_id = e.id
                    JOIN entities ent ON ee.entity_id = ent.id
                    WHERE ent.normalized_name IN ({new_placeholders})
                      AND e.id NOT IN ({seen_placeholders})
                """

                new_rows = conn.execute(
                    new_query,
                    list(new_entity_ids) + list(seen_events),
                ).fetchall()

                added = 0
                for r in new_rows:
                    if r["event_id"] not in seen_events:
                        seen_events.add(r["event_id"])
                        results.append(HoppedEvent(
                            event_id=r["event_id"],
                            chunk_id=r["chunk_id"],
                            content=r["content"],
                            entities=json.loads(r["entities_json"] or "[]"),
                            hop_depth=depth,
                        ))
                        added += 1
                        if len(seen_events) >= MAX_TOTAL_EVENTS:
                            break

                if added == 0 or len(seen_events) >= MAX_TOTAL_EVENTS:
                    break

        conn.close()
        return results

    def get_hyperedge(
        self,
        query_entity_ids: List[str],
        max_events: int = 100,
    ) -> List[HyperedgeNode]:
        """获取动态超边子图"""
        if not query_entity_ids:
            return []

        conn = self._get_conn()
        placeholders = ",".join("?" * len(query_entity_ids))

        rows = conn.execute(f"""
            WITH seed_events AS (
                SELECT DISTINCT ee.event_id
                FROM event_entities ee
                WHERE ee.entity_id IN ({placeholders})
                LIMIT ?
            ),
            expanded_entities AS (
                SELECT ee.entity_id, 1 AS is_seed
                FROM event_entities ee
                WHERE ee.entity_id IN ({placeholders})
                UNION
                SELECT ee.entity_id, 0 AS is_seed
                FROM event_entities ee
                WHERE ee.event_id IN (SELECT event_id FROM seed_events)
                  AND ee.entity_id NOT IN ({placeholders})
            )
            SELECT DISTINCT
                e.id AS event_id,
                e.chunk_id,
                ent.id AS entity_id,
                ent.name AS entity_name,
                ent.type AS entity_type,
                ex.is_seed
            FROM expanded_entities ex
            JOIN event_entities ee ON ex.entity_id = ee.entity_id
            JOIN events e ON ee.event_id = e.id
            JOIN entities ent ON ex.entity_id = ent.id
            ORDER BY ex.is_seed DESC
            LIMIT ?
        """, query_entity_ids + [max_events, max_events]).fetchall()

        conn.close()
        return [
            HyperedgeNode(
                event_id=r["event_id"],
                chunk_id=r["chunk_id"],
                entity_id=r["entity_id"],
                entity_name=r["entity_name"],
                entity_type=r["entity_type"],
                is_seed=bool(r["is_seed"]),
            )
            for r in rows
        ]


# ============================================================================
# PostgreSQL 实现（生产环境）
# ============================================================================

class PGEntityFrontier:
    """PostgreSQL 后端的 Entity Frontier"""

    def __init__(self, pg_conn):
        self.pg = pg_conn

    def expand_seed(self, seed_event_ids: List[str]) -> List[FrontierEntity]:
        if not seed_event_ids:
            return []
        cur = self.pg.cursor()
        cur.execute("SELECT * FROM get_entity_frontier(%s)", (seed_event_ids,))
        rows = cur.fetchall()
        return [
            FrontierEntity(entity_id=r[0], name=r[1], type=r[2], event_count=r[3])
            for r in rows
        ]

    def hop_entities(
        self, entity_ids: List[str],
        exclude_event_ids: Optional[List[str]] = None, hop_limit: int = 1,
    ) -> List[HoppedEvent]:
        if not entity_ids:
            return []
        cur = self.pg.cursor()
        cur.execute("SELECT * FROM hop_entities(%s, %s, %s)",
                    (entity_ids, exclude_event_ids or [], hop_limit))
        rows = cur.fetchall()
        return [
            HoppedEvent(
                event_id=r[0], chunk_id=r[1], content=r[2],
                entities=json.loads(r[3] or "[]"), hop_depth=r[4],
            ) for r in rows
        ]

    def get_hyperedge(self, query_entity_ids: List[str], max_events: int = 100) -> List[HyperedgeNode]:
        if not query_entity_ids:
            return []
        cur = self.pg.cursor()
        cur.execute("SELECT * FROM get_dynamic_hyperedge(%s, %s)",
                    (query_entity_ids, max_events))
        rows = cur.fetchall()
        return [
            HyperedgeNode(
                event_id=r[0], chunk_id=r[1], entity_id=r[3],
                entity_name=r[4], entity_type=r[5], is_seed=r[6],
            ) for r in rows
        ]


# ============================================================================
# 统一入口（自动选后端）
# ============================================================================

class EntityFrontier:
    """Entity Frontier 查询引擎。"""

    def __init__(self, pg_conn=None, sqlite_path: str = "data/memory.db"):
        self._pg = pg_conn
        self._sqlite = SQLiteEntityFrontier(sqlite_path) if not pg_conn else None
        self._pg_frontier = PGEntityFrontier(pg_conn) if pg_conn else None
        self._backend = "pg" if pg_conn else "sqlite"
        logger.info(f"[EntityFrontier] 后端: {self._backend}")

    def expand_seed(self, seed_event_ids: List[str]) -> List[FrontierEntity]:
        if self._pg_frontier:
            try:
                return self._pg_frontier.expand_seed(seed_event_ids)
            except Exception as e:
                logger.warning(f"PG expand_seed 失败，降级 SQLite: {e}")
        return self._sqlite.expand_seed(seed_event_ids) if self._sqlite else []

    def hop_entities(
        self, entity_ids: List[str],
        exclude_event_ids: Optional[List[str]] = None, hop_limit: int = 1,
    ) -> List[HoppedEvent]:
        if self._pg_frontier:
            try:
                return self._pg_frontier.hop_entities(entity_ids, exclude_event_ids, hop_limit)
            except Exception as e:
                logger.warning(f"PG hop_entities 失败，降级 SQLite: {e}")
        return self._sqlite.hop_entities(entity_ids, exclude_event_ids, hop_limit) if self._sqlite else []

    def get_hyperedge(self, query_entity_ids: List[str], max_events: int = 100) -> List[HyperedgeNode]:
        if self._pg_frontier:
            try:
                return self._pg_frontier.get_hyperedge(query_entity_ids, max_events)
            except Exception as e:
                logger.warning(f"PG get_hyperedge 失败，降级 SQLite: {e}")
        return self._sqlite.get_hyperedge(query_entity_ids, max_events) if self._sqlite else []

    @property
    def backend_name(self) -> str:
        return self._backend


# ============================================================================
# 自检
# ============================================================================

if __name__ == "__main__":
    ef = EntityFrontier()
    logger.info("backend: %s", ef.backend_name)
    entities = ef.expand_seed(["evt_001", "evt_002"])
    logger.info("expand_seed: %d entities", len(entities))
    events = ef.hop_entities(["ent_pa66", "ent_gear"], hop_limit=1)
    logger.info("hop_entities: %d events", len(events))
    logger.info("OK — EntityFrontier 就绪")
