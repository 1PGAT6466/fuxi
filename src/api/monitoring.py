"""
监控中心 API — 系统健康指标、告警、日志分析
"""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger("api.monitoring")

router = APIRouter(prefix="/api/monitoring", tags=["监控中心"])

# ============ 系统指标 ============


@router.get("/metrics")
async def get_system_metrics():
    """获取系统健康指标"""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        # 获取网络 IO
        net_io = psutil.net_io_counters()

        # 获取进程数
        pids = psutil.pids()

        return {
            "status": "success",
            "data": {
                "cpu": {
                    "percent": cpu_percent,
                    "count": psutil.cpu_count(),
                    "freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used,
                    "percent": memory.percent,
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": disk.percent,
                },
                "network": {
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv,
                },
                "processes": {
                    "total": len(pids),
                },
                "timestamp": time.time(),
            },
        }
    except Exception as e:
        logger.error(f"获取系统指标失败: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/metrics/history")
async def get_metrics_history(hours: int = Query(24, ge=1, le=168)):
    """获取历史指标（简化版，返回最近数据）"""
    # 这里应该从时序数据库获取历史数据
    # 简化版：返回空数组
    return {
        "status": "success",
        "data": {
            "timestamps": [],
            "cpu": [],
            "memory": [],
            "disk": [],
        },
    }


# ============ 告警管理 ============

# 告警规则存储
_alert_rules_file = Path("data/alert_rules.json")
_alerts_history_file = Path("data/alerts_history.json")


def _load_alert_rules() -> List[Dict]:
    """加载告警规则"""
    if _alert_rules_file.exists():
        try:
            return json.loads(_alert_rules_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # 默认告警规则
    return [
        {
            "id": "cpu_high",
            "name": "CPU 使用率过高",
            "condition": "cpu_percent > 80",
            "threshold": 80,
            "level": "warning",
            "enabled": True,
        },
        {
            "id": "memory_high",
            "name": "内存使用率过高",
            "condition": "memory_percent > 85",
            "threshold": 85,
            "level": "warning",
            "enabled": True,
        },
        {
            "id": "disk_high",
            "name": "磁盘使用率过高",
            "condition": "disk_percent > 90",
            "threshold": 90,
            "level": "critical",
            "enabled": True,
        },
    ]


def _save_alert_rules(rules: List[Dict]) -> None:
    """保存告警规则"""
    _alert_rules_file.parent.mkdir(parents=True, exist_ok=True)
    _alert_rules_file.write_text(json.dumps(rules, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_alerts_history() -> List[Dict]:
    """加载告警历史"""
    if _alerts_history_file.exists():
        try:
            return json.loads(_alerts_history_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_alerts_history(alerts: List[Dict]) -> None:
    """保存告警历史"""
    _alerts_history_file.parent.mkdir(parents=True, exist_ok=True)
    _alerts_history_file.write_text(json.dumps(alerts, indent=2, ensure_ascii=False), encoding="utf-8")


@router.get("/alerts")
async def get_alerts(level: Optional[str] = Query(None), limit: int = Query(50, ge=1, le=200)):
    """获取告警列表"""
    alerts = _load_alerts_history()

    # 按级别过滤
    if level:
        alerts = [a for a in alerts if a.get("level") == level]

    # 按时间倒序
    alerts.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    return {
        "status": "success",
        "data": alerts[:limit],
        "total": len(alerts),
    }


@router.get("/alerts/rules")
async def get_alert_rules():
    """获取告警规则"""
    rules = _load_alert_rules()
    return {
        "status": "success",
        "data": rules,
    }


@router.post("/alerts/rules")
async def create_alert_rule(rule: Dict):
    """创建告警规则"""
    rules = _load_alert_rules()

    # 生成 ID
    rule["id"] = f"rule_{int(time.time())}"
    rule["created_at"] = datetime.now().isoformat()

    rules.append(rule)
    _save_alert_rules(rules)

    return {"status": "success", "data": rule}


@router.put("/alerts/rules/{rule_id}")
async def update_alert_rule(rule_id: str, update: Dict):
    """更新告警规则"""
    rules = _load_alert_rules()

    for i, rule in enumerate(rules):
        if rule.get("id") == rule_id:
            rules[i].update(update)
            _save_alert_rules(rules)
            return {"status": "success", "data": rules[i]}

    raise HTTPException(404, f"告警规则 {rule_id} 不存在")


@router.delete("/alerts/rules/{rule_id}")
async def delete_alert_rule(rule_id: str):
    """删除告警规则"""
    rules = _load_alert_rules()
    rules = [r for r in rules if r.get("id") != rule_id]
    _save_alert_rules(rules)

    return {"status": "success", "message": f"告警规则 {rule_id} 已删除"}


# ============ 日志分析 ============


@router.get("/logs/analysis")
async def get_logs_analysis(hours: int = Query(24, ge=1, le=168)):
    """获取日志分析"""
    log_dir = Path("logs")

    analysis = {
        "total_files": 0,
        "total_size": 0,
        "by_level": {
            "INFO": 0,
            "WARNING": 0,
            "ERROR": 0,
            "CRITICAL": 0,
        },
        "recent_errors": [],
    }

    if not log_dir.exists():
        return {"status": "success", "data": analysis}

    # 统计日志文件
    for log_file in log_dir.glob("*.log"):
        analysis["total_files"] += 1
        analysis["total_size"] += log_file.stat().st_size

        # 简单分析最近的错误
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                for line in lines[-100:]:  # 只看最后100行
                    if "ERROR" in line:
                        analysis["by_level"]["ERROR"] += 1
                        if len(analysis["recent_errors"]) < 10:
                            analysis["recent_errors"].append(
                                {
                                    "file": log_file.name,
                                    "message": line.strip()[:200],
                                }
                            )
                    elif "WARNING" in line:
                        analysis["by_level"]["WARNING"] += 1
                    elif "INFO" in line:
                        analysis["by_level"]["INFO"] += 1
                    elif "CRITICAL" in line:
                        analysis["by_level"]["CRITICAL"] += 1
        except Exception:
            pass

    return {"status": "success", "data": analysis}


@router.get("/logs/patterns")
async def get_logs_patterns():
    """获取日志模式（错误频率）"""
    return {
        "status": "success",
        "data": {
            "patterns": [],
            "message": "日志模式分析功能开发中",
        },
    }
