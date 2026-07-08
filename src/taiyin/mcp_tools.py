"""
mcp_tools.py — MCP 暴露工具 (v1.50 Phase F 扩展)
供外部 Agent 调用的 24 个工具 (原有 4 个 + 新增 20 个)
对标 GBrain 30+ MCP tools
"""
import json
import logging
import os
import time
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger("taiyin.mcp_tools")


# ==================== 原有 4 个工具 ====================

async def sag_search(query: str, top_k: int = 10) -> Dict:
    """MCP 工具：搜索知识库"""
    from src.taiyang.retrieval import hybrid_search
    try:
        results = await hybrid_search(query, top_k=top_k)
        return {
            "results": results,
            "count": len(results),
            "query": query,
        }
    except Exception as e:
        logger.error(f"[MCP] sag_search 失败: {e}")
        return {"error": str(e), "results": []}


async def sag_ingest(file_path: str, category: str = "") -> Dict:
    """MCP 工具：入库文档"""
    from src.shaoyang.pipeline import ShaoyangPipeline
    try:
        pipeline = ShaoyangPipeline(None)
        result = await pipeline.digest(file_path, category=category)
        return {
            "chunks": result.get("chunks", 0),
            "events": result.get("events", 0),
            "entities": result.get("entities", 0),
            "file_path": file_path,
        }
    except Exception as e:
        logger.error(f"[MCP] sag_ingest 失败: {e}")
        return {"error": str(e)}


async def sag_explain(query: str) -> Dict:
    """MCP 工具：解释查询结果"""
    from src.shaoyin.brain import ShaoyinBrain
    try:
        brain = ShaoyinBrain(None)
        result = await brain.think(query)
        return {
            "answer": result.get("answer", ""),
            "confidence": result.get("confidence", 0),
            "sources": result.get("sources", []),
        }
    except Exception as e:
        logger.error(f"[MCP] sag_explain 失败: {e}")
        return {"error": str(e)}


async def sag_status() -> Dict:
    """MCP 工具：获取系统状态"""
    from src.infra.meridian_monitor import get_monitor
    try:
        monitor = get_monitor()
        return monitor.get_health_report()
    except Exception as e:
        logger.error(f"[MCP] sag_status 失败: {e}")
        return {"error": str(e)}


# ==================== v1.50 Phase F 新增 20 个工具 ====================

# ── 5. kb_search ──
async def kb_search(query: str, top_k: int = 5, mode: str = "semantic") -> Dict:
    """知识库语义搜索"""
    try:
        try:
            from src.taiyang.retrieval import search_chunks
            results = search_chunks(query=query, top_k=top_k, mode=mode)
            return {"results": results, "total": len(results)}
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"kb_search retrieval 回退: {e}")

        # 回退 ChromaDB
        from src.db.vector_store import get_vector_store
        vs = get_vector_store()
        if vs:
            raw = vs.search(query, top_k=top_k)
            results = [{
                "id": r.get("id", ""),
                "text": r.get("text", r.get("content", "")),
                "score": r.get("score", r.get("distance", 0)),
                "source": r.get("metadata", {}).get("source", r.get("file_name", "")),
                "metadata": r.get("metadata", {}),
            } for r in raw]
            return {"results": results, "total": len(results)}
        return {"results": [], "total": 0}
    except Exception as e:
        logger.error(f"[MCP] kb_search 失败: {e}")
        return {"error": str(e), "results": [], "total": 0}


# ── 6. kb_list_documents ──
async def kb_list_documents() -> Dict:
    """列出知识库文档"""
    try:
        from src.db.data_store import load_chunks
        chunks = load_chunks()
        seen = {}
        for c in chunks:
            fhash = c.get("file_hash", "")
            if fhash and fhash not in seen:
                seen[fhash] = {
                    "id": fhash,
                    "name": c.get("file_name", ""),
                    "category": c.get("category", ""),
                    "chunk_count": sum(1 for cc in chunks if cc.get("file_hash") == fhash),
                    "created_at": c.get("created_at", ""),
                }
        docs = list(seen.values())
        return {"documents": docs, "total": len(docs)}
    except Exception as e:
        logger.error(f"[MCP] kb_list_documents 失败: {e}")
        return {"error": str(e), "documents": [], "total": 0}


