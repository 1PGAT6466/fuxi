"""
routes.py — 数据分析服务 API 路由

端点:
  POST /api/analytics/stats   — 综合统计
  POST /api/analytics/trends  — 趋势数据
  POST /api/analytics/report  — 统计报表
  POST /api/analytics/storage — 存储分布
  POST /api/analytics/export  — 导出 CSV
  GET  /api/analytics/health   — 健康检查
"""

import csv
import io
import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

# ── 从项目配置获取路径 ──
from src.config import DATA_DIR, LOG_DIR

logger = logging.getLogger("services.data-analytics.routes")

router = APIRouter(prefix="", tags=["Data Analytics"])

# ── Pydantic 请求模型 ──

class TrendsRequest(BaseModel):
    """趋势查询请求"""
    period: str = Field(
        default="day",
        description="时间维度: day / week / month",
        examples=["day", "week", "month"]
    )
    start_date: Optional[str] = Field(
        default=None,
        description="起始日期 (YYYY-MM-DD)，不填则默认最近 30 天",
        examples=["2026-01-01"]
    )
    end_date: Optional[str] = Field(
        default=None,
        description="结束日期 (YYYY-MM-DD)，不填则默认今天",
        examples=["2026-01-31"]
    )


class ReportRequest(BaseModel):
    """报表请求"""
    report_type: str = Field(
        default="summary",
        description="报表类型: summary / detailed",
        examples=["summary", "detailed"]
    )
    period: str = Field(
        default="month",
        description="时间范围: today / week / month / all",
        examples=["month"]
    )


class ExportRequest(BaseModel):
    """导出请求"""
    format: str = Field(
        default="csv",
        description="导出格式: csv",
        examples=["csv"]
    )
    report_type: str = Field(
        default="summary",
        description="报表类型: summary / detailed",
        examples=["summary", "detailed"]
    )


# ══════════════════════════════════════════════════
#  数据采集层 — 从各数据源提取统计信息
# ══════════════════════════════════════════════════

def _get_chroma_stats() -> dict:
    """从 ChromaDB 获取向量存储统计"""
    chroma_path = DATA_DIR / "chroma" / "chroma.sqlite3"
    result = {
        "collections": 0,
        "embeddings": 0,
        "vectors_total": 0,
        "storage_size_bytes": 0,
    }
    try:
        if chroma_path.exists():
            conn = sqlite3.connect(str(chroma_path))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # 集合数
            cur.execute("SELECT COUNT(*) as cnt FROM collections")
            row = cur.fetchone()
            result["collections"] = row["cnt"] if row else 0

            # 嵌入向量数 (从 FTS data 估算)
            cur.execute("SELECT COUNT(*) as cnt FROM embedding_fulltext_search_data")
            row = cur.fetchone()
            fts_count = row["cnt"] if row else 0
            result["embeddings"] = fts_count

            # 向量总数（segment 级别的 counting）
            cur.execute("SELECT COUNT(*) as cnt FROM segments WHERE type='VECTOR'")
            row = cur.fetchone()
            seg_count = row["cnt"] if row else 0
            result["vectors_total"] = fts_count

            conn.close()

        # 存储大小：chroma 目录总大小
        chroma_dir = DATA_DIR / "chroma"
        if chroma_dir.exists():
            total_bytes = sum(
                f.stat().st_size
                for f in chroma_dir.rglob("*")
                if f.is_file()
            )
            result["storage_size_bytes"] = total_bytes

    except Exception as e:
        logger.warning(f"获取 ChromaDB 统计失败: {e}")

    return result


def _get_chunks_stats() -> dict:
    """从 chunks.db 获取文档分块统计"""
    from src.config import CHUNKS_DB_PATH

    result = {
        "total_chunks": 0,
        "total_documents": 0,
        "active_chunks": 0,
        "categories": {},
    }
    try:
        db_path = Path(CHUNKS_DB_PATH)
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # 总数
            cur.execute("SELECT COUNT(*) as cnt FROM chunks")
            row = cur.fetchone()
            result["total_chunks"] = row["cnt"] if row else 0

            # 活跃
            cur.execute("SELECT COUNT(*) as cnt FROM chunks WHERE status='active'")
            row = cur.fetchone()
            result["active_chunks"] = row["cnt"] if row else 0

            # 按 category 分布
            cur.execute(
                "SELECT category, COUNT(*) as cnt FROM chunks "
                "GROUP BY category ORDER BY cnt DESC"
            )
            cats = {}
            for row in cur.fetchall():
                cat = row["category"] or "未分类"
                cats[cat] = row["cnt"]
            result["categories"] = cats

            # 不同文档数（按 file_hash 去重）
            cur.execute(
                "SELECT COUNT(DISTINCT file_hash) as cnt FROM chunks WHERE file_hash IS NOT NULL"
            )
            row = cur.fetchone()
            result["total_documents"] = row["cnt"] if row else 0

            conn.close()

    except Exception as e:
        logger.warning(f"获取 chunks 统计失败: {e}")

    return result


