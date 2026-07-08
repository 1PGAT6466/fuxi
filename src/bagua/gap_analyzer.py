#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gap_analyzer.py — 兑卦后处理 · 知识盲区标注 (Gap Analysis)

伏羲 v1.50 Phase A：GBrain Synthesis + Gap Analysis
====================================================

核心功能：
  在 LLM 回答末尾自动标注"知识库的已知边界"——对比 LLM 生成的 answer
  与检索到的 source chunks，找出 answer 中哪些 claim 没有被任何 source
  覆盖，标注为 "gap" 并追加警告文本。

设计原则（GBrain 风格）：
  - 纯规则驱动，零 LLM 调用
  - 轻量级关键词重叠度判断
  - 可独立验证、可单独测试

用法::

    from src.bagua.gap_analyzer import GapAnalyzer

    analyzer = GapAnalyzer()
    result = analyzer.analyze(
        answer="公司 2024 年营收 50 亿，同比增长 20%。我们计划 2025 年进入欧洲市场。",
        sources=["公司 2024 年报：营收达到 50 亿元，同比增长 20%。"]
    )
    # result.gaps → ["我们计划 2025 年进入欧洲市场。"]
    # result.gap_text → "⚠️ 以下信息来自我的常识推理，非知识库原文..."

作者：AI系统构建工程师
创建：2026-07-08
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bagua.gap_analyzer")


# ============================================================================
# 数据类
# ============================================================================


@dataclass
class SentenceResult:
    """单句分析结果"""
    sentence: str                      # 原句文本
    covered: bool                       # 是否被某个 source 覆盖
    matched_source_index: Optional[int] = None  # 覆盖该句的 source 索引
    coverage_score: float = 0.0        # 覆盖度得分 (0.0 ~ 1.0)
    keywords: List[str] = field(default_factory=list)   # 提取的关键词
    matched_keywords: List[str] = field(default_factory=list)  # 匹配到的关键词


@dataclass
class GapResult:
    """Gap Analysis 完整结果"""
    answer: str                         # 原始 answer
    covered: List[str] = field(default_factory=list)     # 被覆盖的句子列表
    gaps: List[str] = field(default_factory=list)         # 未被覆盖的句子列表
    gap_text: str = ""                  # 格式化的 gap 警告文本
    has_gaps: bool = False              # 是否存在知识盲区
    total_sentences: int = 0            # 总句子数
    coverage_rate: float = 0.0          # 覆盖率 (covered / total)
    details: List[SentenceResult] = field(default_factory=list)  # 逐句详情


# ============================================================================
# 核心类：GapAnalyzer
# ============================================================================