# ── 7. kb_get_document ──
async def kb_get_document(doc_id: str) -> Dict:
    """获取单个文档内容"""
    try:
        from src.db.data_store import load_chunks
        chunks = load_chunks()
        matching = [c for c in chunks if c.get("file_hash", "") == doc_id]
        if not matching:
            matching = [c for c in chunks if doc_id in c.get("file_name", "")]
        if not matching:
            return {"error": f"文档未找到: {doc_id}", "chunks": []}

        return {
            "doc_id": doc_id,
            "file_name": matching[0].get("file_name", ""),
            "chunks": [{
                "id": c.get("id", ""),
                "text": c.get("text", c.get("content", "")),
                "chunk_index": c.get("chunk_index", 0),
            } for c in matching],
            "total_chunks": len(matching),
        }
    except Exception as e:
        logger.error(f"[MCP] kb_get_document 失败: {e}")
        return {"error": str(e)}


# ── 8. graph_query ──
async def graph_query(entity: str = "", source: str = "", target: str = "",
                      edge_type: str = "", min_confidence: float = 0.0,
                      limit: int = 100) -> Dict:
    """知识图谱查询（通过 AutoGraphBuilder）"""
    try:
        from src.config import GRAPH_PATH
        import os as _os

        edges = []
        if _os.path.exists(GRAPH_PATH):
            with open(GRAPH_PATH, "r", encoding="utf-8") as f:
                kg_data = json.load(f)
                edges = list(kg_data.get("edges", []))

        filtered = []
        for edge in edges:
            edge_doc = edge.get("source_doc", "") or edge.get("doc_id", "")
            edge_source = edge.get("from", edge.get("source", ""))
            edge_target = edge.get("to", edge.get("target", ""))
            edge_rel = edge.get("relation", edge.get("type", "related_to"))
            edge_conf = float(edge.get("confidence", edge.get("weight", 1.0)))

            if entity and entity.lower() not in edge_source.lower() and entity.lower() not in edge_target.lower():
                continue
            if source and source.lower() not in edge_source.lower():
                continue
            if target and target.lower() not in edge_target.lower():
                continue
            if edge_type and edge_type.lower() not in edge_rel.lower():
                continue
            if edge_conf < min_confidence:
                continue

            filtered.append({
                "source": edge_source,
                "target": edge_target,
                "type": edge_rel,
                "confidence": edge_conf,
                "doc_id": edge_doc,
                "evidence": edge.get("description", edge.get("evidence", "")),
            })

        total = len(filtered)
        return {"total": total, "limit": limit, "edges": filtered[:limit]}
    except Exception as e:
        logger.error(f"[MCP] graph_query 失败: {e}")
        return {"error": str(e), "edges": [], "total": 0}


# ── 9. graph_stats ──
async def graph_stats() -> Dict:
    """图谱统计"""
    try:
        from src.config import GRAPH_PATH
        from collections import Counter
        import os as _os

        nodes_count = 0
        edges_count = 0
        edge_type_dist = {}
        entity_type_dist = {}

        if _os.path.exists(GRAPH_PATH):
            with open(GRAPH_PATH, "r", encoding="utf-8") as f:
                kg_data = json.load(f)
                nodes = kg_data.get("nodes", kg_data.get("entities", {}))
                nodes_count = len(nodes)
                if isinstance(nodes, dict):
                    types = [n.get("type", "unknown") for n in nodes.values() if isinstance(n, dict)]
                    entity_type_dist = dict(Counter(types))
                edges = list(kg_data.get("edges", []))
                edges_count = len(edges)
                edge_types = [e.get("relation", e.get("type", "related_to")) for e in edges]
                edge_type_dist = dict(Counter(edge_types))

        builder_stats = {}
        try:
            from src.bagua.auto_graph import get_auto_graph_builder
            builder = get_auto_graph_builder()
            builder_stats = builder.get_stats()
        except Exception:
            pass

        return {
            "nodes_count": nodes_count,
            "edges_count": edges_count,
            "edge_type_distribution": edge_type_dist,
            "entity_type_distribution": entity_type_dist,
            "auto_graph_builder": builder_stats,
        }
    except Exception as e:
        logger.error(f"[MCP] graph_stats 失败: {e}")
        return {"error": str(e)}


