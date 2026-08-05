"""
安全防护模块 (Safety Guard)
===========================
自修复引擎的安全防护机制：
  - 频率限制（冷却期）
  - 快照与回滚
  - 审计日志
  - 人工审批
"""

import asyncio
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """修复动作风险等级"""

    LOW = "low"  # 低危：可自动执行
    MEDIUM = "medium"  # 中危：记录后自动执行
    HIGH = "high"  # 高危：需要人工审批
    CRITICAL = "critical"  # 极危：禁止自动执行


class RepairStatus(str, Enum):
    """修复执行状态"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    APPROVAL_REQUIRED = "approval_required"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


@dataclass
class Snapshot:
    """修复前快照"""

    action_id: str
    created_at: datetime
    data: Dict[str, Any]  # 快照数据（由各动作自行定义）
    path: Optional[str] = None  # 文件快照路径


@dataclass
class AuditRecord:
    """审计记录"""

    action_id: str
    action_name: str
    status: RepairStatus
    risk_level: RiskLevel
    triggered_by: str  # "auto" | "manual" | "alert"
    alert_id: Optional[str]
    started_at: datetime
    finished_at: Optional[datetime] = None
    snapshot_id: Optional[str] = None
    error_message: Optional[str] = None
    rollback_performed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class CooldownGuard:
    """频率限制守卫"""

    def __init__(self):
        self._last_execution: Dict[str, float] = {}

    def can_execute(self, action_id: str, cooldown: int) -> bool:
        """检查动作是否可以执行（不在冷却期内）"""
        last_time = self._last_execution.get(action_id)
        if last_time is None:
            return True
        elapsed = time.time() - last_time
        return elapsed >= cooldown

    def record_execution(self, action_id: str):
        """记录执行时间"""
        self._last_execution[action_id] = time.time()

    def get_remaining_cooldown(self, action_id: str, cooldown: int) -> float:
        """获取剩余冷却时间（秒）"""
        last_time = self._last_execution.get(action_id)
        if last_time is None:
            return 0.0
        elapsed = time.time() - last_time
        remaining = cooldown - elapsed
        return max(0.0, remaining)


class SnapshotManager:
    """快照与回滚管理器"""

    def __init__(self, snapshot_dir: str, max_snapshots: int = 50):
        self.snapshot_dir = snapshot_dir
        self.max_snapshots = max_snapshots
        os.makedirs(snapshot_dir, exist_ok=True)
        self._snapshots: Dict[str, Snapshot] = {}

    async def create_snapshot(self, action_id: str, data: Dict[str, Any]) -> Snapshot:
        """创建快照"""
        snapshot_id = f"{action_id}_{int(time.time())}"
        snapshot_path = os.path.join(self.snapshot_dir, snapshot_id)
        os.makedirs(snapshot_path, exist_ok=True)

        # 保存快照元数据
        meta_path = os.path.join(snapshot_path, "snapshot.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "action_id": action_id,
                    "created_at": datetime.now().isoformat(),
                    "data": data,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        snapshot = Snapshot(
            action_id=action_id,
            created_at=datetime.now(),
            data=data,
            path=snapshot_path,
        )
        self._snapshots[snapshot_id] = snapshot

        # 清理旧快照
        await self._cleanup_old_snapshots(action_id)

        logger.info(f"快照已创建: {snapshot_id}")
        return snapshot

    async def rollback(self, snapshot: Snapshot, rollback_fn: Optional[Callable] = None) -> bool:
        """回滚到快照"""
        try:
            if rollback_fn:
                result = await rollback_fn(snapshot.data)
                if not result:
                    logger.error(f"回滚函数返回失败: {snapshot.action_id}")
                    return False

            logger.info(f"已回滚到快照: {snapshot.action_id} @ {snapshot.created_at}")
            return True
        except Exception as e:
            logger.error(f"回滚失败: {e}")
            return False

    async def _cleanup_old_snapshots(self, action_id: str):
        """清理旧快照，保留最新的 max_snapshots 个"""
        action_snapshots = [sid for sid in self._snapshots if self._snapshots[sid].action_id == action_id]
        if len(action_snapshots) <= self.max_snapshots:
            return

        # 按时间排序，删除最旧的
        action_snapshots.sort(key=lambda sid: self._snapshots[sid].created_at)
        to_remove = action_snapshots[: len(action_snapshots) - self.max_snapshots]
        for sid in to_remove:
            snapshot = self._snapshots.pop(sid)
            if snapshot.path and os.path.exists(snapshot.path):
                shutil.rmtree(snapshot.path, ignore_errors=True)


class AuditLogger:
    """审计日志"""

    def __init__(self, log_path: str, max_records: int = 1000):
        self.log_path = log_path
        self.max_records = max_records
        self._records: List[AuditRecord] = []
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

    def log(self, record: AuditRecord):
        """记录审计日志"""
        self._records.append(record)
        if len(self._records) > self.max_records:
            self._records = self._records[-self.max_records :]

        # 写入文件
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "action_id": record.action_id,
                            "action_name": record.action_name,
                            "status": record.status.value,
                            "risk_level": record.risk_level.value,
                            "triggered_by": record.triggered_by,
                            "alert_id": record.alert_id,
                            "started_at": record.started_at.isoformat(),
                            "finished_at": record.finished_at.isoformat() if record.finished_at else None,
                            "error_message": record.error_message,
                            "rollback_performed": record.rollback_performed,
                            "metadata": record.metadata,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        except Exception as e:
            logger.error(f"审计日志写入失败: {e}")

    def get_records(
        self,
        action_id: Optional[str] = None,
        status: Optional[RepairStatus] = None,
        limit: int = 100,
    ) -> List[AuditRecord]:
        """查询审计记录"""
        records = self._records
        if action_id:
            records = [r for r in records if r.action_id == action_id]
        if status:
            records = [r for r in records if r.status == status]
        return sorted(records, key=lambda r: r.started_at, reverse=True)[:limit]


class ApprovalGuard:
    """人工审批守卫"""

    def __init__(self, timeout: int = 300, auto_approve_low_risk: bool = True):
        self.timeout = timeout
        self.auto_approve_low_risk = auto_approve_low_risk
        self._pending: Dict[str, asyncio.Future] = {}

    def needs_approval(self, risk_level: RiskLevel) -> bool:
        """判断是否需要人工审批"""
        if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            return True
        if risk_level == RiskLevel.MEDIUM and not self.auto_approve_low_risk:
            return True
        return False

    async def request_approval(self, action_id: str, risk_level: RiskLevel) -> bool:
        """请求人工审批，返回是否批准"""
        if not self.needs_approval(risk_level):
            return True

        # 创建 Future 等待审批
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending[action_id] = future

        try:
            # 等待审批或超时
            result = await asyncio.wait_for(future, timeout=self.timeout)
            return result
        except asyncio.TimeoutError:
            logger.warning(f"审批超时: {action_id}")
            return False
        finally:
            self._pending.pop(action_id, None)

    def approve(self, action_id: str) -> bool:
        """批准修复动作"""
        future = self._pending.get(action_id)
        if future and not future.done():
            future.set_result(True)
            return True
        return False

    def reject(self, action_id: str) -> bool:
        """拒绝修复动作"""
        future = self._pending.get(action_id)
        if future and not future.done():
            future.set_result(False)
            return True
        return False

    def get_pending(self) -> List[str]:
        """获取等待审批的动作列表"""
        return list(self._pending.keys())
