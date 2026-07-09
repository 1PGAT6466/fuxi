# -*- coding: utf-8 -*-
"""
graph.py — 知识图谱 API 路由

伏羲 v1.50 Phase B: Self-Wiring Knowledge Graph
提供自动图谱边查询和统计 API。
"""

from fastapi import APIRouter, Query, Request, HTTPException

router = APIRouter(tags=["知识图谱"])


# ============================================================================
# 兼容原有端点
# ============================================================================

@router.get("/api/graph")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def graph(entity: str = Query(""), request: Request = None):
    """知识图谱查询 — 兼容原有 API"""
    from src.db.data_store import load_graph
    try:
        data = load_graph()
        nodes = data.get("nodes", {})
        edges = data.get("edges", [])
        _wants_v2 = request and (request.query_params.get("format") == "v2" or
                                 request.headers.get("X-API-Format", "").lower() == "v2")
        if entity:
            filtered_nodes = {k: v for k, v in nodes.items() if entity.lower() in k.lower()}
            result = {"nodes": filtered_nodes, "edges": edges}
        else:
            result = {"nodes": nodes, "edges": edges}
        if _wants_v2:
            from src.api.response import success
            return success(data=result, message="知识图谱数据")
        return result
    except Exception as e:  # TODO: Narrow exception type
        result = {"nodes": {}, "edges": [], "error": str(e)}
        _wants_v2 = request and (request.query_params.get("format") == "v2" or
                                 request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import error
            return error("知识图谱查询失败", status_code=500, detail=str(e))
        return result


# ============================================================================
# v1.50 Phase B: 自动图谱 API
# ============================================================================

@router.get("/api/graph/auto-edges")
# FAKE-ASYNC
async def auto_edges(
    doc_id: str = Query("", description="文档 ID"),
    source: str = Query("", description="按源实体过滤"),
    target: str = Query("", description="按目标实体过滤"),
    edge_type: str = Query("", description="按边类型过滤"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0, description="最小置信度"),
    limit: int = Query(100, ge=1, le=500, description="返回上限"),
    request: Request = None,
):
    """查询自动提取的知识图谱边
    
    可按 doc_id / source / target / edge_type / min_confidence 过滤。
    内部读取 knowledge_graph.json 中标记为 auto 的边。
    
    Args:
        doc_id:          文档 ID（按来源过滤）
        source:          源实体名（模糊匹配）
        target:          目标实体名（模糊匹配）
        edge_type:       边类型（works_at, invested_in, supplied_by, ...）
        min_confidence:  最低置信度阈值
        limit:           最大返回数
    """
    try:
        from src.config import GRAPH_PATH
        import json
        import os

        edges = []
        if os.path.exists(GRAPH_PATH):
            with open(GRAPH_PATH, "r", encoding="utf-8") as f:
                kg_data = json.load(f)
                edges = list(kg_data.get("edges", []))

        # 过滤
        filtered = []
        for edge in edges:
            # doc_id 过滤
            edge_doc = edge.get("source_doc", "") or edge.get("doc_id", "")
            if doc_id and edge_doc != doc_id:
                # 也尝试短 ID 匹配
                if not (edge_doc.startswith(doc_id[:8]) if len(doc_id) >= 8 else False):
                    continue
            
            # source 过滤
            if source and source.lower() not in edge.get("from", edge.get("source", "")).lower():
                continue
            
            # target 过滤
            if target and target.lower() not in edge.get("to", edge.get("target", "")).lower():
                continue
            
            # edge_type 过滤
            if edge_type:
                edge_relation = edge.get("relation", edge.get("type", ""))
                if edge_type.lower() not in edge_relation.lower():
                    continue
            
            # confidence 过滤
            edge_confidence = float(edge.get("confidence", edge.get("weight", 1.0)))
            if edge_confidence < min_confidence:
                continue
            
            # 标准化输出格式
            filtered.append({
                "source": edge.get("from", edge.get("source", "")),
                "target": edge.get("to", edge.get("target", "")),
                "type": edge.get("relation", edge.get("type", "related_to")),
                "confidence": edge_confidence,
                "doc_id": edge_doc,
                "evidence": edge.get("description", edge.get("evidence", "")),
            })

        total = len(filtered)
        filtered = filtered[:limit]

        _wants_v2 = request and (request.query_params.get("format") == "v2" or
                                 request.headers.get("X-API-Format", "").lower() == "v2")
        result = {"total": total, "limit": limit, "edges": filtered}
        if _wants_v2:
            from src.api.response import success
            return success(data=result, message="自动图谱边查询")
        return result

    except Exception as e:  # TODO: Narrow exception type
        _wants_v2 = request and (request.query_params.get("format") == "v2" or
                                 request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import error
            return error("自动图谱边查询失败", status_code=500, detail=str(e))
        return {"error": str(e), "edges": []}


@router.get("/api/graph/stats")
# FAKE-ASYNC
async def graph_stats(request: Request = None):
    """知识图谱统计
    
    返回：
      - nodes_count:     节点总数
      - edges_count:     边总数
      - edge_type_dist:  边类型分布
      - entity_type_dist: 实体类型分布
      - auto_graph:       自动图谱构建器统计
      - llm_calls:        LLM 调用数（应为 0）
    """
    try:
        from src.config import GRAPH_PATH
        from src.bagua.auto_graph import get_auto_graph_builder
        import json
        import os
        from collections import Counter

        # 读取知识图谱
        nodes_count = 0
        edges_count = 0
        edge_type_dist: dict = {}
        entity_type_dist: dict = {}
        recent_edges: list = []

        if os.path.exists(GRAPH_PATH):
            with open(GRAPH_PATH, "r", encoding="utf-8") as f:
                kg_data = json.load(f)
                nodes = kg_data.get("nodes", kg_data.get("entities", {}))
                nodes_count = len(nodes)
                
                # 实体类型分布
                if isinstance(nodes, dict):
                    types = [n.get("type", "unknown") for n in nodes.values() if isinstance(n, dict)]
                    entity_type_dist = dict(Counter(types))
                
                edges = list(kg_data.get("edges", []))
                edges_count = len(edges)
                
                # 边类型分布
                edge_types = [e.get("relation", e.get("type", "related_to")) for e in edges]
                edge_type_dist = dict(Counter(edge_types))
                
                # 最近 20 条边
                recent_edges = edges[-20:]
        
        # 自动图谱构建器统计
        builder = get_auto_graph_builder()
        builder_stats = builder.get_stats()

        _wants_v2 = request and (request.query_params.get("format") == "v2" or
                                 request.headers.get("X-API-Format", "").lower() == "v2")
        result = {
            "nodes_count": nodes_count,
            "edges_count": edges_count,
            "edge_type_distribution": edge_type_dist,
            "entity_type_distribution": entity_type_dist,
            "recent_edges": recent_edges,
            "auto_graph_builder": builder_stats,
        }

        if _wants_v2:
            from src.api.response import success
            return success(data=result, message="图谱统计")
        return result

    except Exception as e:  # TODO: Narrow exception type
        _wants_v2 = request and (request.query_params.get("format") == "v2" or
                                 request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import error
            return error("图谱统计查询失败", status_code=500, detail=str(e))
        return {"error": str(e)}


@router.post("/api/graph/rebuild-auto")
# FAKE-ASYNC
async def rebuild_auto(doc_id: str = Query(..., description="要重建图谱的文档 ID"),
                       request: Request = None):
    """对指定文档重新执行自动图谱构建
    
    可用于文档内容更新后重建实体和边。
    完全是零 LLM 调用。
    """
    try:
        # 尝试从坤卦获取文档内容
        from src.bagua.kun import KunGua
        
        # 尝试从 chunks.db 读取
        from src.db.memory_store import get_store
        store = get_store()
        chunks = store.get_by_hash(doc_id)
        
        # 如果没有精确匹配，尝试从坤卦 wiki_store 读取
        content = ""
        if chunks:
            content = "\n\n".join(c.get("text", "") for c in chunks)
        else:
            # 尝试坤卦内存缓存
            try:
                from src.services.uni import get_module
                kun = get_module("kun")
                if kun:
                    page = kun.get_page(doc_id)
                    if page:
                        content = page.get("content", "")
                    else:
                        # 尝试 short hash
                        for wiki_id, wiki_page in kun._wiki_store.items():
                            if wiki_id.startswith(doc_id[:8]):
                                content = wiki_page.get("content", "")
                                doc_id = wiki_id
                                break
            except Exception:  # TODO: Narrow exception type
                pass
        
        if not content:
            _wants_v2 = request and (request.query_params.get("format") == "v2" or
                                     request.headers.get("X-API-Format", "").lower() == "v2")
            if _wants_v2:
                from src.api.response import error
                return error("未找到文档内容", status_code=404, detail=f"doc_id={doc_id}")
            raise HTTPException(status_code=404, detail=f"未找到文档内容: {doc_id}")
        
        # 执行自动图谱构建
        from src.bagua.auto_graph import get_auto_graph_builder
        builder = get_auto_graph_builder()
        graph_data = builder.build_full_graph(content, doc_id)
        
        # 写入存储
        from src.bagua.kun import KunGua
        
        # 创建临时坤卦实例写入
        temp_kun = KunGua()
        temp_kun.start()
        store_result = temp_kun.store_graph(
            entities=graph_data["entities"],
            relations=graph_data["edges"],
            doc_id=doc_id,
        )
        temp_kun.stop()
        
        _wants_v2 = request and (request.query_params.get("format") == "v2" or
                                 request.headers.get("X-API-Format", "").lower() == "v2")
        result = {
            "ok": True,
            "doc_id": doc_id,
            "entity_count": graph_data["stats"]["entity_count"],
            "edge_count": graph_data["stats"]["edge_count"],
            "graph_stored": store_result.get("ok", False),
            "llm_calls": 0,
        }
        if _wants_v2:
            from src.api.response import success
            return success(data=result, message="图谱重建完成")
        return result

    except HTTPException:
        raise
    except Exception as e:  # TODO: Narrow exception type
        _wants_v2 = request and (request.query_params.get("format") == "v2" or
                                 request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import error
            return error("图谱重建失败", status_code=500, detail=str(e))
        return {"ok": False, "error": str(e)}
