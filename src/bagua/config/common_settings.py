"""
common_settings.py — 八卦层通用配置 & Meridian 工厂函数

提供 get_meridian() 作为伏羲经络系统的工厂函数，
给 fuxi.py 的 Fuxi 类提供全身唯一信号总线实例。
"""

from __future__ import annotations

import logging
import sys
import os
from typing import Optional

logger = logging.getLogger("bagua.config")


# 缓存已创建的 Meridian 实例（单例模式）
_meridian_instance: Optional[object] = None


def get_meridian() -> object:
    """获取或创建 Meridian（经络系统）实例

    Meridian 是伏羲体内唯一的信号总线，所有器官和四象模块通过
    经络收发信号。本函数为工厂方法，返回经络单例。

    导入优先级：
      1. src.hypothalamus.meridian.Meridian（主路径）
      2. scripts.archive._v1_hypothalamus.meridian.Meridian（归档备份）

    Returns:
        Meridian 实例（单例），可调用 .start(), .stop(), .stats()

    Raises:
        ImportError: 当两个路径都无法导入时
    """
    global _meridian_instance

    if _meridian_instance is not None:
        return _meridian_instance

    # 尝试从主路径导入
    MeridianClass = _try_import_meridian()

    if MeridianClass is None:
        raise ImportError(
            "无法导入 Meridian 类。请确保 "
            "src/hypothalamus/meridian.py 存在，"
            "或 scripts/archive/_v1_hypothalamus/meridian.py 可用。"
        )

    _meridian_instance = MeridianClass()
    logger.info("[config] Meridian 经络实例已创建（单例）")
    return _meridian_instance


def get_or_create_meridian() -> object:
    """获取当前缓存的 Meridian 实例，如果不存在则创建。

    这是 get_meridian() 的别名。

    Returns:
        Meridian 实例
    """
    return get_meridian()


def reset_meridian() -> None:
    """重置经络单例缓存（主要用于测试）"""
    global _meridian_instance
    _meridian_instance = None
    logger.info("[config] Meridian 缓存已重置")


def _try_import_meridian():
    """尝试从候选路径导入 Meridian 类

    按优先级尝试：
      1. src.hypothalamus.meridian
      2. scripts.archive._v1_hypothalamus.meridian（归档备份）

    Returns:
        Meridian 类，或 None（全部失败时）
    """
    # 候选导入路径
    candidates = [
        ("src.hypothalamus.meridian", "Meridian"),
        ("scripts.archive._v1_hypothalamus.meridian", "Meridian"),
    ]

    for module_path, class_name in candidates:
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name, None)
            if cls is not None:
                logger.debug(
                    "[config] 从 %s 导入 Meridian 类成功", module_path
                )
                return cls
        except ImportError as e:
            logger.debug(
                "[config] 从 %s 导入 Meridian 失败: %s", module_path, e
            )
            continue

    return None


__all__ = [
    "get_meridian",
    "get_or_create_meridian",
    "reset_meridian",
]
