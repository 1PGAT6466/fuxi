# v2.1 — 评测路由（完整版）
# 路径对齐：前端 EvaluationView.vue 调用 /api/evaluation/{datasets,tasks,results}
# 本模块为这些端点提供完整实现
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["评测"])

@router.get("/api/evaluation/overview")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def evaluation_overview(request: Request = None):
    """评测概览"""
    try:
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"search_stats": {}, "rag_eval": {}, "test_cases_count": 0}, message="评测概览")
        return {"search_stats": {}, "rag_eval": {}, "test_cases_count": 0}
    except Exception as e:
        logger.exception(f"evaluation_overview 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})

# ============ v2.1 新增：数据集、任务、结果端点 ============
# 前端 EvaluationView.vue 调用 /api/evaluation/datasets, /tasks, /results

@router.get("/api/evaluation/datasets")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def evaluation_datasets(request: Request = None):
    """评测数据集列表"""
    try:
        from src.services.eval_automation import get_eval_automation
        automation = get_eval_automation()
        history = await automation.get_eval_history()
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"datasets": history or []}, message="数据集列表")
        return {"datasets": history or []}
    except Exception as e:
        logger.exception(f"evaluation_datasets 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})

@router.get("/api/evaluation/tasks")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def evaluation_tasks(request: Request = None):
    """评测任务列表"""
    try:
        from src.services.eval_automation import get_eval_automation
        automation = get_eval_automation()
        history = await automation.get_eval_history()
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"tasks": history or []}, message="任务列表")
        return {"tasks": history or []}
    except Exception as e:
        logger.exception(f"evaluation_tasks 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})

@router.get("/api/evaluation/results")
# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def evaluation_results(request: Request = None):
    """评测结果列表"""
    try:
        from src.services.eval_automation import get_eval_automation
        automation = get_eval_automation()
        report = await automation.get_latest_report()
        history = await automation.get_eval_history()
        _wants_v2 = request and (request.query_params.get("format") == "v2" or request.headers.get("X-API-Format", "").lower() == "v2")
        if _wants_v2:
            from src.api.response import success
            return success(data={"results": history or [], "latest_report": report}, message="结果列表")
        return {"results": history or [], "latest_report": report}
    except Exception as e:
        logger.exception(f"evaluation_results 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})

@router.post("/api/evaluation")
async def evaluation_create(request: Request):
    """创建评测任务"""
    try:
        body = await request.json()
        logger.info(f"[evaluation] 创建评测请求: {body}")
        # 触发评测运行
        from src.services.eval_automation import get_eval_automation
        automation = get_eval_automation()
        result = await automation.run_daily_eval()
        return {"ok": True, "result": result}
    except Exception as e:
        logger.exception(f"evaluation_create 失败: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(e)})
