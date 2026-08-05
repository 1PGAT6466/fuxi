"""联网搜索 API 端点"""

from fastapi import APIRouter, Depends, HTTPException
from src.api.auth import require_admin

router = APIRouter()


@router.post("/api/search/web")
async def search_web(query: dict, user=Depends(require_admin)):
    from src.services.web_search import web_search

    q = query.get("query", "")
    if not q:
        raise HTTPException(400, "查询不能为空")
    results = await web_search(q)
    return {"results": [{"title": r.title, "content": r.content, "url": r.url, "score": r.score} for r in results]}
