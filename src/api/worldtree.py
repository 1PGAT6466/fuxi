"""
伏羲 v1.50 — WorldTree 路由（真实数据版）
数据来源：chunks.db + worldtree.db + 知识图谱
"""
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WorldTree"])


@router.get("/api/worldtree/stats")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def worldtree_stats(request: Request = None):
    """WorldTree 统计 — v1.50 真实数据版

    从真实数据库获取：
      - wiki_pages: worldtree.db 中 wiki_pages 表行数
      - entities: 知识图谱节点数
      - terms: chunks 中的唯一文件/术语数
    """
    try:
        wiki_pages_count = 0
        entities_count = 0
        terms_count = 0

        # 1. Wiki 页面数
        try:
            from src.taiyang.wiki import get_wiki_engine
            engine = get_wiki_engine()
            pages = engine.list_pages()
            wiki_pages_count = len(pages) if pages else 0
        except ImportError:
            pass
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"Wiki 查询失败: {e}")

        # 2. 知识图谱实体数
        try:
            from src.taiyang.graph import get_graph_stats
            stats = get_graph_stats()
            entities_count = stats.get("nodes_count", 0)
        except ImportError:
            pass
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"图谱查询失败: {e}")

        # 3. 术语/文件数
        try:
            from src.db.data_store import load_chunks
            chunks = load_chunks() or []
            terms_count = len(set(c.get("file_name", "") for c in chunks if c.get("file_name")))
        except Exception:  # TODO: Narrow exception type
            pass

        data = {
            "wiki_pages": wiki_pages_count,
            "entities": entities_count,
            "terms": terms_count,
            "generated_at": None,  # can add timestamp later
        }

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data=data, message="WorldTree 统计")
        return data
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"worldtree_stats 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


@router.get("/api/worldtree/terms")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def worldtree_terms(limit: int = Query(2000, ge=1, le=10000), request: Request = None):
    """实体/术语列表 — v1.50 真实数据版

    从 chunks.db + Wiki pages + 知识图谱聚合术语。
    """
    try:
        from src.db.data_store import load_chunks
        chunks = load_chunks() or []

        # 从 chunks 中提取术语（按 file_name 去重）
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
                    "source": "chunks_db",
                })
                if len(terms) >= limit:
                    break

        # 补充 Wiki 页面标题
        if len(terms) < limit:
            try:
                from src.taiyang.wiki import get_wiki_engine
                engine = get_wiki_engine()
                pages = engine.list_pages() or []
                for p in pages:
                    title = p.get("title", "")
                    if title and title not in seen:
                        seen.add(title)
                        terms.append({
                            "name": title,
                            "category": p.get("category", "wiki"),
                            "type": "wiki_page",
                            "source": "worldtree_db",
                        })
                        if len(terms) >= limit:
                            break
            except ImportError:
                pass
            except Exception as e:  # TODO: Narrow exception type
                logger.warning(f"Wiki 术语补充失败: {e}")

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data={"ok": True, "terms": terms, "total": len(terms)}, message="WorldTree 术语列表")
        return {"ok": True, "terms": terms, "total": len(terms)}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"worldtree_terms 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


@router.get("/api/worldtree/wiki/tree")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def worldtree_wiki_tree(request: Request = None):
    """Wiki 树 — v1.50 真实数据版

    从 worldtree.db 读取 Wiki 页面，按 category 构建树形结构。
    如果无数据，返回空 tree + 引导信息。
    """
    try:
        tree = []
        hint = None

        try:
            from src.taiyang.wiki import get_wiki_engine
            engine = get_wiki_engine()
            pages = engine.list_pages() or []

            # 按 category 分组构建树
            category_groups = {}
            for p in pages:
                cat = p.get("category", "未分类")
                if cat not in category_groups:
                    category_groups[cat] = []
                category_groups[cat].append({
                    "id": p.get("id", ""),
                    "title": p.get("title", ""),
                    "summary": p.get("summary", "")[:100] if p.get("summary") else "",
                    "quality_score": p.get("quality_score"),
                })

            for cat, items in category_groups.items():
                tree.append({
                    "category": cat,
                    "count": len(items),
                    "pages": items,
                })
        except ImportError:
            tree = []
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"Wiki 树构建失败: {e}")

        if not tree:
            hint = (
                "暂无 Wiki 页面。通过知识库上传文档后，系统会自动生成 Wiki 页面，"
                "也可以手动创建：POST /api/wiki"
            )

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data={"tree": tree, "hint": hint}, message="WorldTree Wiki 树")
        return {"tree": tree, "hint": hint}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"worldtree_wiki_tree 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


