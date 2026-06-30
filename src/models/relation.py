"""
relation.py — 三层关系模型
碎片↔事件↔实体 的关联
"""
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class Relation:
    """关系 — 碎片↔事件↔实体 的关联"""

    relation_id: str = ""
    source_type: str = ""
    source_id: str = ""
    target_type: str = ""
    target_id: str = ""
    relation_type: str = ""
    weight: float = 1.0
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "weight": self.weight,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Relation":
        return cls(
            relation_id=d.get("relation_id", ""),
            source_type=d.get("source_type", ""),
            source_id=d.get("source_id", ""),
            target_type=d.get("target_type", ""),
            target_id=d.get("target_id", ""),
            relation_type=d.get("relation_type", ""),
            weight=d.get("weight", 1.0),
            created_at=d.get("created_at", ""),
        )
