"""
feedback_loop.py — 反馈闭环封装层（第九宫 · 中宫）

封装 src/services/feedback_store.py 的反馈记录去重与批量学习触发功能，
在第九宫（EvolutionGua）框架内统一调用。

不复制代码，全部 import 自 services/feedback_store。
"""

import logging
from typing import Dict, List, Optional

# ---- 从 services 导入原有实现 ----
from src.services.feedback_store import (
    log_feedback_unified,
    get_feedback_stats as _store_get_stats,
    clear_feedback_cache,
)

logger = logging.getLogger("evolution.feedback_loop")


class FeedbackLoop:
    """反馈闭环 — 第九宫内部的反馈管理组件

    封装 feedback_store 的底层实现，提供一致的演化层接口。

    主要功能：
      - record(): 记录用户反馈（带去重、批量学习触发）
      - stats():  获取反馈统计信息
      - clear_cache(): 清空去重缓存
    """

    def __init__(self):
        self._initialized = True
        logger.info("[FeedbackLoop] 初始化完成")

    # FAKE-ASYNC: 标记 async 仅为接口统一，内部同步执行
    async def record(
        self,
        user_id: str,
        query: str,
        action: str,
        results: Optional[List] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """记录用户反馈

        Args:
            user_id:  用户标识
            query:    查询文本
            action:   反馈动作 (like/dislike/correct/copy/click)
            results:  关联的搜索结果（可选）
            metadata: 附加元数据（可选）

        Returns:
            {"ok": bool, "dedup": bool, "learn_triggered": bool}
        """
        return await log_feedback_unified(
            user_id=user_id,
            query=query,
            action=action,
            results=results,
            metadata=metadata,
        )

    def stats(self) -> Dict:
        """获取反馈统计

        Returns:
            {"dedup_cache_size": int, "learn_buffer_size": int, "learn_buffer_threshold": int}
        """
        return _store_get_stats()

    def clear_cache(self) -> None:
        """清空去重缓存"""
        clear_feedback_cache()


# ---- 便捷函数 ----

def has_feedback_loop() -> bool:
    """检查反馈闭环是否就绪（始终返回 True，因为 feedback_store 是无状态模块）

    Returns:
        True
    """
    return True


async def record_feedback(
    user_id: str,
    query: str,
    action: str,
    results: Optional[List] = None,
    metadata: Optional[Dict] = None,
) -> Dict:
    """便捷函数：记录用户反馈

    等价于 FeedbackLoop().record(...)

    Args:
        user_id:  用户标识
        query:    查询文本
        action:   反馈动作
        results:  关联结果
        metadata: 元数据

    Returns:
        {"ok": bool, "dedup": bool, "learn_triggered": bool}
    """
    loop = FeedbackLoop()
    return await loop.record(
        user_id=user_id,
        query=query,
        action=action,
        results=results,
        metadata=metadata,
    )


def get_feedback_loop_stats() -> Dict:
    """便捷函数：获取反馈统计"""
    return _store_get_stats()


def clear_feedback_dedup_cache() -> None:
    """便捷函数：清空去重缓存"""
    clear_feedback_cache()
