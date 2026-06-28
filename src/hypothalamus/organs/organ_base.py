#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
organ_base.py — 器官基类 · 伏羲 v1.42 易理融合

先天为体 · 后天为用 · 体用合一
每个器官携带完整的易学元数据：八卦、五行、天干、九宫
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional
import time


class Element(Enum):
    """五行"""
    WOOD = "木"
    FIRE = "火"
    EARTH = "土"
    METAL = "金"
    WATER = "水"


class PrenatalBagua(Enum):
    """先天八卦 (体·架构)"""
    QIAN = "乾 ☰"
    DUI  = "兑 ☱"
    LI   = "离 ☲"
    ZHEN = "震 ☳"
    XUN  = "巽 ☴"
    KAN  = "坎 ☵"
    GEN  = "艮 ☶"
    KUN  = "坤 ☷"


class PostnatalBagua(Enum):
    """后天八卦 (用·功能)"""
    LI   = "离 ☲"
    KAN  = "坎 ☵"
    ZHEN = "震 ☳"
    DUI  = "兑 ☱"
    XUN  = "巽 ☴"
    GEN  = "艮 ☶"
    QIAN = "乾 ☰"
    KUN  = "坤 ☷"


class Stem(Enum):
    """十天干"""
    JIA  = "甲"
    YI   = "乙"
    BING = "丙"
    DING = "丁"
    WU   = "戊"
    JI   = "己"
    GENG = "庚"
    XIN  = "辛"
    REN  = "壬"
    GUI  = "癸"


@dataclass
class OrganMetadata:
    """器官易理元数据"""
    organ_id: str
    name: str
    emoji: str
    description: str
    prenatal_gua: PrenatalBagua
    prenatal_direction: str
    postnatal_gua: PostnatalBagua
    postnatal_direction: str
    element: Element
    stem: Stem
    palace_number: int
    ui_position: str
    peak_hour: str
    rest_hour: str

    _SHENG = {
        Element.WOOD: Element.FIRE, Element.FIRE: Element.EARTH,
        Element.EARTH: Element.METAL, Element.METAL: Element.WATER,
        Element.WATER: Element.WOOD
    }
    _KE = {
        Element.WOOD: Element.EARTH, Element.FIRE: Element.METAL,
        Element.EARTH: Element.WATER, Element.METAL: Element.WOOD,
        Element.WATER: Element.FIRE
    }
    _SHENG_BY = {v: k for k, v in _SHENG.items()}
    _KE_BY = {v: k for k, v in _KE.items()}


class OrganBase:
    """器官基类 — 所有器官的抽象父类"""

    def __init__(self, meridian, metadata: OrganMetadata):
        self.meridian = meridian
        self.md = metadata
        self.organ_id = metadata.organ_id
        self._born_at = time.time()
        self._alive = True
        self._stats = {}

    def get_wuxing_info(self) -> Dict:
        e = self.md.element
        return {
            "element": e.value,
            "generates": OrganMetadata._SHENG[e].value,
            "generated_by": OrganMetadata._SHENG_BY[e].value,
            "controls": OrganMetadata._KE[e].value,
            "controlled_by": OrganMetadata._KE_BY[e].value,
        }

    def get_bagua_info(self) -> Dict:
        return {
            "prenatal": {"gua": self.md.prenatal_gua.value, "direction": self.md.prenatal_direction},
            "postnatal": {"gua": self.md.postnatal_gua.value, "direction": self.md.postnatal_direction},
        }

    def get_stem_hour_info(self) -> Dict:
        return {"stem": self.md.stem.value, "peak_hour": self.md.peak_hour, "rest_hour": self.md.rest_hour}

    @property
    def element(self) -> Element:
        return self.md.element

    @property
    def emoji(self) -> str:
        return self.md.emoji

    @property
    def name(self) -> str:
        return self.md.name

    def alive(self) -> bool:
        return self._alive

    def stats(self) -> Dict:
        return {**self._stats, "alive": self._alive, "uptime": round(time.time() - self._born_at)}
