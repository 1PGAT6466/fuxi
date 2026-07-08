#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_synthesizer.py — CrossEntitySynthesizer 单元测试

伏羲 v1.50 Phase D: Synthesis 跨实体合成测试

测试覆盖：
  1. 单实体合成
  2. 多实体+关系合成
  3. 空实体回退
  4. 时间线排序
  5. 来源引用格式
  6. 指定实体名
  7. Synthesizer.from_rag_result 便捷方法
  8. 边界情况（空查询、空 chunk、超长文本）
"""

import pytest
from src.bagua.synthesizer import (
    CrossEntitySynthesizer,
    SynthesisResult,
    get_synthesizer,
)


# ============================================================================
# 测试夹具
# ============================================================================

@pytest.fixture
def synthesizer() -> CrossEntitySynthesizer:
    """创建 CrossEntitySynthesizer 实例"""
    return CrossEntitySynthesizer(max_chunks=20, max_entities=10)


@pytest.fixture
def sample_chunks() -> list:
    """示例 RAG 检索 chunk 数据"""
    return [
        {
            "doc_id": "doc-001",
            "content": "张三于2018年加入阿里巴巴，负责淘宝项目的技术架构设计。他在阿里云担任高级架构师，"
                       "主导了双十一大促的技术保障工作。",
            "source": "员工档案.md",
            "date": "2020-03-15",
        },
        {
            "doc_id": "doc-002",
            "content": "李四在2019年加入阿里巴巴，担任产品经理，负责淘宝项目的需求分析和产品规划。"
                       "她与张三密切合作，共同推动项目迭代。",
            "source": "入职记录.md",
            "date": "2019-07-01",
        },
        {
            "doc_id": "doc-003",
            "content": "阿里巴巴集团成立于1999年，总部位于杭州。集团主要业务包括电商、云计算、数字媒体等。"
                       "淘宝是天猫和聚划算等平台的基础。",
            "source": "公司简介.md",
            "date": "2022-01-01",
        },
        {
            "doc_id": "doc-004",
            "content": "淘宝项目2021年完成了重大技术升级，张三带领团队将系统迁移到阿里云原生架构，"
                       "使系统吞吐量提升300%。李四负责迁移后的产品验收。",
            "source": "项目报告.md",
            "date": "2021-12-31",
        },
        {
            "doc_id": "doc-005",
            "content": "2022年第一季度，阿里巴巴电商业务GMV突破1万亿。云业务收入同比增长20%。"
                       "公司计划在未来三年投入1000亿用于技术研发。",
            "source": "财报摘要.md",
            "date": "2022-04-01",
        },
    ]


@pytest.fixture
def sample_graph_entities() -> list:
    """示例知识图谱实体数据"""
    return [
        {"name": "张三", "type": "person", "description": "阿里巴巴高级架构师"},
        {"name": "李四", "type": "person", "description": "阿里巴巴产品经理"},
        {"name": "阿里巴巴", "type": "company", "description": "电商与云计算集团"},
        {"name": "淘宝项目", "type": "product", "description": "电商平台"},
        {"name": "阿里云", "type": "product", "description": "云计算服务"},
        {"name": "杭州", "type": "location", "description": "公司总部"},
    ]


@pytest.fixture
def sample_graph_edges() -> list:
    """示例知识图谱边数据"""
    return [
        {"source": "张三", "target": "阿里巴巴", "type": "works_at", "confidence": 0.95,
         "evidence": "张三于2018年加入阿里巴巴"},
        {"source": "李四", "target": "阿里巴巴", "type": "works_at", "confidence": 0.90,
         "evidence": "李四在2019年加入阿里巴巴"},
        {"source": "张三", "target": "淘宝项目", "type": "leads", "confidence": 0.85,
         "evidence": "负责淘宝项目的技术架构设计"},
        {"source": "李四", "target": "淘宝项目", "type": "contributes_to", "confidence": 0.80,
         "evidence": "负责淘宝项目的需求分析和产品规划"},
        {"source": "张三", "target": "阿里云", "type": "works_at", "confidence": 0.75,
         "evidence": "在阿里云担任高级架构师"},
        {"source": "阿里巴巴", "target": "杭州", "type": "located_in", "confidence": 0.90,
         "evidence": "总部位于杭州"},
    ]


# ============================================================================
# 测试 1: 单实体合成
# ============================================================================

class TestSingleEntitySynthesis:
    """单实体合成测试"""

    def test_single_entity_with_graph(
        self, synthesizer, sample_chunks, sample_graph_entities, sample_graph_edges
    ):
        """测试单实体合成（指定实体名 + 知识图谱）"""
        result = synthesizer.synthesize(
            query="张三在阿里巴巴的职责",
            retrieved_chunks=sample_chunks,
            graph_entities=sample_graph_entities,
            graph_edges=sample_graph_edges,
            entity_names=["张三"],
        )

        assert result is not None
        assert result.mode == "cross_entity"
        assert result.entity_count == 1

        # 验证合成文本格式
        text = result.synthesized_text
        assert "张三" in text
        assert "跨实体合成回答" in text

        # 验证来源引用
        assert len(result.sources) > 0

    def test_single_entity_auto_detect(
        self, synthesizer, sample_chunks, sample_graph_entities, sample_graph_edges
    ):
        """测试单实体合成（自动检测实体名）"""
        result = synthesizer.synthesize(
            query="张三在阿里巴巴做什么",
            retrieved_chunks=sample_chunks,
            graph_entities=sample_graph_entities,
            graph_edges=sample_graph_edges,
        )

        assert result.mode == "cross_entity"
        assert result.entity_count >= 1

        # 实体分组应包含"张三"
        entity_names_in_groups = [g["entity"] for g in result.entity_groups]
        assert "张三" in entity_names_in_groups

    def test_single_entity_no_graph(
        self, synthesizer, sample_chunks
    ):
        """测试单实体合成（无知识图谱数据）"""
        result = synthesizer.synthesize(
            query="张三在阿里巴巴的职责",
            retrieved_chunks=sample_chunks,
            entity_names=["张三"],
        )

        assert result is not None
        assert result.mode == "cross_entity" or result.mode == "fallback_rag"
        assert len(result.relations) == 0  # 无图谱数据应无关系


# ============================================================================
# 测试 2: 多实体+关系合成
# ============================================================================

class TestMultiEntitySynthesis:
    """多实体+关系合成测试"""

    def test_multi_entity_with_relations(
        self, synthesizer, sample_chunks, sample_graph_entities, sample_graph_edges
    ):
        """测试多实体合成 + 关系边"""
        result = synthesizer.synthesize(
            query="张三和李四在淘宝项目的合作情况",
            retrieved_chunks=sample_chunks,
            graph_entities=sample_graph_entities,
            graph_edges=sample_graph_edges,
            entity_names=["张三", "李四", "淘宝项目"],
        )

        assert result.mode == "cross_entity"
        assert result.entity_count == 3

        # 验证实体分组
        entity_names = [g["entity"] for g in result.entity_groups]
        assert "张三" in entity_names
        assert "李四" in entity_names
        assert "淘宝项目" in entity_names

        # 验证关系边
        assert len(result.relations) > 0
        relation_types = [r["type"] for r in result.relations]
        assert any("works_at" in t or "leads" in t or "contributes_to" in t 
                   for t in relation_types)

        # 验证合成文本包含关系描述
        text = result.synthesized_text
        assert "关联关系" in text or "→" in text

    def test_multi_entity_chunk_grouping(
        self, synthesizer, sample_chunks, sample_graph_entities, sample_graph_edges
    ):
        """测试多实体时 chunk 按实体正确分组"""
        result = synthesizer.synthesize(
            query="阿里巴巴和淘宝",
            retrieved_chunks=sample_chunks,
            graph_entities=sample_graph_entities,
            graph_edges=sample_graph_edges,
        )

        # 每个实体组应有对应的 items
        for group in result.entity_groups:
            assert "entity" in group
            assert "items" in group
            assert len(group["items"]) > 0
            assert "mention_count" in group

        # 实体组按提及次数排序
        mentions = [g["mention_count"] for g in result.entity_groups]
        assert mentions == sorted(mentions, reverse=True)


# ============================================================================
# 测试 3: 空实体回退
# ============================================================================

class TestFallbackToRAG:
    """空实体回退测试"""

    def test_no_entities_fallback(self, synthesizer):
        """测试无实体可提取时回退到 RAG 模式"""
        # 使用纯英文且不含大写字母的文本（避开中文人名/公司/产品模式）
        chunks_without_entities = [
            {
                "doc_id": "doc-x",
                "content": "this is a general description of an abstract process."
                           "it discusses methodology and approaches in a theoretical manner.",
                "source": "abstract_doc.md",
                "date": "2024-01-01",
            },
            {
                "doc_id": "doc-y",
                "content": "another paragraph about concepts and frameworks."
                           "this text contains no proper nouns or named entities at all.",
                "source": "concept_doc.md",
                "date": "2024-02-01",
            },
        ]

        # 不使用 graph_entities，因此无法匹配到已知实体
        result = synthesizer.synthesize(
            query="abstract concept description",
            retrieved_chunks=chunks_without_entities,
            graph_entities=[],  # 无已知实体
            graph_edges=[],
        )

        assert result.mode == "fallback_rag"
        assert result.entity_count == 0
        assert len(result.entity_groups) == 0

        # 回退模式应有 chunk 预览
        text = result.synthesized_text
        assert "未检测到明确的实体" in text or "检索结果" in text or "暂无" in text

    def test_empty_chunks_fallback(self, synthesizer):
        """测试空 chunk 列表回退"""
        result = synthesizer.synthesize(
            query="任何查询",
            retrieved_chunks=[],
        )

        assert result.mode == "fallback_rag"
        assert "未找到" in result.synthesized_text or "暂无" in result.synthesized_text

    def test_empty_query(self, synthesizer):
        """测试空查询"""
        result = synthesizer.synthesize(
            query="",
            retrieved_chunks=[{"content": "test", "doc_id": "1"}],
        )

        assert result.mode == "fallback_rag"


# ============================================================================
# 测试 4: 时间线排序
# ============================================================================

class TestTimelineSorting:
    """时间线排序测试"""

    def test_items_sorted_by_date(self, synthesizer, sample_chunks, 
                                   sample_graph_entities, sample_graph_edges):
        """测试实体组内信息按时间排序"""
        result = synthesizer.synthesize(
            query="淘宝项目的历史",
            retrieved_chunks=sample_chunks,
            graph_entities=sample_graph_entities,
            graph_edges=sample_graph_edges,
            entity_names=["淘宝项目"],
        )

        # 查找淘宝项目实体组
        taobao_group = None
        for g in result.entity_groups:
            if "淘宝" in g["entity"]:
                taobao_group = g
                break

        if taobao_group:
            dates = [item.get("date", "0000-00-00") for item in taobao_group["items"]]
            # 验证日期是升序的
            assert dates == sorted(dates)

    def test_mixed_date_chunks(self, synthesizer):
        """测试混合日期 chunk 的排序"""
        mixed_chunks = [
            {"doc_id": "d1", "content": "2022年的张三报告", "source": "r1.md", "date": "2022-06-01"},
            {"doc_id": "d2", "content": "2020年的张三报告", "source": "r2.md", "date": "2020-01-01"},
            {"doc_id": "d3", "content": "2021年的张三报告", "source": "r3.md", "date": "2021-12-15"},
            {"doc_id": "d4", "content": "无日期的张三报告", "source": "r4.md"},
        ]

        result = synthesizer.synthesize(
            query="张三的报告",
            retrieved_chunks=mixed_chunks,
            entity_names=["张三"],
        )

        # 查找张三实体组
        if result.entity_groups:
            group = result.entity_groups[0]
            dates = [item.get("date", "0000-00-00") for item in group["items"]]
            assert dates == sorted(dates)


# ============================================================================
# 测试 5: 来源引用格式
# ============================================================================

class TestSourceCitation:
    """来源引用格式测试"""

    def test_source_format_in_text(self, synthesizer, sample_chunks,
                                     sample_graph_entities, sample_graph_edges):
        """测试来源引用在合成文本中格式正确"""
        result = synthesizer.synthesize(
            query="张三",
            retrieved_chunks=sample_chunks,
            graph_entities=sample_graph_entities,
            graph_edges=sample_graph_edges,
            entity_names=["张三"],
        )

        text = result.synthesized_text
        # 应包含 "来源：" 标记
        assert "来源：" in text

    def test_source_collection_unique(self, synthesizer, sample_chunks):
        """测试来源收集去重"""
        # 多个 chunk 来自同一来源
        dup_source_chunks = [
            {"doc_id": "d1", "content": "张三在阿里巴巴", "source": "同一来源.md", "date": "2020-01-01"},
            {"doc_id": "d2", "content": "张三的职责", "source": "同一来源.md", "date": "2020-02-01"},
            {"doc_id": "d3", "content": "张三的项目", "source": "另一来源.md", "date": "2020-03-01"},
        ]

        result = synthesizer.synthesize(
            query="张三",
            retrieved_chunks=dup_source_chunks,
            entity_names=["张三"],
        )

        # sources 应去重
        source_names = [s["source"] for s in result.sources]
        assert len(source_names) == len(set(source_names))
        assert len(result.sources) <= 2  # 两个唯一来源


# ============================================================================
# 测试 6: 指定实体名
# ============================================================================

class TestSpecifyEntityNames:
    """指定实体名测试"""

    def test_specify_entity_names_priority(self, synthesizer, sample_chunks,
                                            sample_graph_entities, sample_graph_edges):
        """测试指定实体名优先使用"""
        result = synthesizer.synthesize(
            query="项目情况",
            retrieved_chunks=sample_chunks,
            graph_entities=sample_graph_entities,
            graph_edges=sample_graph_edges,
            entity_names=["淘宝项目"],  # 只指定淘宝项目
        )

        # 应只包含指定的实体
        assert result.entity_count == 1
        entity_names = [g["entity"] for g in result.entity_groups]
        assert "淘宝项目" in entity_names

    def test_specify_nonexistent_entity(self, synthesizer, sample_chunks):
        """测试指定不存在的实体名"""
        result = synthesizer.synthesize(
            query="项目情况",
            retrieved_chunks=sample_chunks,
            entity_names=["不存在的实体XYZ"],
        )

        # 即使实体不存在也应返回结果（只是没有匹配到信息）
        assert result is not None
        assert result.entity_count == 1
        # 实体组的 items 可能为空
        if result.entity_groups:
            group = result.entity_groups[0]
            assert group["entity"] == "不存在的实体XYZ"


# ============================================================================
# 测试 7: 便捷方法
# ============================================================================

class TestConvenienceMethods:
    """便捷方法测试"""

    def test_synthesize_from_rag_result(self, synthesizer):
        """测试 synthesize_from_rag_result 便捷方法"""
        rag_result = {
            "results": [
                {"doc_id": "d1", "content": "张三在阿里巴巴", "source": "doc1.md"},
                {"doc_id": "d2", "content": "李四在字节跳动", "source": "doc2.md"},
            ],
            "total": 2,
        }
        graph_data = {
            "entities": [
                {"name": "张三", "type": "person"},
                {"name": "阿里巴巴", "type": "company"},
            ],
            "edges": [
                {"source": "张三", "target": "阿里巴巴", "type": "works_at", "confidence": 0.9},
            ],
        }

        result = synthesizer.synthesize_from_rag_result(
            query="张三在阿里巴巴",
            rag_result=rag_result,
            graph_data=graph_data,
        )

        assert result is not None
        assert result.mode in ("cross_entity", "fallback_rag")

    def test_get_stats(self, synthesizer, sample_chunks):
        """测试统计信息"""
        stats_before = synthesizer.get_stats()
        assert stats_before["total_synthesis"] >= 0

        # 执行一次合成
        synthesizer.synthesize(
            query="张三",
            retrieved_chunks=sample_chunks,
            entity_names=["张三"],
        )

        stats_after = synthesizer.get_stats()
        assert stats_after["total_synthesis"] == stats_before["total_synthesis"] + 1


# ============================================================================
# 测试 8: 边界情况
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""

    def test_very_long_query(self, synthesizer, sample_chunks):
        """测试超长查询"""
        long_query = "查询" * 200
        result = synthesizer.synthesize(
            query=long_query,
            retrieved_chunks=sample_chunks,
        )
        assert result is not None

    def test_single_chunk(self, synthesizer):
        """测试单个 chunk"""
        result = synthesizer.synthesize(
            query="张三",
            retrieved_chunks=[{"doc_id": "d1", "content": "张三在阿里巴巴工作", "source": "doc1.md"}],
            entity_names=["张三"],
        )
        assert result is not None
        if result.entity_groups:
            assert len(result.entity_groups[0]["items"]) == 1

    def test_many_chunks_limit(self, synthesizer):
        """测试超过 max_chunks 限制"""
        many_chunks = [
            {"doc_id": f"d{i}", "content": f"张三的第{i}份报告", "source": f"doc{i}.md"}
            for i in range(50)
        ]
        result = synthesizer.synthesize(
            query="张三",
            retrieved_chunks=many_chunks,
            entity_names=["张三"],
        )
        assert result is not None
        # 不会处理超过 max_chunks 的 chunk
        assert result.chunk_count == 50  # 记录原始数量

    def test_chunk_without_content(self, synthesizer):
        """测试无 content 字段的 chunk"""
        bad_chunks = [
            {"doc_id": "d1"},  # 无 content
            {"doc_id": "d2", "content": "张三在阿里巴巴", "source": "doc2.md"},
        ]
        result = synthesizer.synthesize(
            query="张三",
            retrieved_chunks=bad_chunks,
            entity_names=["张三"],
        )
        # 不应崩溃
        assert result is not None

    def test_graph_edges_with_missing_fields(self, synthesizer, sample_chunks):
        """测试缺失字段的 graph_edges"""
        incomplete_edges = [
            {"source": "张三", "target": "李四"},  # 无 type
            {"source": "张三", "type": "works_at"},  # 无 target
            {},  # 空边
        ]
        result = synthesizer.synthesize(
            query="张三",
            retrieved_chunks=sample_chunks,
            graph_entities=[{"name": "张三", "type": "person"}],
            graph_edges=incomplete_edges,
        )
        # 不应崩溃
        assert result is not None

    def test_synthesis_result_to_dict(self, synthesizer, sample_chunks):
        """测试 SynthesisResult.to_dict()"""
        result = synthesizer.synthesize(
            query="张三",
            retrieved_chunks=sample_chunks,
            entity_names=["张三"],
        )
        d = result.to_dict()

        assert "query" in d
        assert "synthesized_text" in d
        assert "entity_groups" in d
        assert "relations" in d
        assert "sources" in d
        assert "entity_count" in d
        assert "chunk_count" in d
        assert "mode" in d


# ============================================================================
# 测试 9: 全局单例
# ============================================================================

class TestGlobalSingleton:
    """全局单例测试"""

    def test_get_synthesizer_singleton(self):
        """测试 get_synthesizer 返回单例"""
        syn1 = get_synthesizer()
        syn2 = get_synthesizer()
        assert syn1 is syn2

    def test_get_synthesizer_functional(self):
        """测试全局单例可用"""
        syn = get_synthesizer()
        result = syn.synthesize(
            query="测试",
            retrieved_chunks=[{"doc_id": "d1", "content": "测试内容", "source": "test.md"}],
        )
        assert result is not None


# ============================================================================
# 直接运行
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
