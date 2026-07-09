#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kan.py — 坎卦 ☵ · 伏羲 v2.1

坎为水，主风险控制与数据精炼。
迁移自：KidneyAgent（肾）数据精炼 + LiverAgent（肝）免疫过滤

核心能力：
  - 数据质量评分 (score_quality)
  - 知识薄弱区域检测 (detect_deficiency)
  - 低质量数据清理 (purge_low_quality)
  - 访问计数管理 (load_access_counts / save_access_counts)
  - 免疫记忆黑名单 (filter_by_immune_memory / learn_harmful_source / get_immune_memory)

注意：本模块不依赖 organs/ 目录，所有逻辑已内联。
"""


import json
import logging
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.bagua.base_gua import GuaBase

logger = logging.getLogger("bagua.kan")

# 访问计数持久化文件（与 KidneyDataLayer 保持兼容）
ACCESS_COUNTS_FILE = os.environ.get(
    "KB_ACCESS_COUNTS_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "access_counts.json"),
)


class KanGua(GuaBase):
    """坎卦 — 风险控制与数据精炼

    继承自 GuaBase，提供：
      - 4 级健康梯度 + 断路器管理
      - 数据质量评分、薄弱检测、废物清理
      - 免疫记忆（有害来源黑名单）过滤
    """

    GUA_NAME = "kan"
    GUA_EMOJI = "☵"
    GUA_DESCRIPTION = "风险控制与数据精炼 — 质量评分、薄弱检测、免疫过滤"

    # ========================================================================
    # 阈值常量
    # ========================================================================

    MAX_CHUNKS_THRESHOLD: int = 8000
    STALE_DAYS: int = 30
    ESSENCE_THRESHOLD: float = 0.5
    DEFICIENCY_THRESHOLD: float = 0.3

    # 免疫过滤阈值
    IMMUNE_TOXICITY_THRESHOLD: float = 0.6
    MIN_TEXT_LENGTH: int = 10
    MIN_VALID_CHAR_RATIO: float = 0.5

    # ========================================================================
    # 初始化
    # ========================================================================

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        # -- 访问计数缓存 --
        self._access_counts: Optional[Dict[str, int]] = None

        # -- 免疫记忆 {source_name: {"toxicity": float, "count": int}} --
        self._immune_memory: Dict[str, Dict] = {}
        self._filtered_count: int = 0

        # 从持久化存储加载免疫记忆
        self._load_immune_memory_from_store()

    # ========================================================================
    # GuaBase 要求实现的方法
    # ========================================================================

    def _setup_degradation_rules(self) -> None:
        """定义降级规则"""
        from src.bagua.base_gua import DegradationRule, FallbackAction

        # 规则 1：数据存储不可用时降级为只返回缓存结果
        self.add_rule(DegradationRule(
            name="data_store_unavailable",
            condition_fn=lambda: not self._is_data_store_available(),
            fallback=FallbackAction(
                name="return_cached_stats",
                handler=self._degraded_data_handler,
                description="数据存储不可用，返回缓存统计",
            ),
            priority=1,
        ))

    def _execute_core(self, params: Dict[str, Any]) -> Any:
        """核心路由：根据 params["action"] 分发到对应方法

        支持的 action:
          - score_quality:     对 chunk 列表做质量评分
          - detect_deficiency: 检测知识库薄弱区域
          - purge_low_quality: 清理低质量数据
          - load_access_counts:加载访问计数
          - save_access_counts:保存访问计数
          - filter_by_immune:  基于免疫记忆过滤结果
          - learn_harmful:     学习有害来源
          - get_immune_memory: 获取免疫记忆
          - stats:             获取统计摘要
        """
        action = params.get("action", "")

        if action == "score_quality":
            return self.score_quality(params.get("chunks", []))
        elif action == "detect_deficiency":
            return self.detect_deficiency(params.get("category", ""))
        elif action == "purge_low_quality":
            return self.purge_low_quality(params.get("threshold", 0.3))
        elif action == "load_access_counts":
            return self.load_access_counts()
        elif action == "save_access_counts":
            return self.save_access_counts(params.get("counts", {}))
        elif action == "filter_by_immune":
            return {
                "filtered": self.filter_by_immune_memory(params.get("results", [])),
                "original_count": len(params.get("results", [])),
                "filtered_count": self._filtered_count,
            }
        elif action == "learn_harmful":
            self.learn_harmful_source(
                source=params.get("source", ""),
                toxicity=params.get("toxicity", 0.2),
            )
            return {"ok": True}
        elif action == "get_immune_memory":
            return self.get_immune_memory()
        elif action == "stats":
            return self.stats()
        else:
            raise ValueError(f"[坎卦] 未知 action: {action}")

    # ========================================================================
    # 数据存储可用性检查
    # ========================================================================

    @staticmethod
    def _is_data_store_available() -> bool:
        """检查 data_store 是否可用"""
        try:
            from src.db.data_store import load_chunks
            return True
        except Exception:  # TODO: Narrow exception type
            return False

    @staticmethod
    def _degraded_data_handler(params: Dict[str, Any]) -> Dict[str, Any]:
        """降级：数据存储不可用时的兜底返回"""
        return {
            "degraded": True,
            "message": "数据存储暂不可用",
            "action": params.get("action", ""),
        }

    # ========================================================================
    # 1. 数据质量评分（迁自 KidneyUtilityLayer.calculate_quality_score）
    # ========================================================================

    def score_quality(self, chunks: list) -> list:
        """对 Chunk 列表做质量评分

        评分维度（每项 0.0-1.0）：
          1. 访问频率（偏移 -0.3 ~ +0.3）
          2. 新鲜度（偏移 -0.1 ~ +0.1）
          3. 文本完整性（偏移 -0.4 ~ 0）

        Args:
            chunks: 数据块列表，每个元素为 dict

        Returns:
            带 _quality_score 字段的 chunk 列表
        """
        for chunk in chunks:
            score = self._calculate_quality_score(chunk)
            chunk["_quality_score"] = round(score, 4)
        return chunks

    @staticmethod
    def _calculate_quality_score(chunk: Dict) -> float:
        """计算单个数据块的质量分数（0.0-1.0）

        内部评分逻辑，等同于 KidneyUtilityLayer.calculate_quality_score
        """
        score = 0.5

        # 1. 访问频率（0-0.3分）
        access_count = chunk.get("access_count", 0)
        if access_count > 10:
            score += 0.3
        elif access_count > 3:
            score += 0.15
        elif access_count == 0:
            score -= 0.3

        # 2. 新鲜度
        created_at = chunk.get("created_at", "")
        if created_at:
            try:
                created = datetime.fromisoformat(str(created_at).replace("Z", ""))
                days_old = (datetime.now() - created).days
                if days_old < 30:
                    score += 0.1
                elif days_old > 180:
                    score -= 0.1
            except (ValueError, TypeError) as e:
                logger.debug("[坎卦] 解析 created_at 失败 '%s': %s", created_at, e)

        # 3. 完整性
        if not chunk.get("text", "").strip():
            score -= 0.4

        return max(min(score, 1.0), 0.0)

    # ========================================================================
    # 2. 知识薄弱检测（迁自 KidneyBusinessLayer.detect_deficiency）
    # ========================================================================

    def detect_deficiency(self, category: str = "") -> Dict[str, Any]:
        """检测知识库薄弱区域

        流程：
          1. 按 category 分组统计各分类数据量
          2. 计算平均值
          3. 找出数量低于均值 * DEFICIENCY_THRESHOLD 的分类

        Args:
            category: 可选，指定只检测某个分类

        Returns:
            {
                "weak_areas": [{"category": str, "count": int, "deficiency": float}, ...],
                "category_distribution": {category: count, ...}
            }
        """
        try:
            chunks = self._load_chunks()

            # 统计分类
            cat_counts: Dict[str, int] = {}
            for chunk in chunks:
                cat = chunk.get("category", "未分类")
                cat = str(cat) if cat is not None else "未分类"
                if category and cat != category:
                    continue
                cat_counts[cat] = cat_counts.get(cat, 0) + 1

            # 计算薄弱区域
            weak_areas: List[Dict[str, Any]] = []
            if cat_counts:
                avg = sum(cat_counts.values()) / len(cat_counts)
                for cat, count in cat_counts.items():
                    if count < avg * self.DEFICIENCY_THRESHOLD:
                        deficiency = round(1 - count / max(avg, 1), 2)
                        weak_areas.append({
                            "category": cat,
                            "count": count,
                            "deficiency": deficiency,
                        })

            return {
                "weak_areas": weak_areas,
                "category_distribution": cat_counts,
            }

        except Exception as e:  # TODO: Narrow exception type
            logger.error("[坎卦] 薄弱检测失败: %s", e)
            return {"error": str(e)}

    # ========================================================================
    # 3. 低质量数据清理（迁自 KidneyBusinessLayer.purge_waste）
    # ========================================================================

    def purge_low_quality(self, threshold: float = 0.3) -> Dict[str, Any]:
        """清理低质量数据

        流程：
          1. 加载所有数据块
          2. 对每个 chunk 计算质量分数
          3. 删除分数低于 threshold 的 chunk
          4. 保存剩余数据

        Args:
            threshold: 质量分数阈值，低于此值将被清除

        Returns:
            {"purged": int, "survived": int, "total_processed": int}
        """
        try:
            chunks = self._load_chunks()
            if not chunks:
                return {"purged": 0, "survived": 0, "total_processed": 0}

            survivors: List[Dict] = []
            purged = 0

            for chunk in chunks:
                score = self._calculate_quality_score(chunk)
                if score < threshold:
                    purged += 1
                else:
                    chunk["_quality_score"] = round(score, 4)
                    survivors.append(chunk)

            # 保存幸存数据
            if purged > 0:
                self._save_chunks(survivors)

            logger.info("[坎卦] 清理 %d 个低质量数据块 (threshold=%.2f)", purged, threshold)

            return {
                "purged": purged,
                "survived": len(survivors),
                "total_processed": len(chunks),
            }

        except Exception as e:  # TODO: Narrow exception type
            logger.error("[坎卦] 低质量清理失败: %s", e)
            return {"error": str(e)}

    # ========================================================================
    # 4. 访问计数管理（迁自 KidneyDataLayer）
    # ========================================================================

    def load_access_counts(self) -> Dict[str, int]:
        """从磁盘加载访问计数

        Returns:
            {file_hash: count, ...}
        """
        if self._access_counts is not None:
            return self._access_counts

        path = Path(ACCESS_COUNTS_FILE)
        if not path.exists():
            self._access_counts = {}
            return self._access_counts

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._access_counts = data.get("counts", {}) if isinstance(data, dict) else {}
        except Exception as e:  # TODO: Narrow exception type
            logger.warning("[坎卦] 加载访问计数失败: %s", e)
            self._access_counts = {}

        return self._access_counts

    def save_access_counts(self, counts: Dict[str, int]) -> Dict[str, Any]:
        """持久化访问计数

        Args:
            counts: {file_hash: count, ...}

        Returns:
            {"saved": True, "file": str}
        """
        path = Path(ACCESS_COUNTS_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "counts": counts,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }, f, ensure_ascii=False, indent=2)
            self._access_counts = counts
            return {"saved": True, "file": str(path)}
        except Exception as e:  # TODO: Narrow exception type
            logger.warning("[坎卦] 保存访问计数失败: %s", e)
            return {"saved": False, "error": str(e)}

    def increment_access_count(self, file_hash: str) -> int:
        """增加访问计数并返回新值"""
        counts = self.load_access_counts()
        counts[file_hash] = counts.get(file_hash, 0) + 1
        self.save_access_counts(counts)
        return counts[file_hash]

    # ========================================================================
    # 5. 免疫记忆过滤（迁自 LiverAgent._filter + _handle_learn）
    # ========================================================================

    def filter_by_immune_memory(self, results: list) -> list:
        """基于免疫记忆黑名单过滤搜索结果

        过滤规则：
          1. 如果来源在免疫记忆中且 toxicity > 0.6，则标记为有害并过滤
          2. 文本长度 < MIN_TEXT_LENGTH 的过滤
          3. 有效字符比例 < MIN_VALID_CHAR_RATIO 的过滤

        Args:
            results: 搜索结果列表 [{file_name, text, ...}, ...]

        Returns:
            过滤后的干净结果列表
        """
        clean: List[Dict] = []
        for r in results:
            source_file = r.get("file_name", "")
            # 1. 免疫记忆黑名单过滤
            if source_file in self._immune_memory:
                toxicity = self._immune_memory[source_file]["toxicity"]
                if toxicity > self.IMMUNE_TOXICITY_THRESHOLD:
                    r["_toxic"] = True
                    r["_toxicity"] = toxicity
                    self._filtered_count += 1
                    continue

            # 2. 文本长度过滤
            text = r.get("text", "").strip()
            if len(text) < self.MIN_TEXT_LENGTH:
                continue

            # 3. 有效字符比例过滤
            valid_chars = sum(
                1 for c in text
                if '\u4e00' <= c <= '\u9fff' or c.isascii()
            )
            if valid_chars / max(len(text), 1) < self.MIN_VALID_CHAR_RATIO:
                continue

            clean.append(r)

        return clean

    def learn_harmful_source(self, source: str, toxicity: float = 0.2) -> None:
        """学习一个有害来源，加入免疫记忆

        每次调用增加 toxicity 计数，toxicity 上限为 1.0。

        Args:
            source:   来源标识（如文件名）
            toxicity: 毒性增量（默认 0.2）
        """
        if not source:
            return

        if source not in self._immune_memory:
            self._immune_memory[source] = {"toxicity": 0.0, "count": 0}

        self._immune_memory[source]["count"] += 1
        self._immune_memory[source]["toxicity"] = min(
            self._immune_memory[source]["toxicity"] + float(toxicity),
            1.0,
        )

        logger.info(
            "[坎卦] 学习有害来源: %s (toxicity=%.1f, count=%d)",
            source,
            self._immune_memory[source]["toxicity"],
            self._immune_memory[source]["count"],
        )

        self._save_immune_memory_to_store()

    def get_immune_memory(self) -> Dict[str, Dict]:
        """获取完整免疫记忆

        Returns:
            {source_name: {"toxicity": float, "count": int}, ...}
        """
        return dict(self._immune_memory)

    # ========================================================================
    # 免疫记忆持久化（迁自 LiverAgent._load_immune_memory / _save_immune_memory）
    # ========================================================================

    def _load_immune_memory_from_store(self) -> None:
        """从 data_store 加载免疫记忆"""
        try:
            from src.db.data_store import load_config
            cfg = load_config()
            mem = cfg.get("liver_immune_memory", {})
            if isinstance(mem, dict):
                self._immune_memory = mem
                logger.info("[坎卦] 加载 %d 条免疫记忆", len(mem))
        except Exception as e:  # TODO: Narrow exception type
            logger.warning("[坎卦] 加载免疫记忆失败: %s", e)

    def _save_immune_memory_to_store(self) -> None:
        """通过 data_store 持久化免疫记忆"""
        try:
            from src.db.data_store import load_config, save_config
            cfg = load_config()
            cfg["liver_immune_memory"] = self._immune_memory
            save_config(cfg)
        except Exception as e:  # TODO: Narrow exception type
            logger.warning(
                "[坎卦] 保存免疫记忆失败: %s\n%s",
                e, traceback.format_exc(),
            )

    # ========================================================================
    # 数据加载 / 保存辅助方法
    # ========================================================================

    @staticmethod
    def _load_chunks() -> List[Dict]:
        """加载所有数据块"""
        try:
            from src.db.data_store import load_chunks
            return load_chunks()
        except Exception as e:  # TODO: Narrow exception type
            logger.error("[坎卦] 加载数据块失败: %s", e)
            return []

    @staticmethod
    def _save_chunks(chunks: List[Dict]) -> bool:
        """保存数据块"""
        try:
            from src.db.data_store import save_chunks
            save_chunks(chunks)
            return True
        except Exception as e:  # TODO: Narrow exception type
            logger.error("[坎卦] 保存数据块失败: %s", e)
            return False

    # ========================================================================
    # 统计信息
    # ========================================================================

    def stats(self) -> Dict[str, Any]:
        """获取坎卦统计摘要"""
        return {
            "gua": self.GUA_NAME,
            "emoji": self.GUA_EMOJI,
            "health": self._health.value,
            "uptime_sec": self.uptime_sec,
            "immune_memory_size": len(self._immune_memory),
            "filtered_total": self._filtered_count,
        }


__all__ = ["KanGua"]
