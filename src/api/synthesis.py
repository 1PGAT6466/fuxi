#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
synthesis.py — 跨实体合成 API

伏羲 v1.50 Phase D: Synthesis 跨实体合成 API 端点。

端点：
  POST /api/synthesis/cross-entity — 跨实体合成查询

依赖：
  - src.bagua.synthesizer.CrossEntitySynthesizer
  - src.bagua.auto_graph.AutoGraphBuilder
  - src.taiyang.retrieval / src.services.retrieval
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("api.synthesis")

router = APIRouter(tags=["Synthesis 跨实体合成"])


# ============================================================================
# 请求/响应模型
# ============================================================================

class CrossEntityRequest(BaseModel):
    """跨实体合成请求
    
    Attributes:
        query:          用户查询
        entity_names:   可选，指定要合成的实体列表（不指定则自动提取）
        top_k:          检索数量（默认 10）
        include_graph:  是否包含知识图谱数据（默认 True）
        mode:           合成模式
                        - "auto": 自动检测（默认）
                        - "force_cross_entity": 强制跨实体合成
                        - "rag_only": 仅 RAG 检索（回退模式）
    """
    query: str = Field(..., min_length=1, max_length=5000, description="用户查询")
    entity_names: Optional[List[str]] = Field(None, max_length=20, description="指定实体列表")
    top_k: int = Field(10, ge=1, le=50, description="检索数量")
    include_graph: bool = Field(True, description="是否包含知识图谱")
    mode: str = Field("auto", description="合成模式: auto | force_cross_entity | rag_only")


class CrossEntityResponse(BaseModel):
    """跨实体合成响应"""
    query: str
    synthesized_text: str
    entity_groups: List[Dict[str, Any]] = []
    relations: List[Dict[str, Any]] = []
    sources: List[Dict[str, Any]] = []
    entity_count: int = 0
    chunk_count: int = 0
    mode: str = "cross_entity"
    metadata: Dict[str, Any] = {}


# ============================================================================
# POST /api/synthesis/cross-entity
# ============================================================================