class GapAnalyzer:
    """
    兑卦后处理器：对比 source 和 answer，标注知识盲区。

    核心逻辑：
      1. 接收 LLM 生成的 answer + 检索到的 source chunks
      2. 用轻量规则（非 LLM）找出 answer 中有哪些 claim 没有被 source 覆盖
      3. 返回 gap 标注文本，追加到 answer 末尾

    覆盖度判定：
      - 将 answer 分割为句子
      - 对每个句子提取关键词
      - 如果句子中 >50% 的关键词出现在某个 source 中，认为 covered
      - 阈值可通过 coverage_threshold 参数调整

    属性:
      coverage_threshold: 覆盖度阈值（默认 0.5，即 >50%）
      min_sentence_length: 最短句子长度（短于此长度不分析）
      keyword_min_length: 关键词最小长度（中文 2 字，英文 4 字符）
      source_min_length: source 最小长度（短于此长度的 source 跳过）

    Usage::

        analyzer = GapAnalyzer(coverage_threshold=0.5)
        result = analyzer.analyze(answer=..., sources=[...])
        if result.has_gaps:
            final_answer = answer + "\\n\\n" + result.gap_text
    """

    # 中文句子分隔符
    _CN_SENTENCE_SEP = re.compile(r'(?<=[。！？；\n])\s*')

    # 英文句子分隔符（更保守：. 后面跟空格+大写或换行）
    _EN_SENTENCE_SEP = re.compile(
        r'(?<=[.!?;])\s+(?=[A-Z])|(?<=[.!?;]\n)'
    )

    # 中文关键词提取：连续中文字符（2 字以上）
    _CN_WORD_RE = re.compile(r'[\u4e00-\u9fff]{2,}')

    # 英文关键词提取：连续英文字母（4 字符以上）
    _EN_WORD_RE = re.compile(r'[a-zA-Z]{4,}')

    # 数字 + 单位模式（金额/百分比/数量）
    _NUM_PATTERN_RE = re.compile(
        r'\d+(?:\.\d+)?\s*(?:亿元|亿|万元|万|千|百|%|元|美元|欧元|岁|年|月|日|人|次|个)'
    )

    # 停用词（中文高频无意义词，不参与关键词匹配）
    _CN_STOP_WORDS: set = frozenset({
        "我们", "他们", "你们", "这个", "那个", "这些", "那些",
        "可以", "需要", "应该", "能够", "可能", "已经", "正在",
        "通过", "因为", "所以", "但是", "而且", "或者", "以及",
        "如果", "虽然", "然而", "因此", "关于", "对于", "按照",
        "如下", "上述", "以下", "以上", "其中", "其实", "另外",
        "一方面", "另一方面", "总而言之", "一般来说",
        "一个", "一种", "一些", "什么", "怎么", "为什么",
        "是", "的", "了", "在", "和", "有", "不", "这", "那",
        "就", "也", "都", "会", "要", "把", "被", "让", "从",
        "到", "对", "与", "或", "而", "及", "以", "之", "其",
        "进行", "利用", "采用", "使用", "用来", "用以",
        "它们", "它", "他", "她", "自己",
        "之间", "之内", "之外",
    })

    def __init__(
        self,
        coverage_threshold: float = 0.5,
        min_sentence_length: int = 4,
        keyword_min_length: int = 2,
        source_min_length: int = 10,
        debug: bool = False,
    ) -> None:
        """
        Args:
            coverage_threshold: 覆盖度阈值 (0.0 ~ 1.0)
                               句子中匹配到的关键词占比超过此值即认为 covered
            min_sentence_length: 最短句子长度（字符数），短于此值不分析
            keyword_min_length: 关键词最小长度（字符数）
            source_min_length: source 块最短长度，短于此值跳过
            debug: 是否输出调试信息
        """
        self.coverage_threshold = coverage_threshold
        self.min_sentence_length = min_sentence_length
        self.keyword_min_length = keyword_min_length
        self.source_min_length = source_min_length
        self.debug = debug

    # ========================================================================
    # 公共 API
    # ========================================================================

    def analyze(
        self,
        answer: str,
        sources: Optional[List[str]] = None,
    ) -> GapResult:
        """
        分析 answer 中有哪些 claim 没有被 source 覆盖。

        Args:
            answer:  LLM 生成的回答文本
            sources: 检索到的知识库 source chunks 列表

        Returns:
            GapResult: 包含 covered、gaps、gap_text 等字段
        """
        sources = sources or []

        # 初步验证
        if not answer or not answer.strip():
            return GapResult(
                answer=answer,
                gap_text="",
                has_gaps=False,
            )

        # 过滤空/太短的 sources
        valid_sources = [
            s for s in sources
            if s and isinstance(s, str) and len(s.strip()) >= self.source_min_length
        ]

        # 分割句子
        sentences = self._split_sentences(answer)

        # 过滤太短的句子
        sentences = [s for s in sentences if len(s) >= self.min_sentence_length]

        if not sentences:
            return GapResult(
                answer=answer,
                total_sentences=0,
                has_gaps=False,
            )

        # 对每个句子进行分析
        sentence_results: List[SentenceResult] = []
        for sentence in sentences:
            result = self._analyze_sentence(sentence, valid_sources)
            sentence_results.append(result)

        # 汇总
        covered = [r.sentence for r in sentence_results if r.covered]
        gaps = [r.sentence for r in sentence_results if not r.covered]
        coverage_rate = len(covered) / len(sentence_results) if sentence_results else 0.0

        # 生成 gap_text
        gap_text = self._build_gap_text(gaps) if gaps else ""

        logger.info(
            "🔍 [GapAnalyzer] 分析完成: %d 句, %d covered (%.0f%%), %d gaps",
            len(sentence_results), len(covered), coverage_rate * 100, len(gaps),
        )

        return GapResult(
            answer=answer,
            covered=covered,
            gaps=gaps,
            gap_text=gap_text,
            has_gaps=len(gaps) > 0,
            total_sentences=len(sentence_results),
            coverage_rate=round(coverage_rate, 4),
            details=sentence_results,
        )

    # ========================================================================
    # 句子分析
    # ========================================================================

    def _analyze_sentence(
        self,
        sentence: str,
        sources: List[str],
    ) -> SentenceResult:
        """
        分析单个句子是否被任何 source 覆盖。

        判定逻辑：
          1. 从句子中提取关键词
          2. 对每个 source，统计有多少关键词出现在 source 中
          3. 如果匹配率 > coverage_threshold，认为 covered
          4. 选择匹配率最高的 source 作为 matched_source

        Args:
            sentence: 待分析的句子
            sources: 所有有效 source chunks

        Returns:
            SentenceResult
        """
        keywords = self._extract_keywords(sentence)

        # 如果句子没有足够关键词（如纯标点或数字），默认 covered
        if not keywords:
            return SentenceResult(
                sentence=sentence,
                covered=True,
                coverage_score=1.0,
                keywords=keywords,
                matched_keywords=[],
            )

        best_coverage = 0.0
        best_source_index: Optional[int] = None
        best_matched: List[str] = []

        for idx, source in enumerate(sources):
            source_lower = source.lower()
            matched = [kw for kw in keywords if kw.lower() in source_lower]
            coverage_score = len(matched) / len(keywords) if keywords else 0.0

            if coverage_score > best_coverage:
                best_coverage = coverage_score
                best_source_index = idx
                best_matched = matched

            # 如果已经超过阈值，可以提前退出
            if best_coverage > self.coverage_threshold:
                break

        covered = best_coverage > self.coverage_threshold

        if self.debug:
            logger.debug(
                "  句子: %.50s... | covered=%s (%.0f%%) | matched=%d/%d keywords",
                sentence.strip(), covered, best_coverage * 100,
                len(best_matched), len(keywords),
            )

        return SentenceResult(
            sentence=sentence,
            covered=covered,
            matched_source_index=best_source_index,
            coverage_score=round(best_coverage, 4),
            keywords=keywords,
            matched_keywords=best_matched,
        )

    # ========================================================================
    # 关键词提取
    # ========================================================================

    def _extract_keywords(self, text: str) -> List[str]:
        """
        从文本中提取关键词。

        策略：
          - 中文：提取连续 2-6 字的中文词汇（滑动窗口），过滤停用词
          - 英文：提取 4+ 字符的英文单词
          - 数字模式：提取数字+单位（金额、百分比等）
          - 去重、保持顺序

        Args:
            text: 输入文本

        Returns:
            去重后的关键词列表
        """
        keywords: List[str] = []

        # 中文关键词：使用滑动窗口提取 2-4 字的有意义词汇
        cn_segments = self._CN_WORD_RE.findall(text)
        for segment in cn_segments:
            seg_len = len(segment)
            # 对长段（6+ 字）使用滑动窗口拆分
            if seg_len >= 6:
                for win_size in (4, 3, 2):
                    if win_size <= seg_len:
                        for i in range(0, seg_len - win_size + 1):
                            w = segment[i:i + win_size]
                            if w not in self._CN_STOP_WORDS:
                                keywords.append(w)
                # 也加入完整段作为可选关键词
                if segment not in self._CN_STOP_WORDS:
                    keywords.append(segment)
            elif seg_len >= self.keyword_min_length:
                # 对 2-5 字的中文段也检查子词
                if segment not in self._CN_STOP_WORDS:
                    keywords.append(segment)
                # 对 3+ 字的段，也提取 2-3 字子词（增加匹配灵活性）
                if seg_len >= 3:
                    for i in range(0, seg_len - 1):
                        sub = segment[i:i + 2]
                        if sub not in self._CN_STOP_WORDS:
                            keywords.append(sub)

        # 英文关键词
        en_words = self._EN_WORD_RE.findall(text)
        for w in en_words:
            if len(w) >= self.keyword_min_length + 2:  # 英文需要更长
                keywords.append(w.lower())

        # 数字 + 单位
        num_matches = self._NUM_PATTERN_RE.findall(text)
        keywords.extend(num_matches)

        # 去重但保持顺序
        seen: set = set()
        unique: List[str] = []
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in seen:
                seen.add(kw_lower)
                unique.append(kw)

        return unique

    # ========================================================================
    # 句子分割
    # ========================================================================

    def _split_sentences(self, text: str) -> List[str]:
        """
        将文本分割为句子列表。

        支持中英文混合文本：
          - 中文：按 。！？；\n 分割
          - 英文：按 .!? 后跟空格的边界分割
          - 清理空句

        Args:
            text: 输入文本

        Returns:
            句子列表（已去除首尾空白）
        """
        # 先按中文分隔符拆分
        raw_parts = self._CN_SENTENCE_SEP.split(text)

        sentences: List[str] = []
        for part in raw_parts:
            part = part.strip()
            if not part:
                continue

            # 对较长的英文段再按英文分隔符拆分
            if self._contains_english_sentence_end(part):
                en_parts = self._EN_SENTENCE_SEP.split(part)
                for ep in en_parts:
                    ep = ep.strip()
                    if ep:
                        sentences.append(ep)
            else:
                sentences.append(part)

        return sentences

    def _contains_english_sentence_end(self, text: str) -> bool:
        """检查文本中是否包含英文句子结束标记（用于二次分割）"""
        return bool(re.search(r'[.!?]\s+[A-Z]', text))

    # ========================================================================
    # Gap Text 生成
    # ========================================================================

    def _build_gap_text(self, gaps: List[str]) -> str:
        """
        生成格式化的 gap 警告文本。

        参考 GBrain 的 "⚠️ 以下信息来自我的常识推理..." 格式。

        Args:
            gaps: 未覆盖的句子列表

        Returns:
            格式化的警告文本
        """
        lines: List[str] = [
            "⚠️ 以下信息来自我的常识推理，非知识库原文，请以实际文档为准：",
            "",
        ]

        for i, gap in enumerate(gaps, 1):
            # 截断过长句子（最多 80 字符）
            display = gap.strip()
            if len(display) > 80:
                display = display[:77] + "..."

            lines.append(f"· {display}")

        return "\n".join(lines)

    # ========================================================================
    # 工具方法
    # ========================================================================

    def analyze_and_append(
        self,
        answer: str,
        sources: Optional[List[str]] = None,
        sep: str = "\n\n",
    ) -> str:
        """
        便捷方法：分析 answer 并自动拼接 gap_text。

        如果存在 gaps，则在 answer 末尾追加 gap_text；
        如果不存在 gaps，直接返回原 answer。

        Args:
            answer:  LLM 生成的回答
            sources: source chunks
            sep:     answer 与 gap_text 之间的分隔符

        Returns:
            拼接了 gap_text 的 answer，或原 answer（如果无 gaps）
        """
        result = self.analyze(answer=answer, sources=sources)
        if result.has_gaps and result.gap_text:
            return answer.rstrip() + sep + result.gap_text
        return answer


# ============================================================================
# Feature Flag 辅助
# ============================================================================

# 全局 Feature Flag：是否启用 Gap Analysis
# 可通过环境变量 FUXI_ENABLE_GAP_ANALYSIS=0 关闭
import os as _os

_ENABLE_GAP_ANALYSIS: bool = (
    _os.getenv("FUXI_ENABLE_GAP_ANALYSIS", "1").lower() in ("1", "true", "yes", "on")
)

# 默认的全局 GapAnalyzer 实例（懒加载）
_default_analyzer: Optional[GapAnalyzer] = None


def get_gap_analyzer() -> GapAnalyzer:
    """获取全局默认的 GapAnalyzer 实例"""
    global _default_analyzer
    if _default_analyzer is None:
        _default_analyzer = GapAnalyzer()
    return _default_analyzer


def is_gap_analysis_enabled() -> bool:
    """检查 Gap Analysis 是否全局启用"""
    return _ENABLE_GAP_ANALYSIS


__all__ = [
    "GapAnalyzer",
    "GapResult",
    "SentenceResult",
    "get_gap_analyzer",
    "is_gap_analysis_enabled",
]
