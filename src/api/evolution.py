import asyncio
"""
伏羲 v1.50 — 进化路由（真实数据版）
数据来源：Dream Cycle 日报 + 系统指标
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(tags=["进化"])

# Dream Cycle 日报存储路径
_DREAM_REPORT_DIR = Path(
    os.environ.get(
        "DREAM_CYCLE_REPORT_DIR",
        os.path.join(os.path.dirname(__file__), "..", "data", "dream_reports"),
    )
)
_DREAM_REPORT_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/api/evolution/overview")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def evolution_overview(request: Request = None):
    """进化概览 — v1.50 真实数据版

    返回：
      - Dream Cycle 最近运行状态
      - 系统进化指标（chunks 增长、向量数）
      - 实时 knowledge graph 统计
    """
    try:
        from src.db.data_store import load_chunks
        from src.db.vector_store import get_vector_store

        chunks = await asyncio.to_thread(load_chunks) or []
        unique_files = len(set(c.get("file_name", "") for c in chunks if c.get("file_name")))

        vs = get_vector_store()
        vector_count = 0
        if vs:
            try:
                vector_count = vs.count
                if vector_count < 0:
                    vector_count = 0
            except Exception:  # TODO: Narrow exception type
                pass

        # 知识图谱统计
        graph_nodes = 0
        graph_edges = 0
        try:
            from src.taiyang.graph import get_graph_stats
            stats = get_graph_stats()
            graph_nodes = stats.get("nodes_count", 0)
            graph_edges = stats.get("edges_count", 0)
        except ImportError:
            pass
        except Exception:  # TODO: Narrow exception type
            pass

        # Dream Cycle 状态
        dream_status = _get_dream_cycle_status()

        data = {
            "evolution": {
                "total_chunks": len(chunks),
                "unique_files": unique_files,
                "vector_count": vector_count,
                "graph_nodes": graph_nodes,
                "graph_edges": graph_edges,
                "dream_cycle": dream_status,
                "generated_at": time.time(),
            }
        }

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data=data, message="进化概览")
        return data
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"evolution_overview 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


def _get_dream_cycle_status() -> dict:
    """获取 Dream Cycle 的实际运行状态"""
    report_files = list(_DREAM_REPORT_DIR.glob("dream_data_*.json"))
    report_count = len(report_files)

    if report_count == 0:
        return {
            "status": "never_run",
            "report_count": 0,
            "last_run": None,
            "hint": "Dream Cycle 尚未执行。每晚 02:00 自动运行，或手动触发 POST /api/evolution/dream-cycle/run。",
        }

    # 读取最新报告
    latest = sorted(report_files, reverse=True)[0]
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
        timestamp = data.get("timestamp", "")
        results = data.get("results", {})

        # v1.50 修复: 验证报告数据与数据库是否一致
        is_consistent = True
        try:
            from src.db.data_store import load_chunks
            _chunks = await asyncio.to_thread(load_chunks)
            actual_chunks = len(_chunks or [])
            claimed_docs = results.get("digest", {}).get("total_docs", 0)
            if actual_chunks < 100 and claimed_docs > 100:
                is_consistent = False
        except Exception:  # TODO: Narrow exception type
            pass

        return {
            "status": "running" if report_count > 0 else "never_run",
            "report_count": report_count,
            "last_run": timestamp,
            "last_report": latest.stem,
            "data_consistent": is_consistent,
            "note": "报告数据与数据库一致" if is_consistent else "报告中的数字与实际数据库不符，可能为占位数据",
            "summary": {
                "digest_new_docs": results.get("digest", {}).get("new_docs", 0),
                "digest_embedded": results.get("digest", {}).get("embedded", 0),
                "gap_queries": results.get("gap_scan", {}).get("gap_queries", 0),
            },
        }
    except Exception as e:  # TODO: Narrow exception type
        logger.warning(f"解析 Dream 报告失败: {e}")
        return {
            "status": "error",
            "report_count": report_count,
            "last_run": str(latest),
            "error": str(e),
        }


@router.post("/api/evolution/dream-cycle/run")
async def trigger_dream_cycle():
    """手动触发 Dream Cycle — 执行真实消化循环"""
    try:
        from src.evolution.dream_cycle import DreamCycle

        dc = DreamCycle()
        report = await dc.run()

        return {
            "ok": True,
            "message": "Dream Cycle 执行完成",
            "report": report,
        }
    except ImportError as e:
        logger.error(f"DreamCycle 导入失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "DreamCycle 模块不可用", "detail": str(e)},
        )
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"DreamCycle 执行失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "DreamCycle 执行失败", "detail": str(e)},
        )


@router.get("/api/evolution/dream-cycle/report")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def get_latest_report():
    """获取最新 Dream Cycle 日报 — 从文件系统读取真实日报"""
    try:
        report_files = sorted(
            _DREAM_REPORT_DIR.glob("dream_report_*.md"),
            reverse=True,
        )
        data_files = sorted(
            _DREAM_REPORT_DIR.glob("dream_data_*.json"),
            reverse=True,
        )

        if not report_files:
            return {
                "ok": True,
                "has_report": False,
                "message": "暂无日报。Dream Cycle 每晚 02:00 自动运行，或手动触发 POST /api/evolution/dream-cycle/run。",
            }

        latest_report = report_files[0]
        report_content = latest_report.read_text(encoding="utf-8")

        response = {
            "ok": True,
            "has_report": True,
            "report": report_content,
            "file": str(latest_report),
            "generated_at": latest_report.stem.replace("dream_report_", ""),
        }

        if data_files:
            try:
                data = json.loads(data_files[0].read_text(encoding="utf-8"))
                response["metadata"] = {
                    k: v for k, v in data.items()
                    if k not in ("results", "report_path")
                }
                results = data.get("results", {})
                response["summary"] = {
                    "digest_new_docs": results.get("digest", {}).get("new_docs", 0),
                    "digest_embedded": results.get("digest", {}).get("embedded", 0),
                    "enrich_enriched": results.get("enrich", {}).get("enriched", 0),
                    "consolidate_duplicates": results.get("consolidate", {}).get("duplicates_found", 0),
                    "gap_queries": results.get("gap_scan", {}).get("gap_queries", 0),
                }

                # v1.50: 检查数据一致性
                try:
                    from src.db.data_store import load_chunks
                    _chunks2 = await asyncio.to_thread(load_chunks)
                    actual = len(_chunks2 or [])
                    claimed_total = results.get("digest", {}).get("total_docs", 0)
                    if actual < 100 and claimed_total > 100:
                        response["data_warning"] = (
                            f'报告声称 {claimed_total} 个文档，但数据库实际只有 {actual} 条 chunk。'
                            f'此报告数据为占位值，并非真实的演化结果。'
                        )
                except Exception:  # TODO: Narrow exception type
                    pass

            except Exception as e:  # TODO: Narrow exception type
                logger.debug("读取日报 JSON 数据失败: %s", e)

        return response

    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"获取日报失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "获取日报失败", "detail": str(e)},
        )


@router.get("/api/evolution/dream-cycle/history")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def get_report_history(limit: int = 30):
    """获取 Dream Cycle 日报历史"""
    try:
        data_files = sorted(
            _DREAM_REPORT_DIR.glob("dream_data_*.json"),
            reverse=True,
        )

        history = []
        for df in data_files[:limit]:
            try:
                data = json.loads(df.read_text(encoding="utf-8"))
                timestamp = data.get("timestamp", "")
                results = data.get("results", {})

                entry = {
                    "timestamp": timestamp,
                    "report_file": data.get("report_path", ""),
                    "data_file": str(df),
                    "summary": {
                        "digest_new_docs": results.get("digest", {}).get("new_docs", 0),
                        "digest_embedded": results.get("digest", {}).get("embedded", 0),
                        "enrich_enriched": results.get("enrich", {}).get("enriched", 0),
                        "consolidate_duplicates": results.get("consolidate", {}).get("duplicates_found", 0),
                        "gap_queries": results.get("gap_scan", {}).get("gap_queries", 0),
                    },
                    "errors": [
                        err
                        for cat_results in results.values()
                        if isinstance(cat_results, dict)
                        for err in cat_results.get("errors", [])
                    ],
                }
                history.append(entry)
            except Exception as e:  # TODO: Narrow exception type
                logger.debug("解析日报历史 %s 失败: %s", df, e)

        return {
            "ok": True,
            "total": len(history),
            "history": history,
        }

    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"获取日报历史失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "获取日报历史失败", "detail": str(e)},
        )
