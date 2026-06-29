"""
routers/worldtree.py — WorldTree 1.0 前端 API (v4 — 接入 lib.db)
从 worldtree.db 读取 Wiki树 + 实体 + 术语 + 关系
"""
from fastapi import APIRouter, HTTPException, Query
from src.core.db import connect, count_worldtree, get_wiki_tree, get_wiki_pages, get_knowledge_graph
import json

router = APIRouter(prefix="/api/worldtree", tags=["worldtree"])

# ========== Wiki 四级树 ==========
@router.get("/wiki/tree")
async def wiki_tree():
    with connect("worldtree") as db:
        rows = db.execute(
            "SELECT id, title, summary, category_path, quality_score, updated_at "
            "FROM wiki_pages ORDER BY category_path, title"
        ).fetchall()
    
    if not rows:
        return {"tree": [], "total": 0, "version": "worldtree-v4"}
    
    tree = {}
    for r in rows:
        parts = r["category_path"].split(" > ")
        cur = tree
        for p in parts:
            if p not in cur:
                cur[p] = {"_children": {}, "_count": 0, "name": p}
            cur[p]["_count"] += 1
            cur = cur[p]["_children"]
    
    def build_node(name, node):
        children = [build_node(k, v) for k, v in node.get("_children", {}).items()]
        return {
            "name": name,
            "count": node["_count"],
            "children": sorted(children, key=lambda x: -x["count"]) if children else []
        }
    
    root = [build_node(k, v) for k, v in sorted(tree.items(), key=lambda x: -x[1]["_count"])]
    return {"tree": root, "total": len(rows), "version": "worldtree-v4"}

# ========== Wiki 页面详情 ==========
@router.get("/wiki/{wiki_id}")
async def wiki_page(wiki_id: str):
    with connect("worldtree") as db:
        row = db.execute(
            "SELECT id, title, summary, content, category_path, quality_score, created_at, updated_at "
            "FROM wiki_pages WHERE id=?", (wiki_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, "Wiki page not found")
    return dict(row)

# ========== 实体列表 ==========
@router.get("/entities")
async def entities(limit: int = Query(500, ge=1, le=5000)):
    with connect("worldtree") as db:
        rows = db.execute(
            "SELECT id, name, type, category_path, mentions, created_at "
            "FROM entities ORDER BY mentions DESC, created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]

# ========== 实体关系 ==========
@router.get("/relations")
async def relations(entity_id: str = Query("")):
    with connect("worldtree") as db:
        if entity_id:
            rows = db.execute(
                "SELECT e1.name as from_name, e2.name as to_name, er.relation_type "
                "FROM entity_relations er "
                "LEFT JOIN entities e1 ON er.from_id=e1.id "
                "LEFT JOIN entities e2 ON er.to_id=e2.id "
                "WHERE er.from_id=? OR er.to_id=?", (entity_id, entity_id)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT e1.name as from_name, e2.name as to_name, er.relation_type "
                "FROM entity_relations er "
                "LEFT JOIN entities e1 ON er.from_id=e1.id "
                "LEFT JOIN entities e2 ON er.to_id=e2.id LIMIT 200"
            ).fetchall()
    return {"entity_id": entity_id, "relations": [dict(r) for r in rows]}

# ========== 实体关联 Wiki ==========
@router.get("/entity/{entity_id}/wiki")
async def entity_wiki(entity_id: str):
    with connect("worldtree") as db:
        rows = db.execute(
            "SELECT w.id, w.title, w.summary, w.category_path "
            "FROM wiki_entity_links we JOIN wiki_pages w ON we.wiki_id=w.id "
            "WHERE we.entity_id=?", (entity_id,)
        ).fetchall()
    return {"entity_id": entity_id, "wiki_pages": [dict(r) for r in rows]}

# ========== 术语 ==========
@router.get("/terms")
async def terms(limit: int = Query(2000, ge=1, le=10000)):
    with connect("worldtree") as db:
        rows = db.execute(
            "SELECT id, term, definition, category, created_at FROM terms ORDER BY term LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]

# ========== 统计 ==========
@router.get("/stats")
async def stats():
    return count_worldtree()
