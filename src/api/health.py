"""
健康检查端点
============
GET /health - 返回服务健康状态，包括内存、磁盘和服务运行信息
"""
import os
import time
import psutil
from fastapi import APIRouter
from src.config import START_TIME, VERSION

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """返回服务健康状态：内存、磁盘、服务运行时间"""
    # 内存信息
    mem = psutil.virtual_memory()
    memory_info = {
        "total_mb": round(mem.total / (1024 * 1024), 2),
        "available_mb": round(mem.available / (1024 * 1024), 2),
        "used_mb": round(mem.used / (1024 * 1024), 2),
        "percent": mem.percent,
    }

    # 磁盘信息（工作目录所在磁盘）
    disk_usage = psutil.disk_usage(os.getcwd())
    disk_info = {
        "total_gb": round(disk_usage.total / (1024 ** 3), 2),
        "used_gb": round(disk_usage.used / (1024 ** 3), 2),
        "free_gb": round(disk_usage.free / (1024 ** 3), 2),
        "percent": round(disk_usage.percent, 2),
    }

    # 服务运行时间
    uptime_seconds = time.time() - START_TIME
    hours = int(uptime_seconds // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    uptime_str = f"{hours}h {minutes}m"

    # 状态判断
    status = "healthy"
    warnings = []
    
    if mem.percent > 90:
        status = "critical"
        warnings.append("内存使用率超过90%")
    elif mem.percent > 80:
        status = "degraded"
        warnings.append("内存使用率超过80%")
    
    if disk_usage.percent > 90:
        status = "critical"
        warnings.append("磁盘使用率超过90%")

    return {
        "status": status,
        "version": VERSION,
        "uptime": uptime_str,
        "memory": memory_info,
        "disk": disk_info,
        "warnings": warnings,
    }
