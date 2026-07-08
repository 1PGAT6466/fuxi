# 兼容层 - WorldTree路由
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WorldTree"])

@router.get("/api/worldtree/stats")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def worldtree_stats(request: Request = None):
    """WorldTree统计"""
    try:
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"wiki_pages": 0, "entities": 0, "terms": 0}, message="WorldTree 统计")
        return {"wiki_pages": 0, "entities": 0, "terms": 0}
    except Exception as e:
        logger.exception(f"worldtree_stats 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})

# ── 任务 B.5: /api/worldtree/terms 实体/术语列表 ──
@router.get("/api/worldtree/terms")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def worldtree_terms(limit: int = Query(2000, ge=1, le=10000), request: Request = None):
    """前端调用的 /api/worldtree/terms — 返回实体/术语列表"""
    try:
        from src.db.data_store import load_chunks
        chunks = load_chunks()
        # 从 chunks 中提取术语/实体（按 file_name 去重）
        seen = set()
        terms = []
        for c in chunks:
            name = c.get("file_name", "")
            if name and name not in seen:
                seen.add(name)
                terms.append({
                    "name": name,
                    "category": c.get("category", ""),
                    "type": "document",
                })
                if len(terms) >= limit:
                    break
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"ok": True, "terms": terms, "total": len(terms)}, message="WorldTree 术语列表")
        return {"ok": True, "terms": terms, "total": len(terms)}
    except Exception as e:
        logger.exception(f"worldtree_terms 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})

@router.get("/api/worldtree/wiki/tree")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def worldtree_wiki_tree(request: Request = None):
    """Wiki树"""
    try:
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"tree": []}, message="WorldTree Wiki 树")
        return {"tree": []}
    except Exception as e:
        logger.exception(f"worldtree_wiki_tree 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})

# ── 任务 B.7: /api/worldtree/wiki 别名 → wiki/tree ──
@router.get("/api/worldtree/wiki")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def worldtree_wiki():
    """前端调用的 /api/worldtree/wiki — 代理到 wiki/tree"""
    return await worldtree_wiki_tree()

@router.get("/api/worldtree/entities")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def worldtree_entities(request: Request = None):
    """实体列表"""
    try:
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"entities": []}, message="WorldTree 实体列表")
        return {"entities": []}
    except Exception as e:
        logger.exception(f"worldtree_entities 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


# ── v1.44 Phase 1 Fix: WorldTree 缺失端点 ──

@router.get("/api/worldtree/wiki/{page_id}")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def worldtree_wiki_by_id(page_id: str, request: Request = None):
    """WorldTree Wiki 页面详情 — 代理到 /api/wiki/page/{page_id}"""
    try:
        from src.taiyang.wiki import get_wiki_engine
        engine = get_wiki_engine()
        page = engine.get_page(page_id)
        if not page:
            return JSONResponse(
                status_code=404,
                content={"error": "页面未找到", "detail": f"Wiki 页面 {page_id} 不存在"}
            )

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data=page, message="获取 Wiki 页面成功")
        return {"ok": True, "page": page}
    except Exception as e:
        logger.exception(f"worldtree_wiki_by_id 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


@router.get("/api/worldtree/entity/{entity_id}/wiki")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def worldtree_entity_wiki(entity_id: str, request: Request = None):
    """WorldTree 实体关联 Wiki — 按实体名查找关联的 Wiki 页面"""
    try:
        from src.taiyang.wiki import get_wiki_engine
        engine = get_wiki_engine()
        # 按实体名搜索 Wiki 页面
        pages = engine.search_by_title(entity_id, limit=5)
        if not pages:
            pages = engine.search_content(entity_id, limit=5)

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"entity_id": entity_id, "wiki_pages": pages, "total": len(pages)}, message="获取实体关联 Wiki 成功")
        return {"entity_id": entity_id, "wiki_pages": pages, "total": len(pages)}
    except Exception as e:
        logger.exception(f"worldtree_entity_wiki 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


@router.get("/api/worldtree/relations")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def worldtree_relations(request: Request = None, entity_id: str = "", entity_name: str = ""):
    """WorldTree 关系图数据 — 返回实体间的关系"""
    try:
        # 支持 entity_id 和 entity_name 两个参数名
        entity = entity_id or entity_name
        relations = []
        try:
            from src.db.ontology import get_relevant_relations
            if entity:
                relations = get_relevant_relations(entity, limit=50)
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"get_relevant_relations 失败: {e}")

        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"relations": relations, "total": len(relations)}, message="获取 WorldTree 关系成功")
        return {"relations": relations, "total": len(relations)}
    except Exception as e:
        logger.exception(f"worldtree_relations 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})
