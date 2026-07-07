-- ============================================================================
-- 伏羲 RAG 4.0 — PostgreSQL + pgvector 数据库 Schema
-- 版本: v1.0 | 日期: 2026-07-07
-- 基于: SAG 论文 (arXiv:2606.15971) + 伏羲 v4.2 八卦架构
-- ============================================================================

-- 1. 扩展
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- 模糊匹配

-- ============================================================================
-- 2. 核心表
-- ============================================================================

-- 2.1 chunks（文档碎片）
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id       TEXT PRIMARY KEY,           -- "chunk_000001"
    document_id    TEXT NOT NULL,              -- 所属文档
    document_name  TEXT,
    content        TEXT NOT NULL,              -- 原文
    chunk_index    INTEGER,                   -- 文档内序号
    token_count    INTEGER,
    metadata       JSONB DEFAULT '{}',
    embedding      vector(768),
    created_at     TIMESTAMPTZ DEFAULT now(),
    updated_at     TIMESTAMPTZ DEFAULT now()
);

-- 2.2 events（原子事件 — SAG 核心）
CREATE TABLE IF NOT EXISTS events (
    event_id       TEXT PRIMARY KEY,           -- "evt_000001"
    chunk_id       TEXT NOT NULL REFERENCES chunks(chunk_id) ON DELETE CASCADE,
    content        TEXT NOT NULL,              -- 事件完整语义描述
    event_type     TEXT,                       -- "声明"/"测量"/"流程"/"关系"/...
    entities_json  JSONB DEFAULT '[]',         -- [{name, type, confidence}]
    confidence     REAL DEFAULT 0.0,
    status         TEXT DEFAULT 'active',      -- active/pending/stale
    metadata       JSONB DEFAULT '{}',
    embedding      vector(768),
    created_at     TIMESTAMPTZ DEFAULT now()
);

-- 2.3 entities（索引实体 — SAG 11 类）
CREATE TABLE IF NOT EXISTS entities (
    entity_id      TEXT PRIMARY KEY,           -- "ent_000001"
    name           TEXT NOT NULL,
    normalized_name TEXT NOT NULL,             -- 归一化名称（去空格/小写）
    type           TEXT NOT NULL,              -- person/org/location/time/product/...
    aliases_json   JSONB DEFAULT '[]',         -- 别名列表
    chunk_ids_json JSONB DEFAULT '[]',         -- 关联 chunk
    metadata       JSONB DEFAULT '{}',
    embedding      vector(768),
    created_at     TIMESTAMPTZ DEFAULT now()
);

-- 2.4 event_entities（多对多关联 — SAG 超边基础）
CREATE TABLE IF NOT EXISTS event_entities (
    id             SERIAL PRIMARY KEY,
    event_id       TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    entity_id      TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    role           TEXT,                       -- "subject"/"object"/"location"/...
    confidence     REAL DEFAULT 1.0,
    UNIQUE(event_id, entity_id)
);

-- ============================================================================
-- 3. 索引
-- ============================================================================

-- 向量索引（IVFFlat — 先插入数据再建）
-- CREATE INDEX ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
-- CREATE INDEX ON events USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
-- CREATE INDEX ON entities USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

-- 全文索引
CREATE INDEX IF NOT EXISTS idx_chunks_fts ON chunks USING gin (to_tsvector('simple', content));
CREATE INDEX IF NOT EXISTS idx_events_fts ON events USING gin (to_tsvector('simple', content));
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities (normalized_name);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities (type);

-- 关联索引
CREATE INDEX IF NOT EXISTS idx_event_entities_event ON event_entities(event_id);
CREATE INDEX IF NOT EXISTS idx_event_entities_entity ON event_entities(entity_id);
CREATE INDEX IF NOT EXISTS idx_events_chunk ON events(chunk_id);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);

-- ============================================================================
-- 4. SAG 动态超边查询函数
-- ============================================================================

-- 4.1 从 seed events 反查关联 entities（Entity Frontier）
CREATE OR REPLACE FUNCTION get_entity_frontier(seed_event_ids TEXT[])
RETURNS TABLE(entity_id TEXT, entity_name TEXT, entity_type TEXT, event_count BIGINT)
LANGUAGE sql STABLE AS $$
    SELECT
        ee.entity_id,
        e.name,
        e.type,
        COUNT(DISTINCT ee.event_id) AS event_count
    FROM event_entities ee
    JOIN entities e ON ee.entity_id = e.entity_id
    WHERE ee.event_id = ANY(seed_event_ids)
    GROUP BY ee.entity_id, e.name, e.type
    ORDER BY event_count DESC;