def _get_users_stats() -> dict:
    """从用户数据获取统计"""
    result = {"total_users": 0, "active_users": 0, "roles": {}}
    try:
        users_file = DATA_DIR / "users.json"
        if users_file.exists():
            data = json.loads(users_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                result["total_users"] = len(data)
                if "roles" in data:
                    result["roles"] = data["roles"]
            elif isinstance(data, list):
                result["total_users"] = len(data)
    except Exception as e:
        logger.warning(f"获取用户统计失败: {e}")

    return result


def _get_search_logs_stats(start_date: Optional[str] = None, end_date: Optional[str] = None) -> list:
    """从搜索日志中提取查询记录（按天聚合）"""
    records = []
    try:
        # 读取搜索日志 JSONL 文件
        log_dir = Path(LOG_DIR)
        if not log_dir.exists():
            return records

        # 如果没有指定日期范围，默认最近 30 天
        if not end_date:
            end_dt = datetime.now()
        else:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        if not start_date:
            start_dt = end_dt - timedelta(days=30)
        else:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")

        # 按天聚合
        daily_counts = {}
        current = start_dt
        while current <= end_dt:
            key = current.strftime("%Y-%m-%d")
            daily_counts[key] = {"count": 0, "total_latency": 0.0}
            current += timedelta(days=1)

        # 读取日志文件
        log_files = list(log_dir.glob("search_*.jsonl"))
        for log_file in log_files:
            try:
                content = log_file.read_text(encoding="utf-8")
                for line in content.strip().split("\n"):
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        ts = entry.get("timestamp", "")
                        date_key = ts[:10] if ts else None
                        if date_key and date_key in daily_counts:
                            daily_counts[date_key]["count"] += 1
                            daily_counts[date_key]["total_latency"] += entry.get(
                                "latency_ms", 0
                            )
                    except json.JSONDecodeError:
                        continue
            except Exception as e:
                logger.warning("解析搜索日志条目失败: %s", e, exc_info=True)
                continue

        records = [
            {
                "date": k,
                "query_count": v["count"],
                "avg_latency_ms": round(v["total_latency"] / v["count"], 1)
                if v["count"] > 0
                else 0,
            }
            for k, v in sorted(daily_counts.items())
        ]

    except Exception as e:
        logger.warning(f"获取搜索日志统计失败: {e}")

    return records


def _get_uploads_stats() -> dict:
    """从 uploads 目录获取文件统计"""
    result = {
        "total_files": 0,
        "total_size_bytes": 0,
        "by_extension": {},
    }
    try:
        upload_dir = DATA_DIR / "uploads"
        if upload_dir.exists():
            extensions = {}
            total_bytes = 0
            total_files = 0
            for f in upload_dir.rglob("*"):
                if f.is_file():
                    total_files += 1
                    size = f.stat().st_size
                    total_bytes += size
                    ext = f.suffix.lower() or "无后缀"
                    if ext not in extensions:
                        extensions[ext] = {"count": 0, "size_bytes": 0}
                    extensions[ext]["count"] += 1
                    extensions[ext]["size_bytes"] += size
            result["total_files"] = total_files
            result["total_size_bytes"] = total_bytes
            result["by_extension"] = extensions
    except Exception as e:
        logger.warning(f"获取上传文件统计失败: {e}")

    return result


def _get_audit_stats() -> dict:
    """从 audit.db 获取审计/API 调用统计"""
    result = {
        "total_events": 0,
        "api_calls": {},
    }
    try:
        audit_path = DATA_DIR / "audit.db"
        if audit_path.exists():
            conn = sqlite3.connect(str(audit_path))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # 检查表结构
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cur.fetchall()]
            logger.debug(f"audit.db tables: {tables}")

            if "audit_events" in tables:
                cur.execute("SELECT COUNT(*) as cnt FROM audit_events")
                row = cur.fetchone()
                result["total_events"] = row["cnt"] if row else 0

                # 按端点聚合
                cur.execute(
                    "SELECT endpoint, COUNT(*) as cnt FROM audit_events "
                    "GROUP BY endpoint ORDER BY cnt DESC"
                )
                api_calls = {}
                for row in cur.fetchall():
                    api_calls[row["endpoint"]] = row["cnt"]
                result["api_calls"] = api_calls

            conn.close()
    except Exception as e:
        logger.warning(f"获取审计统计失败: {e}")

    return result