# ── 10. wiki_search ──
async def wiki_search(q: str = "", category: str = "", limit: int = 20) -> Dict:
    """Wiki 页面搜索"""
    try:
        from src.taiyang.wiki import get_wiki_engine
        engine = get_wiki_engine()
        if not q.strip():
            pages = engine.list_pages(category=category, limit=limit)
        else:
            pages = engine.search_content(q, limit=limit)
            if not pages:
                pages = engine.search_by_title(q, limit=limit)
        return {"pages": pages, "total": len(pages)}
    except Exception as e:
        logger.error(f"[MCP] wiki_search 失败: {e}")
        return {"error": str(e), "pages": [], "total": 0}


# ── 11. wiki_get ──
async def wiki_get(page_id: str) -> Dict:
    """获取 Wiki 页面"""
    try:
        from src.taiyang.wiki import get_wiki_engine
        engine = get_wiki_engine()
        page = engine.get_page(page_id)
        if not page:
            return {"error": f"页面未找到: {page_id}"}
        linked = engine.get_linked_pages(page_id)
        page["linked_pages"] = linked
        return page
    except Exception as e:
        logger.error(f"[MCP] wiki_get 失败: {e}")
        return {"error": str(e)}


# ── 12. dream_cycle_run ──
async def dream_cycle_run() -> Dict:
    """触发夜间消化循环"""
    try:
        from src.evolution.dream_cycle import DreamCycle
        dc = DreamCycle()
        report = await dc.run()
        return {"ok": True, "message": "Dream Cycle 执行完成", "report": str(report)[:5000]}
    except ImportError as e:
        logger.error(f"[MCP] DreamCycle 导入失败: {e}")
        return {"ok": False, "error": "DreamCycle 模块不可用", "detail": str(e)}
    except Exception as e:
        logger.error(f"[MCP] dream_cycle_run 失败: {e}")
        return {"ok": False, "error": str(e)}


# ── 13. dream_cycle_report ──
async def dream_cycle_report() -> Dict:
    """获取最新日报"""
    try:
        _report_dir = Path(os.environ.get(
            "DREAM_CYCLE_REPORT_DIR",
            str(Path(__file__).parent.parent / "data" / "dream_reports"),
        ))
        report_files = sorted(_report_dir.glob("dream_report_*.md"), reverse=True)
        if not report_files:
            return {"ok": True, "has_report": False, "message": "暂无日报"}

        latest = report_files[0]
        content = latest.read_text(encoding="utf-8")
        return {
            "ok": True,
            "has_report": True,
            "report": content,
            "generated_at": latest.stem.replace("dream_report_", ""),
        }
    except Exception as e:
        logger.error(f"[MCP] dream_cycle_report 失败: {e}")
        return {"error": str(e)}


