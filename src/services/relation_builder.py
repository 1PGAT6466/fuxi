"""
relation_builder.py — 实体关系自动构建 (RAG 3.0 v2)
策略升级: 基于共现分析 + LLM 辅助
  1. 快速通道: 从 chunks 文本中匹配已有 entities，共现=关系
  2. LLM 通道: DeepSeek 辅助抽取新实体关系 (限速)
"""
import asyncio
import hashlib
import json
import logging
import sqlite3
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ============ 快速通道: 共现分析 ============

async def extract_relations_cooccurrence(chunks: list) -> list:
    """基于共现: 在同一 chunk 中出现的 entities → 建立关系"""
    try:
        from src.config import WORLDTREE_DB_PATH
        db = sqlite3.connect(str(WORLDTREE_DB_PATH), timeout=10)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=5000")
        entities = db.execute("SELECT id, name, type FROM entities").fetchall()
        entity_names = {r[1]: (r[0], r[2]) for r in entities}
        db.close()
    except Exception:
        return []
    
    if len(entity_names) < 2:
        return []
    
    # 构建 name→id 的快速查找
    relations = []
    seen_pairs = set()
    
    for chunk in chunks:
        text = chunk.get("text", "")
        if len(text) < 30:
            continue
        
        # 找出文本中出现过的所有实体
        found = []
        text_lower = text.lower()
        for name, (eid, etype) in entity_names.items():
            if name.lower() in text_lower:
                found.append((name, eid, etype))
        
        # 两两配对 → 关系
        for i in range(len(found)):
            for j in range(i+1, len(found)):
                name_a, id_a, type_a = found[i]
                name_b, id_b, type_b = found[j]
                
                pair_key = f"{id_a}|{id_b}"
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                
                # 推断关系类型
                rel_type = _infer_relation(name_a, name_b, type_a, type_b, text)
                relations.append({
                    "from_name": name_a, "from_id": id_a,
                    "to_name": name_b, "to_id": id_b,
                    "relation_type": rel_type
                })
    
    return relations


def _infer_relation(name_a: str, name_b: str, type_a: str, type_b: str, text: str) -> str:
    """根据实体类型和文本内容推断关系类型"""
    text_lower = text.lower()
    
    # 关键词匹配
    if any(kw in text_lower for kw in ["供应商", "采购", "supplier", "从", "购买"]):
        return "supplier_of"
    if any(kw in text_lower for kw in ["包含", "组成", "包括", "consists", "contains"]):
        return "contains"
    if any(kw in text_lower for kw in ["替代", "alternative", "替代品"]):
        return "alternative_to"
    if any(kw in text_lower for kw in ["兼容", "compatible"]):
        return "compatible_with"
    if any(kw in text_lower for kw in ["使用", "采用", "选用", "uses"]):
        return "uses"
    if any(kw in text_lower for kw in ["标准", "standard", "DIN", "ISO", "GB"]):
        return "standard_of"
    if any(kw in text_lower for kw in ["零件", "组件", "部件", "part of"]):
        return "part_of"
    
    # 默认
    return "related_to"


async def build_relations_from_chunks(chunks: list, batch_size: int = 50) -> dict:
    """批量构建实体关系"""
    if not chunks:
        return {"extracted": 0, "inserted": 0}
    
    # 快速通道: 共现分析
    relations = await extract_relations_cooccurrence(chunks[:batch_size])
    
    inserted = 0
    if relations:
        try:
            from src.config import WORLDTREE_DB_PATH
            db = sqlite3.connect(str(WORLDTREE_DB_PATH), timeout=10)
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA busy_timeout=5000")
            
            for r in relations:
                try:
                    db.execute(
                        "INSERT OR IGNORE INTO entity_relations (from_id, to_id, relation_type) VALUES (?, ?, ?)",
                        (r["from_id"], r["to_id"], r["relation_type"])
                    )
                    inserted += 1
                except Exception as e:

                    logger.warning(f"[{module}] suppressed exception", exc_info=True)
            db.commit()
            db.close()
            logger.info(f"[RelationBuilder] Extracted {len(relations)} relations (co-occurrence), inserted {inserted}")
        except Exception as e:
            logger.warning(f"[RelationBuilder] DB write failed: {e}")
    
    return {"extracted": len(relations), "inserted": inserted}


def get_relation_stats() -> dict:
    try:
        from src.config import WORLDTREE_DB_PATH
        db = sqlite3.connect(str(WORLDTREE_DB_PATH), timeout=10)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=5000")
        total = db.execute("SELECT COUNT(1) FROM entity_relations").fetchone()[0]
        entities = db.execute("SELECT COUNT(1) FROM entities").fetchone()[0]
        db.close()
        return {"total_relations": total, "total_entities": entities, "density": round(total / max(1, entities), 3)}
    except Exception:
        return {"total_relations": 0, "total_entities": 0, "density": 0}


async def auto_build_relations(limit: int = 100) -> dict:
    try:
        from src.db.data_store import load_chunks
        chunks = load_chunks(limit=limit)
        if not chunks:
            return {"message": "no chunks to process"}
        return await build_relations_from_chunks(chunks, batch_size=min(limit, 100))
    except Exception as e:
        return {"error": str(e)}
