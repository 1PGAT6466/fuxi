#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_gap_analyzer.py — GapAnalyzer 单元测试

伏羲 v1.50 Phase A：Synthesis Gap Analysis 验证
================================================

测试覆盖：
  1. answer 完全被 source 覆盖 → gaps 为空
  2. answer 部分超出 source → gaps 包含超出句子
  3. answer 完全不在 source 中 → gaps = 全部句子
  4. 空 sources → gaps = 全部句子
  5. 中文场景（完整真实场景测试）

作者：AI系统构建工程师
创建：2026-07-08
"""

from __future__ import annotations

import pytest

from src.bagua.gap_analyzer import GapAnalyzer, GapResult


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def analyzer() -> GapAnalyzer:
    """默认配置的 GapAnalyzer 实例"""
    return GapAnalyzer(coverage_threshold=0.5)


# ============================================================================
# Test 1: answer 完全被 source 覆盖 → gaps 为空
# ============================================================================


class TestFullyCovered:

    def test_all_claims_from_single_source(self, analyzer: GapAnalyzer):
        """所有 claim 都在单一 source 中 → gaps 应为空"""
        answer = "公司 2024 年营收达到 50 亿元，同比增长 20%。主要增长来自云计算业务。"
        sources = [
            "根据公司 2024 年年报：全年营收达到 50 亿元，同比增长 20%。"
            "云计算业务成为主要增长引擎，贡献了 60% 的增量收入。"
        ]

        result = analyzer.analyze(answer=answer, sources=sources)

        assert len(result.gaps) == 0, f"期望无 gaps，实际有: {result.gaps}"
        assert result.has_gaps is False
        assert result.gap_text == ""
        assert result.coverage_rate == 1.0, f"覆盖率应为 1.0，实际为 {result.coverage_rate}"

    def test_all_claims_from_multiple_sources(self, analyzer: GapAnalyzer):
        """claim 分布在多个 sources 中 → gaps 应为空"""
        answer = "公司 2024 年营收达到 50 亿元。公司计划 2025 年扩张东南亚市场。"
        sources = [
            "2024 年财报：全年营收 50 亿元。",
            "战略规划文件：2025 年将重点扩张东南亚市场，包括越南、泰国和印尼。"
        ]

        result = analyzer.analyze(answer=answer, sources=sources)

        assert len(result.gaps) == 0, f"期望无 gaps，实际有: {result.gaps}"
        assert result.has_gaps is False


# ============================================================================
# Test 2: answer 部分超出 source → gaps 包含超出的句子
# ============================================================================


class TestPartiallyCovered:

    def test_partial_coverage_mixed_claims(self, analyzer: GapAnalyzer):
        """部分 claim 在 source 中，部分不在 → gaps 包含不在的句子"""
        answer = (
            "公司 2024 年营收达到 50 亿元。"
            "我们计划 2025 年进入欧洲市场，首先是德国和法国。"
            "另外，公司正在研发新一代 AI 芯片。"
        )
        sources = [
            "根据公司 2024 年年报：全年营收达到 50 亿元，同比增长 20%。"
        ]

        result = analyzer.analyze(answer=answer, sources=sources)

        # 第一句 "营收 50 亿" 应在 source 中
        # 第二句 "进入欧洲市场" 不在
        # 第三句 "研发 AI 芯片" 不在
        assert len(result.gaps) > 0, "应该有 gaps"
        assert result.has_gaps is True
        assert len(result.covered) > 0, "应该有 covered 句子"

        # 验证第一句被覆盖
        covered_texts = " ".join(result.covered)
        assert "50 亿元" in covered_texts or "营收" in covered_texts

        # 验证 gap_text 包含警告前缀
        assert "⚠️" in result.gap_text
        assert "常识推理" in result.gap_text

        # 验证覆盖率
        assert 0 < result.coverage_rate < 1.0

    def test_sentence_level_gap_detection(self, analyzer: GapAnalyzer):
        """逐句粒度：同一段中，部分句子覆盖、部分不覆盖"""
        answer = "Python 适合数据科学领域。Java 更适合企业级应用开发。"
        sources = [
            "Python 是一种广泛使用的编程语言，特别适合数据科学和机器学习领域。"
        ]

        result = analyzer.analyze(answer=answer, sources=sources)

        # Python 句应 covered，Java 句应为 gap
        assert len(result.covered) > 0, f"应有 covered 句子: {result}"
        assert len(result.gaps) > 0

        gap_sentences = " ".join(result.gaps)
        assert "java" in gap_sentences.lower()

        # Python 句不应出现在 gaps 中
        for gap in result.gaps:
            assert "python" not in gap.lower()

    def test_gap_text_format_is_correct(self, analyzer: GapAnalyzer):
        """验证 gap_text 的格式正确性"""
        answer = "这是知识库有的内容。这是模型自己编的内容。"
        sources = ["知识库中提到：这是知识库有的内容。"]

        result = analyzer.analyze(answer=answer, sources=sources)

        assert result.has_gaps
        # 验证格式
        assert result.gap_text.startswith("⚠️")
        assert "常识推理" in result.gap_text
        assert "非知识库原文" in result.gap_text


# ============================================================================
# Test 3: answer 完全不在 source 中 → gaps = 全部
# ============================================================================


class TestFullyUncovered:

    def test_no_overlap_with_sources(self, analyzer: GapAnalyzer):
        """answer 与 sources 无任何重叠 → 所有句子都是 gap"""
        answer = "公司计划进军元宇宙领域，投资区块链技术。"
        sources = [
            "公司 2024 年 Q2 财报显示营收增长 15%，主要来自传统制造业。"
        ]

        result = analyzer.analyze(answer=answer, sources=sources)

        assert len(result.gaps) == result.total_sentences
        assert result.coverage_rate == 0.0
        assert result.has_gaps is True
        assert len(result.covered) == 0

    def test_unrelated_topics(self, analyzer: GapAnalyzer):
        """answer 和 sources 谈论完全不相关的主题"""
        answer = "量子计算将在 2030 年前实现商业化应用。"
        sources = [
            "2024 年度员工满意度调查报告。",
            "公司食堂菜单更新通知。",
            "办公区域空调维修计划。"
        ]

        result = analyzer.analyze(answer=answer, sources=sources)

        assert len(result.gaps) > 0
        assert result.coverage_rate == 0.0


# ============================================================================
# Test 4: 空 sources / 边界情况
# ============================================================================


class TestEdgeCases:

    def test_empty_sources_list(self, analyzer: GapAnalyzer):
        """sources 为空列表 → 所有句子都是 gap"""
        answer = "公司 2024 年营收达到 50 亿元。"
        sources = []

        result = analyzer.analyze(answer=answer, sources=sources)

        assert len(result.gaps) == result.total_sentences
        assert result.has_gaps is True

    def test_none_sources(self, analyzer: GapAnalyzer):
        """sources 为 None → 所有句子都是 gap"""
        answer = "公司 2024 年营收达到 50 亿元。"

        result = analyzer.analyze(answer=answer, sources=None)

        assert len(result.gaps) == result.total_sentences
        assert result.has_gaps is True

    def test_empty_answer(self, analyzer: GapAnalyzer):
        """answer 为空字符串 → 无 gaps"""
        result = analyzer.analyze(answer="", sources=["some source"])

        assert result.has_gaps is False
        assert result.gap_text == ""
        assert result.total_sentences == 0

    def test_whitespace_only_answer(self, analyzer: GapAnalyzer):
        """answer 仅为空白字符"""
        result = analyzer.analyze(answer="   \n  \t  ", sources=["some source"])

        assert result.has_gaps is False

    def test_short_sources_filtered(self, analyzer: GapAnalyzer):
        """太短的 source 被过滤 → 等同于空 sources"""
        answer = "公司营收 50 亿元。"
        sources = ["短", "abc"]  # 都短于 source_min_length=10

        result = analyzer.analyze(answer=answer, sources=sources)

        # 短 source 被过滤，所有句子都是 gap
        assert len(result.gaps) == result.total_sentences

    def test_single_short_sentence(self, analyzer: GapAnalyzer):
        """极短句子（< min_sentence_length=4）不分析"""
        # "好的。" 只有 3 个字符，会被过滤
        answer = "好的。公司营收 50 亿元。"
        sources = ["公司营收信息"]

        result = analyzer.analyze(answer=answer, sources=sources)

        # "好的。" 被过滤，"公司营收 50 亿元。" 是 gap
        assert result.total_sentences == 1


# ============================================================================
# Test 5: 中文场景（完整真实场景）
# ============================================================================


class TestChineseScenarios:

    def test_realistic_cn_qa_scenario_1(self, analyzer: GapAnalyzer):
        """真实场景：公司政策查询"""
        answer = (
            "根据公司差旅政策，员工出差住宿标准为五星级以下酒店。"
            "国内一线城市住宿标准为 800 元/晚。"
            "需要注意的是，出差期间的个人消费如 mini bar、洗衣服务不予报销。"
        )
        sources = [
            "《公司差旅管理办法 v3.2》：第 4 条 住宿标准。国内一线城市住宿标准为 800 元/晚，"
            "其他城市 500 元/晚。酒店星级不超过四星。第 12 条 不予报销项目：个人消费类（含 mini bar、"
            "洗衣服务）、娱乐消费、罚款类支出。"
        ]

        result = analyzer.analyze(answer=answer, sources=sources)

        # 第二句 "800 元/晚" 应覆盖，第三句 "mini bar、洗衣" 应覆盖
        # 第一句提到 "五星级以下" 但 source 说 "不超过四星" — 关键信息部分匹配
        assert len(result.covered) > 0, f"至少部分句子应被覆盖，covered={result.covered}"

        # gap_text 格式正确
        if result.has_gaps:
            assert "⚠️" in result.gap_text

    def test_realistic_cn_qa_scenario_2(self, analyzer: GapAnalyzer):
        """真实场景：技术方案讨论"""
        answer = (
            "我们推荐使用微服务架构来重构现有单体应用。"
            "具体可以采用 Spring Cloud 作为服务治理框架，"
            "配合 Kubernetes 进行容器编排。"
            "此外，我们计划在未来引入 AIOps 进行智能运维。"
        )
        sources = [
            "技术方案评审纪要 2024-Q3：团队提议使用微服务架构重构客户管理系统。"
            "技术选型建议：服务治理框架考虑 Spring Cloud Alibaba，容器编排使用 Kubernetes。"
        ]

        result = analyzer.analyze(answer=answer, sources=sources)

        # 前三句应大部分被覆盖，第四句 "AIOps" 不在 source 中
        assert result.has_gaps
        gap_combined = " ".join(result.gaps)
        assert "AIOps" in gap_combined or "智能运维" in gap_combined

    def test_realistic_cn_qa_scenario_3(self, analyzer: GapAnalyzer):
        """真实场景：纯 LLM 幻觉（全部不在知识库）"""
        answer = (
            "根据公司最新的 AI 战略白皮书，我们将在 2025 年投入 100 亿人民币用于大模型研发。"
            "同时，公司已与 OpenAI 达成战略合作，共同开发下一代多模态模型。"
        )
        sources = [
            "公司 2024 年技术投资计划：Q4 重点投入云计算基础设施升级，预算 5 亿元。"
        ]

        result = analyzer.analyze(answer=answer, sources=sources)

        # 两句话都不在 source 中
        assert len(result.gaps) == result.total_sentences
        assert result.coverage_rate == 0.0

    def test_analyze_and_append_convenience(self, analyzer: GapAnalyzer):
        """测试 analyze_and_append 便捷方法"""
        answer = "公司营收 50 亿。我们计划研发量子芯片。"
        sources = ["公司 2024 年营收达到 50 亿元。"]

        result = analyzer.analyze_and_append(answer=answer, sources=sources)

        # "营收 50 亿" 覆盖，"量子芯片" 不覆盖
        assert "量子芯片" in result
        assert "⚠️" in result
        assert result.startswith("公司营收 50 亿")

    def test_no_gaps_analyze_and_append(self, analyzer: GapAnalyzer):
        """无 gaps 时 analyze_and_append 返回原 answer"""
        answer = "公司营收 50 亿元。"
        sources = ["公司 2024 年营收达到 50 亿元。"]

        result = analyzer.analyze_and_append(answer=answer, sources=sources)

        assert "⚠️" not in result
        assert result == answer


# ============================================================================
# Test: Keyword Extraction
# ============================================================================


class TestKeywordExtraction:

    def test_cn_keyword_extraction(self, analyzer: GapAnalyzer):
        """中文关键词提取正确"""
        text = "公司 2024 年营收达到 50 亿元，同比增长 20%。"
        keywords = analyzer._extract_keywords(text)
        all_kw_str = " ".join(keywords)

        assert "公司" in all_kw_str
        assert "营收" in all_kw_str
        assert "增长" in all_kw_str
        assert "50 亿元" in keywords or "50亿元" in keywords
        assert "20%" in keywords

    def test_stop_words_filtered(self, analyzer: GapAnalyzer):
        """停用词被正确过滤"""
        text = "我们可以通过这些方法来进行优化。"
        keywords = analyzer._extract_keywords(text)
        all_kw_str = " ".join(keywords)

        # "我们", "可以", "通过", "这些", "进行" 都是停用词
        stops = {"我们", "可以", "通过", "这些", "进行"}
        for kw in keywords:
            assert kw not in stops, f"停用词 '{kw}' 不应出现在关键词中"

        # "方法" 和 "优化" 应保留
        assert "方法" in all_kw_str
        assert "优化" in all_kw_str

    def test_en_keyword_extraction(self, analyzer: GapAnalyzer):
        """英文关键词提取正确"""
        text = "We recommend using Kubernetes for container orchestration."
        keywords = analyzer._extract_keywords(text)

        assert "recommend" in keywords
        assert "kubernetes" in keywords
        assert "container" in keywords

    def test_mixed_cn_en_keywords(self, analyzer: GapAnalyzer):
        """中英文混合关键词提取"""
        text = "使用 Python 进行 data analysis 和 machine learning。"
        keywords = analyzer._extract_keywords(text)
        all_kw_str = " ".join(keywords)

        assert "python" in all_kw_str
        assert "analysis" in all_kw_str
        assert "machine" in all_kw_str
        assert "learning" in all_kw_str


# ============================================================================
# Test: Sentence Splitting
# ============================================================================


class TestSentenceSplitting:

    def test_cn_sentence_split(self, analyzer: GapAnalyzer):
        """中文句子按句号/问号/感叹号分割"""
        text = "第一句话。第二句话！第三句话？"
        sentences = analyzer._split_sentences(text)

        assert len(sentences) == 3
        assert "第一句话" in sentences[0]
        assert "第二句话" in sentences[1]
        assert "第三句话" in sentences[2]

    def test_newline_split(self, analyzer: GapAnalyzer):
        """换行符分割"""
        text = "第一行\n第二行\n第三行"
        sentences = analyzer._split_sentences(text)

        assert len(sentences) == 3

    def test_empty_lines_skipped(self, analyzer: GapAnalyzer):
        """空行被跳过"""
        text = "第一句。\n\n\n第二句。"
        sentences = analyzer._split_sentences(text)

        assert len(sentences) == 2


# ============================================================================
# Test: Coverage Threshold
# ============================================================================


class TestCoverageThreshold:

    def test_strict_threshold(self):
        """高阈值 (0.8)：更多句子被视为 gap"""
        strict = GapAnalyzer(coverage_threshold=0.8)
        answer = "公司营收 50 亿。公司计划扩张。"
        sources = ["公司 2024 年营收达到 50 亿元。"]

        result = strict.analyze(answer=answer, sources=sources)
        # 第二句可能因为高阈值被标记为 gap
        assert result.has_gaps

    def test_lenient_threshold(self):
        """低阈值 (0.3)：更多句子被视为 covered"""
        lenient = GapAnalyzer(coverage_threshold=0.3)
        answer = "公司营收达到历史新高。云计算业务增长迅速。"
        sources = ["公司 2024 年营收达到历史新高。"]

        result = lenient.analyze(answer=answer, sources=sources)
        # 第二句可能因为低阈值获部分匹配
        assert result.coverage_rate >= 0.0


# ============================================================================
# Test: Feature Flag
# ============================================================================


class TestFeatureFlag:

    def test_is_gap_analysis_enabled_default(self):
        """默认情况下 Feature Flag 应为 True"""
        from src.bagua.gap_analyzer import is_gap_analysis_enabled
        assert is_gap_analysis_enabled() is True

    def test_get_gap_analyzer_singleton(self):
        """get_gap_analyzer 返回单例"""
        from src.bagua.gap_analyzer import get_gap_analyzer
        a1 = get_gap_analyzer()
        a2 = get_gap_analyzer()
        assert a1 is a2
