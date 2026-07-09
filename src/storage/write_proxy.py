"""
伏羲 RAG 4.0 — WriteProxy 双写机制
=====================================
同时写入 ChromaDB（向量主力）+ PostgreSQL（结构化/SQL JOIN）

设计原则:
- 任一方失败不影响另一方（独立 try/except）
- PG 不可用时自动降级为仅 ChromaDB
- 支持同步/异步批量写入

数据流:
    chunk + event + entity
        ├─ ChromaDB: chunk embedding → chroma_collection
        └─ PostgreSQL: chunk + event + entity + 关联 → pg_tables

性能优化 (Round 1 审计):
- FIX-10: pending_pg 队列上限 MAX_PENDING_PG=500，超限 FIFO 淘汰 + CRITICAL 告警
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# ===== pending 队列上限 =====
MAX_PENDING_PG = 500  # 防止 OOM


@dataclass
class ChunkData:
    chunk_id: str
    document_id: str
    document_name: str
    content: str
    chunk_index: int = 0
    token_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None


@dataclass
class EventData:
    event_id: str
    chunk_id: str
    content: str
    event_type: str = "general"
    entities_json: List[Dict] = field(default_factory=list)
    confidence: float = 0.0
    status: str = "active"
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None


@dataclass
class EntityData:
    entity_id: str
    name: str
    normalized_name: str
    type: str
    aliases: List[str] = field(default_factory=list)
    chunk_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None


@dataclass
class EventEntityLink:
    event_id: str
    entity_id: str
    role: Optional[str] = None
    confidence: float = 1.0


class WriteProxy:
    """双写代理：同时写入 ChromaDB 和 PostgreSQL"""

    def __init__(self, chroma_client=None, pg_conn=None):
        self.chroma = chroma_client
        self.pg = pg_conn
        self._chroma_ok = True
        self._pg_ok = True
        self._pending_pg: List[Dict] = []
        self._pending_dropped = 0  # 已丢弃的累计数量

    # ========================================================================
    # 公开 API
    # ========================================================================

    async def write(
        self,
        chunk: ChunkData,
        events: List[EventData] = None,
        entities: List[EntityData] = None,
        links: List[EventEntityLink] = None,
    ) -> Dict[str, Any]:
        """核心写入入口。所有数据同时双写。"""
        result = {"chroma": {}, "pg": None, "errors": []}

        await self._write_chroma(chunk, events or [], result)
        pg_ok = await self._write_pg(chunk, events or [], entities or [], links or [], result)

        if not pg_ok:
            # FIX-10: pending 队列上限控制
            if len(self._pending_pg) >= MAX_PENDING_PG:
                discarded = self._pending_pg.pop(0)  # FIFO 淘汰最旧的
                self._pending_dropped += 1
                logger.critical(
                    f"[WriteProxy] ⚠️  pending 队列已满({MAX_PENDING_PG})，丢弃最旧条目！"
                    f"  累计丢弃: {self._pending_dropped}"
                )

            self._pending_pg.append({
                "chunk": chunk,
                "events": events,
                "entities": entities,
                "links": links,
                "queued_at": datetime.utcnow().isoformat(),
            })
            logger.warning(
                f"[WriteProxy] PG 不可用，{len(self._pending_pg)}/{MAX_PENDING_PG} 条待回放"
            )

        return result

    async def write_batch(
        self,
        chunks: List[ChunkData],
        events: List[EventData] = None,
        entities: List[EntityData] = None,
        links: List[EventEntityLink] = None,
    ) -> Dict[str, Any]:
        """批量写入"""
        results = {
            "chroma": {"chunks": 0, "events": 0, "failures": 0},
            "pg": None, "errors": [],
        }

        for chunk in chunks:
            chunk_events = [e for e in (events or []) if e.chunk_id == chunk.chunk_id]
            r = await self.write(
                chunk=chunk, events=chunk_events or None,
                entities=entities, links=links,
            )
            if r["chroma"].get("ok"):
                results["chroma"]["chunks"] += 1
                results["chroma"]["events"] += r["chroma"].get("events_count", 0)
            else:
                results["chroma"]["failures"] += 1
            results["errors"].extend(r.get("errors", []))

        if self._pg_ok:
            results["pg"] = "ok"
        elif self._pending_pg:
            results["pg"] = f"queued ({len(self._pending_pg)})"

        return results

    async def replay_pending(self) -> int:
        """重放 PG 故障期间的积压数据"""
        if not self._pg_ok or not self.pg:
            return 0

        replayed = 0
        still_pending = []

        for item in self._pending_pg:
            try:
                await self._write_pg_batch(
                    [item["chunk"]], item.get("events") or [],
                    item.get("entities") or [], item.get("links") or [],
                )
                replayed += 1
            except Exception as e:  # TODO: Narrow exception type
                still_pending.append(item)
                logger.error(f"[WriteProxy] 回放失败: {e}")

        self._pending_pg = still_pending
        logger.info(f"[WriteProxy] 回放: {replayed} 成功, {len(still_pending)} 仍待处理")
        return replayed

    # ========================================================================
    # 内部实现
    # ========================================================================

    async def _write_chroma(self, chunk: ChunkData, events: List[EventData], result: Dict):
        try:
            if self.chroma and self._chroma_ok:
                metadata = {
                    "document_id": chunk.document_id,
                    "document_name": chunk.document_name,
                    "chunk_index": chunk.chunk_index,
                    "token_count": chunk.token_count,
                    **chunk.metadata,
                }
                emb = chunk.embedding or self._dummy_embedding()
                self.chroma.add(
                    ids=[chunk.chunk_id], embeddings=[emb],
                    documents=[chunk.content], metadatas=[metadata],
                )

                events_count = 0
                if events and hasattr(self.chroma, "event_collection"):
                    for evt in events:
                        self.chroma.event_collection.add(
                            ids=[evt.event_id],
                            embeddings=[evt.embedding or self._dummy_embedding()],
                            documents=[evt.content],
                            metadatas=[{
                                "chunk_id": evt.chunk_id,
                                "event_type": evt.event_type,
                                "confidence": evt.confidence,
                            }],
                        )
                        events_count += 1

                result["chroma"] = {"ok": True, "events_count": events_count}
            else:
                result["chroma"] = {"ok": None, "reason": "chroma not available"}
        except Exception as e:  # TODO: Narrow exception type
            self._chroma_ok = False
            result["chroma"] = {"ok": False, "error": str(e)}
            result["errors"].append(f"ChromaDB write failed: {e}")
            logger.error(f"[WriteProxy] ChromaDB 写入失败: {e}")

    async def _write_pg(
        self, chunk: ChunkData, events: List[EventData],
        entities: List[EntityData], links: List[EventEntityLink], result: Dict,
    ) -> bool:
        if not self.pg or not self._pg_ok:
            result["pg"] = "skipped (pg not available)"
            return False
        return await self._write_pg_batch([chunk], events, entities, links)

    async def _write_pg_batch(
        self, chunks: List[ChunkData], events: List[EventData],
        entities: List[EntityData], links: List[EventEntityLink],
    ) -> bool:
        import json
        try:
            cur = self.pg.cursor()
            for c in chunks:
                emb_str = self._embedding_to_str(c.embedding) if c.embedding else None
                cur.execute(
                    """INSERT INTO chunks (chunk_id, document_id, document_name, content,
                       chunk_index, token_count, metadata, embedding)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (chunk_id) DO UPDATE SET content=EXCLUDED.content, updated_at=now()""",
                    (c.chunk_id, c.document_id, c.document_name, c.content,
                     c.chunk_index, c.token_count, json.dumps(c.metadata), emb_str),
                )
            for e in events:
                emb_str = self._embedding_to_str(e.embedding) if e.embedding else None
                cur.execute(
                    """INSERT INTO events (event_id, chunk_id, content, event_type,
                       entities_json, confidence, status, metadata, embedding)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (event_id) DO UPDATE SET content=EXCLUDED.content, updated_at=now()""",
                    (e.event_id, e.chunk_id, e.content, e.event_type,
                     json.dumps(e.entities_json), e.confidence, e.status,
                     json.dumps(e.metadata), emb_str),
                )
            for ent in entities:
                emb_str = self._embedding_to_str(ent.embedding) if ent.embedding else None
                cur.execute(
                    """INSERT INTO entities (entity_id, name, normalized_name, type,
                       aliases_json, chunk_ids_json, metadata, embedding)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (entity_id) DO UPDATE
                       SET aliases_json = entities.aliases_json || EXCLUDED.aliases_json,
                           chunk_ids_json = entities.chunk_ids_json || EXCLUDED.chunk_ids_json,
                           updated_at = now()""",
                    (ent.entity_id, ent.name, ent.normalized_name, ent.type,
                     json.dumps(ent.aliases), json.dumps(ent.chunk_ids),
                     json.dumps(ent.metadata), emb_str),
                )
            for link in links:
                cur.execute(
                    """INSERT INTO event_entities (event_id, entity_id, role, confidence)
                       VALUES (%s,%s,%s,%s)
                       ON CONFLICT (event_id, entity_id) DO NOTHING""",
                    (link.event_id, link.entity_id, link.role, link.confidence),
                )
            self.pg.commit()
            return True
        except Exception as e:  # TODO: Narrow exception type
            self._pg_ok = False
            try:
                self.pg.rollback()
            except Exception:  # TODO: Narrow exception type
                pass
            logger.error(f"[WriteProxy] PostgreSQL 写入失败: {e}")
            return False

    # ========================================================================
    # 工具方法
    # ========================================================================

    @staticmethod
    def _dummy_embedding(dim: int = 768) -> List[float]:
        return [0.0] * dim

    @staticmethod
    def _embedding_to_str(embedding: List[float]) -> str:
        return f"[{','.join(str(x) for x in embedding)}]"

    @property
    def stats(self) -> Dict:
        return {
            "chroma_ok": self._chroma_ok,
            "pg_ok": self._pg_ok,
            "pending_pg": len(self._pending_pg),
            "pending_dropped": self._pending_dropped,
            "pending_limit": MAX_PENDING_PG,
        }