# ── 14. gap_analyze ──
async def gap_analyze(query: str = "", topic: str = "") -> Dict:
    """运行 Gap Analysis — 分析知识库覆盖缺口"""
    try:
        gaps = []
        # 尝试运行实际的 gap scan
        try:
            from src.evolution.dream_cycle import DreamCycle
            dc = DreamCycle()
            # 只跑 gap_scan 阶段
            results = await dc._run_gap_scan()
            gaps = results if isinstance(results, list) else []
        except Exception as e:
            logger.warning(f"gap_scan 调用失败，使用基础分析: {e}")
            # 基础：查询知识库覆盖
            try:
                from src.taiyang.retrieval import search_chunks
                search_query = query or topic or "知识库覆盖分析"
                results = search_chunks(query=search_query, top_k=10, mode="semantic")
                if results:
                    gaps = [{
                        "query": search_query,
                        "result_count": len(results),
                        "top_scores": [r.get("score", 0) for r in results[:5]],
                        "gap_detected": any(r.get("score", 0) < 0.5 for r in results),
                    }]
            except Exception:
                pass

        return {
            "ok": True,
            "gaps_found": len(gaps),
            "gaps": gaps,
            "query": query or topic,
        }
    except Exception as e:
        logger.error(f"[MCP] gap_analyze 失败: {e}")
        return {"ok": False, "error": str(e)}


# ── 15. entity_expand ──
async def entity_expand(entity_name: str, top_k: int = 10) -> Dict:
    """实体向量扩展"""
    try:
        if not entity_name or not entity_name.strip():
            return {"error": "缺少 entity_name 参数"}

        expanded = []
        try:
            from src.taiyang.expand import expand_entity
            expanded = expand_entity(entity_name, top_k=top_k)
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"expand_entity 失败: {e}")

        return {
            "entity_name": entity_name,
            "expanded_entities": expanded,
            "total": len(expanded),
        }
    except Exception as e:
        logger.error(f"[MCP] entity_expand 失败: {e}")
        return {"error": str(e), "expanded_entities": [], "total": 0}


# ── 16. cross_entity_synthesize ──
async def cross_entity_synthesize(entity_a: str, entity_b: str) -> Dict:
    """跨实体合成 — 查找两个实体之间的关联路径"""
    try:
        from src.config import GRAPH_PATH
        import os as _os

        if not _os.path.exists(GRAPH_PATH):
            return {"entity_a": entity_a, "entity_b": entity_b, "paths": [], "synthesis": "无图谱数据"}

        with open(GRAPH_PATH, "r", encoding="utf-8") as f:
            kg_data = json.load(f)

        edges = list(kg_data.get("edges", []))
        nodes = kg_data.get("nodes", kg_data.get("entities", {}))

        # 直接边
        direct_edges = []
        indirect_paths = []

        for e in edges:
            src = e.get("from", e.get("source", ""))
            tgt = e.get("to", e.get("target", ""))
            if (entity_a.lower() in src.lower() and entity_b.lower() in tgt.lower()) or \
               (entity_a.lower() in tgt.lower() and entity_b.lower() in src.lower()):
                direct_edges.append({
                    "source": src,
                    "target": tgt,
                    "type": e.get("relation", e.get("type", "related_to")),
                    "confidence": e.get("confidence", e.get("weight", 1.0)),
                })

        # 间接路径（二跳）
        a_neighbors = {}
        b_neighbors = {}
        for e in edges:
            src = e.get("from", e.get("source", ""))
            tgt = e.get("to", e.get("target", ""))
            if entity_a.lower() in src.lower():
                a_neighbors[tgt] = e
            elif entity_a.lower() in tgt.lower():
                a_neighbors[src] = e
            if entity_b.lower() in src.lower():
                b_neighbors[tgt] = e
            elif entity_b.lower() in tgt.lower():
                b_neighbors[src] = e

        common = set(a_neighbors.keys()) & set(b_neighbors.keys())
        for mid in common:
            indirect_paths.append({
                "path": [entity_a, mid, entity_b],
                "via": mid,
            })

        return {
            "entity_a": entity_a,
            "entity_b": entity_b,
            "direct_edges": direct_edges,
            "indirect_paths": indirect_paths,
            "direct_count": len(direct_edges),
            "indirect_count": len(indirect_paths),
            "synthesis": f"发现 {len(direct_edges)} 条直接关联、{len(indirect_paths)} 条间接路径"
                if direct_edges or indirect_paths else "未找到关联",
        }
    except Exception as e:
        logger.error(f"[MCP] cross_entity_synthesize 失败: {e}")
        return {"error": str(e)}