@router.post("/api/synthesis/cross-entity", response_model=CrossEntityResponse)
async def cross_entity_synthesize(body: CrossEntityRequest, request: Request = None):
    """跨实体合成查询
    
    将 RAG 检索结果与知识图谱数据结合，生成跨实体/跨文档的整合回答。
    
    工作流程：
      1. RAG 检索 — 从 ChromaDB/向量数据库检索相关 chunk
      2. 知识图谱查询 — 获取实体和关系数据
      3. 跨实体合成 — 按实体分组、时间线排序、关系整合
      4. 格式化输出 — Markdown + 来源引用
    
    请求示例:
    ```json
    {
        "query": "张三在阿里巴巴的职责和项目",
        "entity_names": ["张三", "阿里巴巴"],
        "top_k": 10,
        "include_graph": true
    }
    ```
    
    返回示例:
    ```json
    {
        "query": "张三在阿里巴巴的职责和项目",
        "synthesized_text": "## 关于 张三\\n· 张三在阿里巴巴负责淘宝项目...\\n> 来源：员工档案.md",
        "entity_groups": [...],
        "relations": [...],
        "sources": [...],
        "entity_count": 2,
        "chunk_count": 10,
        "mode": "cross_entity",
        "metadata": {...}
    }
    ```
    """
    try:
        from src.bagua.synthesizer import CrossEntitySynthesizer, SynthesisResult
        from src.bagua.auto_graph import get_auto_graph_builder
        
        synthesizer = CrossEntitySynthesizer()
        graph_builder = get_auto_graph_builder()
        
        # ---- 步骤 1: RAG 检索 ----
        retrieved_chunks: List[Dict[str, Any]] = []
        graph_entities: List[Dict[str, Any]] = []
        graph_edges: List[Dict[str, Any]] = []
        
        try:
            # 尝试 taiyang retrieval
            from src.taiyang.retrieval import search_chunks
            retrieved_chunks = search_chunks(
                query=body.query,
                top_k=body.top_k,
                mode="semantic",
            )
        except (ImportError, Exception):
            pass
        
        # 回退：尝试 services.retrieval
        if not retrieved_chunks:
            try:
                from src.services.retrieval import search as svc_search
                retrieved_chunks = svc_search(query=body.query, top_k=body.top_k)
            except (ImportError, Exception):
                pass
        
        # 回退：尝试 db/vector_store
        if not retrieved_chunks:
            try:
                from src.db.vector_store import get_vector_store
                vs = get_vector_store()
                if vs:
                    raw_results = vs.search(body.query, top_k=body.top_k)
                    for r in raw_results:
                        retrieved_chunks.append({
                            "content": r.get("text", r.get("content", "")),
                            "doc_id": r.get("id", ""),
                            "source": r.get("metadata", {}).get("source", ""),
                            "date": r.get("metadata", {}).get("date", ""),
                            "score": r.get("score", 0),
                        })
            except (ImportError, Exception) as e:
                logger.warning("所有检索方法失败: %s", e)
        
        # ---- 步骤 2: 知识图谱数据 ----
        if body.include_graph:
            # 尝试从 graph_router 或 auto_graph 获取
            try:
                from src.taiyang.graph_router import load_graph
                graph_data = load_graph()
                graph_entities = graph_data.get("entities", [])
                graph_edges = graph_data.get("edges", graph_data.get("relations", []))
            except (ImportError, Exception):
                pass
            
            # 回退：从 knowledge_graph.json 读取
            if not graph_entities:
                try:
                    import json
                    import os
                    kg_path = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                        "data", "knowledge_graph.json"
                    )
                    if os.path.exists(kg_path):
                        with open(kg_path, "r", encoding="utf-8") as f:
                            kg_data = json.load(f)
                        graph_entities = kg_data.get("entities", [])
                        graph_edges = kg_data.get("edges", kg_data.get("relations", []))
                except (ImportError, Exception) as e:
                    logger.debug("knowledge_graph.json 读取失败: %s", e)
        
        # ---- 步骤 3: 跨实体合成 ----
        result: SynthesisResult = synthesizer.synthesize(
            query=body.query,
            retrieved_chunks=retrieved_chunks,
            graph_entities=graph_entities,
            graph_edges=graph_edges,
            entity_names=body.entity_names,
        )
        
        # ---- 步骤 4: 构建响应 ----
        return CrossEntityResponse(
            query=result.query,
            synthesized_text=result.synthesized_text,
            entity_groups=result.entity_groups,
            relations=result.relations,
            sources=result.sources,
            entity_count=result.entity_count,
            chunk_count=result.chunk_count,
            mode=result.mode,
            metadata={
                "retrieved_chunks": len(retrieved_chunks),
                "graph_entities": len(graph_entities),
                "graph_edges": len(graph_edges),
                "synthesizer_stats": synthesizer.get_stats(),
            },
        )
        
    except ValueError as e:
        logger.warning("跨实体合成参数错误: %s", e)
        return JSONResponse(status_code=400, content={
            "error": "参数错误",
            "detail": str(e),
        })
    except Exception as e:
        logger.exception("跨实体合成失败: %s", e)
        return JSONResponse(status_code=500, content={
            "error": "内部服务错误",
            "detail": str(e),
        })


# ============================================================================
# GET /api/synthesis/health — 健康检查
# ============================================================================

@router.get("/api/synthesis/health")
async def synthesis_health(request: Request = None):
    """Synthesis 模块健康检查"""
    try:
        from src.bagua.synthesizer import get_synthesizer
        syn = get_synthesizer()
        return {
            "status": "ok",
            "module": "synthesis",
            "stats": syn.get_stats(),
        }
    except Exception as e:
        return JSONResponse(status_code=503, content={
            "status": "unavailable",
            "error": str(e),
        })


__all__ = ["router"]
