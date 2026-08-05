# -*- coding: utf-8 -*-
"""
graph.py — 知识图谱 API 路由

伏羲 v1.50 Phase B: Self-Wiring Knowledge Graph
提供自动图谱边查询和统计 API。

端点清单：
  - /api/graph                — 知识图谱查询（兼容原有 API）
  - /api/graph/overview       — 图谱全景概览（节点数、边数、类型分布等）
  - /api/graph/search         — 模糊搜索节点和边
  - /api/graph/node/{id}      — 节点详情及关系（outgoing/incoming）
  - /api/graph/node/{id}/neighbors — 邻居节点
  - /api/graph/statistics     — 图谱统计信息（含 avg_degree、density）
  - /api/graph/auto-edges     — 自动图谱边查询（v1.50 Phase B）
  - /api/graph/stats          — 图谱统计（含 auto_graph_builder 详情）
  - /api/graph/rebuild-auto   — 重新构建指定文档的图谱
"""

import asyncio
import json
import logging
import os
from collections import Counter
from typing import Dict, List, Optional, Set

from fastapi import APIRouter, HTTPException
from fastapi import Path as PathParam
from fastapi import Query, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["知识图谱"])


# ============================================================================
# 辅助函数
# ============================================================================


def _read_graph_data() -> tuple:
    """读取图谱数据，返回 (nodes, edges) 元组。

    优先从 GRAPH_PATH 读取 JSON 文件，若不存在则从 data_store 加载。

    Returns:
        (nodes, edges): nodes 为 dict，edges 为 list
    """
    try:
        from src.config import GRAPH_PATH

        if os.path.exists(GRAPH_PATH):
            with open(GRAPH_PATH, "r", encoding="utf-8") as f:
                kg_data = json.load(f)
            nodes = kg_data.get("nodes", kg_data.get("entities", {}))
            edges = list(kg_data.get("edges", []))
            return nodes, edges
    except (ImportError, OSError, json.JSONDecodeError) as e:
        logger.debug("从 GRAPH_PATH 读取失败: %s，尝试 data_store", e)

    try:
        from src.db.data_store import load_graph

        data = load_graph()
        nodes = data.get("nodes", {})
        edges = data.get("edges", [])
        return nodes, edges
    except (ImportError, OSError, json.JSONDecodeError) as e:
        logger.warning("从 data_store 加载图谱失败: %s", e)
        return {}, []


def _is_v2(request: Request) -> bool:
    """判断请求是否使用 v2 格式"""
    return bool(
        request
        and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
    )


def _build_wants_v2(request: Request) -> bool:
    """兼容旧变量名的 v2 检测"""
    return _is_v2(request)


