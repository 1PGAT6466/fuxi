"""
signal_layer.py — 肾信号层

职责：处理经络信号（对外接口）
"""

import asyncio
import logging
from typing import Dict

from src.hypothalamus.meridian import Meridian, Signal, SignalPriority
from src.hypothalamus.organs.organ_base import OrganBase, OrganMetadata, Element, PrenatalBagua, PostnatalBagua, Stem

from .data_layer import KidneyDataLayer
from .business_layer import KidneyBusinessLayer
from .utility_layer import KidneyUtilityLayer

logger = logging.getLogger("kidney.signal")


class KidneyAgent(OrganBase):
    """肾智能体——信号层

    职责：
    1. 接收经络信号
    2. 调用业务层处理
    3. 返回处理结果

    信号类型：
    - heartbeat: 心跳信号
    - filter: 过滤数据
    - purge: 清理数据
    - detect_deficiency: 检测薄弱
    """

    FILTER_INTERVAL = 25

    def __init__(self, meridian: Meridian):
        # 初始化器官基类
        super().__init__(meridian, OrganMetadata(
            organ_id="kidney",
            name="肾·精炼",
            emoji="🫘",
            description="数据精炼过滤",
            prenatal_gua=PrenatalBagua.KAN,
            prenatal_direction="西",
            postnatal_gua=PostnatalBagua.KAN,
            postnatal_direction="北",
            element=Element.WATER,
            stem=Stem.REN,
            palace_number=1,
            ui_position="north",
            peak_hour="17:00-19:00",
            rest_hour="05:00-07:00"
        ))

        # 初始化各层
        self._data_layer = KidneyDataLayer()
        self._utility_layer = KidneyUtilityLayer()
        self._business_layer = KidneyBusinessLayer(self._data_layer, self._utility_layer)

        # 状态
        self._running = False
        self._task = None

        # 注册到经络
        self.meridian.register_organ(
            self.organ_id, "肾", "🫘",
            "数据精炼：过滤→保留精华→排泄废物→维持平衡",
        )

        # 订阅信号
        self.meridian.subscribe(self.organ_id, "heartbeat", self._handle_heartbeat)
        self.meridian.subscribe(self.organ_id, "filter", self._handle_filter)
        self.meridian.subscribe(self.organ_id, "purge", self._handle_purge)
        self.meridian.subscribe(self.organ_id, "detect_deficiency", self._handle_deficiency)

    # ══════════════════════════════════════════
    # 信号层：处理经络信号
    # ══════════════════════════════════════════

    def _handle_heartbeat(self, signal: Signal) -> None:
        """处理心跳信号"""
        self.meridian.heartbeat(self.organ_id)

    async def _handle_filter(self, signal: Signal) -> None:
        """处理过滤信号"""
        result = await self._business_layer.filter_blood()
        self.meridian.reply(signal, result)

        # 通知大脑
        if "error" not in result:
            self.meridian.send(Signal(
                source=self.organ_id,
                target="brain",
                signal_type="filter_complete",
                payload={
                    "essence": result.get("essence", 0),
                    "waste": result.get("waste", 0),
                },
                priority=SignalPriority.LOW,
            ))

    async def _handle_purge(self, signal: Signal) -> None:
        """处理清理信号"""
        result = await self._business_layer.purge_waste()
        self.meridian.reply(signal, result)

        # 通知脾
        if "error" not in result and result.get("purged", 0) > 0:
            self.meridian.send(Signal(
                source=self.organ_id,
                target="spleen",
                signal_type="data_purged",
                payload={"purged_count": result["purged"]},
                priority=SignalPriority.LOW,
            ))

    async def _handle_deficiency(self, signal: Signal) -> None:
        """处理薄弱检测信号"""
        category = signal.payload.get("category", "")
        result = await self._business_layer.detect_deficiency(category)
        self.meridian.reply(signal, result)

        # 通知大脑
        if "error" not in result and result.get("weak_areas"):
            self.meridian.send(Signal(
                source=self.organ_id,
                target="brain",
                signal_type="deficiency_detected",
                payload={"weak_areas": result["weak_areas"]},
                priority=SignalPriority.NORMAL,
            ))

    # ══════════════════════════════════════════
    # 生命周期：启动/停止
    # ══════════════════════════════════════════

    def start_filtering(self) -> None:
        """启动肾脏过滤"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._filter_loop())
        logger.info("[Kidney] 肾脏过滤已启动 🫘")

    def stop_filtering(self) -> None:
        """停止肾脏过滤"""
        self._running = False
        if self._task:
            self._task.cancel()

    async def _filter_loop(self) -> None:
        """过滤循环"""
        while self._running:
            try:
                await asyncio.sleep(self.FILTER_INTERVAL)
                self.meridian.heartbeat(self.organ_id)
                await self._business_layer.filter_blood()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Kidney] 过滤循环错误: {e}")

    # ══════════════════════════════════════════
    # 对外接口：供其他模块调用
    # ══════════════════════════════════════════

    def stats(self) -> Dict:
        """获取统计信息"""
        return self._business_layer.get_stats(
            alive=self.meridian.is_alive(self.organ_id)
        )

    # ══════════════════════════════════════════
    # 向后兼容：保留原有方法接口
    # ══════════════════════════════════════════

    # DEPRECATED: 未使用，v1.50 标记待删除
    def _score_chunk(self, chunk: Dict) -> float:
        """向后兼容：计算数据块质量分数"""
        return self._utility_layer.calculate_quality_score(chunk)
# DEPRECATED: 未使用，v1.50 标记待删除

    def _load_access_counts(self) -> Dict[str, int]:
        """向后兼容：加载访问计数"""
        # DEPRECATED: 未使用，v1.50 标记待删除
        return self._data_layer.load_access_counts()

    def _save_access_counts(self, counts: Dict[str, int]) -> None:
        # DEPRECATED: 未使用，v1.50 标记待删除
        """向后兼容：保存访问计数"""
        self._data_layer.save_access_counts(counts)

    # DEPRECATED: 未使用，v1.50 标记待删除
    async def _filter_blood(self) -> Dict:
        """向后兼容：过滤数据"""
        return await self._business_layer.filter_blood()
# DEPRECATED: 未使用，v1.50 标记待删除

    async def _purge_waste(self) -> Dict:
        """向后兼容：清理数据"""
        return await self._business_layer.purge_waste()

    async def _detect_deficiency(self, category: str = "") -> Dict:
        """向后兼容：检测薄弱"""
        return await self._business_layer.detect_deficiency(category)
