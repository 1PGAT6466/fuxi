# 兼容层 - 进化路由
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(tags=["进化"])

# ==================== v1.50 Phase C: Dream Cycle 日报存储路径 ====================
_DREAM_REPORT_DIR = Path(
    os.environ.get(
        "DREAM_CYCLE_REPORT_DIR",
        os.path.join(os.path.dirname(__file__), "..", "data", "dream_reports"),
    )
)
_DREAM_REPORT_DIR.mkdir(parents=True, exist_ok=True)


# ==================== 基础端点 ====================

@router.get("/api/evolution/overview")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def evolution_overview(request: Request = None):
    """进化概览"""
    try:
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"evolution": {}}, message="进化概览")
        return {"evolution": {}}
    except Exception as e:
        logger.exception(f"evolution_overview 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})


# ==================== v1.50 Phase C: Dream Cycle API ====================

@router.post("/api/evolution/dream-cycle/run")
async def trigger_dream_cycle():
    """手动触发 Dream Cycle 消化循环

    立即运行一次完整的消化循环（digest -> enrich -> consolidate -> gap_scan），
    返回生成的日报内容。

    正常情况下由 EasyClaw cron 每夜 02:00 自动触发。
    """
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
    except Exception as e:
        logger.exception(f"DreamCycle 执行失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "DreamCycle 执行失败", "detail": str(e)},
        )


@router.get("/api/evolution/dream-cycle/report")
async def get_latest_report():
    """获取最新的 Dream Cycle 日报

    Returns:
        JSON: 包含最新日报的 Markdown 内容和元数据
    """
    try:
        # 查找最新的日报文件
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
                "message": "暂无日报，请先运行 /api/evolution/dream-cycle/run",
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

        # 附上 JSON 数据
        if data_files:
            try:
                data = json.loads(data_files[0].read_text(encoding="utf-8"))
                response["metadata"] = {
                    k: v for k, v in data.items()
                    if k not in ("results", "report_path")
                }
                # 摘要：提取各阶段计数
                results = data.get("results", {})
                response["summary"] = {
                    "digest_new_docs": results.get("digest", {}).get("new_docs", 0),
                    "digest_embedded": results.get("digest", {}).get("embedded", 0),
                    "enrich_enriched": results.get("enrich", {}).get("enriched", 0),
                    "consolidate_duplicates": results.get("consolidate", {}).get("duplicates_found", 0),
                    "gap_queries": results.get("gap_scan", {}).get("gap_queries", 0),
                }
            except Exception as e:
                logger.debug("读取日报 JSON 数据失败: %s", e)

        return response

    except Exception as e:
        logger.exception(f"获取日报失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "获取日报失败", "detail": str(e)},
        )


@router.get("/api/evolution/dream-cycle/history")
async def get_report_history(limit: int = 30):
    """获取 Dream Cycle 日报历史列表

    Args:
        limit: 返回条数上限（默认 30）

    Returns:
        JSON: 日报历史列表，包含文件路径和生成时间
    """
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
            except Exception as e:
                logger.debug("解析日报历史 %s 失败: %s", df, e)

        return {
            "ok": True,
            "total": len(history),
            "history": history,
        }

    except Exception as e:
        logger.exception(f"获取日报历史失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "获取日报历史失败", "detail": str(e)},
        )