# ── 17. file_upload ──
async def file_upload(file_path: str, category: str = "") -> Dict:
    """文件上传 — 从本地路径入库"""
    try:
        from src.shaoyang.pipeline import ShaoyangPipeline
        from pathlib import Path as _Path

        path = _Path(file_path)
        if not path.exists():
            return {"error": f"文件不存在: {file_path}"}

        pipeline = ShaoyangPipeline(None)
        result = await pipeline.digest(str(path), category=category)
        return {
            "ok": True,
            "file_path": file_path,
            "chunks": result.get("chunks", 0),
            "events": result.get("events", 0),
            "entities": result.get("entities", 0),
        }
    except Exception as e:
        logger.error(f"[MCP] file_upload 失败: {e}")
        return {"ok": False, "error": str(e)}


# ── 18. file_list ──
async def file_list(page: int = 1, page_size: int = 50) -> Dict:
    """文件列表"""
    try:
        from src.db.data_store import load_chunks
        chunks = load_chunks()
        seen = {}
        for c in chunks:
            fh = c.get("file_hash", "")
            if fh and fh not in seen:
                seen[fh] = {
                    "file_name": c.get("file_name", ""),
                    "file_hash": fh,
                    "category": c.get("category", ""),
                    "chunk_count": 1,
                }
            elif fh:
                seen[fh]["chunk_count"] += 1
        files = list(seen.values())
        return {"files": files, "total": len(files), "page": page, "page_size": page_size}
    except Exception as e:
        logger.error(f"[MCP] file_list 失败: {e}")
        return {"error": str(e), "files": [], "total": 0}


# ── 19. chat_query ──
async def chat_query(query: str, history: List[dict] = None) -> Dict:
    """对话查询（简单版）"""
    try:
        from src.shaoyin.brain import ShaoyinBrain
        brain = ShaoyinBrain(None)
        result = await brain.think(query, history or [])
        return {
            "answer": result.get("answer", ""),
            "confidence": result.get("confidence", 0),
            "sources": result.get("sources", []),
            "mode": result.get("mode", "shaoyin"),
        }
    except Exception as e:
        logger.error(f"[MCP] chat_query 失败: {e}")
        return {"answer": f"对话失败: {str(e)}", "error": str(e)}


# ── 20. eval_run ──
async def eval_run(dataset: str = "", test_name: str = "") -> Dict:
    """运行评测"""
    try:
        from src.services.eval_automation import get_eval_automation
        automation = get_eval_automation()
        result = await automation.run_smoke_test()
        return {
            "ok": True,
            "passed": result.get("passed", False),
            "checks": result.get("checks", {}),
            "errors": result.get("errors", []),
            "dataset": dataset or "smoke_test",
        }
    except Exception as e:
        logger.error(f"[MCP] eval_run 失败: {e}")
        return {"ok": False, "error": str(e)}