@router.get("/api/worldtree/wiki")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def worldtree_wiki():
    """前端调用的 /api/worldtree/wiki — 代理到 wiki/tree"""
    return await worldtree_wiki_tree()


@router.get("/api/worldtree/entities")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def worldtree_entities(request: Request = None):
    """实体列表 — v1.50 真实数据版

    从知识图谱获取所有实体节点。
    """
    try:
        entities = []
        try:
            from src.taiyang.graph import get_graph_stats
            stats = get_graph_stats()
            # 获取实际实体列表
            try:
                from src.taiyang.graph import get_all_nodes
                entities = get_all_nodes() or []
            except (ImportError, AttributeError):
                # fallback: 从 knowledge_graph.json 读取
                import json
                kg_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "data", "knowledge_graph.json",
                )
                if os.path.exists(kg_path):
                    with open(kg_path, "r", encoding="utf-8") as f:
                        kg_data = json.load(f)
                    entities = [
                        {"name": n, "type": n.get("type", "entity") if isinstance(n, dict) else "entity"}
                        for n in kg_data.get("nodes", [])
                    ]
        except ImportError:
            pass
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"图谱实体查询失败: {e}")

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data={"entities": entities, "total": len(entities)}, message="WorldTree 实体列表")
        return {"entities": entities, "total": len(entities)}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"worldtree_entities 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


@router.get("/api/worldtree/wiki/{page_id}")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def worldtree_wiki_by_id(page_id: str, request: Request = None):
    """WorldTree Wiki 页面详情"""
    try:
        from src.taiyang.wiki import get_wiki_engine
        engine = get_wiki_engine()
        page = engine.get_page(page_id)
        if not page:
            return JSONResponse(
                status_code=404,
                content={"error": "页面未找到", "detail": f"Wiki 页面 {page_id} 不存在"}
            )

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data=page, message="获取 Wiki 页面成功")
        return {"ok": True, "page": page}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"worldtree_wiki_by_id 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


@router.get("/api/worldtree/entity/{entity_id}/wiki")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def worldtree_entity_wiki(entity_id: str, request: Request = None):
    """WorldTree 实体关联 Wiki"""
    try:
        from src.taiyang.wiki import get_wiki_engine
        engine = get_wiki_engine()
        pages = engine.search_by_title(entity_id, limit=5)
        if not pages:
            pages = engine.search_content(entity_id, limit=5)

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data={"entity_id": entity_id, "wiki_pages": pages, "total": len(pages)}, message="获取实体关联 Wiki 成功")
        return {"entity_id": entity_id, "wiki_pages": pages, "total": len(pages)}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"worldtree_entity_wiki 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


@router.get("/api/worldtree/relations")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def worldtree_relations(request: Request = None, entity_id: str = "", entity_name: str = ""):
    """WorldTree 关系图数据"""
    try:
        entity = entity_id or entity_name
        relations = []
        try:
            from src.db.ontology import get_relevant_relations
            if entity:
                relations = get_relevant_relations(entity, limit=50)
            else:
                # 返回所有关系
                import json
                kg_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "data", "knowledge_graph.json",
                )
                if os.path.exists(kg_path):
                    with open(kg_path, "r", encoding="utf-8") as f:
                        kg_data = json.load(f)
                    relations = kg_data.get("edges", [])
        except ImportError:
            pass
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(f"get_relevant_relations 失败: {e}")

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data={"relations": relations, "total": len(relations)}, message="获取 WorldTree 关系成功")
        return {"relations": relations, "total": len(relations)}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"worldtree_relations 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )
