#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
water_mirror.py — 水镜 · 多模型并行推理裁决

方案第 25 条优化建议标记 ★：水镜模块
在乾卦中作为可选的决策增强模式。

核心逻辑：
  对同一 query 同时调 MiMo + DeepSeek + 4o-mini 三路推理，
  对结果做多数表决：
    - 三路返回 → 多数表决（2/3 一致即采用）
    - 两路返回 → 取置信度高的
    - 一路返回 → 直接采用
    - 零路返回 → 宣告不可用

Usage::

    from src.bagua.water_mirror import WaterMirror

    mirror = WaterMirror()
    result = await mirror.reflect(
        query="GPT-5 什么时候发布？",
        system_prompt="你是知识问答助手",
    )
    # result == {"consensus_answer": "...", "votes": {...}, "models_used": [...]}
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("bagua.water_mirror")


class WaterMirror:
    """水镜 — 多模型并行推理 + 多数表决

    三路并行调用 MiMo + DeepSeek + 4o-mini（SiliconFlow），
    对返回结果做多数表决。

    表决策略（优先级从高到低）：
      1. 三路返回 → 两路及以上文本相似则取多数
      2. 两路返回 → 取置信度高的
      3. 一路返回 → 直接采用
      4. 零路返回 → None（上游应降级到 ShaoyinBrain）

    Attributes:
        TIMEOUT_SECONDS: 每路调用的超时时间（默认 30s）
        SIMILARITY_THRESHOLD: 文本相似度阈值（Jaccard）用于判断多数一致
    """

    TIMEOUT_SECONDS: float = 30.0
    SIMILARITY_THRESHOLD: float = 0.3

    def __init__(self) -> None:
        self._call_count: int = 0
        self._total_latency_ms: float = 0.0

    # ========================================================================
    # 公共 API
    # ========================================================================

    async def reflect(
        self,
        query: str,
        system_prompt: str = "",
        max_tokens: int = 300,
        temperature: float = 0.3,
    ) -> Optional[Dict[str, Any]]:
        """水镜反射 — 多模型并行推理主入口

        Args:
            query:          用户提问文本
            system_prompt:  系统提示（可选）
            max_tokens:     最大 token 数
            temperature:    温度参数

        Returns:
            {
                "consensus_answer": str,        # 共识答案
                "votes": {                       # 各模型投票详情
                    "mimo": {"text": str, "confidence": float},
                    "deepseek": {"text": str, "confidence": float},
                    "gpt4o_mini": {"text": str, "confidence": float},
                },
                "models_used": [str, ...],       # 实际返回的模型列表
                "decision_mode": str,            # "majority"|"max_confidence"|"single"|"none"
                "elapsed_ms": float,
            }
            或 None（所有模型均失败时）
        """
        start_time = time.time()
        self._call_count += 1

        votes: Dict[str, Dict[str, Any]] = {}
        models_used: List[str] = []

        # ---- 三路并行调用 ----
        tasks = [
            self._call_mimo(query, system_prompt, max_tokens, temperature),
            self._call_deepseek(query, system_prompt, max_tokens, temperature),
            self._call_gpt4o_mini(query, system_prompt, max_tokens, temperature),
        ]

        model_names = ["mimo", "deepseek", "gpt4o_mini"]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for name, result in zip(model_names, results):
            if isinstance(result, Exception):
                logger.warning(
                    "💧 [水镜] %s 调用异常: %s", name, result
                )
                continue
            if result and result.get("text"):
                votes[name] = result
                models_used.append(name)

        elapsed_ms = (time.time() - start_time) * 1000
        self._total_latency_ms += elapsed_ms

        # ---- 按有效模型数量选择表决策略 ----
        num_models = len(models_used)

        if num_models == 0:
            logger.warning("💧 [水镜] 所有模型均无有效返回")
            return None

        if num_models == 1:
            # 策略 3: 只有一路返回 → 直接采用
            sole = models_used[0]
            decision = {
                "consensus_answer": votes[sole]["text"],
                "votes": votes,
                "models_used": models_used,
                "decision_mode": "single",
                "elapsed_ms": round(elapsed_ms, 1),
            }
            logger.info(
                "💧 [水镜] 单模型决策: %s, elapsed=%.0fms",
                sole, elapsed_ms,
            )
            return decision

        if num_models == 2:
            # 策略 2: 两路返回 → 取置信度高的
            a, b = models_used[0], models_used[1]
            if votes[a].get("confidence", 0) >= votes[b].get("confidence", 0):
                winner = a
            else:
                winner = b
            decision = {
                "consensus_answer": votes[winner]["text"],
                "votes": votes,
                "models_used": models_used,
                "decision_mode": "max_confidence",
                "elapsed_ms": round(elapsed_ms, 1),
            }
            logger.info(
                "💧 [水镜] 置信度决策: winner=%s (conf=%.2f), elapsed=%.0fms",
                winner,
                votes[winner].get("confidence", 0),
                elapsed_ms,
            )
            return decision

        # 策略 1: 三路返回 → 多数表决
        majority_result = self._majority_vote(votes)
        decision = {
            "consensus_answer": majority_result,
            "votes": votes,
            "models_used": models_used,
            "decision_mode": "majority",
            "elapsed_ms": round(elapsed_ms, 1),
        }
        logger.info(
            "💧 [水镜] 多数表决完成: models=%d, elapsed=%.0fms",
            num_models, elapsed_ms,
        )
        return decision

    # ========================================================================
    # 模型调用方法（三路独立）
    # ========================================================================

    async def _call_mimo(
        self,
        query: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> Optional[Dict[str, Any]]:
        """调用 MiMo 模型"""
        try:
            from src.config import (
                MIMO_API_KEY, MIMO_BASE_URL, MIMO_MODEL, MIMO_TIMEOUT,
            )
            if not MIMO_API_KEY:
                return None

            from src.services.llm import _call_api
            messages = [
                {"role": "system", "content": system_prompt or "你是一个知识问答助手"},
                {"role": "user", "content": query},
            ]
            text = await asyncio.wait_for(
                _call_api(
                    MIMO_BASE_URL, MIMO_API_KEY, MIMO_MODEL,
                    messages, max_tokens, temperature,
                    min(MIMO_TIMEOUT, self.TIMEOUT_SECONDS),
                ),
                timeout=self.TIMEOUT_SECONDS,
            )
            if text:
                confidence = self._estimate_confidence(text)
                return {"text": text, "confidence": confidence, "model": "mimo"}
            return None
        except asyncio.TimeoutError:
            logger.debug("💧 [水镜] MiMo 超时")
            return None
        except Exception as exc:
            logger.debug("💧 [水镜] MiMo 异常: %s", exc)
            return None

    async def _call_deepseek(
        self,
        query: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> Optional[Dict[str, Any]]:
        """调用 DeepSeek 模型"""
        try:
            from src.config import (
                DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, DEEPSEEK_TIMEOUT,
            )
            if not DEEPSEEK_API_KEY:
                return None

            from src.services.llm import _call_api
            messages = [
                {"role": "system", "content": system_prompt or "你是一个知识问答助手"},
                {"role": "user", "content": query},
            ]
            text = await asyncio.wait_for(
                _call_api(
                    DEEPSEEK_BASE_URL, DEEPSEEK_API_KEY, DEEPSEEK_MODEL,
                    messages, max_tokens, temperature,
                    min(DEEPSEEK_TIMEOUT, self.TIMEOUT_SECONDS),
                ),
                timeout=self.TIMEOUT_SECONDS,
            )
            if text:
                confidence = self._estimate_confidence(text)
                return {"text": text, "confidence": confidence, "model": "deepseek"}
            return None
        except asyncio.TimeoutError:
            logger.debug("💧 [水镜] DeepSeek 超时")
            return None
        except Exception as exc:
            logger.debug("💧 [水镜] DeepSeek 异常: %s", exc)
            return None

    async def _call_gpt4o_mini(
        self,
        query: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> Optional[Dict[str, Any]]:
        """调用 GPT-4o-mini（通过 SiliconFlow）"""
        try:
            from src.config import SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL
            if not SILICONFLOW_API_KEY:
                return None

            from src.services.llm import _call_api
            messages = [
                {"role": "system", "content": system_prompt or "你是一个知识问答助手"},
                {"role": "user", "content": query},
            ]
            text = await asyncio.wait_for(
                _call_api(
                    SILICONFLOW_BASE_URL, SILICONFLOW_API_KEY,
                    "OpenAI/GPT-4o-mini",
                    messages, max_tokens, temperature,
                    self.TIMEOUT_SECONDS,
                ),
                timeout=self.TIMEOUT_SECONDS,
            )
            if text:
                confidence = self._estimate_confidence(text)
                return {"text": text, "confidence": confidence, "model": "gpt4o_mini"}
            return None
        except asyncio.TimeoutError:
            logger.debug("💧 [水镜] GPT-4o-mini 超时")
            return None
        except Exception as exc:
            logger.debug("💧 [水镜] GPT-4o-mini 异常: %s", exc)
            return None

    # ========================================================================
    # 表决逻辑
    # ========================================================================

    def _majority_vote(self, votes: Dict[str, Dict[str, Any]]) -> str:
        """三路多数表决

        对三路结果两两计算 Jaccard 相似度。
        如果有两路相似度 > SIMILARITY_THRESHOLD，视为"一致"，
        返回其中一方的文本。
        如果都不一致，返回置信度最高的。

        Args:
            votes: {
                "mimo": {"text": str, "confidence": float},
                "deepseek": {"text": str, "confidence": float},
                "gpt4o_mini": {"text": str, "confidence": float},
            }

        Returns:
            共识答案文本
        """
        models = list(votes.keys())
        if len(models) < 3:
            # 不应该到这里，防御性处理
            return votes[models[0]]["text"]

        pairs = [
            (models[0], models[1]),
            (models[1], models[2]),
            (models[0], models[2]),
        ]

        for a, b in pairs:
            sim = self._jaccard_similarity(votes[a]["text"], votes[b]["text"])
            if sim >= self.SIMILARITY_THRESHOLD:
                logger.info(
                    "💧 [水镜] 多数一致: %s ↔ %s (sim=%.2f)",
                    a, b, sim,
                )
                return votes[a]["text"]

        # 无多数一致 → 取置信度最高
        winner = max(models, key=lambda m: votes[m].get("confidence", 0))
        logger.info(
            "💧 [水镜] 无多数一致，取最高置信: %s (conf=%.2f)",
            winner, votes[winner].get("confidence", 0),
        )
        return votes[winner]["text"]

    # ========================================================================
    # 工具方法
    # ========================================================================

    @staticmethod
    def _jaccard_similarity(text_a: str, text_b: str) -> float:
        """计算两段文本的 Jaccard 相似度（基于词级 token）

        Args:
            text_a: 文本 A
            text_b: 文本 B

        Returns:
            相似度 [0.0, 1.0]
        """
        if not text_a or not text_b:
            return 0.0

        # 简单分词：按空白和常见标点分割
        import re
        def tokenize(text: str) -> set:
            tokens = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z]+|\d+", text.lower())
            return set(tokens)

        set_a = tokenize(text_a)
        set_b = tokenize(text_b)

        if not set_a or not set_b:
            return 0.0

        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union) if union else 0.0

    @staticmethod
    def _estimate_confidence(text: str) -> float:
        """基于文本质量启发式估计置信度

        根据文本长度、完整性等启发式指标估算置信度。

        Args:
            text: 模型输出文本

        Returns:
            估计置信度 [0.0, 1.0]
        """
        if not text or len(text) < 10:
            return 0.0

        score = 0.5  # 基础分

        # 长度适中 → 加分（太短可能不完整，太长可能啰嗦）
        length = len(text)
        if 100 <= length <= 500:
            score += 0.2
        elif 50 <= length < 100:
            score += 0.1

        # 不以截断结尾 → 加分
        if not text.rstrip().endswith((",", "，", "、", "...")):
            score += 0.1

        # 包含中文字符 → 加分（说明生成了实质性内容）
        import re
        if re.search(r"[\u4e00-\u9fff]", text):
            score += 0.1

        # 无明显错误标识
        error_markers = ["抱歉", "无法", "对不起", "error", "I cannot"]
        if not any(m in text for m in error_markers):
            score += 0.1
        else:
            score -= 0.2

        return min(max(round(score, 2), 0.0), 1.0)

    # ========================================================================
    # 统计
    # ========================================================================

    def stats(self) -> Dict[str, Any]:
        """返回水镜使用统计"""
        return {
            "call_count": self._call_count,
            "avg_latency_ms": (
                round(self._total_latency_ms / max(self._call_count, 1), 1)
            ),
            "total_latency_ms": round(self._total_latency_ms, 1),
        }


# ============================================================================
# 便捷函数
# ============================================================================


async def water_mirror_reflect(
    query: str,
    system_prompt: str = "",
    max_tokens: int = 300,
    temperature: float = 0.3,
) -> Optional[Dict[str, Any]]:
    """便捷函数：水镜反射

    等价于 WaterMirror().reflect(...)
    """
    mirror = WaterMirror()
    return await mirror.reflect(
        query=query,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )


__all__ = ["WaterMirror", "water_mirror_reflect"]
