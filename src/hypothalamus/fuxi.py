"""
hypothalamus/fuxi.py — 伏羲生命体启动器 v2.1

这是伏羲的"出生"文件。
v2.1: 器官层已归档，仅保留四象 + 八卦模块。
"""

import asyncio
import logging
from typing import Dict, Optional

from src.bagua.config.common_settings import get_meridian

# 四象模块
from src.shaoyang.pipeline import ShaoyangPipeline
from src.taiyang.retrieval import TaiyangRetrieval
from src.shaoyin.brain import ShaoyinBrain
from src.taiyin.server import TaiyinServer

logger = logging.getLogger("fuxi")


class Fuxi:
    """伏羲——完整生命体 v2.1

    仅保留四象 + 八卦，器官层已归档。

    使用方式：
        fuxi = Fuxi()
        await fuxi.born()
        answer = await fuxi.think("PA66拉伸强度够不够？")
    """

    def __init__(self):
        # 经络——全身唯一信号总线（来自八卦配置）
        self.meridian = get_meridian()

        # 四象模块
        self.shaoyang: Optional[ShaoyangPipeline] = None
        self.taiyang: Optional[TaiyangRetrieval] = None
        self.shaoyin: Optional[ShaoyinBrain] = None
        self.taiyin: Optional[TaiyinServer] = None

        self._born = False

    async def born(self) -> None:
        """伏羲诞生——初始化四象 + 八卦"""
        logger.info("=" * 50)
        logger.info("  伏羲 Fuxi 2.1 — 生命体启动（精简版）")
        logger.info("=" * 50)

        # 1. 启动经络
        await self.meridian.start()
        logger.info("🔗 经络已激活")

        # 2. 创建四象模块
        self.shaoyang = ShaoyangPipeline(self.meridian)
        logger.info("🌱 少阳·消化 已就绪")

        self.taiyang = TaiyangRetrieval(self.meridian)
        logger.info("☀️ 太阳·筑基 已就绪")

        self.shaoyin = ShaoyinBrain(self.meridian)
        logger.info("🌙 少阴·炼化 已就绪")

        self.taiyin = TaiyinServer(self.meridian)
        logger.info("🌑 太阴·显化 已就绪")

        self._born = True

        logger.info("=" * 50)
        logger.info("  伏羲 Fuxi 2.1 — 已苏醒（四象 + 八卦）")
        logger.info("=" * 50)

    async def think(self, query: str,
                    enable_external: bool = False) -> Dict:
        """用户向伏羲提问"""
        if not self._born:
            raise RuntimeError("伏羲尚未诞生，请先调用 born()")

        # 通过少阴·炼化处理
        if self.shaoyin:
            return await self.shaoyin.think(query)
        raise RuntimeError("少阴模块不可用")

    async def digest_file(self, file_path: str) -> Dict:
        """喂食一份文件 —— 通过少阳管线处理"""
        if self.shaoyang:
            return await self.shaoyang.digest(file_path)
        raise RuntimeError("少阳模块不可用")

    def health_report(self) -> Dict:
        """全身健康报告"""
        report = {
            "symbols": {},
            "meridian": self.meridian.stats(),
        }

        # 四象状态
        if self.shaoyang:
            report["symbols"]["shaoyang"] = self.shaoyang.get_status()
        if self.taiyang:
            report["symbols"]["taiyang"] = self.taiyang.get_status()
        if self.shaoyin:
            report["symbols"]["shaoyin"] = self.shaoyin.get_status()
        if self.taiyin:
            report["symbols"]["taiyin"] = self.taiyin.get_status()

        return report

    async def sleep(self) -> None:
        """伏羲休眠"""
        logger.info("伏羲进入休眠…")
        if self.meridian:
            await self.meridian.stop()
        self._born = False
        logger.info("伏羲已休眠")
