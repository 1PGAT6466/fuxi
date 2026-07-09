"""
伏羲 v1.50 — 评测路由（真实数据版）
数据来源：eval_automation + 数据目录
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging
import json
import time
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(tags=["评测"])

# 评测数据路径
from src.config import DATA_DIR as CONFIG_DATA_DIR

EVAL_DIR = Path(CONFIG_DATA_DIR) / "evaluation"
REPORT_DIR = EVAL_DIR / "reports"


def _get_real_search_stats() -> dict:
    """从运行时指标获取真实搜索统计数据"""
    try:
        from src.infra.request_metrics import get_request_metrics
        metrics = get_request_metrics()
        return {
            "total_searches": metrics.total_requests or 0,
            "avg_results": 0,  # 需要额外追踪
            "avg_latency_ms": round(getattr(metrics, 'avg_latency_ms', 0) or 0, 1),
            "zero_result_rate": 0.0,
            "p50_latency_ms": 0,
        }
    except Exception:  # TODO: Narrow exception type
        return {
            "total_searches": 0,
            "avg_results": 0,
            "avg_latency_ms": 0,
            "zero_result_rate": 0.0,
            "p50_latency_ms": 0,
        }


def _get_rag_eval_status() -> dict:
    """获取 RAG 评测真实状态"""
    reports_exist = False
    report_count = 0
    last_report_time = None

    if REPORT_DIR.exists():
        report_files = list(REPORT_DIR.glob("*.json"))
        report_count = len(report_files)
        if report_count > 0:
            reports_exist = True
            latest = max(report_files, key=lambda f: f.stat().st_mtime)
            last_report_time = latest.stat().st_mtime

    if not reports_exist:
        return {
            "available": False,
            "status": "never_run",
            "test_cases": 0,
            "report_count": 0,
            "last_run": None,
            "hint": (
                "评测尚未执行。上传测试集并调用 POST /api/eval/run 启动评测，"
                "或通过管理面板手动触发。评测管线已就绪，等待首次运行。"
            ),
            "next_steps": [
                "1. 前往评测页面，选择数据集并运行评测",
                "2. 或通过 API: POST /api/eval/run 启动每日评测",
                "3. 评测结果将保存在 data/evaluation/reports/ 目录",
            ],
        }

    return {
        "available": True,
        "status": "completed",
        "test_cases": 0,
        "report_count": report_count,
        "last_run": last_report_time,
        "last_run_formatted": (
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_report_time))
            if last_report_time else None
        ),
    }


@router.get("/api/evaluation/overview")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def evaluation_overview(request: Request = None):
    """评测概览 — v1.50 真实数据版

    返回真实的搜索统计（来自运行时指标）和评测状态。
    如果评测从未执行，返回"never_run"状态和操作引导。
    """
    try:
        search_stats = _get_real_search_stats()
        rag_eval = _get_rag_eval_status()

        # 测试用例计数：从 ground_truth 文件获取
        test_cases_count = 0
        try:
            from src.services.eval_dataset import get_ground_truth
            gt = get_ground_truth()
            if gt and isinstance(gt, list):
                test_cases_count = len(gt)
        except ImportError:
            pass
        except Exception:  # TODO: Narrow exception type
            pass

        data = {
            "search_stats": search_stats,
            "rag_eval": rag_eval,
            "test_cases_count": test_cases_count,
            "generated_at": time.time(),
            "status": rag_eval.get("status", "never_run"),
        }

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data=data, message="评测概览")
        return data
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"evaluation_overview 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


@router.get("/api/evaluation/datasets")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def evaluation_datasets(request: Request = None):
    """评测数据集列表 — v1.50 真实数据版

    从 ground_truth.json 和 eval_automation 获取真实数据。
    """
    try:
        from src.services.eval_automation import get_eval_automation
        automation = get_eval_automation()
        history = None
        try:
            import asyncio
            history = await automation.get_eval_history()
        except RuntimeError:
            try:
                loop = asyncio.get_event_loop()
                history = loop.run_until_complete(automation.get_eval_history())
            except Exception:  # TODO: Narrow exception type
                pass
        except Exception:  # TODO: Narrow exception type
            pass

        datasets = history or []

        # 如果仍为空，检查 ground_truth.json
        if not datasets:
            from src.services.eval_dataset import get_ground_truth
            try:
                gt = get_ground_truth()
                if gt and isinstance(gt, list) and len(gt) > 0:
                    datasets = [{
                        "id": "ground_truth",
                        "name": "基准测试集",
                        "test_count": len(gt),
                        "status": "ready",
                        "created_at": None,
                        "note": "评测尚未执行，数据集已就绪",
                    }]
            except ImportError:
                pass
            except Exception:  # TODO: Narrow exception type
                pass

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data={
                "datasets": datasets,
                "total": len(datasets),
                "hint": None if datasets else "暂无数据集。上传评测数据或导入 ground_truth.json。",
            }, message="数据集列表")
        return {"datasets": datasets, "total": len(datasets)}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"evaluation_datasets 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


@router.get("/api/evaluation/tasks")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def evaluation_tasks(request: Request = None):
    """评测任务列表 — v1.50 真实数据版"""
    try:
        from src.services.eval_automation import get_eval_automation
        automation = get_eval_automation()
        history = None
        try:
            import asyncio
            history = await automation.get_eval_history()
        except RuntimeError:
            try:
                loop = asyncio.get_event_loop()
                history = loop.run_until_complete(automation.get_eval_history())
            except Exception:  # TODO: Narrow exception type
                pass
        except Exception:  # TODO: Narrow exception type
            pass

        tasks = history or []

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data={
                "tasks": tasks,
                "hint": None if tasks else "暂无评测任务。前往评测页面创建第一个评测任务。",
            }, message="任务列表")
        return {"tasks": tasks, "hint": None if tasks else "暂无评测任务"}
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"evaluation_tasks 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


@router.get("/api/evaluation/results")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def evaluation_results(request: Request = None):
    """评测结果列表 — v1.50 真实数据版"""
    try:
        from src.services.eval_automation import get_eval_automation
        automation = get_eval_automation()

        report = history = None
        try:
            import asyncio
            report = await automation.get_latest_report()
            history = await automation.get_eval_history()
        except RuntimeError:
            try:
                loop = asyncio.get_event_loop()
                report = loop.run_until_complete(automation.get_latest_report())
                history = loop.run_until_complete(automation.get_eval_history())
            except Exception:  # TODO: Narrow exception type
                pass
        except Exception:  # TODO: Narrow exception type
            pass

        # 如果自动化没有报告，尝试从文件系统读取
        if not report:
            report = _load_latest_report_from_disk()

        results = history or []

        _wants_v2 = request and (
            request.query_params.get("format") == "v2"
            or request.headers.get("X-API-Format", "").lower() == "v2"
        )
        if _wants_v2:
            from src.api.response import success
            return success(data={
                "results": results,
                "latest_report": report,
                "hint": None if results else "暂无评测结果。执行评测后结果将显示在此处。",
            }, message="结果列表")
        return {
            "results": results,
            "latest_report": report,
            "hint": None if results else "暂无评测结果",
        }
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"evaluation_results 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


@router.post("/api/evaluation")
async def evaluation_create(request: Request):
    """创建评测任务 — 触发真实评测执行"""
    try:
        body = await request.json()
        logger.info(f"[evaluation] 创建评测请求: user={getattr(request.state, 'user', 'anonymous')}")

        from src.services.eval_automation import get_eval_automation
        automation = get_eval_automation()
        result = await automation.run_daily_eval()
        return {
            "ok": True,
            "result": result,
            "message": "评测已在后台启动，完成后可在评测结果页面查看",
        }
    except Exception as e:  # TODO: Narrow exception type
        logger.exception(f"evaluation_create 失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


def _load_latest_report_from_disk() -> dict:
    """从文件系统读取最新评测报告"""
    try:
        if not REPORT_DIR.exists():
            return None

        report_files = sorted(REPORT_DIR.glob("*.json"), reverse=True)
        if not report_files:
            return None

        latest = report_files[0]
        with open(latest, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # TODO: Narrow exception type
        return None
