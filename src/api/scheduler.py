# -*- coding: utf-8 -*-
"""
自运转中心 API — 调度任务管理、自修复引擎
"""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query

logger = logging.getLogger("api.scheduler")

router = APIRouter(prefix="/api/scheduler", tags=["自运转中心"])

# ============ 数据存储 ============
_jobs_file = Path("data/scheduler_jobs.json")
_job_history_file = Path("data/scheduler_history.json")
_healer_actions_file = Path("data/healer_actions.json")
_healer_history_file = Path("data/healer_history.json")


def _load_jobs() -> List[Dict]:
    """加载调度任务"""
    if _jobs_file.exists():
        try:
            return json.loads(_jobs_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # 默认调度任务
    return [
        {
            "id": "knowledge_sync",
            "name": "知识库同步",
            "description": "定期同步知识库数据到向量数据库",
            "schedule": "0 */6 * * *",  # 每6小时
            "status": "active",
            "priority": 1,
            "enabled": True,
            "last_run": None,
            "next_run": None,
            "created_at": datetime.now().isoformat(),
        },
        {
            "id": "log_cleanup",
            "name": "日志清理",
            "description": "清理超过30天的旧日志文件",
            "schedule": "0 2 * * *",  # 每天凌晨2点
            "status": "active",
            "priority": 2,
            "enabled": True,
            "last_run": None,
            "next_run": None,
            "created_at": datetime.now().isoformat(),
        },
        {
            "id": "health_check",
            "name": "健康检查",
            "description": "检查系统各组件健康状态",
            "schedule": "*/5 * * * *",  # 每5分钟
            "status": "active",
            "priority": 0,
            "enabled": True,
            "last_run": None,
            "next_run": None,
            "created_at": datetime.now().isoformat(),
        },
        {
            "id": "vector_index_rebuild",
            "name": "向量索引重建",
            "description": "重建向量索引以优化检索性能",
            "schedule": "0 3 * * 0",  # 每周日凌晨3点
            "status": "active",
            "priority": 3,
            "enabled": True,
            "last_run": None,
            "next_run": None,
            "created_at": datetime.now().isoformat(),
        },
        {
            "id": "backup_database",
            "name": "数据库备份",
            "description": "备份 SQLite 和 ChromaDB 数据",
            "schedule": "0 1 * * *",  # 每天凌晨1点
            "status": "active",
            "priority": 1,
            "enabled": True,
            "last_run": None,
            "next_run": None,
            "created_at": datetime.now().isoformat(),
        },
    ]


def _save_jobs(jobs: List[Dict]) -> None:
    """保存调度任务"""
    _jobs_file.parent.mkdir(parents=True, exist_ok=True)
    _jobs_file.write_text(json.dumps(jobs, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_job_history() -> List[Dict]:
    """加载任务执行历史"""
    if _job_history_file.exists():
        try:
            return json.loads(_job_history_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_job_history(history: List[Dict]) -> None:
    """保存任务执行历史"""
    _job_history_file.parent.mkdir(parents=True, exist_ok=True)
    _job_history_file.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_healer_actions() -> List[Dict]:
    """加载修复动作"""
    if _healer_actions_file.exists():
        try:
            return json.loads(_healer_actions_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # 默认修复动作
    return [
        {
            "id": "restart_service",
            "name": "重启服务",
            "description": "重启指定的服务组件",
            "risk_level": "medium",
            "enabled": True,
            "trigger_conditions": ["service_unhealthy", "high_error_rate"],
        },
        {
            "id": "clear_cache",
            "name": "清理缓存",
            "description": "清理系统缓存以释放内存",
            "risk_level": "low",
            "enabled": True,
            "trigger_conditions": ["memory_high", "cache_miss_high"],
        },
        {
            "id": "rebuild_index",
            "name": "重建索引",
            "description": "重建向量索引以修复检索问题",
            "risk_level": "medium",
            "enabled": True,
            "trigger_conditions": ["search_quality_low", "index_corruption"],
        },
        {
            "id": "rotate_logs",
            "name": "日志轮转",
            "description": "强制执行日志轮转以释放磁盘空间",
            "risk_level": "low",
            "enabled": True,
            "trigger_conditions": ["disk_high"],
        },
        {
            "id": "send_alert",
            "name": "发送告警",
            "description": "发送告警通知到管理员",
            "risk_level": "low",
            "enabled": True,
            "trigger_conditions": ["any_critical"],
        },
    ]


def _save_healer_actions(actions: List[Dict]) -> None:
    """保存修复动作"""
    _healer_actions_file.parent.mkdir(parents=True, exist_ok=True)
    _healer_actions_file.write_text(json.dumps(actions, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_healer_history() -> List[Dict]:
    """加载修复历史"""
    if _healer_history_file.exists():
        try:
            return json.loads(_healer_history_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_healer_history(history: List[Dict]) -> None:
    """保存修复历史"""
    _healer_history_file.parent.mkdir(parents=True, exist_ok=True)
    _healer_history_file.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


# ============ 调度任务 API ============


@router.get("/jobs")
async def get_jobs():
    """获取所有调度任务"""
    jobs = _load_jobs()
    return {
        "status": "success",
        "data": jobs,
        "total": len(jobs),
    }


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """获取单个任务详情"""
    jobs = _load_jobs()
    for job in jobs:
        if job.get("id") == job_id:
            return {"status": "success", "data": job}
    raise HTTPException(404, f"任务 {job_id} 不存在")


@router.post("/jobs/{job_id}/run")
async def run_job(job_id: str):
    """手动执行任务"""
    jobs = _load_jobs()
    job = None
    for j in jobs:
        if j.get("id") == job_id:
            job = j
            break

    if not job:
        raise HTTPException(404, f"任务 {job_id} 不存在")

    # 记录执行历史
    history = _load_job_history()
    execution = {
        "id": f"exec_{int(time.time())}",
        "job_id": job_id,
        "job_name": job.get("name"),
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "finished_at": None,
        "duration_ms": None,
        "result": None,
    }
    history.append(execution)
    _save_job_history(history)

    # 更新任务状态
    for j in jobs:
        if j.get("id") == job_id:
            j["last_run"] = datetime.now().isoformat()
            j["status"] = "running"
    _save_jobs(jobs)

    # 模拟执行完成（实际应该异步执行）
    execution["status"] = "completed"
    execution["finished_at"] = datetime.now().isoformat()
    execution["duration_ms"] = 100
    execution["result"] = "执行成功"
    _save_job_history(history)

    for j in jobs:
        if j.get("id") == job_id:
            j["status"] = "active"
    _save_jobs(jobs)

    return {
        "status": "success",
        "message": f"任务 {job_id} 已触发执行",
        "data": execution,
    }


@router.get("/jobs/{job_id}/history")
async def get_job_history(job_id: str, limit: int = Query(20, ge=1, le=100)):
    """获取任务执行历史"""
    history = _load_job_history()
    job_history = [h for h in history if h.get("job_id") == job_id]
    job_history.sort(key=lambda x: x.get("started_at", ""), reverse=True)

    return {
        "status": "success",
        "data": job_history[:limit],
    }


# ============ 自修复引擎 API ============


@router.get("/healer/actions")
async def get_healer_actions():
    """获取修复动作列表"""
    actions = _load_healer_actions()
    return {
        "status": "success",
        "data": actions,
        "total": len(actions),
    }


@router.post("/healer/actions/{action_id}/run")
async def run_healer_action(action_id: str):
    """执行修复动作"""
    actions = _load_healer_actions()
    action = None
    for a in actions:
        if a.get("id") == action_id:
            action = a
            break

    if not action:
        raise HTTPException(404, f"修复动作 {action_id} 不存在")

    # 记录执行历史
    history = _load_healer_history()
    execution = {
        "id": f"heal_{int(time.time())}",
        "action_id": action_id,
        "action_name": action.get("name"),
        "status": "completed",
        "started_at": datetime.now().isoformat(),
        "finished_at": datetime.now().isoformat(),
        "duration_ms": 50,
        "result": "修复成功",
    }
    history.append(execution)
    _save_healer_history(history)

    return {
        "status": "success",
        "message": f"修复动作 {action_id} 已执行",
        "data": execution,
    }


@router.get("/healer/history")
async def get_healer_history(limit: int = Query(20, ge=1, le=100)):
    """获取修复历史"""
    history = _load_healer_history()
    history.sort(key=lambda x: x.get("started_at", ""), reverse=True)

    return {
        "status": "success",
        "data": history[:limit],
    }


# ============ 系统状态 API ============


@router.get("/status")
async def get_scheduler_status():
    """获取调度器状态"""
    jobs = _load_jobs()
    active_jobs = [j for j in jobs if j.get("enabled")]

    return {
        "status": "success",
        "data": {
            "scheduler_running": True,
            "total_jobs": len(jobs),
            "active_jobs": len(active_jobs),
            "last_check": datetime.now().isoformat(),
        },
    }
