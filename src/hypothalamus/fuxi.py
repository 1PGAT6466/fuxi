"""
hypothalamus/fuxi.py — 伏羲生命体启动器 v1.40

这是伏羲的"出生"文件。
在这里，所有器官被创建、注册到经络，然后伏羲活过来。
"""

import asyncio
import logging
from typing import Dict, Optional

from src.hypothalamus.meridian import Meridian, Signal, SignalPriority
from src.hypothalamus.brain import Brain
try:
    from src.hypothalamus.organs.stomach import StomachAgent
except ImportError:
    StomachAgent = None  # stomach 已迁至装载机
from src.hypothalamus.organs.spleen import SpleenAgent
from src.hypothalamus.organs.lung import LungAgent
from src.hypothalamus.organs.liver import LiverAgent
from src.hypothalamus.organs.heart import HeartAgent
from src.hypothalamus.organs.skeleton import SkeletonAgent
from src.hypothalamus.organs.limbs import LimbsAgent
from src.hypothalamus.organs.kidney import KidneyAgent
from src.hypothalamus.organs.nose import NoseAgent
from src.hypothalamus.balance.five_elements import FiveElementsBalance
from src.hypothalamus.balance.stem_scheduler import StemScheduler
from src.hypothalamus.balance.meridian_rhythm import MeridianRhythm
from src.hypothalamus.organs.skin import SkinAgent
from src.hypothalamus.organs.small_intestine import SmallIntestineAgent
from src.hypothalamus.organs.gallbladder import GallbladderAgent
from src.hypothalamus.organs.sanjiao import SanJiaoAgent

logger = logging.getLogger("fuxi")


class Fuxi:
    """伏羲——完整生命体
    
    创建所有器官，通过经络连为一体，然后活过来。
    
    使用方式：
        fuxi = Fuxi()
        await fuxi.born()
        answer = await fuxi.think("PA66拉伸强度够不够？")
    """
    
    def __init__(self):
        # 经络——全身唯一信号总线
        self.meridian = Meridian()
        
        # 大脑——唯一意识
        self.brain: Optional[Brain] = None
        
        # 器官
        self.stomach = None  # stomach 已迁至装载机
        self.spleen: Optional[SpleenAgent] = None
        self.lung: Optional[LungAgent] = None
        self.liver: Optional[LiverAgent] = None
        self.heart: Optional[HeartAgent] = None
        self.skeleton: Optional[SkeletonAgent] = None
        self.limbs: Optional[LimbsAgent] = None
        self.kidney: Optional[KidneyAgent] = None
        self.nose: Optional[NoseAgent] = None
        
        self._born = False
    
    async def born(self) -> None:
        """伏羲诞生——创建所有器官，启动生命"""
        logger.info("=" * 50)
        logger.info("  伏羲 Fuxi 1.42 — 生命体启动")
        logger.info("=" * 50)
        
        # 1. 启动经络
        await self.meridian.start()
        logger.info("🔗 经络已激活")
        
        # 2. 创建器官（顺序反映它们在活体中的重要性）
        self.heart = HeartAgent(self.meridian)
        logger.info("🫀 心脏已启动")
        
        self.brain = Brain(self.meridian)
        logger.info("🧠 大脑已觉醒")
        
        if StomachAgent:
            self.stomach = StomachAgent(self.meridian)
        logger.info("🍽️ 胃已就绪")
        
        self.spleen = SpleenAgent(self.meridian)
        logger.info("🩸 脾已就绪")
        
        self.lung = LungAgent(self.meridian)
        logger.info("🫁 肺已就绪")
        
        self.liver = LiverAgent(self.meridian)
        logger.info("🛡️ 肝已就绪")
        
        self.skeleton = SkeletonAgent(self.meridian)
        logger.info("🦴 骨骼已就绪")
        
        self.limbs = LimbsAgent(self.meridian)
        logger.info("💪 四肢已就绪")
        
        # v1.42: 头发外探能力已融入皮肤，不再独立注册
        logger.info("🧖 皮肤触角已就绪（含头发外探能力）")
        
        self.kidney = KidneyAgent(self.meridian)
        logger.info("🫘 肾脏已就绪")
        
        self.nose = NoseAgent(self.meridian)
        logger.info("👃 鼻已就绪")
        
        self.skin = SkinAgent(self.meridian)
        self.small_intestine = SmallIntestineAgent(self.meridian)
        self.gallbladder = GallbladderAgent(self.meridian)
        self.sanjiao = SanJiaoAgent(self.meridian)
        logger.info("🧖 皮肤·屏障已就绪")
        
        # 2.5 启动平衡监控
        self.five_elements = FiveElementsBalance(self)
        self.stem_scheduler = StemScheduler(self)
        self.rhythm = MeridianRhythm(self.meridian)
        await self.five_elements.start()
        await self.stem_scheduler.start()
        await self.rhythm.start()
        logger.info("⚖️ 五行平衡 + 天干调度 + 经络流注已启动")

        # 3. 启动自主节律
        await self.heart.start_beating()
        await self.lung.start_breathing()
        await self.kidney.start_filtering()
        await self.nose.start_sniffing()
        if self.stomach:
            await self.stomach.start()
        await self.skeleton.start_scanning()
        await self.brain.start_pulsing()
        await self.liver.start_filtering()
        await self.spleen.start_working()
        await self.small_intestine.start_working()
        await self.gallbladder.start_working()
        await self.sanjiao.start_working()
        # v1.43 fix: skeleton 无 start_working，已在 132 行 start_scanning
        await self.skin.start_guarding()
        
        self._born = True
        
        logger.info("=" * 50)
        logger.info("  伏羲 Fuxi 1.42 — 已苏醒")
        logger.info("=" * 50)
    
    async def think(self, query: str, 
                    enable_external: bool = False) -> Dict:
        """用户向伏羲提问"""
        if not self._born:
            raise RuntimeError("伏羲尚未诞生，请先调用 born()")
        
        return await self.brain.think(query, enable_external=enable_external)
    
    async def digest_file(self, file_path: str) -> Dict:
        """喂食一份文件 —— 通过经络发给胃消化"""
        result = await self.meridian.send_and_wait(
            self.meridian.send(Signal(
                source="brain", target="stomach", signal_type="digest",
                payload={"file_path": file_path},
                priority=SignalPriority.NORMAL,
            )),
            timeout=0
        )
        return result
    
    def health_report(self) -> Dict:
        """全身健康报告"""
        return {
            "organs": {
                info.organ_id: {
                    "name": info.name,
                    "emoji": info.emoji,
                    "alive": self.meridian.is_alive(info.organ_id),
                    "stats": getattr(self, info.organ_id, None).stats() 
                    if hasattr(getattr(self, info.organ_id, None), "stats") 
                    else {}
                }
                for info in self.meridian.list_organs()
            },
            "meridian": self.meridian.stats(),
        }
    
    async def sleep(self) -> None:
        """伏羲休眠"""
        logger.info("伏羲进入休眠…")
        if self.heart:
            await self.heart.stop_beating()
        if self.lung:
            await self.lung.stop_breathing()
        if self.nose:
            await self.nose.stop_sniffing()
        if self.kidney:
            await self.kidney.stop_filtering()
        if self.meridian:
            await self.meridian.stop()
        self._born = False
        logger.info("伏羲已休眠")
