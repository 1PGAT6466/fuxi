"""
business_layer.py — 肾业务层

职责：核心处理逻辑（过滤/清理/检测）
"""

import logging
from typing import Dict, List

from .data_layer import KidneyDataLayer
from .utility_layer import KidneyUtilityLayer

logger = logging.getLogger("kidney.business")


class KidneyBusinessLayer:
    """肾业务层——核心处理逻辑"""

    # 阈值配置
    MAX_CHUNKS_THRESHOLD = 8000
    STALE_DAYS = 30
    ESSENCE_THRESHOLD = 0.5
    DEFICIENCY_THRESHOLD = 0.3

    def __init__(self, data_layer: KidneyDataLayer, utility_layer: KidneyUtilityLayer):
        self._data = data_layer
        self._util = utility_layer
        self._filter_count = 0
        self._purged_total = 0
        self._essence_total = 0

    # ── 核心业务 ──

    async def filter_blood(self) -> Dict:
        """过滤全身数据——保留精华，标记废物
        
        流程：
        1. 加载所有数据块
        2. 计算每个数据块的质量分数
        3. 按分数分为精华和废物
        4. 如果数据量超过阈值，触发清理
        """
        try:
            # 1. 加载数据
            chunks = self._data.load_chunks()
            if not chunks:
                return self._util.format_filter_result(0, 0, 0)

            # 2. 加载访问计数
            access_counts = self._data.load_access_counts()

            # 3. 分类数据
            essence = []
            waste = []

            for chunk in chunks:
                # 注入访问计数
                file_hash = chunk.get("file_hash", "")
                if file_hash:
                    chunk["access_count"] = access_counts.get(file_hash, 0)

                # 计算质量分数
                score = self._util.calculate_quality_score(chunk)

                # 分类
                if self._util.is_essence(score, self.ESSENCE_THRESHOLD):
                    chunk["_quality_score"] = score
                    essence.append(chunk)
                else:
                    chunk["_quality_score"] = score
                    chunk["_waste"] = True
                    waste.append(chunk)

            # 4. 更新统计
            self._essence_total = len(essence)
            self._filter_count += 1

            # 5. 检查是否需要清理
            if len(chunks) > self.MAX_CHUNKS_THRESHOLD:
                await self.purge_waste()

            return self._util.format_filter_result(len(chunks), len(essence), len(waste))

        except Exception as e:
            logger.error(f"[Kidney] 过滤失败: {e}")
            return {"error": str(e)}

    def purge_waste(self) -> Dict:
        """排泄废物——真正删除低质/过期数据
        
        流程：
        1. 加载所有数据块
        2. 筛选出过期数据
        3. 保存未过期数据
        """
        try:
            # 1. 加载数据
            chunks = self._data.load_chunks()

            # 2. 筛选数据
            survivors = []
            purged = 0

            for chunk in chunks:
                last_access = chunk.get("last_accessed", 0)
                if isinstance(last_access, str):
                    import time
                    try:
                        last_access = time.mktime(time.strptime(last_access, "%Y-%m-%d"))
                    except Exception:
                        last_access = 0

                if self._util.is_stale(float(last_access or 0), self.STALE_DAYS):
                    purged += 1
                else:
                    survivors.append(chunk)

            # 3. 保存数据
            if purged > 0:
                self._data.save_chunks(survivors)

            # 4. 更新统计
            self._purged_total += purged
            logger.info(f"[Kidney] 清理 {purged} 个过期数据块")

            return self._util.format_purge_result(purged, self._purged_total)

        except Exception as e:
            logger.error(f"[Kidney] 清理失败: {e}")
            return {"error": str(e)}

    def detect_deficiency(self, category: str = "") -> Dict:
        """检测知识薄弱领域——缺数据的主题
        
        流程：
        1. 统计各分类数据量
        2. 计算平均值
        3. 找出低于阈值的分类
        """
        try:
            # 1. 加载数据
            chunks = self._data.load_chunks()

            # 2. 统计分类
            cat_counts: Dict[str, int] = {}
            for chunk in chunks:
                cat = chunk.get("category", "未分类")
                cat = cat if isinstance(cat, str) else str(cat)
                cat_counts[cat] = cat_counts.get(cat, 0) + 1

            # 3. 计算薄弱区域
            weak_areas = []
            if cat_counts:
                avg = sum(cat_counts.values()) / len(cat_counts)
                weak_areas = [
                    {
                        "category": cat,
                        "count": count,
                        "deficiency": self._util.calculate_deficiency(count, avg)
                    }
                    for cat, count in cat_counts.items()
                    if self._util.is_deficient(count, avg, self.DEFICIENCY_THRESHOLD)
                ]

            return self._util.format_deficiency_result(weak_areas, cat_counts)

        except Exception as e:
            logger.error(f"[Kidney] 薄弱检测失败: {e}")
            return {"error": str(e)}

    # ── 统计信息 ──

    def get_stats(self, alive: bool) -> Dict:
        """获取统计信息"""
        return self._util.format_stats(
            filter_count=self._filter_count,
            purged_total=self._purged_total,
            essence_total=self._essence_total,
            running=True,  # 由信号层控制
            stale_days=self.STALE_DAYS,
            alive=alive,
        )
