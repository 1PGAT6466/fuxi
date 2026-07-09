#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen.py — 艮卦 ☶ · 伏羲 v2.1

艮为山，主稳定性与自我修复。
对应能力：健康检查、断路器管理、自动回滚、配置校验。

v2.1 Phase 1: 融合鼻(NoseAgent)异常嗅探能力
  → 零结果检测、搜索延迟监控、日志异常分析
  → 独立于 organs/ 目录，数据通过 params 传入
"""


import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from src.bagua.base_gua import (
    GuaBase,
    DegradationRule,
    FallbackAction,
)

logger = logging.getLogger("bagua.gen")


# ---- 内容安全：敏感词 + 正则模式 ----
import re as _re

# NSFW / 高危敏感词列表
_SENSITIVE_KEYWORDS: list = [
    # 政治敏感
    "颠覆国家政权", "分裂国家", "恐怖主义", "极端主义",
    "反党", "反华", "颠覆",
    # 成人/NSFW（中文）
    "色情", "淫秽", "裸体", "成人影片", "性服务", "约炮",
    # 成人/NSFW（英文）
    "porn", "xxx", "nsfw", "explicit", "adult content",
    # 暴力/违法
    "制作炸弹", "买枪", "杀人", "贩毒", "洗钱",
    "黑客攻击", "盗取密码", "DDoS攻击",
    # 仇恨言论
    "种族歧视", "种族灭绝", "仇恨言论",
]

# 高危正则模式（身份证号、银行卡号等需要额外审核）
_SENSITIVE_REGEX_PATTERNS: list = [
    (_re.compile(r"\b\d{6}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dxX]\b"), "身份证号"),
    (_re.compile(r"\b1[3-9]\d{9}\b"), "手机号"),
    (_re.compile(r"\b\d{16,19}\b"), "银行卡号"),
]


class GenGua(GuaBase):
    """艮卦 ☶ — 稳定性与自我修复 + 异常嗅探 + 内容安全审核

    融合了鼻(NoseAgent)的异常嗅探能力：
    - detect_zero_results: 零结果查询检测与趋势分析
    - check_latency: 搜索延迟异常检测
    - monitor_logs: 日志异常模式分析

    新增内容安全审核（NSFW检测）：
    - content_safety_check: 敏感词过滤 + 正则模式 + 可选LLM判断

    数据通过 params 传入（不依赖 organs/ 目录），
    所有方法为同步纯函数，便于集成到 GuaBase 的执行框架。
    """

    GUA_NAME = "gen"
    GUA_EMOJI = "☶"
    GUA_DESCRIPTION = "稳定性与自我修复 — 健康检查、断路器、回滚、异常嗅探"

    # 基线配置
    DEFAULT_ZERO_RESULT_THRESHOLD: float = 0.3
    DEFAULT_LATENCY_THRESHOLD_MS: float = 5000.0
    DEFAULT_TIMEOUT_THRESHOLD_MS: float = 10000.0
    DEFAULT_LOW_SCORE_THRESHOLD: int = 2
    DEFAULT_SUSTAINED_DAYS: int = 3
    DEFAULT_MIN_ENTRIES: int = 10

    # 嗅探循环间隔（秒）
    SNIFF_LOOP_INTERVAL: float = 25.0

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        # 嗅探状态
        self._sniff_count: int = 0
        self._baseline: Dict[str, float] = {
            "avg_score": 0.0,
            "avg_latency_ms": 0.0,
            "zero_result_rate": 0.0,
        }

        # 异步嗅探循环任务
        self._sniff_loop_task: Optional[asyncio.Task] = None

    # ========================================================================
    # GuaBase 接口实现
    # ========================================================================

    def _setup_dependencies(self) -> None:
        """注册依赖：搜索数据存储"""
        self.register_dependency(
            "search_db",
            failure_threshold=5,
            recovery_timeout=30.0,
            half_open_max_calls=3,
        )

    def _setup_degradation_rules(self) -> None:
        """定义降级规则"""

        # 规则 1: 搜索 DB 不可用时，使用空列表兜底
        def db_unavailable() -> bool:
            cb = self.get_dependency("search_db")
            if cb is None:
                return False
            return not cb.is_healthy

        self.add_rule(DegradationRule(
            name="search_db_unavailable",
            condition_fn=db_unavailable,
            fallback=FallbackAction(
                name="empty_fallback",
                handler=self._empty_fallback_handler,
                description="搜索 DB 不可用时返回空结果",
            ),
            priority=10,
        ))

    def _execute_core(self, params: Dict[str, Any]) -> Any:
        """统一执行入口：按 operation 分发

        Supported operations:
            - "detect_zero_results": 零结果检测
            - "check_latency": 延迟检测
            - "monitor_logs": 日志异常分析
            - "full_sniff": 执行全部三项检测
            - "stats": 返回统计信息
        """
        operation = params.get("operation", "full_sniff")

        if operation == "detect_zero_results":
            logs = params.get("logs", [])
            return self.detect_zero_results(logs)

        elif operation == "check_latency":
            timings = params.get("timings", [])
            return self.check_latency(timings)

        elif operation == "monitor_logs":
            log_entries = params.get("log_entries", [])
            return self.monitor_logs(log_entries)

        elif operation == "full_sniff":
            logs = params.get("logs", [])
            timings = params.get("timings", [])
            return {
                "zero_results": self.detect_zero_results(logs),
                "latency": self.check_latency(timings),
                "log_anomalies": self.monitor_logs(logs),
            }

        elif operation == "stats":
            return self.sniff_stats()

        else:
            raise ValueError("未知操作: %s" % operation)

    def _empty_fallback_handler(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """降级兜底：返回空检测结果"""
        operation = params.get("operation", "full_sniff")
        if operation == "content_safety_check":
            text = params.get("text", "")
            enable_llm = params.get("enable_llm", False)
            return self.content_safety_check(text, enable_llm=enable_llm)

        if operation == "full_sniff":
            return {
                "zero_results": {"alerts": [], "degraded": True},
                "latency": {"alerts": [], "degraded": True},
                "log_anomalies": {"alerts": [], "degraded": True},
            }
        return {"alerts": [], "degraded": True}

    # ========================================================================
    # 核心嗅探方法（迁移自 NoseAgent）
    # ========================================================================

    def detect_zero_results(
        self,
        logs: list,
        *,
        zero_threshold: float = None,
        sustained_days: int = None,
        min_entries: int = None,
    ) -> Dict[str, Any]:
        """检测零结果查询并分析原因

        分析搜索日志中的零结果率，检测：
        - 短期零结果率过高（单日 >30%）
        - 持续零结果趋势（连续 N 天零结果率 >40%）

        Args:
            logs: 搜索日志条目列表，每条包含：
                  {"timestamp": float, "results": int, "top_score": float, "query": str}
            zero_threshold: 单次检测的零结果率阈值
            sustained_days: 持续天数阈值
            min_entries: 最少条目数才能触发检测

        Returns:
            {
                "alerts": [...],
                "total_entries": int,
                "zero_count": int,
                "zero_rate": float,
                "daily_breakdown": {...},
                "timestamp": float,
            }
        """
        if zero_threshold is None:
            zero_threshold = self.DEFAULT_ZERO_RESULT_THRESHOLD
        if sustained_days is None:
            sustained_days = self.DEFAULT_SUSTAINED_DAYS
        if min_entries is None:
            min_entries = self.DEFAULT_MIN_ENTRIES

        alerts: List[Dict[str, Any]] = []
        total = len(logs)
        now = time.time()

        if total < min_entries:
            return {
                "alerts": alerts,
                "total_entries": total,
                "zero_count": 0,
                "zero_rate": 0.0,
                "daily_breakdown": {},
                "timestamp": now,
                "insufficient_data": True,
            }

        # 短期：整体零结果率
        zero_count = sum(1 for e in logs if e.get("results", 0) == 0)
        zero_rate = zero_count / total if total > 0 else 0.0

        if zero_rate > zero_threshold:
            alerts.append({
                "time": now,
                "type": "high_zero_result",
                "message": "零结果率过高: %.1f%%（最近 %d 条）" % (
                    zero_rate * 100, total
                ),
                "severity": "warning",
                "details": {
                    "zero_count": zero_count,
                    "total": total,
                    "threshold": zero_threshold,
                },
            })

        # 长期趋势：按天统计
        daily_zero: Dict[str, int] = {}
        daily_total: Dict[str, int] = {}
        for e in logs:
            ts = e.get("timestamp", 0)
            if ts == 0:
                continue
            day = time.strftime("%Y-%m-%d", time.localtime(ts))
            daily_total[day] = daily_total.get(day, 0) + 1
            if e.get("results", 0) == 0:
                daily_zero[day] = daily_zero.get(day, 0) + 1

        # 检测连续高零结果率
        consecutive = 0
        daily_rates: Dict[str, float] = {}
        for day in sorted(daily_total.keys()):
            rate = daily_zero.get(day, 0) / max(daily_total[day], 1)
            daily_rates[day] = rate
            if rate > 0.4:
                consecutive += 1
            else:
                consecutive = 0
            if consecutive >= sustained_days:
                alerts.append({
                    "time": now,
                    "type": "sustained_zero",
                    "message": "连续 %d 天零结果率偏高（>40%%）" % consecutive,
                    "severity": "critical",
                    "details": {
                        "consecutive_days": consecutive,
                        "daily_rates": daily_rates,
                    },
                })
                break

        self._sniff_count += 1

        return {
            "alerts": alerts,
            "total_entries": total,
            "zero_count": zero_count,
            "zero_rate": round(zero_rate, 4),
            "daily_breakdown": {
                day: {
                    "total": daily_total[day],
                    "zero": daily_zero.get(day, 0),
                    "rate": round(daily_zero.get(day, 0) / max(daily_total[day], 1), 4),
                }
                for day in sorted(daily_total.keys())
            },
            "timestamp": now,
        }

    def check_latency(
        self,
        timings: list,
        *,
        avg_threshold_ms: float = None,
        timeout_threshold_ms: float = None,
        min_entries: int = None,
    ) -> Dict[str, Any]:
        """检测搜索延迟异常

        Args:
            timings: 延迟数据列表，每条包含 {"ms": float/int, "timestamp": float}
            avg_threshold_ms: 平均延迟告警阈值
            timeout_threshold_ms: 单次超时阈值
            min_entries: 最少条目数

        Returns:
            {
                "alerts": [...],
                "avg_latency_ms": float,
                "max_latency_ms": float,
                "timeout_count": int,
                "total_samples": int,
                "timestamp": float,
            }
        """
        if avg_threshold_ms is None:
            avg_threshold_ms = self.DEFAULT_LATENCY_THRESHOLD_MS
        if timeout_threshold_ms is None:
            timeout_threshold_ms = self.DEFAULT_TIMEOUT_THRESHOLD_MS
        if min_entries is None:
            min_entries = self.DEFAULT_MIN_ENTRIES

        alerts: List[Dict[str, Any]] = []
        now = time.time()

        latencies = [e.get("ms", 0) for e in timings if e.get("ms", 0) > 0]
        if len(latencies) < min_entries:
            return {
                "alerts": alerts,
                "avg_latency_ms": 0.0,
                "max_latency_ms": 0.0,
                "timeout_count": 0,
                "total_samples": len(latencies),
                "timestamp": now,
                "insufficient_data": True,
            }

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        if avg_latency > avg_threshold_ms:
            alerts.append({
                "time": now,
                "type": "high_latency",
                "message": "平均延迟过高: %.0fms（最近 %d 条）" % (
                    avg_latency, len(latencies)
                ),
                "severity": "warning",
                "details": {
                    "avg_ms": round(avg_latency, 1),
                    "max_ms": max_latency,
                    "threshold_ms": avg_threshold_ms,
                },
            })

        # 近 N 条中超时尖峰
        lookback_count = min(10, len(latencies))
        recent = latencies[-lookback_count:]
        timeout_count = sum(1 for l in recent if l > timeout_threshold_ms)
        if timeout_count >= 3:
            alerts.append({
                "time": now,
                "type": "timeout_spike",
                "message": "最近 %d 条中 %d 条超时（>%.0fms）" % (
                    lookback_count, timeout_count, timeout_threshold_ms
                ),
                "severity": "critical",
                "details": {
                    "lookback": lookback_count,
                    "timeout_count": timeout_count,
                    "timeout_threshold_ms": timeout_threshold_ms,
                },
            })

        self._sniff_count += 1

        return {
            "alerts": alerts,
            "avg_latency_ms": round(avg_latency, 1),
            "max_latency_ms": max_latency,
            "timeout_count": timeout_count,
            "total_samples": len(latencies),
            "timestamp": now,
        }

    def monitor_logs(
        self,
        log_entries: list,
        *,
        zero_threshold: float = None,
        low_score_threshold: int = None,
        min_entries: int = None,
    ) -> Dict[str, Any]:
        """分析日志异常模式

        检测搜索日志中的异常信号：
        - 零结果率过高
        - 低质量（低分）结果比例过高

        Args:
            log_entries: 日志条目列表，每条包含：
                         {"results": int, "top_score": float, "query": str, "timestamp": float}
            zero_threshold: 零结果率告警阈值
            low_score_threshold: 低分阈值
            min_entries: 最少条目数

        Returns:
            {
                "alerts": [...],
                "total_entries": int,
                "zero_rate": float,
                "low_quality_rate": float,
                "top_zero_queries": [...],
                "timestamp": float,
            }
        """
        if zero_threshold is None:
            zero_threshold = self.DEFAULT_ZERO_RESULT_THRESHOLD
        if low_score_threshold is None:
            low_score_threshold = self.DEFAULT_LOW_SCORE_THRESHOLD
        if min_entries is None:
            min_entries = self.DEFAULT_MIN_ENTRIES

        alerts: List[Dict[str, Any]] = []
        total = len(log_entries)
        now = time.time()

        if total < min_entries:
            return {
                "alerts": alerts,
                "total_entries": total,
                "zero_rate": 0.0,
                "low_quality_rate": 0.0,
                "top_zero_queries": [],
                "timestamp": now,
                "insufficient_data": True,
            }

        zero_count = sum(1 for e in log_entries if e.get("results", 0) == 0)
        zero_rate = zero_count / total if total > 0 else 0.0

        low_score_count = sum(
            1 for e in log_entries
            if e.get("top_score", 10) < low_score_threshold
        )
        low_rate = low_score_count / total if total > 0 else 0.0

        if zero_rate > zero_threshold:
            alerts.append({
                "time": now,
                "type": "high_zero_result",
                "message": "零结果率过高: %.1f%%（最近 %d 条）" % (
                    zero_rate * 100, total
                ),
                "severity": "warning",
                "details": {
                    "zero_count": zero_count,
                    "total": total,
                    "threshold": zero_threshold,
                },
            })

        if low_rate > 0.5:
            alerts.append({
                "time": now,
                "type": "low_quality",
                "message": "低分结果过多: %.1f%%（最近 %d 条）" % (
                    low_rate * 100, total
                ),
                "severity": "warning",
                "details": {
                    "low_score_count": low_score_count,
                    "total": total,
                    "threshold": low_score_threshold,
                },
            })

        # 提取零结果中最频繁的查询
        zero_queries: Dict[str, int] = {}
        for e in log_entries:
            if e.get("results", 0) == 0:
                q = e.get("query", "").strip()
                if q:
                    zero_queries[q] = zero_queries.get(q, 0) + 1

        top_queries = sorted(
            zero_queries.items(), key=lambda x: x[1], reverse=True
        )[:5]

        self._sniff_count += 1

        return {
            "alerts": alerts,
            "total_entries": total,
            "zero_rate": round(zero_rate, 4),
            "low_quality_rate": round(low_rate, 4),
            "top_zero_queries": [
                {"query": q, "count": c} for q, c in top_queries
            ],
            "timestamp": now,
        }

    # ========================================================================
    # 内容安全审核（新增 — Phase 4 艮卦安全增强）
    # ========================================================================

    def content_safety_check(
        self,
        text: str,
        *,
        enable_llm: bool = False,
    ) -> Dict[str, Any]:
        """内容安全审核 — 敏感词过滤 + 正则模式 + 可选 LLM 判断

        方案中艮卦负责安全：对输入/输出文本做 NSFW 审核。
        支持三层检测：
          L1: 敏感词表匹配（O(n)，最快）
          L2: 正则模式匹配（检测身份证号/手机号/银行卡号泄露风险）
          L3: (可选) LLM 语义判断（当 L1+L2 有疑似命中时调用）

        Args:
            text:       待审核文本
            enable_llm: 是否启用 LLM 二次判断（默认 False，性能优先）

        Returns:
            {
                "safe": bool,               # 是否通过安全审核
                "flags": [str, ...],         # 命中的安全标记列表
                "severity": str,             # "clean" | "warning" | "blocked"
                "llm_verdict": Optional[str], # LLM 二次判断结果
            }
        """
        if not text or not text.strip():
            return {"safe": True, "flags": [], "severity": "clean", "llm_verdict": None}

        text_lower = text.lower()
        flags: List[str] = []

        # ---- L1: 敏感词表匹配 ----
        for keyword in _SENSITIVE_KEYWORDS:
            if keyword.lower() in text_lower:
                flags.append(f"sensitive_keyword:{keyword}")

        # ---- L2: 正则模式匹配 ----
        for pattern, label in _SENSITIVE_REGEX_PATTERNS:
            if pattern.search(text):
                flags.append(f"pii_pattern:{label}")

        # 文本长度异常检查（过长文本可能是注入攻击）
        if len(text) > 10000:
            flags.append("excessive_length")

        # ---- 判定 - 无命中 → clean ----
        if not flags:
            return {"safe": True, "flags": [], "severity": "clean", "llm_verdict": None}

        severity = "blocked" if any(
            kw in f for kw in ["sensitive_keyword", "pii_pattern"]
            for f in flags
        ) else "warning"

        # ---- L3: 可选 LLM 二次判断 ----
        llm_verdict = None
        if enable_llm and severity == "warning":
            llm_verdict = self._llm_safety_check(text)
            if llm_verdict and "safe" in llm_verdict.lower():
                severity = "clean"
                flags = []

        logger.info(
            "☶ [艮] 安全审核: safe=%s severity=%s flags=%d",
            severity == "clean", severity, len(flags),
        )

        return {
            "safe": severity == "clean",
            "flags": flags,
            "severity": severity,
            "llm_verdict": llm_verdict,
        }

    @staticmethod
    def _llm_safety_check(text: str) -> Optional[str]:
        """LLM 二次安全判断（同步降级版本）

        当 L1+L2 检测有疑似命中但不确定时调用。
        使用 LLM 进行更精确的语义判断。

        Notes:
            此方法设计为同步的轻量版本，避免在安全审核路径中
            引入异步复杂性。如需完整异步 LLM 审核，请在调用方使用
            content_safety_check() + 外部 LLM 调用。

        Args:
            text: 待审核文本

        Returns:
            LLM 判断结果字符串，或 None
        """
        try:
            from src.services.llm import call_ai_raw
            import asyncio

            prompt = f"""判断以下文本是否包含NSFW/成人/违法/仇恨内容。
