"""
伏羲 v1.50 — 仪表板路由（真实数据版）
数据来源：真实数据库查询 + 运行时指标
"""
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter(tags=["仪表板"])

# SQLite Chunks 中的种子数据标记
_SEED_FILE_NAMES = frozenset({"test_knowledge.md", "malware.exe"})
_SEED_HASH_PREFIXES = frozenset()  # 可扩展


def _is_seed_chunk(chunk: dict) -> bool:
    """判断一条 chunk 是否为种子/测试数据"""
    fname = (chunk.get("file_name") or "").lower()
    if fname in _SEED_FILE_NAMES:
        return True
    # 按 hash 前缀判断
    fhash = chunk.get("file_hash") or ""
    for prefix in _SEED_HASH_PREFIXES:
        if fhash.startswith(prefix):
            return True
    return False


@router.get("/api/dashboard")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def dashboard(request: Request = None):
    """仪表板 — v1.50 真实数据版

    数据来源：
      - 文档/向量统计 → chunks.db + ChromaDB
      - 搜索统计 → 运行时指标
      - 评测状态 → eval_automation
      - 系统运行时间 → app.state
    """
    try:
        # 1. 文档统计 —— 从 chunks.db 获取
        from src.db.data_store import load_chunks
        from src.db.vector_store import get_vector_store

        chunks = await asyncio.to_thread(load_chunks) or []
        unique_files = set()
        categories = {}
        seed_files = 0
        real_files = 0
        seed_chunks = 0
        real_chunks = 0

        for c in chunks:
            fname = c.get("file_name", "")
            if fname:
                unique_files.add(fname)
            cat = c.get("category", "未分类")
            categories[cat] = categories.get(cat, 0) + 1
            if _is_seed_chunk(c):
                seed_chunks += 1
                if fname:
                    seed_files += 1
            else:
                real_chunks += 1
                if fname:
                    real_files += 1

        # 2. 向量统计 —— 从 ChromaDB 获取
        vector_count = 0
        vs = get_vector_store()
        if vs:
            try:
                vector_count = vs.count
                if vector_count < 0:
                    vector_count = 0
            except Exception:  # TODO: Narrow exception type
                pass

        # 3. 搜索统计 —— 从运行时指标
        search_total = 0
        search_avg_latency_ms = 0
        try:
            from src.infra.request_metrics import get_request_metrics
            metrics = get_request_metrics()
            search_total = metrics.total_requests or 0
            if hasattr(metrics, 'avg_latency_ms'):
                search_avg_latency_ms = round(metrics.avg_latency_ms, 1)
        except Exception:  # TODO: Narrow exception type
            pass

        # 4. 评测状态
        eval_status = "never_run"
        eval_last_run = None
        eval_report_count = 0
        try:
            from src.services.eval_automation import get_eval_automation
            automation = get_eval_automation()
            report = await automation.get_latest_report() if hasattr(automation, 'get_latest_report') else None
            history = await automation.get_eval_history() if hasattr(automation, 'get_eval_history') else []
            if report and report.get("timestamp"):
                eval_status = "completed"
                eval_last_run = report.get("timestamp")
            if history:
                eval_report_count = len(history)
        except Exception:  # TODO: Narrow exception type
            pass

        # 5. 系统运行时间
        from src.config import VERSION
        uptime_seconds = 0.0
        born_at = getattr(request.app.state, "fuxi_born_at", None) if request else None
        if born_at:
            uptime_seconds = time.time() - born_at

        engine = getattr(request.app.state, "engine", "v2") if request else "v2"

        data = {
            "dashboard": {
                # 文档
                "documents": {
                    "total_chunks": len(chunks),
                    "real_chunks": real_chunks,
                    "seed_chunks": seed_chunks,
                    "unique_files": len(unique_files),
                    "real_files": real_files,
                    "seed_files": seed_files,
                    "categories": categories,
                    "has_seed_data": seed_chunks > 0,
                    "seed_data_note": (
                        "当前包含示例/测试数据（种子向量）。"
                        "上传真实业务文档后将替换种子数据。"
                    ) if seed_chunks > 0 else None,
                },
                # 向量库
                "vector_store": {
                    "total_vectors": vector_count,
                    "status": "connected" if vs else "unavailable",
                },
                # 搜索
                "search": {
                    "total_requests": search_total,
                    "avg_latency_ms": search_avg_latency_ms,
                },
                # 评测
                "evaluation": {
                    "status": eval_status,
                    "last_run": eval_last_run,
                    "report_count": eval_report_count,
                    "hint": (
                        "评测尚未执行。前往评测页面或调用 POST /api/eval/run 启动评测。"
                    ) if eval_status == "never_run" else None,
                },
                # 系统
                "system": {
                    "version": VERSION,
                    "engine": engine,
                    "uptime_seconds": round(uptime_seconds, 1),
                    "uptime_formatted": _format_uptime(uptime_seconds),
                },
            }
        }

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data=data, message="仪表板数据")
        return data
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"dashboard 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


def _format_uptime(seconds: float) -> str:
    """格式化运行时间"""
    if seconds < 60:
        return f"{int(seconds)}秒"
    if seconds < 3600:
        return f"{int(seconds / 60)}分钟"
    days = int(seconds / 86400)
    hours = int((seconds % 86400) / 3600)
    minutes = int((seconds % 3600) / 60)
    if days > 0:
        return f"{days}天{hours}小时{minutes}分钟"
    return f"{hours}小时{minutes}分钟"
