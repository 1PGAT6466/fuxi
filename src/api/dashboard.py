"""
伏羲 v1.50 — 仪表板路由（真实数据版）
数据来源：真实数据库查询 + 运行时指标
"""

import asyncio
import json
import logging
import time

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

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
            except (AttributeError, OSError) as e:
                logger.debug("向量库统计跳过: %s", e)

        # 3. 搜索统计 —— 从运行时指标
        search_total = 0
        search_avg_latency_ms = 0
        try:
            from src.infra.request_metrics import get_request_metrics

            metrics = get_request_metrics()
            search_total = metrics.total_requests or 0
            if hasattr(metrics, "avg_latency_ms"):
                search_avg_latency_ms = round(metrics.avg_latency_ms, 1)
        except (ImportError, AttributeError, OSError) as e:
            logger.debug("搜索统计跳过: %s", e)

        # 4. 评测状态
        eval_status = "never_run"
        eval_last_run = None
        eval_report_count = 0
        try:
            from src.services.eval_automation import get_eval_automation

            automation = get_eval_automation()
            report = await automation.get_latest_report() if hasattr(automation, "get_latest_report") else None
            history = await automation.get_eval_history() if hasattr(automation, "get_eval_history") else []
            if report and report.get("timestamp"):
                eval_status = "completed"
                eval_last_run = report.get("timestamp")
            if history:
                eval_report_count = len(history)
        except (ImportError, AttributeError, OSError) as e:
            logger.debug("评测状态跳过: %s", e)

        # 5. 系统运行时间
        from src.config import VERSION

        uptime_seconds = 0.0
        born_at = getattr(request.app.state, "fuxi_born_at", None) if request else None
        if born_at:
            uptime_seconds = time.time() - born_at

        engine = getattr(request.app.state, "engine", "v2") if request else "v2"

        # 6. 数据洞察引擎 — 趋势/异常/洞察
        trends_data = {}
        anomalies_data = []
        insights_data = []
        try:
            from src.services.anomaly_detector import check_anomalies
            from src.services.insight_generator import generate_insights
            from src.services.trend_analyzer import get_all_trends

            trends_data = get_all_trends(7)
            anomalies_data = check_anomalies()
            insights_data = generate_insights(trends_data, anomalies_data)
            if isinstance(trends_data, Exception):
                logger.warning(f"趋势分析失败: {trends_data}")
                trends_data = {}
            if isinstance(anomalies_data, Exception):
                logger.warning(f"异常检测失败: {anomalies_data}")
                anomalies_data = []
            if isinstance(insights_data, Exception):
                logger.warning(f"洞察生成失败: {insights_data}")
                insights_data = []
        except Exception as e:
            logger.warning(f"数据洞察引擎初始化失败: {e}")

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
                        ("当前包含示例/测试数据（种子向量）。" "上传真实业务文档后将替换种子数据。")
                        if seed_chunks > 0
                        else None
                    ),
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
                        ("评测尚未执行。前往评测页面或调用 POST /api/eval/run 启动评测。")
                        if eval_status == "never_run"
                        else None
                    ),
                },
                # 系统
                "system": {
                    "version": VERSION,
                    "engine": engine,
                    "uptime_seconds": round(uptime_seconds, 1),
                    "uptime_formatted": _format_uptime(uptime_seconds),
                },
                # 数据洞察引擎
                "trends": trends_data,
                "anomalies": anomalies_data,
                "insights": insights_data,
            }
        }

        _wants_v2 = request and (
            request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success

            return success(data=data, message="仪表板数据")
        return data
    except (OSError, json.JSONDecodeError, KeyError, ValueError, AttributeError) as e:
        logger.exception(f"dashboard 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


@router.get("/api/dashboard/stats")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def dashboard_stats(request: Request = None):
    """仪表板统计摘要 — 返回统一格式 {status: success, data: {...}}"""
    try:
        import json as _json
        import sqlite3

        from src.api.response import success
        from src.config import BASE_DIR, DATA_DIR

        # 1. 文档/块统计 —— 从 chunks.db
        doc_count = 0
        chunk_count = 0
        categories: dict = {}
        try:
            from src.db.data_store import load_chunks

            chunks = await asyncio.to_thread(load_chunks) or []
            chunk_count = len(chunks)
            seen_files: set = set()
            for c in chunks:
                fhash = c.get("file_hash", "")
                if fhash:
                    seen_files.add(fhash)
                cat = c.get("category", "未分类")
                categories[cat] = categories.get(cat, 0) + 1
            doc_count = len(seen_files)
        except Exception as e:
            logger.warning(f"dashboard_stats load_chunks 失败: {e}")

        # 2. 向量统计 —— 从 ChromaDB
        vector_count = 0
        try:
            from src.db.vector_store import get_vector_store

            vs = get_vector_store()
            if vs:
                vector_count = vs.count
                if vector_count < 0:
                    vector_count = 0
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass

        # 3. 用户统计 —— 从 users.json
        total_users = 0
        try:
            users_path = DATA_DIR / "users.json"
            if users_path.exists():

                def _read_users():
                    return _json.loads(users_path.read_text(encoding="utf-8"))

                users_data = await asyncio.to_thread(_read_users)
                if isinstance(users_data, dict):
                    total_users = len(users_data)
                elif isinstance(users_data, list):
                    total_users = len(users_data)
        except Exception as e:
            logger.warning(f"dashboard_stats 读取 users.json 失败: {e}")

        # 4. 会话统计 —— 从 conversation_sessions.db
        total_sessions = 0
        try:
            sess_db = BASE_DIR / "conversation_sessions.db"
            if sess_db.exists():

                def _count_sessions():
                    conn = sqlite3.connect(str(sess_db))
                    try:
                        cur = conn.execute("SELECT COUNT(*) FROM conversations")
                        return cur.fetchone()[0]
                    finally:
                        conn.close()

                total_sessions = await asyncio.to_thread(_count_sessions)
        except Exception as e:
            logger.warning(f"dashboard_stats 读取 conversation_sessions.db 失败: {e}")

        # 5. Wiki 页面统计 —— 从 worldtree.db（wiki 已合并入 worldtree）
        total_wiki_pages = 0
        try:
            from src.config import WORLDTREE_DB_PATH

            if WORLDTREE_DB_PATH.exists():

                def _count_wiki():
                    conn = sqlite3.connect(str(WORLDTREE_DB_PATH))
                    try:
                        cur = conn.execute("SELECT COUNT(*) FROM wiki_pages")
                        return cur.fetchone()[0]
                    except sqlite3.OperationalError:
                        return 0
                    finally:
                        conn.close()

                total_wiki_pages = await asyncio.to_thread(_count_wiki)
        except Exception as e:
            logger.warning(f"dashboard_stats 读取 wiki 统计失败: {e}")

        # 6. API Keys 统计 —— 从 api_keys.json
        total_api_keys = 0
        try:
            api_keys_path = DATA_DIR / "api_keys.json"
            if api_keys_path.exists():

                def _read_api_keys():
                    return _json.loads(api_keys_path.read_text(encoding="utf-8"))

                api_keys_data = await asyncio.to_thread(_read_api_keys)
                if isinstance(api_keys_data, list):
                    total_api_keys = len(api_keys_data)
                elif isinstance(api_keys_data, dict):
                    total_api_keys = len(api_keys_data)
        except Exception as e:
            logger.warning(f"dashboard_stats 读取 api_keys.json 失败: {e}")

        # 7. Webhooks 统计 —— 从 webhooks.json
        total_webhooks = 0
        try:
            webhooks_path = DATA_DIR / "webhooks.json"
            if webhooks_path.exists():

                def _read_webhooks():
                    return _json.loads(webhooks_path.read_text(encoding="utf-8"))

                webhooks_data = await asyncio.to_thread(_read_webhooks)
                if isinstance(webhooks_data, list):
                    total_webhooks = len(webhooks_data)
                elif isinstance(webhooks_data, dict):
                    total_webhooks = len(webhooks_data)
        except Exception as e:
            logger.warning(f"dashboard_stats 读取 webhooks.json 失败: {e}")

        # 8. 系统信息
        from src.config import VERSION

        uptime_seconds = 0.0
        born_at = getattr(request.app.state, "fuxi_born_at", None) if request else None
        if born_at:
            uptime_seconds = time.time() - born_at

        return success(
            data={
                "total_documents": doc_count,
                "total_chunks": chunk_count,
                "total_vectors": vector_count,
                "total_users": total_users,
                "total_sessions": total_sessions,
                "total_wiki_pages": total_wiki_pages,
                "total_api_keys": total_api_keys,
                "total_webhooks": total_webhooks,
                "categories": categories,
                "version": VERSION,
                "uptime_seconds": round(uptime_seconds, 1),
                "uptime_formatted": _format_uptime(uptime_seconds),
            },
            message="仪表板统计",
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError, AttributeError) as e:
        logger.exception(f"dashboard_stats 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "获取仪表板统计失败", "detail": str(e)},
        )


@router.get("/api/dashboard/trends")
async def dashboard_trends(
    days: int = Query(7, ge=1, le=90, description="回溯天数"),
    period: str = Query("hour", description="聚合粒度: hour / day / week"),
    request: Request = None,
):
    """数据洞察 — 时间序列趋势

    返回各核心指标的时间序列数据及趋势方向。
    数据来源：请求指标日志、在线评测、反馈日志。

    Args:
        days:   回溯天数（默认 7）
        period: 聚合粒度（hour / day / week）

    Returns:
        {
            "status": "success",
            "data": {
                "trends": {
                    "latency_ms": {"values": [...], "direction": "up/down/flat", ...},
                    "error_rate": {...},
                    "qps": {...},
                    "search_score": {...},
                    "feedback_count": {...},
                },
                "generated_at": str,
            }
        }
    """
    try:
        from src.api.response import success
        from src.services.trend_analyzer import get_all_trends, get_trend

        metrics = ["latency_ms", "error_rate", "qps", "search_score", "feedback_count"]
        trends = {}
        for m in metrics:
            trends[m] = get_trend(m, days, period)

        return success(
            data={
                "trends": trends,
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
            message="时间序列趋势",
        )

    except (ImportError, OSError, json.JSONDecodeError) as e:
        logger.warning(f"dashboard_trends 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "获取趋势数据失败", "detail": str(e)},
        )


@router.get("/api/dashboard/anomalies")
async def dashboard_anomalies(request: Request = None) -> JSONResponse:
    """数据洞察 — 异常列表

    返回当前检测到的所有异常项，按严重程度排序。
    基于 Z-score 方法检测延迟异常、错误率异常、检索质量异常。

    Returns:
        {
            "status": "success",
            "data": {
                "anomalies": [
                    {
                        "metric": str,
                        "current": float,
                        "baseline": float,
                        "zscore": float,
                        "severity": "high/medium",
                        "message": str,
                        "recommendation": str,
                    },
                    ...
                ],
                "summary": {
                    "total": int,
                    "high_severity": int,
                    "medium_severity": int,
                    "status": "critical/warning/normal",
                },
                "checked_at": str,
            }
        }
    """
    try:
        from src.api.response import success
        from src.services.anomaly_detector import check_anomalies, get_anomaly_summary

        summary = get_anomaly_summary()

        return success(
            data={
                "anomalies": summary.get("anomalies", []),
                "summary": {
                    "total": summary.get("total", 0),
                    "high_severity": summary.get("high_severity", 0),
                    "medium_severity": summary.get("medium_severity", 0),
                    "status": summary.get("status", "normal"),
                },
                "checked_at": summary.get("checked_at", time.strftime("%Y-%m-%d %H:%M:%S")),
            },
            message="异常检测结果",
        )

    except (ImportError, OSError, json.JSONDecodeError) as e:
        logger.warning(f"dashboard_anomalies 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "获取异常数据失败", "detail": str(e)},
        )


@router.get("/api/dashboard/insights")
async def dashboard_insights(
    days: int = Query(7, ge=1, le=90, description="趋势分析回溯天数"),
    request: Request = None,
):
    """数据洞察 — 洞察建议

    综合趋势和异常数据，生成可行动的自然语言洞察。
    不依赖 LLM，纯规则引擎，保证实时性。

    洞察类型：
      - summary: 总体健康评估
      - trend: 趋势洞察（指标变化方向和幅度）
      - anomaly: 异常洞察（偏离基线的指标）
      - recommendation: 建议洞察

    Args:
        days: 趋势分析回溯天数（默认 7）

    Returns:
        {
            "status": "success",
            "data": {
                "insights": [
                    {
                        "type": "summary/trend/anomaly/recommendation",
                        "severity": "critical/high/warning/info/healthy",
                        "title": str,
                        "description": str,
                        "recommendation": str,
                    },
                    ...
                ],
                "trends_summary": {...},
                "anomaly_count": int,
                "generated_at": str,
            }
        }
    """
    try:
        from src.api.response import success
        from src.services.anomaly_detector import check_anomalies
        from src.services.insight_generator import generate_insights, get_insights_summary
        from src.services.trend_analyzer import get_all_trends

        summary = get_insights_summary()

        return success(
            data={
                "insights": summary.get("insights", []),
                "trends_summary": summary.get("trends", {}),
                "anomaly_count": summary.get("anomaly_count", 0),
                "generated_at": summary.get("generated_at", time.strftime("%Y-%m-%d %H:%M:%S")),
            },
            message="洞察建议",
        )

    except (ImportError, OSError, json.JSONDecodeError) as e:
        logger.warning(f"dashboard_insights 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "获取洞察建议失败", "detail": str(e)},
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
