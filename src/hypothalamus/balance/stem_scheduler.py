#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stem_scheduler.py — 天干时序调度器 · 伏羲 v1.42

根据当前时辰的天干（2小时为一时辰），动态调整器官工作优先级，
顺应自然节律提升系统效率。
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Callable

logger = logging.getLogger("stem_scheduler")


class StemScheduler:
    """十天干时序调度器"""

    # 时辰→天干映射
    STEM_HOURS = {
        0: "子·甲", 1: "子·甲",
        2: "丑·乙",
        3: "寅·丙", 4: "寅·丙",
        5: "卯·丁", 6: "卯·丁",
        7: "辰·戊", 8: "辰·戊",
        9: "巳·己", 10: "巳·己",
        11: "午·庚", 12: "午·庚",
        13: "未·辛", 14: "未·辛",
        15: "申·壬", 16: "申·壬",
        17: "酉·癸", 18: "酉·癸",
        19: "戌·甲", 20: "戌·甲",
        21: "亥·乙", 22: "亥·乙",
        23: "子·甲",
    }

    # 天干→优先器官
    STEM_PRIORITY = {
        "甲": ["liver", "skeleton"],
        "乙": ["liver", "skeleton"],
        "丙": ["heart", "brain"],
        "丁": ["heart", "nose"],
        "戊": ["stomach", "skin"],
        "己": ["spleen", "stomach"],
        "庚": ["brain", "lung"],
        "辛": ["nose", "lung"],
        "壬": ["kidney", "skeleton"],
        "癸": ["kidney", "liver"],
    }

    # 天干→五行
    STEM_ELEMENT = {
        "甲": "木", "乙": "木",
        "丙": "火", "丁": "火",
        "戊": "土", "己": "土",
        "庚": "金", "辛": "金",
        "壬": "水", "癸": "水",
    }

    def __init__(self, fuxi_instance):
        self.fuxi = fuxi_instance
        self._running = False
        self._task = None
        self._schedule_count = 0

    def get_current_stem_info(self) -> Dict:
        """获取当前时辰天干信息"""
        hour = datetime.now().hour
        full = self.STEM_HOURS.get(hour, "子·甲")
        parts = full.split("·")
        p_organ = self.STEM_PRIORITY.get(parts[1], [])
        return {
            "hour": hour,
            "chinese_hour": parts[0],
            "stem": parts[1],
            "element": self.STEM_ELEMENT.get(parts[1], "?"),
            "yin_yang": "阳" if parts[1] in "甲丙戊庚壬" else "阴",
            "priority_organs": p_organ,
            "next_change": ((hour // 2 + 1) * 2) % 24,
        }

    async def schedule(self, organ_id: str = None):
        """根据天干调度一次任务：提升当前优先器官的工作频率"""
        info = self.get_current_stem_info()
        self._schedule_count += 1

        targets = info["priority_organs"] if organ_id is None else [organ_id]
        for oid in targets:
            organ = getattr(self.fuxi, oid, None)
            if organ and hasattr(organ, "meridian"):
                try:
                    # 向优先器官发送一个脉搏信号，触发其工作循环
                    organ.meridian.send_raw(oid, "stem_pulse", {
                        "stem": info["stem"],
                        "element": info["element"],
                        "priority": True,
                    })
                except:
                    pass

        logger.debug(f"[天干] {info['stem']}时辰, 优先: {targets}")

    async def start(self):
        """启动天干时序调度循环"""
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("[天干] 时序调度已启动")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _loop(self):
        while self._running:
            await self.schedule()
            await asyncio.sleep(300)  # 每 5 分钟调度一次

    def stats(self) -> Dict:
        info = self.get_current_stem_info()
        return {
            "current_stem": info["stem"],
            "element": info["element"],
            "priority_organs": info["priority_organs"],
            "next_change": info["next_change"],
            "schedule_count": self._schedule_count,
        }
