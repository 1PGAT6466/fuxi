"""
自修复 API 路由 (Healer Routes)
================================
  - GET  /api/ops/healer/actions            — 获取修复动作列表
  - POST /api/ops/healer/actions/{id}/run   — 手动触发修复
  - GET  /api/ops/healer/history             — 获取修复历史
  - GET  /api/ops/healer/status              — 获取修复引擎状态
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger("fuxi.healer.api")

router = APIRouter(prefix="/api/ops/healer", tags=["自修复引擎"])

# 全局实例（延迟初始化）
_healer_engine = None


def _get_healer() -> "HealerEngine":
    global _healer_engine
    if _healer_engine is None:
        from src.autonomous.healer.engine import HealerEngine

        _healer_engine = HealerEngine()
    return _healer_engine


def set_healer_instance(engine):
    """由 startup 调用，设置全局修复引擎实例"""
    global _healer_engine
    _healer_engine = engine


@router.get("/actions")
async def list_actions():
    """获取所有修复动作列表"""
    engine = _get_healer()
    actions = engine.list_actions()
    return {
        "status": "ok",
        "count": len(actions),
        "actions": actions,
    }


@router.post("/actions/{action_id}/run")
async def run_action(
    action_id: str,
    context: Optional[dict] = None,
):
    """手动触发修复动作"""
    engine = _get_healer()

    action = engine.get_action(action_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"修复动作不存在: {action_id}")

    if not action.enabled:
        raise HTTPException(status_code=400, detail=f"修复动作已禁用: {action_id}")

    result = await engine.execute_action(
        action_id=action_id,
        context=context or {},
        triggered_by="manual",
    )

    return {
        "status": "ok",
        "result": {
            "action_id": result.action_id,
            "status": result.status.value,
            "message": result.message,
            "duration": round(result.duration, 3),
            "details": result.details,
        },
    }


@router.get("/history")
async def get_history(
    action_id: Optional[str] = Query(None, description="按动作ID过滤"),
    status: Optional[str] = Query(None, description="按状态过滤"),
    limit: int = Query(default=100, ge=1, le=1000, description="返回记录数"),
):
    """获取修复历史"""
    engine = _get_healer()

    from src.autonomous.healer.safety import RepairStatus

    status_enum = RepairStatus(status) if status else None

    history = engine.get_history(action_id=action_id, status=status_enum, limit=limit)

    return {
        "status": "ok",
        "count": len(history),
        "history": history,
    }


@router.get("/status")
async def get_status():
    """获取修复引擎状态"""
    engine = _get_healer()
    return {
        "status": "ok",
        "healer": engine.get_status(),
    }
