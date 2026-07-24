"""
test_smart_llm.py - 智能LLM路由测试

测试内容：
1. 查询类型检测
2. 模型选择
3. 自动降级
4. 缓存功能
5. 统计功能
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.model_router import ModelRouter, QueryType
from src.services.smart_llm import SmartLLM, LLMResponse


class TestModelRouter:
    """模型路由器测试"""
    
    def setup_method(self):
        """测试前准备"""
        self.router = ModelRouter()
    
    def test_detect_simple_chat(self):
        """测试检测简单对话"""
        queries = [
            "你好",
            "你好，介绍一下伏羲系统",
            "什么是知识图谱？",
            "帮我查一下",
            "请问一下",
        ]
        for query in queries:
            query_type = self.router.detect_query_type(query)
            assert query_type == QueryType.SIMPLE_CHAT, f"查询 '{query}' 应该检测为 SIMPLE_CHAT，实际为 {query_type}"
    
    def test_detect_complex_json(self):
        """测试检测复杂JSON输出"""
        queries = [
            "提取以下文本中的实体",
            "分析这个数据结构",
            "返回表格数据",
            "分类标签",
        ]
        for query in queries:
            query_type = self.router.detect_query_type(query)
            assert query_type == QueryType.COMPLEX_JSON, f"查询 '{query}' 应该检测为 COMPLEX_JSON，实际为 {query_type}"
    
    def test_detect_code_generation(self):
        """测试检测代码生成"""
        queries = [
            "写一个Python代码",
            "编写一个程序",
            "实现一个函数",
            "写一个脚本",
            "Python代码实现",
        ]
        for query in queries:
            query_type = self.router.detect_query_type(query)
            assert query_type == QueryType.CODE_GENERATION, f"查询 '{query}' 应该检测为 CODE_GENERATION，实际为 {query_type}"
    
    def test_detect_summarization(self):
        """测试检测摘要生成"""
        queries = [
            "总结一下",
            "生成摘要",
            "概括内容",
            "提炼要点",
            "归纳总结",
        ]
        for query in queries:
            query_type = self.router.detect_query_type(query)
            assert query_type == QueryType.SUMMARIZATION, f"查询 '{query}' 应该检测为 SUMMARIZATION，实际为 {query_type}"
    
    def test_detect_translation(self):
        """测试检测翻译"""
        queries = [
            "翻译成英文",
            "translate to Chinese",
            "转换成中文",
            "译成日语",
        ]
        for query in queries:
            query_type = self.router.detect_query_type(query)
            assert query_type == QueryType.TRANSLATION, f"查询 '{query}' 应该检测为 TRANSLATION，实际为 {query_type}"
    
    def test_detect_knowledge_qa(self):
        """测试检测知识问答（默认）"""
        queries = [
            "伏羲系统的核心功能是什么？",
            "如何配置防火墙？",
            "这个功能怎么使用？",
            "请解释一下这个概念",
        ]
        for query in queries:
            query_type = self.router.detect_query_type(query)
            assert query_type == QueryType.KNOWLEDGE_QA, f"查询 '{query}' 应该检测为 KNOWLEDGE_QA，实际为 {query_type}"
    
    def test_select_model_pro(self):
        """测试选择Pro模型"""
        queries = [
            "你好",
            "什么是知识图谱？",
            "写一个Python代码",
            "总结一下",
            "翻译成英文",
        ]
        for query in queries:
            model = self.router.select_model(query)
            assert model == "mimo-v2.5-pro", f"查询 '{query}' 应该选择 mimo-v2.5-pro，实际为 {model}"
    
    def test_select_model_standard(self):
        """测试选择标准模型"""
        queries = [
            "提取以下文本中的实体",
            "分析这个数据结构",
            "返回表格数据",
        ]
        for query in queries:
            model = self.router.select_model(query)
            assert model == "mimo-v2.5", f"查询 '{query}' 应该选择 mimo-v2.5，实际为 {model}"
    
    def test_select_model_with_context(self):
        """测试带上下文的模型选择"""
        # 显式指定需要JSON输出
        context = {"need_json": True}
        model = self.router.select_model("随便什么查询", context)
        assert model == "mimo-v2.5", f"上下文指定需要JSON时应该选择 mimo-v2.5，实际为 {model}"
        
        # 显式指定需要提取实体
        context = {"extract_entities": True}
        model = self.router.select_model("随便什么查询", context)
        assert model == "mimo-v2.5", f"上下文指定需要提取实体时应该选择 mimo-v2.5，实际为 {model}"
    
    def test_get_fallback_model(self):
        """测试获取降级模型"""
        # Pro降级到标准
        fallback = self.router.get_fallback_model("mimo-v2.5-pro")
        assert fallback == "mimo-v2.5", f"Pro降级应该返回 mimo-v2.5，实际为 {fallback}"
        
        # 标准降级到Pro
        fallback = self.router.get_fallback_model("mimo-v2.5")
        assert fallback == "mimo-v2.5-pro", f"标准降级应该返回 mimo-v2.5-pro，实际为 {fallback}"
    
    def test_stats_recording(self):
        """测试统计记录"""
        # 记录成功
        self.router.record_success("mimo-v2.5-pro", 1000)
        self.router.record_success("mimo-v2.5", 500)
        self.router.record_failure("mimo-v2.5-pro")
        
        stats = self.router.get_stats()
        
        assert stats["pro"]["success"] == 1
        assert stats["pro"]["fail"] == 1
        assert stats["standard"]["success"] == 1
        assert stats["standard"]["fail"] == 0
        assert stats["total_queries"] == 0  # record_success不增加查询计数
    
    def test_stats_reset(self):
        """测试统计重置"""
        self.router.record_success("mimo-v2.5-pro", 1000)
        self.router.record_failure("mimo-v2.5")
        
        self.router.reset_stats()
        
        stats = self.router.get_stats()
        assert stats["pro"]["success"] == 0
        assert stats["pro"]["fail"] == 0
        assert stats["standard"]["success"] == 0
        assert stats["standard"]["fail"] == 0


class TestSmartLLM:
    """智能LLM调用器测试"""
    
    def setup_method(self):
        """测试前准备"""
        self.router = ModelRouter()
        self.smart_llm = SmartLLM(self.router)
    
    @pytest.mark.asyncio
    async def test_call_with_cache(self):
        """测试带缓存的调用"""
        # Mock LLM调用
        with patch('src.services.smart_llm._call_api', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "测试响应"
            
            # 第一次调用
            messages = [{"role": "user", "content": "你好"}]
            result1 = await self.smart_llm.call(messages, query="你好")
            
            assert result1.success is True
            assert result1.content == "测试响应"
            assert result1.model == "mimo-v2.5-pro"
            assert result1.fallback is False
            
            # 第二次调用（应该使用缓存）
            result2 = await self.smart_llm.call(messages, query="你好")
            
            assert result2.success is True
            assert result2.content == "测试响应"
            
            # 验证只调用了一次API
            assert mock_call.call_count == 1
    
    @pytest.mark.asyncio
    async def test_call_with_fallback(self):
        """测试自动降级"""
        with patch('src.services.smart_llm._call_api', new_callable=AsyncMock) as mock_call:
            # 第一次调用失败，第二次成功
            mock_call.side_effect = [None, "降级响应"]
            
            messages = [{"role": "user", "content": "提取实体"}]
            result = await self.smart_llm.call(messages, query="提取实体")
            
            assert result.success is True
            assert result.content == "降级响应"
            # 提取实体使用mimo-v2.5，失败后降级到mimo-v2.5-pro
            assert result.model == "mimo-v2.5-pro"  # 降级到Pro模型
            assert result.fallback is True
    
    @pytest.mark.asyncio
    async def test_call_all_models_fail(self):
        """测试所有模型都失败"""
        with patch('src.services.smart_llm._call_api', new_callable=AsyncMock) as mock_call:
            # 所有调用都失败
            mock_call.return_value = None
            
            messages = [{"role": "user", "content": "测试"}]
            result = await self.smart_llm.call(messages, query="测试")
            
            assert result.success is False
            assert result.fallback is True
            assert "服务暂时不可用" in result.content
    
    @pytest.mark.asyncio
    async def test_call_with_json_schema(self):
        """测试带JSON schema的调用"""
        with patch('src.services.smart_llm._call_api', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = '{"entities": ["test"]}'
            
            messages = [{"role": "user", "content": "提取实体"}]
            response_format = {"type": "json_object"}
            result = await self.smart_llm.call(
                messages, 
                query="提取实体",
                response_format=response_format
            )
            
            assert result.success is True
            assert result.model == "mimo-v2.5"  # JSON任务使用标准模型
    
    @pytest.mark.asyncio
    async def test_call_json_schema_empty_response(self):
        """测试JSON schema返回空的情况"""
        with patch('src.services.smart_llm._call_api', new_callable=AsyncMock) as mock_call:
            # 第一次返回空（JSON schema问题），第二次成功
            mock_call.side_effect = [None, '{"entities": ["test"]}']
            
            messages = [{"role": "user", "content": "提取实体"}]
            response_format = {"type": "json_object"}
            result = await self.smart_llm.call(
                messages,
                query="提取实体", 
                response_format=response_format
            )
            
            assert result.success is True
            assert result.fallback is True  # 触发了降级
    
    def test_get_stats(self):
        """测试获取统计信息"""
        stats = self.smart_llm.get_stats()
        
        assert "total_queries" in stats
        assert "total_cost" in stats
        assert "pro" in stats
        assert "standard" in stats
        assert "query_type_distribution" in stats
    
    def test_reset_stats(self):
        """测试重置统计信息"""
        # 先记录一些数据
        self.router.record_success("mimo-v2.5-pro", 1000)
        self.router.record_failure("mimo-v2.5")
        
        # 重置
        self.smart_llm.reset_stats()
        
        stats = self.smart_llm.get_stats()
        assert stats["pro"]["success"] == 0
        assert stats["pro"]["fail"] == 0


class TestIntegration:
    """集成测试"""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """测试完整工作流程"""
        with patch('src.services.smart_llm._call_api', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "成功响应"
            
            from src.services.smart_llm import get_smart_llm
            
            smart_llm = get_smart_llm()
            
            # 测试不同类型查询
            test_cases = [
                ("你好", "mimo-v2.5-pro", "simple_chat"),
                ("提取实体", "mimo-v2.5", "complex_json"),
                ("写Python代码", "mimo-v2.5-pro", "code_generation"),
                ("总结一下", "mimo-v2.5-pro", "summarization"),
            ]
            
            for query, expected_model, expected_type in test_cases:
                messages = [{"role": "user", "content": query}]
                result = await smart_llm.call(messages, query=query)
                
                assert result.success is True
                assert result.model == expected_model
                assert result.query_type == expected_type
            
            # 验证统计
            stats = smart_llm.get_stats()
            assert stats["total_queries"] == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
