#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
meridian_rhythm.py — 经络流注节律 · 伏羲 v1.42

基于子午流注理论，监控十二经络的开放时间窗口，
在对应时辰激活对应经络以顺应自然节律。

十二经脉流注顺序：
寅(肺)→卯(大肠)→辰(胃)→巳(脾)→午(心)→未(小肠)→
申(膀胱)→酉(肾)→戌(心包)→亥(三焦)→子(胆)→丑(肝)
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger("meridian_rhythm")


class MeridianRhythm:
    """经络流注节律监控器"""

    # 子午流注表：时辰→活跃经络→对应器官
    FLOW_TABLE = {
        "寅": ("手太阴肺经", "lung"),
        "卯": ("手阳明大肠经", "skin"),
        "辰": ("足阳明胃经", "stomach"),
        "巳": ("足太阴脾经", "spleen"),
        "午": ("手少阴心经", "heart"),
        "未": ("手太阳小肠经", "limbs"),
        "申": ("足太阳膀胱经", "kidney"),
        "酉": ("足少阴肾经", "kidney"),
        "戌": ("手厥阴心包经", "heart"),
        "亥": ("手少阳三焦经", "nose"),
        "子": ("足少阳胆经", "liver"),
        "丑": ("足厥阴肝经", "liver"),
    }

    CHINESE_HOURS = {
        0: "子", 1: "子", 2: "丑", 3: "寅", 4: "寅", 5: "卯", 6: "卯",
        7: "辰", 8: "辰", 9: "巳", 10: "巳", 11: "午", 12: "午",
        13: "未", 14: "未", 15: "申", 16: "申", 17: "酉", 18: "酉",
        19: "戌", 20: "戌", 21: "亥", 22: "亥", 23: "子",
    }

    def __init__(self, meridian):
        self.meridian = meridian
        self._running = False
        self._task = None
        self._pulse_count = 0
        self._current_meridian = ""
        self._history: List[Dict] = []

    def get_current_flow(self) -> Dict:
        """获取当前流注信息"""
        hour = datetime.now().hour
        chinese_hour = self.CHINESE_HOURS.get(hour, "子")
        meridian_name, organ_id = self.FLOW_TABLE.get(chinese_hour, ("?", "?"))
        return {
            "hour": hour,
            "chinese_hour": chinese_hour,
            "meridian": meridian_name,
            "organ_id": organ_id,
            "active": self._current_meridian == meridian_name,
        }

    async def pulse(self):
        """执行一次流注脉冲 — 向当前活跃经络对应的器官发送激活信号"""
        flow = self.get_current_flow()
        self._current_meridian = flow["meridian"]
        self._pulse_count += 1

        try:
            self.meridian.send_raw(flow["organ_id"], "rhythm_pulse", {
                "meridian": flow["meridian"],
                "chinese_hour": flow["chinese_hour"],
                "pulse": self._pulse_count,
            })
        except:
            pass

        # v1.42 FIX: 每次脉冲同时给所有已注册器官发送心跳
        try:
            for oid in self.meridian._organs:
                self.meridian.send_raw(oid, "heartbeat", {"source": "rhythm"})
        except:
            pass

        self._history.append({
            "time": time.time(),
            "meridian": flow["meridian"],
            "organ": flow["organ_id"],
        })
        if len(self._history) > 1440:  # 保留一天
            self._history = self._history[-1440:]

        logger.debug(f"[流注] {flow['chinese_hour']}时 → {flow['meridian']} → {flow['organ_id']}")

    async def start(self):
        """启动流注循环"""
        self._running = True
        self._task = asyncio.create_task(self._loop())
        flow = self.get_current_flow()
        logger.info(f"[流注] 经络流注已启动, 当前: {flow['chinese_hour']}时 → {flow['meridian']}")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _loop(self):
        while self._running:
            await self.pulse()
            await asyncio.sleep(120)  # 每 2 分钟一次脉冲

    def stats(self) -> Dict:
        flow = self.get_current_flow()
        return {
            "current_meridian": flow["meridian"],
            "active_organ": flow["organ_id"],
            "chinese_hour": flow["chinese_hour"],
            "pulse_count": self._pulse_count,
        }
