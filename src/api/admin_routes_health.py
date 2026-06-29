"""
/admin/api/health — 健康检查相关 API
"""
from fastapi import APIRouter, HTTPException
import time, logging, os, json
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin-health"])


@router.get("/api/health")
async def health():
    """服务健康检查 (v1.43 增强: ratio诊断 + 超时保护 + 告警冷却)"""
    import asyncio
    from src.config import START_TIME, VERSION, DATA_DIR, UPLOAD_DIR
    
    _t0 = time.time()
    status = "alive"
    warnings = []
    
    # 安全获取 chunk 数
    chunk_count = 0
    try:
        chunks = await asyncio.wait_for(
            asyncio.to_thread(lambda: __import__('src.db.data_store', fromlist=['load_chunks']).load_chunks()),
            timeout=5.0
        )
        chunk_count = len(chunks) if chunks else 0
    except (asyncio.TimeoutError, Exception):
        chunk_count = 0
        warnings.append("chunks查询超时")
        status = "degraded"
    
    # 安全获取向量数
    vector_count = 0
    try:
        def _get_vector_count():
            from src.db.vector_store import get_vector_store
            vs = get_vector_store()
            return vs.count if vs else 0
        vector_count = await asyncio.wait_for(
            asyncio.to_thread(_get_vector_count),
            timeout=5.0
        )
    except (asyncio.TimeoutError, Exception):
        vector_count = 0
        warnings.append("向量查询超时")
        status = "degraded"
    
    # 文件数
    file_count = 0
    try:
        file_count = len(os.listdir(UPLOAD_DIR)) if os.path.isdir(UPLOAD_DIR) else 0
    except:
        pass
    
    # ratio 诊断
    ratio_info = None
    if chunk_count > 0:
        if vector_count < chunk_count * 0.3:
            ratio_info = f"向量严重缺失: {chunk_count - vector_count} 个 chunk 无向量"
            warnings.append(ratio_info)
            if status == "alive":
                status = "degraded"
        elif vector_count < chunk_count * 0.9:
            ratio_info = f"向量部分缺失: {chunk_count - vector_count} 个 chunk 无向量"
        elif vector_count > chunk_count * 1.5:
            ratio_info = f"向量冗余: {vector_count - chunk_count} 条孤立向量"
    
    # 告警冷却（10分钟）
    _last_alert_key = "/api/health._last_alert_time"
    _last_alert = getattr(health, '_last_alert_time', 0)
    should_alert = warnings and (time.time() - _last_alert > 600)
    if should_alert:
        logger.warning(f"[Health] 告警: {'; '.join(warnings)}")
        health._last_alert_time = time.time()
    
    uptime_seconds = time.time() - START_TIME
    d = int(uptime_seconds // 86400)
    h = int((uptime_seconds % 86400) // 3600)
    m = int((uptime_seconds % 3600) // 60)
    check_duration_ms = int((time.time() - _t0) * 1000)
    
    return {
        "ok": status == "alive",
        "status": status,
        "version": VERSION,
        "uptime": f"{d}d {h}h {m}m",
        "uptime_seconds": round(uptime_seconds),
        "chunks": chunk_count,
        "total_chunks": chunk_count,
        "vectors": vector_count,
        "files": file_count,
        "total_files": file_count,
        "ratio_info": ratio_info,
        "warnings": warnings if warnings else None,
        "check_duration_ms": check_duration_ms,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
@router.get("/api/stats")
async def stats():
    """快速状态"""
    from src.config import START_TIME
    from src.db.data_store import load_chunks
    try:
        chunks = load_chunks()
        if chunks is None:
            chunks = []
    except Exception as e:
        logger.warning(f"Stats error: {e}")
        chunks = []
    return {
        "total_chunks": len(chunks),
        "uptime_seconds": round(time.time() - START_TIME),
        "ok": True,
    }


@router.get("/api/admin/stats")
async def admin_stats():
    """管理面板统计"""
    from src.db.data_store import load_chunks
    from src.services.distiller import get_distill_state
    try:
        chunks = load_chunks()
    except:
        chunks = []
    try:
        state = get_distill_state()
    except:
        state = {}
    try:
        chunk_count = len(chunks)
        unique_sources = len(set(c.get("source_file", "") for c in chunks))
        total_size = sum(len(str(c.get("text", ""))) for c in chunks)
    except:
        chunk_count = unique_sources = total_size = 0

    categories = {}
    try:
        for c in chunks:
            cat = c.get("category", "未分类")
            categories[cat] = categories.get(cat, 0) + 1
    except:
        pass

    return {
        "ok": True,
        "chunks": chunk_count,
        "unique_sources": unique_sources,
        "total_size_kb": round(total_size / 1024, 1),
        "categories": categories,
        "category_distribution": categories,
        "distill": state,
    }


@router.get("/api/admin/server-status")
async def server_status():
    """服务器状态"""
    from src.config import START_TIME
    uptime = time.time() - START_TIME
    result = {
        "ok": True,
        "uptime_seconds": round(uptime),
        "uptime_hours": round(uptime / 3600, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        import psutil
        result["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        result["memory_percent"] = round(mem.percent, 1)
        disk = psutil.disk_usage("/")
        result["disk_percent"] = round(disk.percent, 1)
    except ImportError:
        result["cpu_percent"] = 0
        result["memory_percent"] = 0
        result["disk_percent"] = 0
    except Exception:
        result["cpu_percent"] = 0
        result["memory_percent"] = 0
        result["disk_percent"] = 0
    return result