$$;

-- 4.2 从 entity frontier 多跳发现新 events（H=1，SAG 默认值）
CREATE OR REPLACE FUNCTION hop_entities(
    entity_ids TEXT[],
    exclude_event_ids TEXT[] DEFAULT '{}',
    hop_limit INTEGER DEFAULT 1
)
RETURNS TABLE(
    event_id TEXT,
    chunk_id TEXT,
    content TEXT,
    entities_json JSONB,
    hop_depth INTEGER
)
LANGUAGE sql STABLE AS $$
    WITH RECURSIVE hop AS (
        -- Base: events directly linked to seed entities
        SELECT DISTINCT
            ee.event_id,
            0 AS depth
        FROM event_entities ee
        WHERE ee.entity_id = ANY(entity_ids)
          AND ee.event_id <> ALL(exclude_event_ids)

        UNION

        -- Recursive: hop through shared entities
        SELECT DISTINCT
            ee2.event_id,
            h.depth + 1
        FROM hop h
        JOIN event_entities ee1 ON h.event_id = ee1.event_id
        JOIN event_entities ee2 ON ee1.entity_id = ee2.entity_id
        WHERE h.depth < hop_limit
          AND ee2.event_id <> ALL(exclude_event_ids)
          AND ee2.event_id NOT IN (SELECT event_id FROM hop)
    )
    SELECT
        e.event_id,
        e.chunk_id,
        e.content,
        e.entities_json,
        h.depth
    FROM hop h
    JOIN events e ON h.event_id = e.event_id
    ORDER BY h.depth, e.confidence DESC;
$$;

-- 4.3 动态超边物化视图（查询时激活的局部子图）
CREATE OR REPLACE FUNCTION get_dynamic_hyperedge(
    query_entity_ids TEXT[],
    max_events INTEGER DEFAULT 100
)
RETURNS TABLE(
    event_id TEXT,
    chunk_id TEXT,
    event_content TEXT,
    entity_id TEXT,
    entity_name TEXT,
    entity_type TEXT,
    is_seed BOOLEAN
)
LANGUAGE sql STABLE AS $$
    WITH seed_events AS (
        SELECT DISTINCT ee.event_id
        FROM event_entities ee
        WHERE ee.entity_id = ANY(query_entity_ids)
        LIMIT max_events
    ),
    expanded_entities AS (
        SELECT DISTINCT ee.entity_id, TRUE AS is_seed
        FROM event_entities ee
        WHERE ee.entity_id = ANY(query_entity_ids)
        UNION ALL
        SELECT DISTINCT ee.entity_id, FALSE AS is_seed
        FROM event_entities ee
        WHERE ee.event_id IN (SELECT event_id FROM seed_events)
          AND ee.entity_id <> ALL(query_entity_ids)
    )
    SELECT DISTINCT
        e.event_id,
        e.chunk_id,
        e.content,
        ent.entity_id,
        ent.name,
        ent.type,
        ex.is_seed
    FROM expanded_entities ex
    JOIN event_entities ee ON ex.entity_id = ee.entity_id
    JOIN events e ON ee.event_id = e.event_id
    JOIN entities ent ON ex.entity_id = ent.entity_id
    ORDER BY ex.is_seed DESC, e.confidence DESC
    LIMIT max_events;
$$;

-- ============================================================================
-- 5. 全文搜索函数
-- ============================================================================

CREATE OR REPLACE FUNCTION search_chunks_fts(query_text TEXT, limit_count INTEGER DEFAULT 20)
RETURNS TABLE(chunk_id TEXT, content TEXT, rank REAL, headline TEXT)
LANGUAGE sql STABLE AS $$
    SELECT
        c.chunk_id,
        c.content,
        ts_rank(to_tsvector('simple', c.content), plainto_tsquery('simple', query_text)) AS rank,
        ts_headline('simple', c.content, plainto_tsquery('simple', query_text), 'MaxWords=50, MinWords=20') AS headline
    FROM chunks c
    WHERE to_tsvector('simple', c.content) @@ plainto_tsquery('simple', query_text)
    ORDER BY rank DESC
    LIMIT limit_count;
$$;
