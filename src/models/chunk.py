"""
chunk.py — 全系统唯一的 Chunk 数据模型
基于周天大阵方案 + 实际代码字段补全
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class ChunkType(Enum):
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"
    CODE = "code"
    MIXED = "mixed"
    SUMMARY = "summary"


class ContentType(Enum):
    ARTICLE = "article"
    CHAT = "chat"
    CONFIG = "config"
    SPREADSHEET = "spreadsheet"


@dataclass
class Chunk:
    """全系统唯一的 Chunk 数据模型"""

    # === 身份 ===
    chunk_id: str = ""
    file_hash: str = ""
    file_name: str = ""
    chunk_index: int = 0
    total_chunks: int = 0

    # === 内容 ===
    text: str = ""
    chunk_type: ChunkType = ChunkType.TEXT
    content_type: ContentType = ContentType.ARTICLE

    # === 结构化数据 ===
    structured_table: Optional[Dict] = None
    image_path: Optional[str] = None
    image_description: Optional[str] = None
    images: List[str] = field(default_factory=list)

    # === 元数据 ===
    category: str = ""
    sub_cat: str = ""
    heading: str = ""
    section_path: str = ""
    page_number: int = 0
    file_type: str = ""
    file_size_kb: float = 0
    tags: List[str] = field(default_factory=list)

    # === 质量控制 ===
    trust: str = "unverified"
    audit_note: str = ""

    # === 父子分块 ===
    chunk_type_label: str = ""
    parent_idx: Optional[int] = None
    parent_context: str = ""
    parent_section: str = ""

    # === 向量 ===
    embedding: Optional[List[float]] = None

    # === 来源追踪 ===
    source_pipeline: str = ""
    source_machine: str = ""
    source_file: str = ""
    created_at: str = ""

    # === SAG 扩展 ===
    previous_heading: str = ""
    previous_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 dict（兼容现有代码）"""
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "file_hash": self.file_hash,
            "file_name": self.file_name,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "chunk_type": self.chunk_type.value,
            "category": self.category,
            "sub_cat": self.sub_cat,
            "heading": self.heading,
            "section_path": self.section_path,
            "page_number": self.page_number,
            "file_type": self.file_type,
            "file_size_kb": self.file_size_kb,
            "tags": self.tags,
            "trust": self.trust,
            "audit_note": self.audit_note,
            "structured_table": self.structured_table,
            "images": self.images,
            "source_pipeline": self.source_pipeline,
            "source_file": self.source_file,
            "created_at": self.created_at,
            "previous_heading": self.previous_heading,
            "previous_summary": self.previous_summary,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Chunk":
        """从 dict 反序列化（兼容现有数据）"""
        chunk_type = ChunkType.TEXT
        try:
            chunk_type = ChunkType(d.get("chunk_type", "text"))
        except ValueError as e:
            pass  # 静默：ValueError 失败不影响主流程

        return cls(
            chunk_id=d.get("chunk_id", d.get("file_hash", "") + ":" + str(d.get("chunk_index", 0))),
            text=d.get("text", ""),
            file_hash=d.get("file_hash", ""),
            file_name=d.get("file_name", ""),
            chunk_index=d.get("chunk_index", 0),
            total_chunks=d.get("total_chunks", 0),
            chunk_type=chunk_type,
            category=d.get("category", ""),
            sub_cat=d.get("sub_cat", ""),
            heading=d.get("heading", ""),
            section_path=d.get("section_path", ""),
            page_number=d.get("page_number", 0),
            file_type=d.get("file_type", ""),
            file_size_kb=d.get("file_size_kb", 0),
            tags=d.get("tags", []),
            trust=d.get("trust", "unverified"),
            audit_note=d.get("audit_note", ""),
            structured_table=d.get("structured_table"),
            images=d.get("images", []),
            source_pipeline=d.get("source_pipeline", ""),
            source_file=d.get("source_file", d.get("file_name", "")),
            created_at=d.get("created_at", ""),
            previous_heading=d.get("previous_heading", ""),
            previous_summary=d.get("previous_summary", ""),
        )

    def validate(self) -> bool:
        """验证数据完整性"""
        if not self.text:
            return False
        if not self.file_hash and not self.chunk_id:
            return False
        return True
