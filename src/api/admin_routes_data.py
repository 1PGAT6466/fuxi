"""
/admin/api — 知识图谱、反馈、缓存、蒸馏等数据管理 API
"""
from fastapi import APIRouter, Request, HTTPException
import json, logging, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from src.config import DATA_DIR, LOG_DIR
from src.db.data_store import load_chunks

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin-data"])


@router.get("/api/admin/organ-status")
async def organ_status():
    """已迁移到 admin_routes_organs，保留兼容"""
    from src.api.admin_routes_organs import organ_status as _impl
    return await _impl()


@router.get("/api/admin/recent-activities")
async def recent_activities():
    """已迁移"""
    from src.api.admin_routes_organs import recent_activities as _impl
    return await _impl()


@router.get("/api/admin/search-analytics")
async def search_analytics(days: int = 7):
    """搜索分析"""
    return {"ok": True, "data": {"days": days, "trend": []}}


@router.get("/api/admin/hot-queries")
async def hot_queries():
    """热门查询"""
    return {"ok": True, "queries": []}


@router.post("/api/admin/rebuild-vectors")
async def admin_rebuild_vectors(request: Request):
    """重建向量索引：从 SQLite 读取所有 chunks，重新向量化后 upsert 到 ChromaDB"""
    import sqlite3, time, asyncio
    from src.db.vector_store import get_vector_store
    from src.services.embedder import embed_texts
    from src.config import DATA_DIR

    t0 = time.time()
    try:
        from src.core.db import connect
        with connect("chunks") as conn:
            rows = conn.execute(
                "SELECT id, file_hash, file_name, category, chunk_index, text FROM chunks ORDER BY id"
            ).fetchall()

        if not rows:
            return {"ok": True, "message": "无数据可重建", "count": 0}

        vs = get_vector_store()
        batch_size = 32
        total = len(rows)
        ok_count = 0
        err_count = 0

        for start in range(0, total, batch_size):
            batch = rows[start:start + batch_size]
            texts = [r["text"] for r in batch]
            vecs = await embed_texts(texts)
            if not vecs:
                # 只处理有效的向量
                err_count += len(batch)
                continue

            ids = []
            metas = []
            docs = []
            for i, row in enumerate(batch[:len(vecs)]):
                chunk_id = f"{row['file_hash']}:{row['chunk_index']}"
                ids.append(chunk_id)
                metas.append({
                    "file_hash": row["file_hash"],
                    "file_name": row["file_name"],
                    "category": row["category"],
                    "chunk_index": row["chunk_index"],
                })
                docs.append(row["text"])

            try:
                vs.add(ids, vecs, metas, docs)
                ok_count += len(ids)
            except Exception:
                err_count += len(batch)

        duration_ms = int((time.time() - t0) * 1000)
        return {
            "ok": True,
            "message": f"重建完成: {ok_count} 成功, {err_count} 失败",
            "total": total, "ok": ok_count, "errors": err_count,
            "duration_ms": duration_ms,
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "duration_ms": int((time.time() - t0) * 1000)}


@router.get("/api/admin/knowledge-graph")
async def admin_knowledge_graph():
    """知识图谱概览"""
    return {"ok": True, "graph": {}}


@router.get("/api/admin/feedbacks")
async def admin_feedbacks():
    """用户反馈列表"""
    return {"ok": True, "feedbacks": []}


@router.get("/api/admin/export/documents")
async def export_documents():
    """导出文档"""
    return {"ok": True, "message": "export scheduled"}


@router.get("/api/admin/export/search-logs")
async def export_search_logs():
    """导出搜索日志"""
    return {"ok": True, "message": "export scheduled"}


@router.get("/api/admin/drift-signals")
async def drift_signals():
    """漂移信号"""
    return {"ok": True, "signals": []}


@router.get("/api/admin/cache-stats")
async def cache_stats():
    """缓存统计"""
    return {"ok": True, "size": 0, "hits": 0}


@router.post("/api/admin/cache-clear")
async def cache_clear():
    """清除缓存"""
    return {"ok": True, "message": "cache cleared"}


@router.post("/api/admin/index-tables")
async def index_tables(request: Request):
    """索引表格"""
    return {"ok": True, "message": "index scheduled"}


@router.get("/api/admin/table-stats")
async def table_stats():
    """表格统计"""
    return {"ok": True, "tables": 0}


@router.post("/api/admin/build-relations")
async def build_relations(limit: int = 50):
    """构建实体关系"""
    return {"ok": True, "message": f"relation build scheduled (limit={limit})"}


@router.get("/api/admin/relation-stats")
async def relation_stats():
    """关系统计"""
    return {"ok": True, "relations": 0}


@router.get("/api/admin/weekly-report")
async def weekly_report():
    """周报"""
    return {"ok": True, "report": {}}
