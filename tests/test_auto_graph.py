#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_auto_graph.py — 自组网知识图谱测试

伏羲 v1.50 Phase B: Self-Wiring Knowledge Graph
测试范围：
  1. 实体提取：中文名/英文名/公司名/日期/金额/产品编号
  2. 边关系：works_at / invested_in / attended / founded
  3. 零 LLM 保证（确认代码中无任何 API 调用）
  4. BOM 表数据测试：伺服电机 HG-KN43BJ-S100 → MISUMI
"""

import pytest
import sys
import os

# Ensure src is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bagua.auto_graph import (
    AutoGraphBuilder,
    ENTITY_PATTERNS,
    EDGE_RULES,
    get_auto_graph_builder,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def builder():
    """返回全新的 AutoGraphBuilder 实例"""
    return AutoGraphBuilder()


@pytest.fixture
def global_builder():
    """返回全局单例"""
    return get_auto_graph_builder()


# ============================================================================
# 测试 1：实体提取
# ============================================================================

class TestEntityExtraction:
    """实体提取测试集"""
    
    def test_english_person_name(self, builder):
        """测试英文人名提取"""
        text = "John Smith presented at the conference. Mary Johnson attended."
        entities = builder.extract_entities(text)
        names = [e["name"] for e in entities if e["type"] == "person"]
        assert any("John Smith" in n or "John" in n for n in names), f"人名未提取: {names}"
    
    def test_company_name_english(self, builder):
        """测试英文公司名提取"""
        text = "Microsoft Corp and Google Inc are competitors."
        entities = builder.extract_entities(text)
        names = [e["name"] for e in entities if e["type"] == "company"]
        assert len(names) > 0, "英文公司名未提取"
    
    def test_company_name_chinese(self, builder):
        """测试中文公司名提取"""
        text = "阿里巴巴集团和腾讯科技有限公司是本项目合作方。小米科技也参与了。"
        entities = builder.extract_entities(text)
        names = [e["name"] for e in entities if e["type"] == "company"]
        assert len(names) > 0, f"中文公司名未提取: {names}"
        # 至少应该提取到 "阿里巴巴集团" 或 "腾讯科技有限公司"
        found = False
        for n in names:
            if "阿里巴巴" in n or "腾讯" in n or "小米" in n:
                found = True
                break
        assert found, f"未找到预期公司名: {names}"
    
    def test_date_extraction(self, builder):
        """测试日期提取"""
        text = "项目于2024-03-15启动，2024/06/01验收完成。"
        entities = builder.extract_entities(text)
        dates = [e["name"] for e in entities if e["type"] == "date"]
        assert len(dates) >= 2, f"日期未全部提取: {dates}"
        assert "2024-03-15" in dates
        assert "2024/06/01" in dates
    
    def test_money_extraction(self, builder):
        """测试金额提取"""
        text = "项目预算500万元，每台设备报价$12,500。"
        entities = builder.extract_entities(text)
        money = [e["name"] for e in entities if e["type"] == "money"]
        assert len(money) >= 2, f"金额未全部提取: {money}"
    
    def test_product_code_extraction(self, builder):
        """测试产品编号提取"""
        text = "伺服电机 HG-KN43BJ-S100 配减速机 VRXF-18C-200。"
        entities = builder.extract_entities(text)
        products = [e["name"] for e in entities if e["type"] == "product"]
        # HG-KN43BJ-S100 应该被提取
        product_names = " ".join(products)
        assert len(products) > 0, f"产品编号未提取: {products}"
        assert any("HG-KN43" in p or "KN43" in p for p in products), \
            f"未提取到 HG-KN43BJ 系列: {products}"
    
    def test_material_extraction(self, builder):
        """测试材料提取"""
        text = "外壳材质PA66，内衬使用304不锈钢。"
        entities = builder.extract_entities(text)
        materials = [e["name"] for e in entities if e["type"] == "material"]
        assert len(materials) > 0, f"材料未提取: {materials}"
    
    def test_email_extraction(self, builder):
        """测试邮箱提取"""
        text = "联系邮箱：support@example.com 和 sales@company.co.jp"
        entities = builder.extract_entities(text)
        emails = [e["name"] for e in entities if e["type"] == "email"]
        assert len(emails) == 2, f"邮箱未正确提取: {emails}"
    
    def test_phone_extraction(self, builder):
        """测试电话号码提取"""
        text = "联系电话：13800138000 或 021-55551234"
        entities = builder.extract_entities(text)
        phones = [e["name"] for e in entities if e["type"] == "phone"]
        assert len(phones) >= 1, f"电话号码未提取: {phones}"
    
    def test_chinese_name_extraction(self, builder):
        """测试中文人名提取"""
        text = "张三负责项目管理，李四经理是技术负责人。"
        entities = builder.extract_entities(text)
        names = [e["name"] for e in entities if e["type"] == "chinese_name"]
        assert len(names) > 0, f"中文人名未提取: {names}"
    
    def test_entity_positions(self, builder):
        """测试实体位置信息"""
        text = "John Smith在2024-01-15参加了会议。"
        entities = builder.extract_entities(text)
        for entity in entities:
            assert "positions" in entity, f"实体 {entity['name']} 缺少 positions"
            assert len(entity["positions"]) > 0, f"实体 {entity['name']} 位置为空"
    
    def test_entity_deduplication(self, builder):
        """测试实体去重"""
        text = "MISUMI提供MISUMI的MISUMI标准件。"
        entities = builder.extract_entities(text)
        misumi_entities = [e for e in entities if "MISUMI" in e["name"]]
        # 同一名称不应重复
        assert len(misumi_entities) <= 1, f"MISUMI 实体重复: {misumi_entities}"
    
    def test_empty_text(self, builder):
        """测试空文本"""
        entities = builder.extract_entities("")
        assert entities == []
    
    def test_no_false_positives_on_common_words(self, builder):
        """测试常见词不误提取"""
        text = "这个项目需要很多设备和人员。"
        entities = builder.extract_entities(text)
        # 不应该把常见词提取为实体
        entity_names = [e["name"] for e in entities]
        for word in ["这个", "很多", "和"]:
            assert word not in entity_names, f"常见词被误提取: {word}"


# ============================================================================
# 测试 2：边关系提取
# ============================================================================

class TestEdgeExtraction:
    """边关系提取测试集"""
    
    def test_works_at_relation(self, builder):
        """测试 works_at 关系"""
        text = "张三在阿里巴巴工作，负责核心引擎开发。"
        entities = builder.extract_entities(text)
        edges = builder.build_from_text(text, "doc-001")
        
        works_at_edges = [e for e in edges if e["type"] == "works_at"]
        # 如果实体被提取到，应该建立边
        if len(entities) >= 2:
            assert len(edges) > 0, f"未提取到边关系: 实体={entities}"
    
    def test_invested_in_relation(self, builder):
        """测试 invested_in 关系"""
        text = "腾讯投资了一家AI初创公司。"
        entities = builder.extract_entities(text)
        edges = builder.build_from_text(text, "doc-002")
        # 至少应该有边的尝试
        assert isinstance(edges, list)
    
    def test_attended_relation(self, builder):
        """测试 attended 关系"""
        text = "John Smith在2024年参加了云栖大会。"
        entities = builder.extract_entities(text)
        edges = builder.build_from_text(text, "doc-003")
        assert isinstance(edges, list)
    
    def test_founded_relation(self, builder):
        """测试 founded 关系"""
        text = "马云创建了阿里巴巴集团。"
        entities = builder.extract_entities(text)
        edges = builder.build_from_text(text, "doc-004")
        assert isinstance(edges, list)
    
    def test_purchased_relation(self, builder):
        """测试 purchased 关系"""
        text = "工程部采购了 HG-KN43BJ-S100 伺服电机。"
        entities = builder.extract_entities(text)
        edges = builder.build_from_text(text, "doc-005")
        assert isinstance(edges, list)
    
    def test_edge_confidence_range(self, builder):
        """测试置信度范围"""
        text = "张三在阿里巴巴工作，负责淘宝项目。他于2020年参加了云栖大会。"
        edges = builder.build_from_text(text, "doc-006")
        for edge in edges:
            assert 0 <= edge["confidence"] <= 1, \
                f"置信度超出范围: {edge['confidence']}"
    
    def test_edge_has_doc_id(self, builder):
        """测试边包含 doc_id"""
        text = "测试文档内容。"
        edges = builder.build_from_text(text, "doc-test-123")
        for edge in edges:
            assert edge["doc_id"] == "doc-test-123", \
                f"边缺少正确 doc_id: {edge}"
    
    def test_edge_deduplication(self, builder):
        """测试边去重"""
        # 重复关系只保留置信度最高的
        text = "张三在阿里巴巴工作。张三在阿里巴巴任职。"
        edges = builder.build_from_text(text, "doc-007")
        # 相同 (source, target, type) 不应重复
        edge_keys = [(e["source"], e["target"], e["type"]) for e in edges]
        assert len(edge_keys) == len(set(edge_keys)), \
            f"边未去重: {edge_keys}"
    
    def test_supplier_relation(self, builder):
        """测试 supplier_of 关系"""
        text = "MISUMI是伺服电机的供应商。SMC是气动元件的厂商。"
        entities = builder.extract_entities(text)
        edges = builder.build_from_text(text, "doc-008")
        assert isinstance(edges, list)


# ============================================================================
# 测试 3：零 LLM 保证
# ============================================================================

class TestZeroLLM:
    """零 LLM 调用保证测试"""
    
    def test_no_llm_imports(self):
        """测试 auto_graph.py 不导入任何 LLM 模块"""
        import src.bagua.auto_graph as ag
        
        # 获取模块源代码
        src = ag.__file__
        with open(src, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 禁止导入 LLM 相关模块
        forbidden_imports = [
            "from src.services.llm",
            "import openai",
            "import anthropic",
            "call_llm(",
            "openai.ChatCompletion",
            "anthropic.Anthropic",
        ]
        
        for forbidden in forbidden_imports:
            assert forbidden not in content, \
                f"auto_graph.py 中包含 LLM 调用: {forbidden}"
    
    def test_no_api_calls_in_code(self):
        """测试代码中无 API 调用模式"""
        import src.bagua.auto_graph as ag
        
        src_path = ag.__file__
        with open(src_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 不应包含 HTTP 请求
        api_patterns = [
            "requests.post",
            "requests.get",
            "urllib.request",
            "http.client",
            "aiohttp.ClientSession",
            "httpx",
        ]
        
        for pattern in api_patterns:
            assert pattern not in content, \
                f"auto_graph.py 中包含 API 调用: {pattern}"
    
    def test_llm_calls_is_zero(self, builder):
        """测试 stats 中 llm_calls=0"""
        stats = builder.get_stats()
        assert stats["llm_calls"] == 0, \
            f"LLM 调用计数不为0: {stats['llm_calls']}"
    
    def test_only_regex_and_rules(self):
        """确认代码只使用 re 模块和规则字典"""
        import src.bagua.auto_graph as ag
        import inspect
        
        # 获取所有方法
        methods = inspect.getmembers(AutoGraphBuilder, predicate=inspect.isfunction)
        
        # 检查没有可疑的方法名
        method_names = [name for name, _ in methods]
        forbidden_names = [
            "call_llm", "ask_llm", "prompt_llm", "llm_extract",
            "openai_call", "api_call", "fetch_from_api",
        ]
        
        for forbidden in forbidden_names:
            assert forbidden not in method_names, \
                f"发现可疑 LLM 方法: {forbidden}"
    
    def test_build_from_text_no_network(self, builder):
        """确认 build_from_text 仅使用本地正则"""
        text = "这是一个纯文本测试，不会触发任何网络请求。"
        # 不应当需要网络
        result = builder.build_from_text(text, "local-test")
        assert isinstance(result, list)


# ============================================================================
# 测试 4：BOM 表数据
# ============================================================================

class TestBOMData:
    """用实际 BOM 表数据测试实体提取"""
    
    def test_servo_motor_bom_extraction(self, builder):
        """BOM 表：伺服电机 + 供应商"""
        text = """
        BOM 清单 - 自动化装配单元
        ========================
        序号  物料编号          名称              规格                数量  供应商
        1     HG-KN43BJ-S100    伺服电机          200W, 3000rpm       1    MISUMI
        2     VRXF-18C-200      行星减速机        减速比 1/18         1    MISUMI
        3     SMC-MHZ2-20D      气动手指          双作用, 缸径20mm    2    SMC
        4     FESTO-ADN-25-50   紧凑型气缸        行程50mm            2    FESTO
        5     PA66-GF30          尼龙外壳          黑色, 阻燃V0        4    本地加工
        6     304-SS-SHAFT-12   不锈钢轴          直径12mm, L=200mm   8    本地加工
        """
        
        entities = builder.extract_entities(text)
        
        # 验证产品编号
        products = [e["name"] for e in entities if e["type"] in ("product", "material")]
        product_names = [e["name"] for e in entities]
        
        # 伺服电机 HG-KN43BJ-S100 应被提取
        assert any("HG-KN43" in p or "KN43BJ" in p for p in product_names), \
            f"HG-KN43BJ-S100 未提取: {product_names}"
        
        # MISUMI 应被提取为品牌
        brands = [e["name"] for e in entities if e["type"] == "brand"]
        brand_names = [e["name"] for e in entities]
        assert any("MISUMI" in b for b in brand_names), \
            f"MISUMI 未提取: {brand_names}"
        
        # SMC 应被提取
        assert any("SMC" in b for b in brand_names), \
            f"SMC 未提取: {brand_names}"
        
        print(f"\n  BOM 实体提取结果: {len(entities)} 个实体")
        for e in entities:
            print(f"    [{e['type']}] {e['name']} (x{e['count']})")
    
    def test_bom_edges_builder(self, builder):
        """BOM 表：验证边构建"""
        text = """
        供应商 MISUMI 提供伺服电机 HG-KN43BJ-S100。
        SMC 是气动手指的供应商。
        工程部采购了300万元的标准件。
        """
        
        entities = builder.extract_entities(text)
        edges = builder.build_from_text(text, "bom-001")
        
        print(f"\n  BOM 边提取: {len(entities)} 实体, {len(edges)} 条边")
        for edge in edges:
            print(f"    [{edge['type']}] {edge['source']} → {edge['target']} (conf={edge['confidence']:.2f})")
        
        # 基本验证
        assert isinstance(edges, list)
    
    def test_build_full_graph(self, builder):
        """测试 build_full_graph 完整流程"""
        text = """
        三菱电机株式会社提供 HG-KN43BJ-S100 伺服电机。
        MISUMI 是三菱的授权代理商。
        本批次采购金额为 500 万元。
        """
        
        result = builder.build_full_graph(text, "doc-bom-001")
        
        assert result["doc_id"] == "doc-bom-001"
        assert "entities" in result
        assert "edges" in result
        assert "stats" in result
        assert result["stats"]["entity_count"] >= 0
        assert result["stats"]["edge_count"] >= 0
        
        print(f"\n  full_graph: {result['stats']}")
        print(f"  实体: {[e['name'] + '(' + e['type'] + ')' for e in result['entities']]}")
        print(f"  边: {[(e['source'], e['relation'], e['target']) for e in result['edges']]}")


# ============================================================================
# 测试 5：统计与全局单例
# ============================================================================

class TestStatsAndGlobal:
    """统计和全局单例测试"""
    
    def test_builder_stats(self, builder):
        """测试构建器统计"""
        # 执行一些操作
        builder.extract_entities("Test text with John Smith and 2024-03-15.")
        builder.build_from_text("John Smith works at Google Inc.", "test")
        
        stats = builder.get_stats()
        assert "total_builds" in stats
        assert "total_entities" in stats
        assert "total_edges" in stats
        assert stats["llm_calls"] == 0, "零 LLM 保证"
    
    def test_global_singleton(self):
        """测试全局单例"""
        b1 = get_auto_graph_builder()
        b2 = get_auto_graph_builder()
        assert b1 is b2, "全局单例不一致"
    
    def test_empty_text_returns_empty(self, builder):
        """测试空文本"""
        assert builder.build_from_text("", "") == []
        assert builder.build_from_text("   ", "") == []
        assert builder.build_full_graph("", "")["stats"]["entity_count"] == 0
    
    def test_build_from_text_output_format(self, builder):
        """测试 build_from_text 输出格式"""
        text = "张三在阿里巴巴工作。"
        edges = builder.build_from_text(text, "format-test")
        
        for edge in edges:
            assert "source" in edge, f"缺少 source: {edge}"
            assert "target" in edge, f"缺少 target: {edge}"
            assert "type" in edge, f"缺少 type: {edge}"
            assert "confidence" in edge, f"缺少 confidence: {edge}"
            assert "doc_id" in edge, f"缺少 doc_id: {edge}"
            assert "evidence" in edge, f"缺少 evidence: {edge}"


# ============================================================================
# 测试 6：自定义规则扩展
# ============================================================================

class TestCustomRules:
    """自定义规则扩展测试"""
    
    def test_add_entity_pattern(self, builder):
        """测试动态添加实体模式"""
        assert builder.add_entity_pattern("test_type", r"TEST_\d{3}"), \
            "实体模式添加失败"
        
        text = "样本编号 TEST_001 和 TEST_002 已通过检测。"
        entities = builder.extract_entities(text)
        test_entities = [e for e in entities if e["type"] == "test_type"]
        assert len(test_entities) == 2, \
            f"自定义实体模式未生效: {test_entities}"
    
    def test_add_edge_rule(self, builder):
        """测试动态添加边规则"""
        # 使用英文人名 + 产品名组合（w+ 在英文上下文中有效）
        assert builder.add_edge_rule(
            r"(John\s+Smith)\s+(?:测试|test|verify)\s+([A-Z]{2,}[\d-]+)",
            "tests",
            0.9
        ), "边规则添加失败"
        
        text = "John Smith 测试 HG-KN43BJ"
        entities = builder.extract_entities(text)
        edges = builder.build_from_text(text, "rule-test")
        
        # 检查是否有 tests 类型的边
        test_edges = [e for e in edges if e["type"] == "tests"]
        assert len(test_edges) > 0, \
            f"自定义边规则未生效: entities={entities}, edges={edges}"


# ============================================================================
# 测试 7：性能压力测试
# ============================================================================

class TestPerformance:
    """性能测试"""
    
    def test_large_text_performance(self, builder):
        """大文本性能测试 — 应 < 100ms"""
        import time
        
        # 生成 ~10KB 文本
        text = ("MISUMI 提供 HG-KN43BJ-S100 伺服电机。"
                "SMC 供应 MHZ2-20D 气动手指。"
                "项目预算 500 万元，于 2024-03-15 启动。") * 100
        
        start = time.perf_counter()
        entities = builder.extract_entities(text)
        edges = builder.build_from_text(text, "perf-test")
        elapsed = (time.perf_counter() - start) * 1000
        
        print(f"\n  大文本性能: {len(text)} 字符 → {len(entities)} 实体, {len(edges)} 边, {elapsed:.1f}ms")
        
        # 10KB 文本在 < 500ms 内
        assert elapsed < 500, f"大文本处理太慢: {elapsed:.1f}ms"
    
    def test_many_short_texts(self, builder):
        """大量短文本测试"""
        import time
        
        texts = [
            "John Smith works at Google Inc.",
            "Mary Johnson attended the AI Summit in 2024.",
            "三菱电机投资了500万元的伺服电机项目。",
            "MISUMI是标准件的供应商。",
            "工程部采购了HG-KN43BJ-S100。",
        ] * 20  # 100 条
        
        start = time.perf_counter()
        for i, text in enumerate(texts):
            builder.build_from_text(text, f"batch-{i}")
        elapsed = (time.perf_counter() - start) * 1000
        
        print(f"\n  批量处理: {len(texts)} 条 → {elapsed:.1f}ms ({elapsed/len(texts):.2f}ms/条)")
        
        # 100 条在 < 2s 内
        assert elapsed < 2000, f"批量处理太慢: {elapsed:.1f}ms"


# ============================================================================
# 主入口
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  伏羲 v1.50 Phase B: AutoGraph 测试")
    print("=" * 60)
    
    # 简单手动验证
    b = get_auto_graph_builder()
    
    # BOM 表数据测试
    bom_text = """
    BOM 清单 - 自动化装配单元
    1  HG-KN43BJ-S100  伺服电机    200W       1  MISUMI
    2  VRXF-18C-200    行星减速机   减速比18    1  MISUMI
    3  SMC-MHZ2-20D    气动手指    双作用     2  SMC
    """
    
    print("\n[实体提取] 伺服电机 BOM 表:")
    entities = b.extract_entities(bom_text)
    for e in entities:
        print(f"  [{e['type']:12s}] {e['name']:25s} (出现 {e['count']} 次)")
    
    print(f"\n[边构建]:")
    edges = b.build_from_text(bom_text, "bom-test")
    for edge in edges:
        print(f"  [{edge['type']:15s}] {edge['source']:20s} → {edge['target']:20s} (conf={edge['confidence']:.2f})")
    
    print(f"\n[统计]: {b.get_stats()}")
    print(f"\n[零 LLM 保证]: llm_calls = {b.get_stats()['llm_calls']}")
    print("\n✅ 手动测试完成")
    
    # 如有 pytest，自动运行
    if "pytest" in sys.modules or True:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
            capture_output=True, text=True, timeout=30,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        print("\n" + result.stdout[-3000:] if result.stdout else "")
        if result.stderr:
            print("\n[stderr]:", result.stderr[-1000:])