# ══════════════════════════════════════════════════
#  API 端点
# ══════════════════════════════════════════════════

# ── 健康检查 ──
@router.get("/health")
def health_check():
    """服务健康检查"""
    import platform
    from src.config import VERSION, START_TIME
    import time

    uptime_seconds = int(time.time() - START_TIME)

    return {
        "status": "ok",
        "service": "data-analytics",
        "version": "1.0.0",
        "platform_version": VERSION,
        "uptime_seconds": uptime_seconds,
        "python_version": platform.python_version(),
        "timestamp": datetime.now().isoformat(),
    }


# ── GET /api/analytics/stats 也支持（方便浏览器调试）──
@router.get("/stats")
def get_stats_get():
    """综合统计 (GET)"""
    return _build_stats()


# ── POST /api/analytics/stats — 综合统计 ──
@router.post("/stats")
def get_stats():
    """
    综合统计
    返回文档数、用户数、向量数、存储大小等综合信息
    """
    return _build_stats()


def _build_stats() -> dict:
    """构建综合统计数据"""
    chroma = _get_chroma_stats()
    chunks = _get_chunks_stats()
    users = _get_users_stats()
    uploads = _get_uploads_stats()
    audit = _get_audit_stats()

    return {
        "timestamp": datetime.now().isoformat(),
        "vectors": {
            "collections": chroma["collections"],
            "embeddings": chroma["embeddings"],
            "vectors_total": chroma["vectors_total"],
            "storage_size_bytes": chroma["storage_size_bytes"],
            "storage_size_mb": round(chroma["storage_size_bytes"] / (1024 * 1024), 2),
        },
        "documents": {
            "total_chunks": chunks["total_chunks"],
            "active_chunks": chunks["active_chunks"],
            "total_documents": chunks["total_documents"],
            "categories": chunks["categories"],
        },
        "users": {
            "total_users": users["total_users"],
            "active_users": users.get("active_users", 0),
            "roles": users.get("roles", {}),
        },
        "storage": {
            "total_files": uploads["total_files"],
            "total_size_bytes": uploads["total_size_bytes"],
            "total_size_mb": round(uploads["total_size_bytes"] / (1024 * 1024), 2),
        },
        "audit": {
            "total_events": audit["total_events"],
            "api_calls": audit.get("api_calls", {}),
        },
    }


# ── POST /api/analytics/trends — 趋势数据 ──
@router.post("/trends")
def get_trends(request: TrendsRequest):
    """
    趋势数据
    按日/周/月维度返回文档增长、查询量、API 调用量
    """
    period = request.period
    if period not in ("day", "week", "month"):
        raise HTTPException(400, "period 必须是 day / week / month 之一")

    search_logs = _get_search_logs_stats(request.start_date, request.end_date)

    # 按维度聚合
    if period == "month":
        aggregated = {}
        for entry in search_logs:
            month_key = entry["date"][:7]  # YYYY-MM
            if month_key not in aggregated:
                aggregated[month_key] = {
                    "period": month_key,
                    "query_count": 0,
                    "total_latency": 0.0,
                }
            aggregated[month_key]["query_count"] += entry["query_count"]
            aggregated[month_key]["total_latency"] += entry["avg_latency_ms"] * entry["query_count"]
        records = []
        for v in aggregated.values():
            records.append({
                "period": v["period"],
                "query_count": v["query_count"],
                "avg_latency_ms": round(
                    v["total_latency"] / v["query_count"], 1
                ) if v["query_count"] > 0 else 0,
            })
        records.sort(key=lambda x: x["period"])
    elif period == "week":
        aggregated = {}
        for entry in search_logs:
            dt = datetime.strptime(entry["date"], "%Y-%m-%d")
            iso_week = dt.isocalendar()
            week_key = f"{iso_week[0]}-W{iso_week[1]:02d}"
            if week_key not in aggregated:
                aggregated[week_key] = {
                    "period": week_key,
                    "query_count": 0,
                    "total_latency": 0.0,
                }
            aggregated[week_key]["query_count"] += entry["query_count"]
            aggregated[week_key]["total_latency"] += entry["avg_latency_ms"] * entry["query_count"]
        records = []
        for v in aggregated.values():
            records.append({
                "period": v["period"],
                "query_count": v["query_count"],
                "avg_latency_ms": round(
                    v["total_latency"] / v["query_count"], 1
                ) if v["query_count"] > 0 else 0,
            })
        records.sort(key=lambda x: x["period"])
    else:
        records = [
            {
                "period": e["date"],
                "query_count": e["query_count"],
                "avg_latency_ms": e["avg_latency_ms"],
            }
            for e in search_logs
        ]

    # 获取 chunk 创建趋势（按日聚合）
    chunk_trends = _get_chunk_creation_trends(request.start_date, request.end_date)

    return {
        "timestamp": datetime.now().isoformat(),
        "period": period,
        "queries": records,
        "documents": chunk_trends,
        "total_days": len(search_logs) if search_logs else 0,
    }


