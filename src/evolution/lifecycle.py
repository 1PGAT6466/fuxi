"""
lifecycle.py — 知识生命周期封装层（第九宫 · 中宫）

封装 src/services/knowledge_lifecycle.py 的知识生命周期管理功能，
在第九宫（EvolutionGua）框架内统一调用。

不复制代码，全部 import 自 services/knowledge_lifecycle。
"""

import logging
from typing import Dict, List, Optional

# ---- 从 services 导入原有实现 ----
from src.services.knowledge_lifecycle import (
    KnowledgeLifecycle,
    get_knowledge_lifecycle,
)

logger = logging.getLogger("evolution.lifecycle")


class EvolutionLifecycle:
    """演化生命周期管理器 — 第九宫的知识生命周期组件

    封装 services/knowledge_lifecycle 的底层实现，提供一致的演化层接口。

    主要功能：
      - record():     记录知识生命周期事件
      - check_triggers(): 检查触发条件
      - get_candidates(): 获取候选知识
      - classify():   分类置信度
    """

    # 触发条件配置（从 KnowledgeLifecycle 继承）
    TRIGGER_CONDITIONS = KnowledgeLifecycle.TRIGGER_CONDITIONS

    # 置信度分级
    CONFIDENCE_LEVELS = KnowledgeLifecycle.CONFIDENCE_LEVELS

    def __init__(self):
        self._lifecycle = get_knowledge_lifecycle()
        self._initialized = True
        logger.info("[EvolutionLifecycle] 初始化完成")

    # FAKE-ASYNC: 标记 async 仅为接口统一
    async def record(self, event_type: str, data: Dict) -> None:
        """记录知识生命周期事件

        例如：实体未找到、同义词变体、缺失关系、空结果、用户质疑等。

        Args:
            event_type: 事件类型 (entity_not_found/synonym_variant/missing_relation/empty_result/user_doubt)
            data:       事件数据
        """
        await self._lifecycle.record_event(event_type, data)

    async def check_triggers(self) -> List[Dict]:
        """检查所有触发条件

        遍历所有 TRIGGER_CONDITIONS，检查各事件类型是否达到阈值。

        Returns:
            [{"event_type": str, "count": int, "threshold": int, "period_days": int}, ...]
        """
        return await self._lifecycle.check_triggers()

    # FAKE-ASYNC: 标记 async 仅为接口统一
    async def get_candidates(self, event_type: str) -> List[Dict]:
        """获取指定事件类型的候选知识

        Args:
            event_type: 事件类型

        Returns:
            候选知识条目列表 [{data_field: value, ...}, ...]
        """
        return await self._lifecycle.get_candidates(event_type)

    def classify(self, confidence: float) -> str:
        """根据置信度分类

        Args:
            confidence: 置信度值 [0.0, 1.0]

        Returns:
            "high" | "medium" | "low"
                - high (≥0.9):  自动添加
                - medium (≥0.7): 待审核队列
                - low (<0.7):   忽略
        """
        return self._lifecycle.classify_confidence(confidence)

    def stats(self) -> Dict:
        """获取生命周期统计摘要

        Returns:
            {"total_events": int, "by_type": {event_type: count, ...}}
        """
        by_type: Dict[str, int] = {}
        total = 0
        for etype in self.TRIGGER_CONDITIONS:
            events = self._lifecycle._events
            count = sum(1 for e in events if e.get("event_type") == etype)
            by_type[etype] = count
            total += count
        return {"total_events": total, "by_type": by_type}


# ---- 便捷函数 ----

async def record_lifecycle_event(event_type: str, data: Dict) -> None:
    """便捷函数：记录知识生命周期事件

    Args:
        event_type: 事件类型
        data:       事件数据
    """
    lifecycle = EvolutionLifecycle()
    await lifecycle.record(event_type, data)


async def check_lifecycle_triggers() -> List[Dict]:
    """便捷函数：检查生命周期触发条件

    Returns:
        触发的事件列表
    """
    lifecycle = EvolutionLifecycle()
    return await lifecycle.check_triggers()


async def get_lifecycle_candidates(event_type: str) -> List[Dict]:
    """便捷函数：获取候选知识

    Args:
        event_type: 事件类型

    Returns:
        候选列表
    """
    lifecycle = EvolutionLifecycle()
    return await lifecycle.get_candidates(event_type)


def classify_lifecycle_confidence(confidence: float) -> str:
    """便捷函数：分类置信度

    Args:
        confidence: 置信度值 [0.0, 1.0]

    Returns:
        "high" | "medium" | "low"
    """
    lifecycle = EvolutionLifecycle()
    return lifecycle.classify(confidence)