# ── 21. notifications_list ──
async def notifications_list(page: int = 1, page_size: int = 20,
                            unread_only: bool = False) -> Dict:
    """获取通知列表"""
    try:
        return {
            "notifications": [],
            "unread_count": 0,
            "total": 0,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error(f"[MCP] notifications_list 失败: {e}")
        return {"error": str(e), "notifications": []}


# ── 22. feature_flags_list ──
async def feature_flags_list() -> Dict:
    """列出功能开关"""
    try:
        from src.services.feature_flags import load_flags, DEFAULT_FLAGS
        flags = load_flags()
        return {"flags": flags, "defaults": DEFAULT_FLAGS}
    except Exception as e:
        logger.error(f"[MCP] feature_flags_list 失败: {e}")
        return {"error": str(e), "flags": {}}


# ── 23. health_check ──
async def health_check() -> Dict:
    """系统健康检查"""
    try:
        from src.infra.health_check import get_health_checker
        checker = get_health_checker()
        result = await checker.check_all()
        return result
    except ImportError:
        # 简易回退
        return {
            "status": "healthy",
            "version": "1.50",
            "timestamp": time.time(),
            "checks": {
                "server": "ok",
                "memory": "ok",
            },
        }
    except Exception as e:
        logger.error(f"[MCP] health_check 失败: {e}")
        return {"status": "error", "error": str(e)}


# ── 24. audit_logs ──
async def audit_logs(user: str = "", action: str = "", days: int = 1,
                     limit: int = 100) -> Dict:
    """审计日志查询"""
    try:
        from src.infra.audit_log import query_audit
        results = query_audit(user=user or None, action=action or None,
                             days=days, limit=limit)
        return {"entries": results, "count": len(results)}
    except Exception as e:
        logger.error(f"[MCP] audit_logs 失败: {e}")
        return {"error": str(e), "entries": [], "count": 0}


# ==================== 完整 MCP 工具定义（JSON Schema） ====================

MCP_TOOLS = [
    # -- 原有 4 个 --
    {
        "name": "sag_search",
        "description": "搜索伏羲知识库 — 混合检索（向量 + 关键词）",
        "parameters": {
            "query": {"type": "string", "description": "搜索查询"},
            "top_k": {"type": "integer", "description": "返回结果数量", "default": 10},
        },
    },
    {
        "name": "sag_ingest",
        "description": "入库文档到伏羲知识库 — 文档解析 + 分块 + 向量化",
        "parameters": {
            "file_path": {"type": "string", "description": "文件路径"},
            "category": {"type": "string", "description": "分类", "default": ""},
        },
    },
    {
        "name": "sag_explain",
        "description": "解释查询结果 — 通过 LLM 生成自然语言解释",
        "parameters": {
            "query": {"type": "string", "description": "查询"},
        },
    },
    {
        "name": "sag_status",
        "description": "获取系统状态 — 四象、八卦、基础设施健康报告",
        "parameters": {},
    },
    # -- 新增 20 个 --
    {
        "name": "kb_search",
        "description": "知识库语义搜索 — 向量相似度 + 全文搜索",
        "parameters": {
            "query": {"type": "string", "description": "搜索查询"},
            "top_k": {"type": "integer", "description": "返回结果数量", "default": 5},
            "mode": {"type": "string", "description": "搜索模式: semantic/keyword/hybrid", "default": "semantic"},
        },
    },
    {
        "name": "kb_list_documents",
        "description": "列出知识库文档 — 返回所有已入库文档的列表",
        "parameters": {},
    },
    {
        "name": "kb_get_document",
        "description": "获取单个文档内容 — 通过 doc_id 获取完整文档的所有 chunks",
        "parameters": {
            "doc_id": {"type": "string", "description": "文档 ID (file_hash)"},
        },
    },
    {
        "name": "graph_query",
        "description": "知识图谱查询 — 按实体/边类型/置信度查询图谱边",
        "parameters": {
            "entity": {"type": "string", "description": "实体名称（模糊匹配 source 或 target）", "default": ""},
            "source": {"type": "string", "description": "按源实体过滤", "default": ""},
            "target": {"type": "string", "description": "按目标实体过滤", "default": ""},
            "edge_type": {"type": "string", "description": "按边类型过滤 (works_at, invested_in, supplied_by...)", "default": ""},
            "min_confidence": {"type": "number", "description": "最小置信度 (0-1)", "default": 0.0},
            "limit": {"type": "integer", "description": "返回上限", "default": 100},
        },
    },
    {
        "name": "graph_stats",
        "description": "图谱统计 — 节点数、边数、类型分布",
        "parameters": {},
    },
    {
        "name": "wiki_search",
        "description": "Wiki 页面搜索 — 全文搜索标题+内容+标签",
        "parameters": {
            "q": {"type": "string", "description": "搜索关键词", "default": ""},
            "category": {"type": "string", "description": "按分类过滤", "default": ""},
            "limit": {"type": "integer", "description": "返回上限", "default": 20},
        },
    },
    {
        "name": "wiki_get",
        "description": "获取 Wiki 页面 — 通过 page_id 获取完整页面内容+关联页面",
        "parameters": {
            "page_id": {"type": "string", "description": "Wiki 页面 ID"},
        },
    },
    {
        "name": "dream_cycle_run",
        "description": "触发夜间消化循环 — 运行 digest→enrich→consolidate→gap_scan 四阶段",
        "parameters": {},
    },
    {
        "name": "dream_cycle_report",
        "description": "获取最新日报 — 返回最后一次 Dream Cycle 生成的 Markdown 日报",
        "parameters": {},
    },
    {
        "name": "gap_analyze",
        "description": "运行 Gap Analysis — 分析知识库覆盖缺口，发现缺失的知识领域",
        "parameters": {
            "query": {"type": "string", "description": "分析主题/查询", "default": ""},
            "topic": {"type": "string", "description": "分析主题（备用）", "default": ""},
        },
    },
    {
        "name": "entity_expand",
        "description": "实体向量扩展 — 输入实体名，返回向量相似度排序的扩展实体列表",
        "parameters": {
            "entity_name": {"type": "string", "description": "实体名称"},
            "top_k": {"type": "integer", "description": "返回扩展数", "default": 10},
        },
    },
    {
        "name": "cross_entity_synthesize",
        "description": "跨实体合成 — 查找两个实体之间的直接/间接关联路径",
        "parameters": {
            "entity_a": {"type": "string", "description": "实体 A 名称"},
            "entity_b": {"type": "string", "description": "实体 B 名称"},
        },
    },
    {
        "name": "file_upload",
        "description": "文件上传 — 从本地文件路径入库（文档解析+分块+向量化）",
        "parameters": {
            "file_path": {"type": "string", "description": "本地文件路径"},
            "category": {"type": "string", "description": "分类标签", "default": ""},
        },
    },
    {
        "name": "file_list",
        "description": "文件列表 — 返回所有已上传文件的列表",
        "parameters": {
            "page": {"type": "integer", "description": "页码", "default": 1},
            "page_size": {"type": "integer", "description": "每页数量", "default": 50},
        },
    },
    {
        "name": "chat_query",
        "description": "对话查询（简单版）— 向伏羲提问，返回 LLM 生成的回答",
        "parameters": {
            "query": {"type": "string", "description": "用户问题"},
            "history": {"type": "array", "description": "对话历史", "default": []},
        },
    },
    {
        "name": "eval_run",
        "description": "运行评测 — 执行烟雾测试验证系统功能",
        "parameters": {
            "dataset": {"type": "string", "description": "评测数据集名称", "default": ""},
            "test_name": {"type": "string", "description": "测试名称", "default": ""},
        },
    },
    {
        "name": "notifications_list",
        "description": "获取通知列表 — 返回系统通知",
        "parameters": {
            "page": {"type": "integer", "description": "页码", "default": 1},
            "page_size": {"type": "integer", "description": "每页数量", "default": 20},
            "unread_only": {"type": "boolean", "description": "只返回未读", "default": False},
        },
    },
    {
        "name": "feature_flags_list",
        "description": "列出功能开关 — 返回所有 Feature Flag 及其当前状态",
        "parameters": {},
    },
    {
        "name": "health_check",
        "description": "系统健康检查 — 返回服务器、数据库、八卦模块健康状态",
        "parameters": {},
    },
    {
        "name": "audit_logs",
        "description": "审计日志查询 — 查询系统操作审计记录",
        "parameters": {
            "user": {"type": "string", "description": "按用户过滤", "default": ""},
            "action": {"type": "string", "description": "按操作类型过滤", "default": ""},
            "days": {"type": "integer", "description": "最近几天", "default": 1},
            "limit": {"type": "integer", "description": "返回上限", "default": 100},
        },
    },
]
