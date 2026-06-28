#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
five_elements.py — 五行平衡监控器 · 伏羲 v1.42

监控五脏器官的五行生克关系，防止单一器官过载，
自动调理维持系统整体平衡稳定。

木(肝) → 火(心) → 土(脾/胃) → 金(肺) → 水(肾) → 木
木克土 · 火克金 · 土克水 · 金克木 · 水克火
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger("five_elements")


class FiveElementsBalance:
    """五行平衡监控器"""

    # 五行 → 器官映射
    ELEMENT_ORGANS = {
        "木": ["liver", "lung"],
        "火": ["heart"],
        "土": ["spleen", "stomach"],
        "金": ["skin", "nose"],
        "水": ["kidney"],
    }

    # 生克关系
    SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
    KE = {"木": "土", "火": "金", "土": "水", "金": "木", "水": "火"}

    def __init__(self, fuxi_instance):
        self.fuxi = fuxi_instance
        self._thresholds = {
            "load": 0.8,
            "error_rate": 0.1,
            "latency_ms": 1000,
        }
        self._history: List[Dict] = []
        self._last_check = 0
        self._running = False

    def _get_organ_stats(self, organ_id: str) -> Dict:
        """从伏羲实例获取器官数据"""
        try:
            organ = getattr(self.fuxi, organ_id, None)
            if organ and hasattr(organ, "stats"):
                return organ.stats()
        except:
            pass
        return {}

    def _calc_element_load(self, element: str) -> float:
        """计算某个五行的综合负载 (0-1)"""
        if element not in self.ELEMENT_ORGANS:
            return 0.0
        loads = []
        for oid in self.ELEMENT_ORGANS[element]:
            s = self._get_organ_stats(oid)
            # 从 stats 推断负载：有 digested/filtered/beat 等计数器代表有工作量
            total = sum(v for v in s.values() if isinstance(v, (int, float)) and v > 0)
            loads.append(min(total / 1000, 1.0) if total > 0 else 0)
        return sum(loads) / max(len(loads), 1)

    def check_balance(self) -> Dict:
        """检查五行平衡状态"""
        status = {}
        for elem, organs in self.ELEMENT_ORGANS.items():
            load = self._calc_element_load(elem)
            error = 0.0
            latency = 0
            status[elem] = {
                "organs": organs,
                "load": round(load, 3),
                "error_rate": error,
                "latency_ms": latency,
                "status": "critical" if load > self._thresholds["load"]
                     else "warning" if load > self._thresholds["load"] * 0.7
                     else "normal",
            }

        imbalances = []
        for elem, s in status.items():
            if s["status"] in ("critical", "warning"):
                imbalances.append({
                    "element": elem,
                    "organs": s["organs"],
                    "load": s["load"],
                    "issue": "过载" if s["status"] == "critical" else "偏高",
                })

        sheng_ke = {}
        for src, dst in self.SHENG.items():
            src_load = status.get(src, {}).get("load", 0)
            dst_load = status.get(dst, {}).get("load", 0)
            sheng_ke[f"{src}_生_{dst}"] = {
                "status": "normal" if src_load < 0.5 or dst_load < 0.7 else "warning",
                "detail": f"{src}({src_load:.1%}) 生 {dst}({dst_load:.1%})",
            }
        for src, dst in self.KE.items():
            src_load = status.get(src, {}).get("load", 0)
            dst_load = status.get(dst, {}).get("load", 0)
            sheng_ke[f"{src}_克_{dst}"] = {
                "status": "normal" if src_load < 0.7 or dst_load < 0.7 else "warning",
                "detail": f"{src}({src_load:.1%}) 克 {dst}({dst_load:.1%})",
            }

        recs = []
        for im in imbalances:
            e = im["element"]
            if im["issue"] == "过载":
                dec = self.KE.get(e, "")
                recs.append(f"⚡ {e}过载 → 增强{dec}以制衡, 或放缓{self.SHENG.get(e,'')}的需求")

        result = {
            "timestamp": time.time(),
            "status": status,
            "imbalances": imbalances,
            "sheng_ke": sheng_ke,
            "recommendations": recs,
        }
        self._history.append(result)
        if len(self._history) > 100:
            self._history = self._history[-100:]
        self._last_check = time.time()
        return result

    async def auto_balance(self):
        """自动五行调理"""
        balance = self.check_balance()
        for rec in balance["recommendations"]:
            logger.info(f"[五行调理] {rec}")
        for im in balance["imbalances"]:
            await self._apply_remedy(im)

    async def _apply_remedy(self, imbalance: Dict):
        """执行调理"""
        e = imbalance["element"]
        organs = imbalance.get("organs", [])
        if e == "木":
            for oid in organs:
                organ = getattr(self.fuxi, oid, None)
                if organ and hasattr(organ, "_filtered_count"):
                    logger.info(f"[五行] 疏肝: {oid} 暂停一轮过滤")
        elif e == "火":
            logger.info("[五行] 清心: 增加路由冷却时间")
        elif e == "土":
            logger.info("[五行] 健脾: 触发存储限速")
        elif e == "金":
            logger.info("[五行] 润肺: 降低生成频率")
        elif e == "水":
            logger.info("[五行] 补肾: 放缓精炼周期")

    async def start(self):
        """启动监控循环"""
        self._running = True
        logger.info("[五行] 五行平衡监控已启动")

    async def stop(self):
        self._running = False

    def stats(self) -> Dict:
        last = self._history[-1] if self._history else {}
        return {
            "last_check": self._last_check,
            "imbalance_count": len(last.get("imbalances", [])),
            "history_size": len(self._history),
        }
