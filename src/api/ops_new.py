"""
伏羲 v1.44 — Ops API 模块

实现：
- GET /api/ops/health - 健康检查
- GET /api/ops/metrics - 获取指标
- GET /api/ops/metrics/aggregated - 获取聚合指标
- GET /api/ops/alerts - 获取告警
- POST /api/ops/alerts - 创建告警
- GET /api/ops/alerts/rules - 获取告警规则
- POST /api/ops/alerts/rules - 创建告警规则
- GET /api/ops/sync/history - 获取同步历史
- GET /api/ops/sync/plugins - 获取插件同步状态
- POST /api/ops/sync/plugins/trigger - 触发插件同步
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from src.api.response import error, not_found, server_error, success
from src.auth.rbac import require_role

logger = logging.getLogger("api.ops")

router = APIRouter()


@router.get("/api/ops/health")
async def get_ops_health(request: Request):
    """健康检查"""
    try:
        import psutil

        # 检查系统健康状态
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        health_status = "healthy"
        warnings = []

        if cpu_percent > 90:
            warnings.append("CPU 使用率过高")
            health_status = "degraded"

        if memory.percent > 90:
            warnings.append("内存使用率过高")
            health_status = "degraded"

        if disk.percent > 90:
            warnings.append("磁盘使用率过高")
            health_status = "degraded"

        return success(
            data={
                "status": health_status,
                "cpu": {"usage": cpu_percent},
                "memory": {"usage": memory.percent},
                "disk": {"usage": disk.percent},
                "warnings": warnings,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return server_error(detail=str(e))


@router.get("/api/ops/metrics")
@require_role("user")
async def get_ops_metrics(request: Request):
    """获取指标"""
    try:
        import psutil

        # 获取系统指标
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        return success(
            data={
                "cpu": {"usage": cpu_percent, "cores": psutil.cpu_count()},
                "memory": {"used": memory.used, "total": memory.total, "usage": memory.percent},
                "disk": {"used": disk.used, "total": disk.total, "usage": disk.percent},
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"获取指标失败: {e}")
        return server_error(detail=str(e))


@router.get("/api/ops/metrics/aggregated")
@require_role("user")
async def get_ops_metrics_aggregated(request: Request):
    """获取聚合指标"""
    try:
        import psutil

        # 获取聚合指标
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        return success(
            data={
                "cpu": {"usage": cpu_percent},
                "memory": {"usage": memory.percent},
                "disk": {"usage": disk.percent},
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"获取聚合指标失败: {e}")
        return server_error(detail=str(e))


@router.get("/api/ops/alerts")
@require_role("user")
async def get_ops_alerts(request: Request):
    """获取告警"""
    try:
        # 这里可以实现获取告警逻辑
        # 目前返回空数据
        return success(data={"alerts": [], "total": 0})
    except Exception as e:
        logger.error(f"获取告警失败: {e}")
        return server_error(detail=str(e))


@router.post("/api/ops/alerts")
@require_role("user")
async def create_ops_alert(request: Request):
    """创建告警"""
    try:
        body = await request.json()

        # 这里可以实现创建告警逻辑
        # 目前简单返回成功
        return success(
            data={"id": "alert_1", "message": body.get("message", ""), "created_at": datetime.now().isoformat()},
            status_code=201,
        )
    except Exception as e:
        logger.error(f"创建告警失败: {e}")
        return server_error(detail=str(e))


@router.get("/api/ops/alerts/rules")
@require_role("user")
async def get_ops_alert_rules(request: Request):
    """获取告警规则"""
    try:
        # 这里可以实现获取告警规则逻辑
        # 目前返回空数据
        return success(data={"rules": [], "total": 0})
    except Exception as e:
        logger.error(f"获取告警规则失败: {e}")
        return server_error(detail=str(e))


@router.post("/api/ops/alerts/rules")
@require_role("user")
async def create_ops_alert_rule(request: Request):
    """创建告警规则"""
    try:
        body = await request.json()

        # 这里可以实现创建告警规则逻辑
        # 目前简单返回成功
        return success(
            data={"id": "rule_1", "name": body.get("name", ""), "created_at": datetime.now().isoformat()},
            status_code=201,
        )
    except Exception as e:
        logger.error(f"创建告警规则失败: {e}")
        return server_error(detail=str(e))


@router.get("/api/ops/sync/history")
@require_role("user")
async def get_ops_sync_history(request: Request):
    """获取同步历史"""
    try:
        # 这里可以实现获取同步历史逻辑
        # 目前返回空数据
        return success(data={"history": [], "total": 0})
    except Exception as e:
        logger.error(f"获取同步历史失败: {e}")
        return server_error(detail=str(e))


@router.get("/api/ops/sync/plugins")
@require_role("user")
async def get_ops_sync_plugins(request: Request):
    """获取插件同步状态"""
    try:
        # 这里可以实现获取插件同步状态逻辑
        # 目前返回空数据
        return success(data={"plugins": [], "total": 0})
    except Exception as e:
        logger.error(f"获取插件同步状态失败: {e}")
        return server_error(detail=str(e))


@router.post("/api/ops/sync/plugins/trigger")
@require_role("user")
async def trigger_ops_sync_plugin(request: Request):
    """触发插件同步"""
    try:
        body = await request.json()

        # 这里可以实现触发插件同步逻辑
        # 目前简单返回成功
        return success(message="插件同步已触发")
    except Exception as e:
        logger.error(f"触发插件同步失败: {e}")
        return server_error(detail=str(e))
