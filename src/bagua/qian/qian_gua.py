"""
qian/qian_gua.py - 乾卦主类
============================

乾卦主类，整合所有子模块。
"""

from dataclasses import dataclass, field
from src.bagua._common import (
    hashlib, json, logging, os, re, time,
    Any, Dict, List, Optional, Tuple,
)

from .intent_loop import IntentLoop, IntentLoopState
from .cycle_guard import CycleGuard, CycleGuardState
from .safety_cruise import SafetyCruise, SafetyCruiseState
from .degradation import DegradationManager
from .session_manager import SessionManager
from .llm_dispatcher import LLMDispatcher
from .fallback import FallbackManager
from .health_check import HealthChecker

logger = logging.getLogger("bagua.qian")

# ============================================================================
# QianGua — 乾卦主类
# ============================================================================


class QianGua:
    """乾卦主类

    伏羲 RAG 系统的意识中枢（0 的居所），通过 IntentBus 调度
    其他 7 个卦，实现完整的"意图循环"。

    Attributes:
        intent_loop:          意图循环
        cycle_guard:          循环守护
        safety_cruise:        安全巡航
        degradation_manager:  降级管理器
        session_manager:      Session 管理器
        llm_dispatcher:       LLM 调度器
        fallback_manager:     降级和回退管理器
        health_checker:       健康检查器
    """

    def __init__(self):
        """初始化乾卦"""
        self.intent_loop = IntentLoop()
        self.cycle_guard = CycleGuard()
        self.safety_cruise = SafetyCruise()
        self.degradation_manager = DegradationManager()
        self.session_manager = SessionManager()
        self.llm_dispatcher = LLMDispatcher()
        self.fallback_manager = FallbackManager()
        self.health_checker = HealthChecker()

        logger.info("☰ [乾] 乾卦初始化完成")

    async def think(
        self,
        query: str,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """思考

        Args:
            query:              用户查询
            session_id:         Session ID
            context:            上下文信息

        Returns:
            最终答案，或 None（失败）
        """
        logger.info("☰ [乾] 思考: %s", query[:50])

        # 获取或创建 Session
        if session_id:
            session = self.session_manager.get_or_create_session(session_id)
            session.think_count += 1
            session.context = context or {}

        # 记录请求
        self.degradation_manager.record_request()

        # 执行意图循环
        try:
            # 健康检查
            health_status = await self.health_checker.check_health()
            if not health_status.vector_store_ok:
                logger.warning("☰ [乾] 向量存储不可用，使用降级模式")
                return await self.fallback_manager.shaoyin_brain_fallback(query, context)

            # 意图循环
            state = IntentLoopState()
            result = await self.intent_loop.think(query, context, state)

            if result:
                logger.info("☰ [乾] 意图循环完成")
                return result

            # 意图循环失败，使用降级
            logger.warning("☰ [乾] 意图循环失败，使用降级模式")
            self.degradation_manager.record_l1_failure()
            return await self.fallback_manager.shaoyin_brain_fallback(query, context)

        except Exception as e:
            logger.error("☰ [乾] 思考失败: %s", e)
            self.degradation_manager.record_l1_failure()
            return await self.fallback_manager.shaoyin_brain_fallback(query, context)

    def clear_session(self, session_id: str) -> None:
        """清除 Session"""
        self.session_manager.clear_session(session_id)

    def clear_all_sessions(self) -> None:
        """清除所有 Session"""
        self.session_manager.clear_all_sessions()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "intent_loop": self.intent_loop.get_stats(),
            "cycle_guard": self.cycle_guard.get_anomaly_stats(),
            "safety_cruise": {
                "active": self.safety_cruise.is_active(self.safety_cruise._state),
            },
            "degradation": self.degradation_manager.get_summary(),
            "session": self.session_manager.get_session_summary(),
            "health": self.health_checker.get_stats(),
        }
