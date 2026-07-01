# 兼容层 - Wiki路由
from fastapi import APIRouter, Query

router = APIRouter(tags=["Wiki"])

@router.get("/api/wiki/pages")
async def wiki_pages():
    """Wiki页面列表"""
    return {"pages": [], "total": 0}

@router.get("/api/wiki/search")
async def wiki_search(q: str = Query("")):
    """Wiki搜索"""
    return {"pages": [], "total": 0}

@router.get("/api/wiki/page/{page_id}")
async def wiki_page(page_id: str):
    """Wiki页面详情"""
    return {"id": page_id, "title": "", "content": ""}
