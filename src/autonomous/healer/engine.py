"""
自修复引擎 (Healer Engine)
==========================
伏羲自运转 Phase 2 核心模块：
  - 接收告警信号，自动触发修复
  - 修复动作执行前快照
  - 执行修复动作
  - 验证修复结果
  - 失败自动回滚
  - 记录修复历史

集成告警引擎，提供自动修复闭环。
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .actions import (
    ACTION_HANDLERS,
    PRESET_ACTIONS,
    ActionResult,
    BaseAction,
    RepairAction,
)
from .config import HealerConfig
from .safety import (
    ApprovalGuard,
    AuditLogger,
    AuditRecord,
    CooldownGuard,
    RepairStatus,
    RiskLevel,
    Snapshot,
    SnapshotManager,
)

logger = logging.getLogger(__name__)


class HealerEngine:
    """自修复引擎"""

    def __init__(self, config: Optional[HealerConfig] = None):
        self.config = config or HealerConfig()

        # 安全防护组件
        self._cooldown = CooldownGuard()
        self._snapshots = SnapshotManager(
            self.config.snapshot_dir,
            self.config.max_snapshots,
        )
        self._audit = AuditLogger(
            self.config.audit_log_path,
            self.config.history_max,
        )
        self._approval = ApprovalGuard(
            self.config.approval_timeout,
            self.config.auto_approve_low_risk,
        )

        # 动作注册表
        self._actions: Dict[str, RepairAction] = dict(PRESET_ACTIONS)
        self._handlers: Dict[str, BaseAction] = dict(ACTION_HANDLERS)

        # 并发控制
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_repairs)
        self._running: Dict[str, asyncio.Task] = {}

        # 告警集成回调
        self._alert_callbacks: List[Callable] = []

        # 统计
        self._total_repairs = 0
        self._total_success = 0
        self._total_failed = 0
        self._total_rolled_back = 0

    # ============================================================
    # 公开 API
    # ============================================================

    def list_actions(self) -> List[Dict[str, Any]]:
        """列出所有注册的修复动作"""
        return [
            {
                "id": a.id,
                "name": a.name,
                "description": a.description,
                "risk_level": a.risk_level.value,
                "cooldown": a.cooldown,
                "enabled": a.enabled,
                "alert_rules": a.alert_rules,
            }
            for a in self._actions.values()
        ]

    def get_action(self, action_id: str) -> Optional[RepairAction]:
        """获取单个修复动作"""
        return self._actions.get(action_id)

    async def execute_action(
        self,
        action_id: str,
        context: Optional[Dict[str, Any]] = None,
        triggered_by: str = "manual",
        alert_id: Optional[str] = None,
    ) -> ActionResult:
        """
        执行修复动作（完整流程：冷却检查 → 审批 → 快照 → 执行 → 验证 → 回滚）
        """
        action = self._actions.get(action_id)
        if not action:
            return ActionResult(
                action_id=action_id,
                status=RepairStatus.FAILED,
                message=f"修复动作不存在: {action_id}",
            )

        if not action.enabled:
            return ActionResult(
                action_id=action_id,
                status=RepairStatus.FAILED,
                message=f"修复动作已禁用: {action_id}",
            )

        handler = self._handlers.get(action_id)
        if not handler:
            return ActionResult(
                action_id=action_id,
                status=RepairStatus.FAILED,
                message=f"修复动作处理器缺失: {action_id}",
            )

        context = context or {}
        effective_cooldown = action.cooldown if action.cooldown > 0 else self.config.default_cooldown

        # 1. 冷却期检查
        if not self._cooldown.can_execute(action_id, effective_cooldown):
            remaining = self._cooldown.get_remaining_cooldown(action_id, effective_cooldown)
            return ActionResult(
                action_id=action_id,
                status=RepairStatus.FAILED,
                message=f"动作 {action_id} 在冷却期内，剩余 {remaining:.0f} 秒",
            )

        # 2. 人工审批
        if self._approval.needs_approval(action.risk_level):
            if triggered_by == "auto":
                # 自动触发的高危动作需要审批
                logger.warning(f"高危动作 {action_id} 需要人工审批，已跳过自动执行")
                self._audit.log(
                    AuditRecord(
                        action_id=action_id,
                        action_name=action.name,
                        status=RepairStatus.APPROVAL_REQUIRED,
                        risk_level=action.risk_level,
                        triggered_by=triggered_by,
                        alert_id=alert_id,
                        started_at=datetime.now(),
                    )
                )
                return ActionResult(
                    action_id=action_id,
                    status=RepairStatus.APPROVAL_REQUIRED,
                    message=f"高危动作 {action_id} 需要人工审批",
                )

        # 3. 并发控制
        async with self._semaphore:
            return await self._do_execute(action, handler, context, triggered_by, alert_id)

    async def handle_alert(self, alert_data: Dict[str, Any]) -> List[ActionResult]:
        """
        处理告警信号，自动匹配并执行修复动作
        alert_data 应包含:
          - id: 告警ID
          - rule_id: 告警规则ID
          - metric: 指标名称
          - current_value: 当前值
          - threshold: 阈值
        """
        alert_id = alert_data.get("id", "unknown")
        rule_id = alert_data.get("rule_id", "")

        # 查找关联的修复动作
        matching_actions = [a for a in self._actions.values() if rule_id in a.alert_rules and a.enabled]

        if not matching_actions:
            logger.info(f"告警 {alert_id} 无匹配的修复动作")
            return []

        results = []
        for action in matching_actions:
            logger.info(f"告警 {alert_id} 触发修复动作: {action.id}")
            result = await self.execute_action(
                action_id=action.id,
                context=alert_data,
                triggered_by="alert",
                alert_id=alert_id,
            )
            results.append(result)

            # 修复成功后反馈到告警系统
            if result.status == RepairStatus.SUCCESS:
                for cb in self._alert_callbacks:
                    try:
                        await cb(alert_id, "resolved")
                    except Exception as e:
                        logger.error(f"告警回调失败: {e}")

        return results

    def get_history(
        self,
        action_id: Optional[str] = None,
        status: Optional[RepairStatus] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """获取修复历史"""
        records = self._audit.get_records(action_id, status, limit)
        return [
            {
                "action_id": r.action_id,
                "action_name": r.action_name,
                "status": r.status.value,
                "risk_level": r.risk_level.value,
                "triggered_by": r.triggered_by,
                "alert_id": r.alert_id,
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "error_message": r.error_message,
                "rollback_performed": r.rollback_performed,
            }
            for r in records
        ]

    def get_status(self) -> Dict[str, Any]:
        """获取修复引擎状态"""
        return {
            "running": True,
            "registered_actions": len(self._actions),
            "enabled_actions": sum(1 for a in self._actions.values() if a.enabled),
            "active_repairs": len(self._running),
            "pending_approvals": self._approval.get_pending(),
            "stats": {
                "total_repairs": self._total_repairs,
                "success": self._total_success,
                "failed": self._total_failed,
                "rolled_back": self._total_rolled_back,
            },
            "config": {
                "max_concurrent": self.config.max_concurrent_repairs,
                "action_timeout": self.config.action_timeout,
                "max_retries": self.config.max_retries,
            },
        }

    def register_action(self, action: RepairAction, handler: BaseAction):
        """注册自定义修复动作"""
        self._actions[action.id] = action
        self._handlers[action.id] = handler
        logger.info(f"注册修复动作: {action.id} ({action.name})")

    def register_alert_callback(self, callback: Callable):
        """注册告警回调（修复成功后调用）"""
        self._alert_callbacks.append(callback)

    def approve_action(self, action_id: str) -> bool:
        """批准待审批的修复动作"""
        return self._approval.approve(action_id)

    def reject_action(self, action_id: str) -> bool:
        """拒绝待审批的修复动作"""
        return self._approval.reject(action_id)

    # ============================================================
    # 内部执行流程
    # ============================================================

    async def _do_execute(
        self,
        action: RepairAction,
        handler: BaseAction,
        context: Dict[str, Any],
        triggered_by: str,
        alert_id: Optional[str],
    ) -> ActionResult:
        """执行修复动作的完整流程"""
        started_at = datetime.now()
        self._total_repairs += 1
        snapshot: Optional[Snapshot] = None

        # 审计记录
        audit = AuditRecord(
            action_id=action.id,
            action_name=action.name,
            status=RepairStatus.RUNNING,
            risk_level=action.risk_level,
            triggered_by=triggered_by,
            alert_id=alert_id,
            started_at=started_at,
        )

        try:
            # 3. 创建快照
            logger.info(f"[Healer] 开始执行: {action.id} ({action.name})")
            snapshot_data = await asyncio.wait_for(
                handler.snapshot(context),
                timeout=self.config.action_timeout,
            )
            snapshot = await self._snapshots.create_snapshot(action.id, snapshot_data)
            audit.snapshot_id = f"{action.id}_{int(time.time())}"
            logger.info(f"[Healer] 快照已创建: {audit.snapshot_id}")

            # 4. 执行修复（带重试）
            result = await self._execute_with_retry(handler, context)

            # 5. 验证结果
            if result.status == RepairStatus.SUCCESS:
                verified = await asyncio.wait_for(
                    handler.verify(context),
                    timeout=self.config.action_timeout,
                )
                if not verified:
                    logger.warning(f"[Healer] 验证失败，触发回滚: {action.id}")
                    result.status = RepairStatus.FAILED
                    result.message += "（验证失败）"

            # 6. 失败则回滚
            if result.status == RepairStatus.FAILED and snapshot:
                rollback_ok = await self._snapshots.rollback(
                    snapshot,
                    rollback_fn=handler.rollback,
                )
                audit.rollback_performed = True
                self._total_rolled_back += 1
                if rollback_ok:
                    result.status = RepairStatus.ROLLED_BACK
                    result.message += "（已回滚）"
                    logger.info(f"[Healer] 回滚成功: {action.id}")
                else:
                    logger.error(f"[Healer] 回滚失败: {action.id}")

            # 更新统计
            if result.status in (RepairStatus.SUCCESS,):
                self._total_success += 1
            elif result.status in (RepairStatus.FAILED, RepairStatus.TIMEOUT):
                self._total_failed += 1

            # 记录冷却
            self._cooldown.record_execution(action.id)

            # 审计
            audit.status = result.status
            audit.finished_at = datetime.now()
            audit.error_message = result.message if result.status != RepairStatus.SUCCESS else None
            self._audit.log(audit)

            logger.info(f"[Healer] 完成: {action.id} -> {result.status.value} " f"({result.duration:.2f}s)")

            return result

        except asyncio.TimeoutError:
            audit.status = RepairStatus.TIMEOUT
            audit.finished_at = datetime.now()
            audit.error_message = f"动作 {action.id} 执行超时"
            self._audit.log(audit)
            self._total_failed += 1

            # 超时也要回滚
            if snapshot:
                await self._snapshots.rollback(snapshot, rollback_fn=handler.rollback)
                audit.rollback_performed = True

            return ActionResult(
                action_id=action.id,
                status=RepairStatus.TIMEOUT,
                message=f"动作 {action.id} 执行超时 ({self.config.action_timeout}s)",
            )

        except Exception as e:
            audit.status = RepairStatus.FAILED
            audit.finished_at = datetime.now()
            audit.error_message = str(e)
            self._audit.log(audit)
            self._total_failed += 1

            # 异常也要回滚
            if snapshot:
                await self._snapshots.rollback(snapshot, rollback_fn=handler.rollback)
                audit.rollback_performed = True

            logger.error(f"[Healer] 异常: {action.id} — {e}")
            return ActionResult(
                action_id=action.id,
                status=RepairStatus.FAILED,
                message=f"动作 {action.id} 执行异常: {e}",
            )

    async def _execute_with_retry(
        self,
        handler: BaseAction,
        context: Dict[str, Any],
    ) -> ActionResult:
        """带重试的执行"""
        last_result: Optional[ActionResult] = None

        for attempt in range(self.config.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    handler.execute(context),
                    timeout=self.config.action_timeout,
                )

                if result.status == RepairStatus.SUCCESS:
                    return result

                last_result = result
                if attempt < self.config.max_retries:
                    logger.info(f"[Healer] 重试 {attempt + 1}/{self.config.max_retries}: " f"{result.message}")
                    await asyncio.sleep(self.config.retry_delay)

            except asyncio.TimeoutError:
                last_result = ActionResult(
                    action_id=handler.__class__.__name__,
                    status=RepairStatus.TIMEOUT,
                    message=f"第 {attempt + 1} 次执行超时",
                )
                if attempt < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_delay)

            except Exception as e:
                last_result = ActionResult(
                    action_id=handler.__class__.__name__,
                    status=RepairStatus.FAILED,
                    message=f"第 {attempt + 1} 次执行异常: {e}",
                )
                if attempt < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_delay)

        return last_result or ActionResult(
            action_id="unknown",
            status=RepairStatus.FAILED,
            message="执行失败，已耗尽重试次数",
        )
