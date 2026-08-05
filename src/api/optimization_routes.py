"""
optimization_routes.py — 性能优化API
提供缓存管理、并行清洗、异步队列的API接口
"""

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/optimization", tags=["optimization"])


@router.get("/cache/stats")
async def get_cache_stats():
    """获取缓存统计信息"""
    try:
        from src.pipeline.parallel_cleaner import get_chunk_cache
        from src.services.llm import get_cache_stats

        llm_cache = get_cache_stats()
        chunk_cache = get_chunk_cache().get_cache_stats()

        return {"status": "success", "data": {"llm_cache": llm_cache, "chunk_cache": chunk_cache}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/clear")
async def clear_cache():
    """清空所有缓存"""
    try:
        from src.pipeline.parallel_cleaner import get_chunk_cache
        from src.services.llm import clear_cache

        clear_cache()
        get_chunk_cache().clear_cache()

        return {"status": "success", "message": "缓存已清空"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue/stats")
async def get_queue_stats():
    """获取任务队列统计信息"""
    try:
        from src.pipeline.async_queue import get_queue_stats

        return {"status": "success", "data": get_queue_stats()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue/tasks")
async def get_queue_tasks():
    """获取所有队列任务状态"""
    try:
        from src.pipeline.async_queue import get_task_queue

        queue = get_task_queue()
        return {"status": "success", "data": queue.get_all_tasks()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/queue/clean")
async def submit_clean_task(file_path: str, priority: int = 0):
    """提交单个文件清洗任务"""
    try:
        from src.pipeline.async_queue import submit_cleaning_task
        from src.pipeline.cleaners import UnifiedCleaner

        # 创建清洗函数
        cleaner = UnifiedCleaner()

        def clean_func(fp):
            with open(fp, "r", encoding="utf-8") as f:
                text = f.read()
            result = cleaner.clean({"text": text, "file_path": fp})
            return result

        task = await submit_cleaning_task(file_path, clean_func, priority)

        return {"status": "success", "data": task.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/queue/batch-clean")
async def submit_batch_clean_task(file_paths: List[str], priority: int = 0):
    """批量提交清洗任务"""
    try:
        from src.pipeline.async_queue import submit_batch_cleaning_tasks
        from src.pipeline.cleaners import UnifiedCleaner

        # 创建清洗函数
        cleaner = UnifiedCleaner()

        def clean_func(fp):
            with open(fp, "r", encoding="utf-8") as f:
                text = f.read()
            result = cleaner.clean({"text": text, "file_path": fp})
            return result

        tasks = await submit_batch_cleaning_tasks(file_paths, clean_func, priority)

        return {"status": "success", "data": [task.to_dict() for task in tasks]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue/task/{task_id}")
async def get_task_status(task_id: str):
    """获取指定任务状态"""
    try:
        from src.pipeline.async_queue import get_task_queue

        queue = get_task_queue()
        task = queue.get_task(task_id)

        if not task:
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

        return {"status": "success", "data": task.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/queue/cancel/{task_id}")
async def cancel_task(task_id: str):
    """取消任务"""
    try:
        from src.pipeline.async_queue import get_task_queue

        queue = get_task_queue()

        success = await queue.cancel_task(task_id)

        if not success:
            raise HTTPException(status_code=400, detail=f"无法取消任务: {task_id}")

        return {"status": "success", "message": f"任务已取消: {task_id}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_optimization_stats():
    """获取所有优化统计信息"""
    try:
        from src.pipeline.async_queue import get_queue_stats
        from src.pipeline.parallel_cleaner import get_chunk_cache, get_parallel_cleaner
        from src.services.llm import get_cache_stats

        return {
            "status": "success",
            "data": {
                "llm_cache": get_cache_stats(),
                "chunk_cache": get_chunk_cache().get_cache_stats(),
                "parallel_cleaner": get_parallel_cleaner().get_stats(),
                "task_queue": get_queue_stats(),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
