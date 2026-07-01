# 兼容层 - WorldTree路由
from fastapi import APIRouter

router = APIRouter(tags=["WorldTree"])

@router.get("/api/worldtree/stats")
async def worldtree_stats():
    """WorldTree统计"""
    return {"wiki_pages": 0, "entities": 0, "terms": 0}

@router.get("/api/worldtree/wiki/tree")
async def worldtree_wiki_tree():
    """Wiki树"""
    return {"tree": []}

@router.get("/api/worldtree/entities")
async def worldtree_entities():
    """实体列表"""
    return {"entities": []}