def _compute_connectivity(nodes: dict, edges: list) -> dict:
    """计算图的连通性指标。

    Returns:
        {
            "communities_count": int,
            "isolated_nodes": int,
            "adjacency": dict,  # {node_id: set(neighbor_ids)}
        }
    """
    connected_nodes: Set[str] = set()
    adjacency: Dict[str, Set[str]] = {}
    for e in edges:
        src = e.get("from", e.get("source", ""))
        tgt = e.get("to", e.get("target", ""))
        if src:
            connected_nodes.add(src)
        if tgt:
            connected_nodes.add(tgt)
        if src and tgt:
            adjacency.setdefault(src, set()).add(tgt)
            adjacency.setdefault(tgt, set()).add(src)

    all_node_ids = set(nodes.keys()) if isinstance(nodes, dict) else set()
    isolated_count = len(all_node_ids - connected_nodes)

    # BFS 连通分量
    visited: Set[str] = set()
    communities = 0
    for node_id in all_node_ids:
        if node_id in visited:
            continue
        queue = [node_id]
        while queue:
            cur = queue.pop(0)
            if cur in visited:
                continue
            visited.add(cur)
            for neighbor in adjacency.get(cur, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        communities += 1

    return {
        "communities_count": communities,
        "isolated_nodes": isolated_count,
        "adjacency": adjacency,
    }


def _extract_node_info(node_info) -> dict:
    """从节点原始数据中提取标准化信息"""
    if isinstance(node_info, dict):
        return {
            "type": node_info.get("type", "unknown"),
            "description": node_info.get("description", ""),
            **{k: v for k, v in node_info.items() if k not in ("type", "description")},
        }
    return {}


# ============================================================================
# 兼容原有端点
# ============================================================================


@router.get("/api/graph")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def graph(entity: str = Query(""), request: Request = None):
    """知识图谱查询 — 兼容原有 API"""
    try:
        nodes, edges = await asyncio.to_thread(_read_graph_data)

        if entity:
            filtered_nodes = (
                {k: v for k, v in nodes.items() if entity.lower() in k.lower()} if isinstance(nodes, dict) else {}
            )
            result = {"nodes": filtered_nodes, "edges": edges}
        else:
            result = {"nodes": nodes, "edges": edges}

        if _is_v2(request):
            from src.api.response import success

            return success(data=result, message="知识图谱数据")
        return result
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("graph 查询失败: %s", e)
        result = {"nodes": {}, "edges": [], "error": str(e)}
        if _is_v2(request):
            from src.api.response import error

            return error("知识图谱查询失败", status_code=500, detail=str(e))
        return result


# ============================================================================
# 图谱全景概览
# ============================================================================


@router.get("/api/graph/overview")
async def graph_overview(request: Request = None) -> JSONResponse:
    """图谱全景概览

    返回图谱的核心指标，适用于前端图谱可视化页面的初始加载。

    Returns:
        {
            "nodes_count": int,
            "edges_count": int,
            "entity_type_distribution": {"person": 10, "company": 5, ...},
            "edge_type_distribution": {"works_at": 3, "located_in": 2, ...},
            "communities_count": int,
            "isolated_nodes": int,
            "avg_degree": float,
            "density": float,
        }
    """
    try:
        nodes, edges = await asyncio.to_thread(_read_graph_data)

        nodes_count = len(nodes) if isinstance(nodes, (dict, list)) else 0
        edges_count = len(edges)

        # 实体类型分布
        entity_type_dist: Dict[str, int] = {}
        if isinstance(nodes, dict):
            for n in nodes.values():
                if isinstance(n, dict):
                    ntype = n.get("type", "unknown")
                    entity_type_dist[ntype] = entity_type_dist.get(ntype, 0) + 1
        elif isinstance(nodes, list):
            for n in nodes:
                if isinstance(n, dict):
                    ntype = n.get("type", "unknown")
                    entity_type_dist[ntype] = entity_type_dist.get(ntype, 0) + 1

        # 边类型分布
        edge_type_dist: Dict[str, int] = {}
        for e in edges:
            rel = e.get("relation", e.get("type", "related_to"))
            edge_type_dist[rel] = edge_type_dist.get(rel, 0) + 1

        # 连通性分析
        connectivity = _compute_connectivity(nodes if isinstance(nodes, dict) else {}, edges)
        communities_count = connectivity["communities_count"]
        isolated_nodes = connectivity["isolated_nodes"]

        # 平均度数：每条边贡献 2 度（入度+出度）
        avg_degree = (2 * edges_count / nodes_count) if nodes_count > 0 else 0.0

        # 图密度：实际边数 / 最大可能边数（有向图）
        max_edges = nodes_count * (nodes_count - 1) if nodes_count > 1 else 1
        density = edges_count / max_edges if max_edges > 0 else 0.0

        result = {
            "nodes_count": nodes_count,
            "edges_count": edges_count,
            "entity_type_distribution": entity_type_dist,
            "edge_type_distribution": edge_type_dist,
            "communities_count": communities_count,
            "isolated_nodes": isolated_nodes,
            "avg_degree": round(avg_degree, 2),
            "density": round(density, 6),
        }

        # 统一返回格式：默认返回 {success, data, message}
        from src.api.response import success

        return success(data=result, message="图谱全景概览")

    except (OSError, json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("graph_overview 失败: %s", e)
        if _is_v2(request):
            from src.api.response import error

            return error("图谱概览查询失败", status_code=500, detail=str(e))
        return {"error": str(e)}


# ============================================================================
# 图谱模糊搜索（节点 + 边）
# ============================================================================


@router.get("/api/graph/search")
async def graph_search(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(50, ge=1, le=200, description="最大返回数"),
    request: Request = None,
):
    """图谱模糊搜索

    在节点名称/属性和边的 source/target/evidence 中搜索关键词（不区分大小写）。

    Args:
        q:     搜索关键词
        limit: 最大返回数

    Returns:
        {
            "query": str,
            "matched_nodes": [{"name": ..., "type": ..., ...}, ...],
            "matched_edges": [{"source": ..., "target": ..., "type": ..., ...}, ...],
            "total_nodes": int,
            "total_edges": int,
        }
    """
    try:
        nodes, edges = await asyncio.to_thread(_read_graph_data)
        q_lower = q.lower()

        # ── 搜索节点 ──
        matched_nodes = []
        if isinstance(nodes, dict):
            for name, info in nodes.items():
                if not isinstance(info, dict):
                    info = {}
                # 匹配节点名称
                name_match = q_lower in name.lower()
                # 匹配节点属性（description、type）
                desc_match = q_lower in str(info.get("description", "")).lower()
                type_match = q_lower in str(info.get("type", "")).lower()

                if name_match or desc_match or type_match:
                    matched_nodes.append({"name": name, **info})
                    if len(matched_nodes) >= limit:
                        break
        elif isinstance(nodes, list):
            for node in nodes:
                name = node.get("name", node.get("id", ""))
                if q_lower in name.lower() or q_lower in str(node.get("type", "")).lower():
                    matched_nodes.append(
                        {
                            "id": node.get("id", name),
                            "name": name,
                            "type": node.get("type", "unknown"),
                            **node,
                        }
                    )
                    if len(matched_nodes) >= limit:
                        break

        # ── 搜索边 ──
        matched_edges = []
        for edge in edges:
            src = str(edge.get("from", edge.get("source", ""))).lower()
            tgt = str(edge.get("to", edge.get("target", ""))).lower()
            evidence = str(edge.get("description", edge.get("evidence", ""))).lower()
            rel = str(edge.get("relation", edge.get("type", ""))).lower()

            if q_lower in src or q_lower in tgt or q_lower in evidence or q_lower in rel:
                matched_edges.append(
                    {
                        "source": edge.get("from", edge.get("source", "")),
                        "target": edge.get("to", edge.get("target", "")),
                        "type": edge.get("relation", edge.get("type", "related_to")),
                        "confidence": edge.get("confidence", edge.get("weight", 1.0)),
                        "evidence": edge.get("description", edge.get("evidence", "")),
                    }
                )
                if len(matched_edges) >= limit:
                    break

        result = {
            "query": q,
            "matched_nodes": matched_nodes,
            "matched_edges": matched_edges,
            "total_nodes": len(matched_nodes),
            "total_edges": len(matched_edges),
        }

        if _is_v2(request):
            from src.api.response import success

            return success(data=result, message="图谱搜索结果")
        return result

    except (OSError, json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("graph_search 失败: %s", e)
        if _is_v2(request):
            from src.api.response import error

            return error("图谱搜索失败", status_code=500, detail=str(e))
        return {"error": str(e)}


# ============================================================================
# 节点详情（含 outgoing/incoming 关系）
# ============================================================================


@router.get("/api/graph/node/{node_id}")
async def graph_node_detail(
    node_id: str = PathParam(..., description="节点 ID/名称"),
    request: Request = None,
):
    """节点详情及关系

    返回指定节点的详细信息及其所有关联边（outgoing + incoming）。

    Args:
        node_id: 节点 ID 或名称

    Returns:
        {
            "node": {"name": ..., "type": ..., ...},
            "relations": {
                "outgoing": [{"source": ..., "target": ..., "type": ..., ...}, ...],
                "incoming": [{"source": ..., "target": ..., "type": ..., ...}, ...],
            },
            "degree": int,
        }
    """
    try:
        nodes, edges = await asyncio.to_thread(_read_graph_data)

        # 查找节点（支持精确匹配和模糊匹配）
        node_info = None
        actual_id = node_id
        if isinstance(nodes, dict):
            if node_id in nodes:
                node_info = nodes[node_id]
                actual_id = node_id
            else:
                # 模糊匹配：大小写不敏感
                for name in nodes:
                    if node_id.lower() in name.lower():
                        node_info = nodes[name]
                        actual_id = name
                        break
        elif isinstance(nodes, list):
            for node in nodes:
                name = node.get("name", node.get("id", ""))
                if name == node_id or node_id.lower() in name.lower():
                    node_info = node
                    actual_id = node.get("id", name)
                    break

        if node_info is None:
            if _is_v2(request):
                from src.api.response import error

                return error(f"节点 {node_id} 未找到", status_code=404)
            raise HTTPException(status_code=404, detail=f"节点 {node_id} 未找到")

        # 收集关联边
        outgoing = []
        incoming = []
        for edge in edges:
            src = edge.get("from", edge.get("source", ""))
            tgt = edge.get("to", edge.get("target", ""))
            edge_data = {
                "source": src,
                "target": tgt,
                "type": edge.get("relation", edge.get("type", "related_to")),
                "confidence": edge.get("confidence", edge.get("weight", 1.0)),
                "evidence": edge.get("description", edge.get("evidence", "")),
            }
            if src == actual_id:
                outgoing.append(edge_data)
            if tgt == actual_id:
                incoming.append(edge_data)

        node_detail = {"name": actual_id, **_extract_node_info(node_info)}

        result = {
            "node": node_detail,
            "relations": {
                "outgoing": outgoing,
                "incoming": incoming,
            },
            "degree": len(outgoing) + len(incoming),
        }

        if _is_v2(request):
            from src.api.response import success

            return success(data=result, message="节点详情")
        return result

    except HTTPException:
        raise
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("graph_node_detail 失败: %s", e)
        if _is_v2(request):
            from src.api.response import error

            return error("节点详情查询失败", status_code=500, detail=str(e))
        return {"error": str(e)}


# ============================================================================
# 邻居节点
# ============================================================================


@router.get("/api/graph/node/{node_id}/neighbors")
async def graph_node_neighbors(
    node_id: str,
    limit: int = Query(50, ge=1, le=200, description="返回上限"),
    relation: str = Query("", description="按关系类型过滤"),
    request: Request = None,
):
    """邻居节点 — 获取指定节点的所有关联节点

    Args:
        node_id:  节点 ID 或名称
        limit:    最大返回数
        relation: 按关系类型过滤（可选）

    Returns:
        {"node_id": str, "total": int, "neighbors": [{name, type, relation, direction, confidence}]}
    """
    try:
        nodes, edges = await asyncio.to_thread(_read_graph_data)

        # 解析节点 ID（支持模糊匹配）
        actual_id = node_id
        if isinstance(nodes, dict) and node_id not in nodes:
            for name in nodes:
                if node_id.lower() in name.lower():
                    actual_id = name
                    break

        # 收集邻居
        neighbors = []
        for e in edges:
            src = e.get("from", e.get("source", ""))
            tgt = e.get("to", e.get("target", ""))
            rel = e.get("relation", e.get("type", "related_to"))
            conf = float(e.get("confidence", e.get("weight", 1.0)))

            if relation and rel != relation:
                continue

            if src == actual_id:
                neighbor_info = nodes.get(tgt, {}) if isinstance(nodes, dict) else {}
                neighbors.append(
                    {
                        "id": tgt,
                        "name": tgt,
                        "type": neighbor_info.get("type", "unknown") if isinstance(neighbor_info, dict) else "unknown",
                        "relation": rel,
                        "direction": "outgoing",
                        "confidence": conf,
                    }
                )
            elif tgt == actual_id:
                neighbor_info = nodes.get(src, {}) if isinstance(nodes, dict) else {}
                neighbors.append(
                    {
                        "id": src,
                        "name": src,
                        "type": neighbor_info.get("type", "unknown") if isinstance(neighbor_info, dict) else "unknown",
                        "relation": rel,
                        "direction": "incoming",
                        "confidence": conf,
                    }
                )

        # 按置信度降序排序
        neighbors.sort(key=lambda x: x["confidence"], reverse=True)
        total = len(neighbors)
        neighbors = neighbors[:limit]

        result = {"node_id": actual_id, "total": total, "neighbors": neighbors}
        if _is_v2(request):
            from src.api.response import success

            return success(data=result, message="邻居节点")
        return result

    except (OSError, json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("graph_node_neighbors 失败: %s", e)
        if _is_v2(request):
            from src.api.response import error

            return error("邻居节点查询失败", status_code=500, detail=str(e))
        return {"error": str(e), "neighbors": []}


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

        edges = []
        if os.path.exists(GRAPH_PATH):

            def _read_graph():
                with open(GRAPH_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)

            kg_data = await asyncio.to_thread(_read_graph)
            edges = list(kg_data.get("edges", []))

        # 过滤
        filtered = []
        for edge in edges:
            # doc_id 过滤
            edge_doc = edge.get("source_doc", "") or edge.get("doc_id", "")
            if doc_id and edge_doc != doc_id:
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
            filtered.append(
                {
                    "source": edge.get("from", edge.get("source", "")),
                    "target": edge.get("to", edge.get("target", "")),
                    "type": edge.get("relation", edge.get("type", "related_to")),
                    "confidence": edge_confidence,
                    "doc_id": edge_doc,
                    "evidence": edge.get("description", edge.get("evidence", "")),
                }
            )

        total = len(filtered)
        filtered = filtered[:limit]

        result = {"total": total, "limit": limit, "edges": filtered}
        if _is_v2(request):
            from src.api.response import success

            return success(data=result, message="自动图谱边查询")
        return result

    except (OSError, json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("auto_edges 失败: %s", e)
        if _is_v2(request):
            from src.api.response import error

            return error("自动图谱边查询失败", status_code=500, detail=str(e))
        return {"error": str(e), "edges": []}


@router.get("/api/graph/stats")
# FAKE-ASYNC
async def graph_stats(request: Request = None):
    """知识图谱统计（含 auto_graph_builder 详情）

    返回：
      - nodes_count:     节点总数
      - edges_count:     边总数
      - edge_type_dist:  边类型分布
      - entity_type_dist: 实体类型分布
      - communities_count: 连通分量数
      - isolated_nodes:  孤立节点数
      - recent_edges:    最近 20 条边
      - auto_graph_builder: 自动图谱构建器统计
    """
    try:
        from src.bagua.auto_graph import get_auto_graph_builder

        nodes, edges = await asyncio.to_thread(_read_graph_data)
        nodes_count = len(nodes) if isinstance(nodes, (dict, list)) else 0
        edges_count = len(edges)

        # 实体类型分布
        entity_type_dist: dict = {}
        if isinstance(nodes, dict):
            types = [n.get("type", "unknown") for n in nodes.values() if isinstance(n, dict)]
            entity_type_dist = dict(Counter(types))
        elif isinstance(nodes, list):
            types = [n.get("type", "unknown") for n in nodes if isinstance(n, dict)]
            entity_type_dist = dict(Counter(types))

        # 边类型分布
        edge_types = [e.get("relation", e.get("type", "related_to")) for e in edges]
        edge_type_dist = dict(Counter(edge_types))

        # 最近 20 条边
        recent_edges = edges[-20:]

        # 连通性
        connectivity = _compute_connectivity(nodes if isinstance(nodes, dict) else {}, edges)

        # 自动图谱构建器统计
        builder = get_auto_graph_builder()
        builder_stats = builder.get_stats()

        result = {
            "nodes_count": nodes_count,
            "edges_count": edges_count,
            "edge_type_distribution": edge_type_dist,
            "entity_type_distribution": entity_type_dist,
            "communities_count": connectivity["communities_count"],
            "isolated_nodes": connectivity["isolated_nodes"],
            "recent_edges": recent_edges,
            "auto_graph_builder": builder_stats,
        }

        # 统一返回格式：默认返回 {success, data, message}
        from src.api.response import success

        return success(data=result, message="图谱统计")

    except (OSError, json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("graph_stats 失败: %s", e)
        if _is_v2(request):
            from src.api.response import error

            return error("图谱统计查询失败", status_code=500, detail=str(e))
        return {"error": str(e)}


@router.get("/api/graph/statistics")
async def graph_statistics(request: Request = None) -> JSONResponse:
    """图谱统计信息（精简版，适用于仪表板展示）

    与 /api/graph/stats 的区别：此端点只返回数值指标，不含原始边数据。

    Returns:
        {
            "nodes_count": int,
            "edges_count": int,
            "entity_type_distribution": {"type": count, ...},
            "edge_type_distribution": {"relation": count, ...},
            "communities_count": int,
            "isolated_nodes": int,
            "avg_degree": float,
            "density": float,
            "auto_graph_builder": {...},
        }
    """
    try:
        from src.bagua.auto_graph import get_auto_graph_builder

        nodes, edges = await asyncio.to_thread(_read_graph_data)
        nodes_count = len(nodes) if isinstance(nodes, dict) else 0
        edges_count = len(edges)

        # 实体类型分布
        entity_type_dist: Dict[str, int] = {}
        if isinstance(nodes, dict):
            types = [n.get("type", "unknown") for n in nodes.values() if isinstance(n, dict)]
            entity_type_dist = dict(Counter(types))

        # 边类型分布
        edge_types = [e.get("relation", e.get("type", "related_to")) for e in edges]
        edge_type_dist = dict(Counter(edge_types))

        # 连通性
        connectivity = _compute_connectivity(nodes if isinstance(nodes, dict) else {}, edges)

        # 图密度
        max_edges = nodes_count * (nodes_count - 1) if nodes_count > 1 else 1
        density = edges_count / max_edges if max_edges > 0 else 0.0
        avg_degree = (2 * edges_count / nodes_count) if nodes_count > 0 else 0.0

        builder = get_auto_graph_builder()
        builder_stats = builder.get_stats()

        result = {
            "nodes_count": nodes_count,
            "edges_count": edges_count,
            "entity_type_distribution": entity_type_dist,
            "edge_type_distribution": edge_type_dist,
            "communities_count": connectivity["communities_count"],
            "isolated_nodes": connectivity["isolated_nodes"],
            "avg_degree": round(avg_degree, 2),
            "density": round(density, 6),
            "auto_graph_builder": builder_stats,
        }

        if _is_v2(request):
            from src.api.response import success

            return success(data=result, message="图谱统计信息")
        return result

    except (OSError, json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("graph_statistics 失败: %s", e)
        if _is_v2(request):
            from src.api.response import error

            return error("图谱统计信息查询失败", status_code=500, detail=str(e))
        return {"error": str(e)}


# ============================================================================
# 重建图谱
# ============================================================================


@router.post("/api/graph/rebuild-auto")
# FAKE-ASYNC
async def rebuild_auto(doc_id: str = Query(..., description="要重建图谱的文档 ID"), request: Request = None):
    """对指定文档重新执行自动图谱构建

    可用于文档内容更新后重建实体和边。
    完全是零 LLM 调用。
    """
    try:
        from src.db.memory_store import get_store

        store = get_store()
        chunks = store.get_by_hash(doc_id)

        # 如果没有精确匹配，尝试从坤卦 wiki_store 读取
        content = ""
        if chunks:
            content = "\n\n".join(c.get("text", "") for c in chunks)
        else:
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
            except (ImportError, AttributeError) as e:
                logger.debug("坤卦模块不可用: %s", e)

        if not content:
            if _is_v2(request):
                from src.api.response import error

                return error("未找到文档内容", status_code=404, detail=f"doc_id={doc_id}")
            raise HTTPException(status_code=404, detail=f"未找到文档内容: {doc_id}")

        # 执行自动图谱构建
        from src.bagua.auto_graph import get_auto_graph_builder

        builder = get_auto_graph_builder()
        graph_data = builder.build_full_graph(content, doc_id)

        # 写入存储
        from src.bagua.kun import KunGua

        temp_kun = KunGua()
        temp_kun.start()
        store_result = temp_kun.store_graph(
            entities=graph_data["entities"],
            relations=graph_data["edges"],
            doc_id=doc_id,
        )
        temp_kun.stop()

        result = {
            "ok": True,
            "doc_id": doc_id,
            "entity_count": graph_data["stats"]["entity_count"],
            "edge_count": graph_data["stats"]["edge_count"],
            "graph_stored": store_result.get("ok", False),
            "llm_calls": 0,
        }
        if _is_v2(request):
            from src.api.response import success

            return success(data=result, message="图谱重建完成")
        return result

    except HTTPException:
        raise
    except (OSError, json.JSONDecodeError, KeyError, ValueError, AttributeError) as e:
        logger.warning("rebuild_auto 失败: %s", e)
        if _is_v2(request):
            from src.api.response import error

            return error("图谱重建失败", status_code=500, detail=str(e))
        return {"ok": False, "error": str(e)}