def _get_chunk_creation_trends(start_date: Optional[str] = None, end_date: Optional[str] = None) -> list:
    """从 chunks.db 提取文档创建趋势"""
    from src.config import CHUNKS_DB_PATH

    records = []
    try:
        db_path = Path(CHUNKS_DB_PATH)
        if not db_path.exists():
            return records

        if not end_date:
            end_dt = datetime.now()
        else:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        if not start_date:
            start_dt = end_dt - timedelta(days=30)
        else:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")

        # 初始化每天
        daily = {}
        current = start_dt
        while current <= end_dt:
            key = current.strftime("%Y-%m-%d")
            daily[key] = 0
            current += timedelta(days=1)

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT DATE(created_at) as d, COUNT(*) as cnt FROM chunks "
            "WHERE created_at IS NOT NULL "
            "GROUP BY DATE(created_at) ORDER BY d"
        )
        for row in cur.fetchall():
            d = row["d"]
            if d in daily:
                daily[d] += row["cnt"]
        conn.close()

        records = [
            {"date": k, "new_documents": v}
            for k, v in sorted(daily.items())
        ]

    except Exception as e:
        logger.warning(f"获取 chunk 趋势失败: {e}")

    return records


# ── POST /api/analytics/report — 统计报表 ──
@router.post("/report")
def generate_report(request: ReportRequest):
    """
    生成统计报表
    返回结构化数据供前端渲染
    """
    report_type = request.report_type
    if report_type not in ("summary", "detailed"):
        raise HTTPException(400, "report_type 必须是 summary / detailed")

    base_stats = _build_stats()
    report = {
        "generated_at": datetime.now().isoformat(),
        "report_type": report_type,
        "period": request.period,
        "summary": {
            "total_documents": base_stats["documents"]["total_documents"],
            "total_chunks": base_stats["documents"]["total_chunks"],
            "active_chunks": base_stats["documents"]["active_chunks"],
            "total_users": base_stats["users"]["total_users"],
            "vector_collections": base_stats["vectors"]["collections"],
            "vector_embeddings": base_stats["vectors"]["embeddings"],
            "storage_mb": base_stats["vectors"]["storage_size_mb"],
        },
    }

    if report_type == "detailed":
        report["details"] = {
            "document_categories": base_stats["documents"]["categories"],
            "storage_by_extension": {},
            "api_usage": base_stats.get("audit", {}).get("api_calls", {}),
            "queries_trend": _get_search_logs_stats(),
            "chunk_trend": _get_chunk_creation_trends(),
        }
        # 添加上传文件扩展名分布
        uploads = _get_uploads_stats()
        report["details"]["storage_by_extension"] = uploads["by_extension"]

    return report


# ── POST /api/analytics/storage — 存储分布 ──
@router.post("/storage")
def get_storage_distribution():
    """
    存储分布
    按文档类型、按用户等维度展示存储分布
    """
    chunks = _get_chunks_stats()
    uploads = _get_uploads_stats()

    # 按文档类型（后缀名）
    extensions = []
    for ext, info in sorted(
        uploads["by_extension"].items(),
        key=lambda x: x[1]["size_bytes"],
        reverse=True,
    ):
        extensions.append({
            "extension": ext,
            "file_count": info["count"],
            "size_bytes": info["size_bytes"],
            "size_mb": round(info["size_bytes"] / (1024 * 1024), 2),
        })

    # 按类别
    categories = [
        {"category": cat, "chunk_count": count}
        for cat, count in sorted(
            chunks["categories"].items(), key=lambda x: x[1], reverse=True
        )
    ]

    # 向量存储大小
    chroma = _get_chroma_stats()

    return {
        "timestamp": datetime.now().isoformat(),
        "by_extension": extensions,
        "by_category": categories,
        "vector_storage": {
            "size_bytes": chroma["storage_size_bytes"],
            "size_mb": round(chroma["storage_size_bytes"] / (1024 * 1024), 2),
            "collections": chroma["collections"],
            "embeddings": chroma["embeddings"],
        },
        "total_uploads_size_mb": round(uploads["total_size_bytes"] / (1024 * 1024), 2),
    }


