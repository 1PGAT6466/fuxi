"""
调度器 API 路由 (Scheduler Routes)
===================================
伏羲自运转调度器的管理 API：
  - GET  /api/ops/scheduler/jobs           — 任务列表
  - GET  /api/ops/scheduler/jobs/{job_id}  — 任务详情
  - POST /api/ops/scheduler/jobs/{job_id}/run — 手动触发
  - GET  /api/ops/scheduler/jobs/{job_id}/history — 执行历史
"""

import logging

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger("fuxi.scheduler.api")

router = APIRouter(prefix="/api/ops/scheduler", tags=["调度器"])


def _get_scheduler():
    """延迟获取调度器实例（从 app.state）"""
    from src.autonomous.scheduler.engine import FuxiScheduler

    # 全局单例，由 startup 设置
    return _scheduler_instance


_scheduler_instance = None


def set_scheduler_instance(scheduler):
    """由 startup 调用，设置全局调度器实例"""
    global _scheduler_instance
    _scheduler_instance = scheduler


@router.get("/jobs")
async def list_jobs():
    """获取所有调度任务列表"""
    scheduler = _get_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="调度器未初始化")
    jobs = scheduler.list_jobs()
    return {"status": "ok", "count": len(jobs), "jobs": jobs}


@router.get("/jobs/{job_id}")
async def get_job_detail(job_id: str):
    """获取单个任务详情"""
    scheduler = _get_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="调度器未初始化")
    job = scheduler.get_job_detail(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"任务 {job_id} 不存在")
    return {"status": "ok", "job": job}


@router.post("/jobs/{job_id}/run")
async def trigger_job(job_id: str):
    """手动触发任务执行"""
    scheduler = _get_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="调度器未初始化")
    result = await scheduler.trigger_job(job_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.get("/jobs/{job_id}/history")
async def get_job_history(
    job_id: str,
    limit: int = Query(default=50, ge=1, le=500, description="返回记录数"),
):
    """获取任务执行历史"""
    scheduler = _get_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="调度器未初始化")
    # 检查任务是否存在
    job = scheduler.get_job_detail(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"任务 {job_id} 不存在")
    history = scheduler.get_job_history(job_id, limit)
    return {"status": "ok", "job_id": job_id, "count": len(history), "history": history}
