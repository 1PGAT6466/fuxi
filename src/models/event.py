"""
event.py — SAG 式事件模型
从碎片中提取的结构化事项
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class Event:
    """事件 — 从碎片中提取的结构化事项"""

    # === 身份 ===
    event_id: str = ""

    # === 内容 ===
    title: str = ""
    summary: str = ""
    content: str = ""
    category: str = ""
    keywords: List[str] = field(default_factory=list)
    priority: str = "UNKNOWN"
    status: str = "UNKNOWN"

    # === SAG 核心：层级关系 ===
    parent_event_id: str = ""
    level: int = 0
    children: List[str] = field(default_factory=list)

    # === SAG 核心：关联 ===
    chunk_ids: List[str] = field(default_factory=list)
    entity_names: List[str] = field(default_factory=list)

    # === SAG 核心：引用 ===
    references: List[int] = field(default_factory=list)

    # === 向量 ===
    embedding: Optional[List[float]] = None

    # === 来源 ===
    file_hash: str = ""
    file_name: str = ""
    source_pipeline: str = ""
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "title": self.title,
            "summary": self.summary,
            "content": self.content,
            "category": self.category,
            "keywords": self.keywords,
            "priority": self.priority,
            "status": self.status,
            "parent_event_id": self.parent_event_id,
            "level": self.level,
            "children": self.children,
            "chunk_ids": self.chunk_ids,
            "entity_names": self.entity_names,
            "references": self.references,
            "file_hash": self.file_hash,
            "file_name": self.file_name,
            "source_pipeline": self.source_pipeline,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Event":
        return cls(
            event_id=d.get("event_id", ""),
            title=d.get("title", ""),
            summary=d.get("summary", ""),
            content=d.get("content", ""),
            category=d.get("category", ""),
            keywords=d.get("keywords", []),
            priority=d.get("priority", "UNKNOWN"),
            status=d.get("status", "UNKNOWN"),
            parent_event_id=d.get("parent_event_id", ""),
            level=d.get("level", 0),
            children=d.get("children", []),
            chunk_ids=d.get("chunk_ids", []),
            entity_names=d.get("entity_names", []),
            references=d.get("references", []),
            file_hash=d.get("file_hash", ""),
            file_name=d.get("file_name", ""),
            source_pipeline=d.get("source_pipeline", ""),
            created_at=d.get("created_at", ""),
        )