# ── POST /api/analytics/export — 导出 CSV ──
@router.post("/export")
def export_report(request: ExportRequest):
    """
    导出统计报表为 CSV 格式
    """
    if request.format != "csv":
        raise HTTPException(400, "目前仅支持 csv 格式导出")

    report_type = request.report_type
    if report_type not in ("summary", "detailed"):
        raise HTTPException(400, "report_type 必须是 summary / detailed")

    output = io.StringIO()
    writer = csv.writer(output)

    stats = _build_stats()

    # 写入 BOM 以支持 Excel 打开中文
    output.write("\ufeff")

    # ── 综合统计 ──
    writer.writerow(["=== 综合统计 ==="])
    writer.writerow(["指标", "数值"])
    writer.writerow(["总文档数", stats["documents"]["total_documents"]])
    writer.writerow(["总分块数", stats["documents"]["total_chunks"]])
    writer.writerow(["活跃分块", stats["documents"]["active_chunks"]])
    writer.writerow(["用户数", stats["users"]["total_users"]])
    writer.writerow(["向量集合数", stats["vectors"]["collections"]])
    writer.writerow(["向量嵌入数", stats["vectors"]["embeddings"]])
    writer.writerow(["向量存储大小(MB)", stats["vectors"]["storage_size_mb"]])
    writer.writerow(["上传文件数", stats["storage"]["total_files"]])
    writer.writerow(["上传存储大小(MB)", stats["storage"]["total_size_mb"]])
    writer.writerow(["审计事件数", stats.get("audit", {}).get("total_events", 0)])
    writer.writerow([])

    if report_type == "detailed":
        # ── 文档分类 ──
        writer.writerow(["=== 文档分类分布 ==="])
        writer.writerow(["类别", "分块数"])
        for cat, cnt in stats["documents"]["categories"].items():
            writer.writerow([cat, cnt])
        writer.writerow([])

        # ── API 调用 ──
        api_calls = stats.get("audit", {}).get("api_calls", {})
        if api_calls:
            writer.writerow(["=== API 调用统计 ==="])
            writer.writerow(["端点", "调用次数"])
            for endpoint, cnt in sorted(api_calls.items(), key=lambda x: x[1], reverse=True):
                writer.writerow([endpoint, cnt])
            writer.writerow([])

        # ── 上传文件扩展名 ──
        uploads = _get_uploads_stats()
        if uploads["by_extension"]:
            writer.writerow(["=== 上传文件类型分布 ==="])
            writer.writerow(["扩展名", "文件数", "大小(MB)"])
            for ext, info in sorted(
                uploads["by_extension"].items(),
                key=lambda x: x[1]["size_bytes"],
                reverse=True,
            ):
                writer.writerow([
                    ext,
                    info["count"],
                    round(info["size_bytes"] / (1024 * 1024), 2),
                ])
            writer.writerow([])

        # ── 搜索趋势 ──
        search_logs = _get_search_logs_stats()
        if search_logs:
            writer.writerow(["=== 搜索查询趋势 (最近30天) ==="])
            writer.writerow(["日期", "查询数", "平均延迟(ms)"])
            for entry in search_logs:
                writer.writerow([
                    entry["date"],
                    entry["query_count"],
                    entry["avg_latency_ms"],
                ])
            writer.writerow([])

    csv_content = output.getvalue()

    from fastapi.responses import Response
    return Response(
        content=csv_content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="analytics_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
            ),
        },
    )


# ── POST /api/analytics/storage 也支持 GET（方便调试）──
@router.get("/storage")
async def get_storage_distribution_get():
    """存储分布 (GET)"""
    return await get_storage_distribution()


@router.get("/report")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def generate_report_get(
    report_type: str = Query("summary", description="summary / detailed"),
    period: str = Query("month", description="today / week / month / all"),
):
    """统计报表 (GET)"""
    return await generate_report(
        ReportRequest(report_type=report_type, period=period)
    )


@router.get("/trends")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def get_trends_get(
    period: str = Query("day", description="day / week / month"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """趋势数据 (GET)"""
    return await get_trends(
        TrendsRequest(period=period, start_date=start_date, end_date=end_date)
    )


@router.get("/export")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def export_report_get(
    format: str = Query("csv"),
    report_type: str = Query("summary"),
):
    """导出报表 (GET)"""
    return await export_report(
        ExportRequest(format=format, report_type=report_type)
    )