只回答 "safe" 或 "unsafe"。

文本：{text[:500]}"""

            # 尝试在同步上下文中调用异步 LLM
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import nest_asyncio
                    nest_asyncio.apply()
                return loop.run_until_complete(
                    call_ai_raw(prompt, max_tokens=20)
                )
            except RuntimeError:
                return asyncio.run(call_ai_raw(prompt, max_tokens=20))

        except Exception as exc:  # TODO: Narrow exception type
            logger.debug("☶ [艮] LLM 安全审核异常: %s", exc)
            return None

    # ========================================================================
    # 周期性嗅探循环（异步）
    # ========================================================================

    async def start_sniff_loop(
        self,
        log_fetcher,
        *,
        interval: float = 25.0,
    ) -> None:
        """启动周期性嗅探循环

        替代原 NoseAgent._sniff_loop，通过回调 log_fetcher 获取数据。

        Args:
            log_fetcher: 异步可调用对象 → (logs_list, timings_list)
            interval: 嗅探间隔（秒）
        """
        if self._sniff_loop_task is not None and not self._sniff_loop_task.done():
            logger.warning("[艮卦] 嗅探循环已在运行")
            return

        async def _loop() -> None:
            logger.info(
                "[艮卦] 嗅探循环启动 ☶ (interval=%.1fs)", interval
            )
            while self.is_alive:
                try:
                    logs, timings = await log_fetcher()

                    zero_result = self.detect_zero_results(logs)
                    latency = self.check_latency(timings)
                    log_anomaly = self.monitor_logs(logs)

                    all_alerts = (
                        zero_result.get("alerts", [])
                        + latency.get("alerts", [])
                        + log_anomaly.get("alerts", [])
                    )

                    if all_alerts:
                        logger.warning(
                            "[艮卦] 嗅探发现 %d 条告警", len(all_alerts)
                        )
                        for alert in all_alerts:
                            logger.warning(
                                "  [%s] %s",
                                alert.get("severity", "info"),
                                alert.get("message", ""),
                            )

                except asyncio.CancelledError:
                    logger.debug("[艮卦] 嗅探循环已取消")
                    break
                except Exception as exc:  # TODO: Narrow exception type
                    logger.error(
                        "[艮卦] 嗅探异常: %s", exc, exc_info=True
                    )

                await asyncio.sleep(interval)

        self._sniff_loop_task = asyncio.ensure_future(_loop())

    async def stop_sniff_loop(self) -> None:
        """停止周期性嗅探循环"""
        if self._sniff_loop_task is not None and not self._sniff_loop_task.done():
            self._sniff_loop_task.cancel()
            try:
                await self._sniff_loop_task
            except asyncio.CancelledError:
                pass
        self._sniff_loop_task = None
        logger.info("[艮卦] 嗅探循环已停止")

    # ========================================================================
    # 统计与生命周期
    # ========================================================================

    def sniff_stats(self) -> Dict[str, Any]:
        """返回嗅探统计信息"""
        return {
            "sniff_count": self._sniff_count,
            "baseline": self._baseline,
            "is_alive": self.is_alive,
            "uptime_sec": self.uptime_sec,
            "health": self.health.value,
        }

    def stop(self) -> None:
        """停止艮卦：同时取消嗅探循环"""
        if self._sniff_loop_task is not None and not self._sniff_loop_task.done():
            self._sniff_loop_task.cancel()
        super().stop()


__all__ = ["GenGua"]
