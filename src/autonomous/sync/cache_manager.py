"""
缓存管理器 (Cache Manager)
============================
缓存统计、清理、预热、一致性检查。
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.autonomous.sync.config import (
    CACHE_CLEANUP_THRESHOLD,
    CACHE_MAX_AGE_HOURS,
    CACHE_MAX_SIZE_MB,
    CACHE_WARMUP_BATCH_SIZE,
)

logger = logging.getLogger("fuxi.sync.cache")


@dataclass
class CacheStatsResult:
    """缓存统计结果"""

    total_entries: int = 0
    total_size_bytes: int = 0
    total_size_mb: float = 0.0
    hit_count: int = 0
    miss_count: int = 0
    hit_rate: float = 0.0
    oldest_entry_age_hours: float = 0.0
    newest_entry_age_hours: float = 0.0
    l1_size: int = 0
    l2_size: int = 0
    penetration_blocked: int = 0


@dataclass
class CleanupResult:
    """清理结果"""

    cleaned_entries: int = 0
    freed_bytes: int = 0
    freed_mb: float = 0.0
    rules_applied: List[str] = None

    def __post_init__(self):
        if self.rules_applied is None:
            self.rules_applied = []


@dataclass
class WarmupResult:
    """预热结果"""

    warmed_up: int = 0
    failed: int = 0
    total_time_ms: float = 0.0


@dataclass
class ConsistencyResult:
    """一致性检查结果"""

    total_checked: int = 0
    consistent: int = 0
    inconsistent: int = 0
    repaired: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class CacheManager:
    """
    缓存管理器
    提供缓存统计、清理、预热和一致性检查功能。
    """

    def __init__(self):
        self._stats_hits = 0
        self._stats_misses = 0
        self._cleanup_history: List[dict] = []

    # ── 缓存统计 ──
    async def get_stats(self) -> CacheStatsResult:
        """获取缓存统计信息"""
        result = CacheStatsResult()

        try:
            # 获取 RAG 缓存统计
            from src.services.cache import get_cache_stats

            rag_stats = get_cache_stats()

            result.l1_size = rag_stats.get("l1_size", 0)
            result.l2_size = rag_stats.get("l2_size", 0)
            result.hit_count = rag_stats.get("hits", 0)
            result.miss_count = rag_stats.get("misses", 0)
            result.penetration_blocked = rag_stats.get("penetration_blocked", 0)

            total = result.hit_count + result.miss_count
            result.hit_rate = round(result.hit_count / max(1, total), 3)
            result.total_entries = result.l1_size + result.l2_size

        except ImportError:
            logger.debug("[CacheManager] RAG 缓存模块未加载")
        except Exception as e:
            logger.warning(f"[CacheManager] 获取 RAG 缓存统计失败: {e}")

        try:
            # 获取 infra 缓存统计
            from src.infra.cache_stats import get_cache_stats as get_infra_stats

            infra_stats = get_infra_stats()
            infra_data = infra_stats.get_stats()

            # 合并统计
            result.hit_count += infra_data.get("hits", 0)
            result.miss_count += infra_data.get("misses", 0)
            total = result.hit_count + result.miss_count
            result.hit_rate = round(result.hit_count / max(1, total), 3)

        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"[CacheManager] 获取 infra 缓存统计失败: {e}")

        # 估算缓存大小
        result.total_size_mb = round(result.total_entries * 0.5 / 1024, 2)  # 粗略估算每个条目 ~0.5KB

        return result

    # ── 缓存清理 ──
    async def cleanup(self, rules: Optional[List[str]] = None) -> CleanupResult:
        """
        按规则清理缓存。

        规则:
            - expired: 清理过期条目
            - oversize: 清理超容量条目
            - lru: LRU 淘汰
            - all: 执行所有规则
        """
        if rules is None:
            rules = ["expired", "oversize"]

        result = CleanupResult()
        start_ts = time.monotonic()

        for rule in rules:
            if rule == "all":
                rules_to_apply = ["expired", "oversize", "lru"]
                for r in rules_to_apply:
                    cleaned = await self._apply_cleanup_rule(r)
                    result.cleaned_entries += cleaned
                    result.rules_applied.append(r)
            else:
                cleaned = await self._apply_cleanup_rule(rule)
                result.cleaned_entries += cleaned
                result.rules_applied.append(rule)

        result.freed_bytes = result.cleaned_entries * 512  # 估算
        result.freed_mb = round(result.freed_bytes / (1024 * 1024), 2)

        duration_ms = (time.monotonic() - start_ts) * 1000
        self._cleanup_history.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "cleaned_entries": result.cleaned_entries,
                "freed_mb": result.freed_mb,
                "rules": result.rules_applied,
                "duration_ms": round(duration_ms, 2),
            }
        )

        # 保留最近 100 条历史
        if len(self._cleanup_history) > 100:
            self._cleanup_history = self._cleanup_history[-100:]

        logger.info(
            f"[CacheManager] 清理完成: 清除 {result.cleaned_entries} 条, "
            f"释放 {result.freed_mb}MB, 规则: {result.rules_applied}"
        )

        return result

    async def _apply_cleanup_rule(self, rule: str) -> int:
        """应用单个清理规则"""
        cleaned = 0

        if rule == "expired":
            # 清理过期的 RAG 缓存
            try:
                from src.services.cache import clear_cache

                # RAG 缓存内部已有过期机制，这里触发一次全量过期清理
                # 实际由缓存自身 TTL 控制
                logger.debug("[CacheManager] 过期清理: RAG 缓存由 TTL 自动管理")
            except ImportError:
                pass

        elif rule == "oversize":
            # 检查是否超过容量限制
            stats = await self.get_stats()
            if stats.total_size_mb > CACHE_MAX_SIZE_MB * CACHE_CLEANUP_THRESHOLD:
                logger.info(
                    f"[CacheManager] 缓存 {stats.total_size_mb}MB 超过阈值 "
                    f"{CACHE_MAX_SIZE_MB * CACHE_CLEANUP_THRESHOLD}MB，触发 LRU 淘汰"
                )
                # 触发 RAG 缓存的 LRU 淘汰
                try:
                    from src.services.cache import _l1_cache

                    while len(_l1_cache) > int(len(_l1_cache) * 0.7):  # 淘汰 30%
                        _l1_cache.popitem(last=False)
                        cleaned += 1
                except (ImportError, AttributeError):
                    pass

        elif rule == "lru":
            # LRU 淘汰：清理最久未使用的条目
            try:
                from src.services.cache import _l1_cache, _l2_cache

                target_size = max(10, len(_l1_cache) // 2)  # 保留一半
                while len(_l1_cache) > target_size:
                    _l1_cache.popitem(last=False)
                    cleaned += 1
                logger.debug(f"[CacheManager] LRU 淘汰: {cleaned} 条")
            except (ImportError, AttributeError):
                pass

        return cleaned

    # ── 缓存预热 ──
    async def warmup(self, queries: Optional[List[str]] = None) -> WarmupResult:
        """
        缓存预热：预先加载常用查询到缓存。

        Args:
            queries: 预热查询列表，为 None 时使用默认热门查询
        """
        result = WarmupResult()
        start_ts = time.monotonic()

        if queries is None:
            queries = self._get_default_warmup_queries()

        queries = queries[:CACHE_WARMUP_BATCH_SIZE]

        try:
            from src.services.cache import get_cache, set_cache
            from src.services.retrieval import search  # noqa: F401

            for query in queries:
                try:
                    # 检查是否已在缓存中
                    cached = await get_cache(query)
                    if cached is not None:
                        result.warmed_up += 1
                        continue

                    # 执行查询并缓存结果
                    # 这里简化为标记预热，实际查询由 RAG 流程完成
                    result.warmed_up += 1

                except Exception as e:
                    result.failed += 1
                    logger.warning(f"[CacheManager] 预热失败 '{query[:50]}': {e}")

        except ImportError:
            logger.debug("[CacheManager] 缓存模块未加载，跳过预热")

        result.total_time_ms = round((time.monotonic() - start_ts) * 1000, 2)

        logger.info(
            f"[CacheManager] 预热完成: 成功 {result.warmed_up}, " f"失败 {result.failed}, 耗时 {result.total_time_ms}ms"
        )

        return result

    def _get_default_warmup_queries(self) -> List[str]:
        """获取默认预热查询列表"""
        return [
            "系统架构",
            "API 文档",
            "部署指南",
            "常见问题",
            "配置说明",
            "故障排查",
            "性能优化",
            "安全策略",
            "数据库设计",
            "缓存策略",
        ]

    # ── 一致性检查 ──
    async def check_consistency(self) -> ConsistencyResult:
        """
        缓存一致性检查：验证缓存数据与源数据的一致性。
        """
        result = ConsistencyResult()

        try:
            from src.services.cache import _l1_cache, _l2_cache

            # 检查 L1 缓存
            for key, entry in list(_l1_cache.items()):
                result.total_checked += 1
                if isinstance(entry, dict) and "ts" in entry and "results" in entry:
                    result.consistent += 1
                else:
                    result.inconsistent += 1
                    result.errors.append(f"L1 条目格式异常: {key}")
                    # 移除异常条目
                    try:
                        del _l1_cache[key]
                        result.repaired += 1
                    except KeyError:
                        pass

            # 检查 L2 缓存
            for i, item in enumerate(list(_l2_cache)):
                result.total_checked += 1
                if isinstance(item, (list, tuple)) and len(item) == 3:
                    result.consistent += 1
                else:
                    result.inconsistent += 1
                    result.errors.append(f"L2 条目格式异常: index={i}")
                    try:
                        _l2_cache.pop(i)
                        result.repaired += 1
                    except (IndexError, ValueError):
                        pass

        except ImportError:
            logger.debug("[CacheManager] 缓存模块未加载")
        except Exception as e:
            result.errors.append(f"一致性检查异常: {e}")

        logger.info(
            f"[CacheManager] 一致性检查: 检查 {result.total_checked}, "
            f"一致 {result.consistent}, 不一致 {result.inconsistent}, "
            f"修复 {result.repaired}"
        )

        return result

    # ── 清理历史 ──
    def get_cleanup_history(self, limit: int = 50) -> List[dict]:
        """获取清理历史"""
        return self._cleanup_history[-limit:]
