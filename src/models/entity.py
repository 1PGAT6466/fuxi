"""
entity.py — SAG 式实体模型
从碎片和事件中提取的关键概念
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class Entity:
    """实体 — 从碎片和事件中提取的关键概念"""

    # === 身份 ===
    entity_id: str = ""

    # === 内容 ===
    name: str = ""
    entity_type: str = ""
    description: str = ""

    # === SAG 核心：别名归一化 ===
    aliases: List[str] = field(default_factory=list)
    canonical_name: str = ""

    # === 关联 ===
    event_ids: List[str] = field(default_factory=list)
    chunk_ids: List[str] = field(default_factory=list)

    # === 统计 ===
    mentions: int = 1

    # === 向量 ===
    embedding: Optional[List[float]] = None

    # === 来源 ===
    file_hash: str = ""
    file_name: str = ""
    source_pipeline: str = ""
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "entity_type": self.entity_type,
            "description": self.description,
            "aliases": self.aliases,
            "canonical_name": self.canonical_name,
            "event_ids": self.event_ids,
            "chunk_ids": self.chunk_ids,
            "mentions": self.mentions,
            "file_hash": self.file_hash,
            "file_name": self.file_name,
            "source_pipeline": self.source_pipeline,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Entity":
        return cls(
            entity_id=d.get("entity_id", ""),
            name=d.get("name", ""),
            entity_type=d.get("entity_type", ""),
            description=d.get("description", ""),
            aliases=d.get("aliases", []),
            canonical_name=d.get("canonical_name", ""),
            event_ids=d.get("event_ids", []),
            chunk_ids=d.get("chunk_ids", []),
            mentions=d.get("mentions", 1),
            file_hash=d.get("file_hash", ""),
            file_name=d.get("file_name", ""),
            source_pipeline=d.get("source_pipeline", ""),
            created_at=d.get("created_at", ""),
        )
