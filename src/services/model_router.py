"""
model_router.py - 智能模型路由器

根据查询类型自动选择最优模型：
- 简单对话 → mimo-v2.5-pro（推理更强）
- 复杂JSON → mimo-v2.5（输出稳定）
- 知识问答 → mimo-v2.5-pro（回答更准）
- 代码生成 → mimo-v2.5-pro（代码更好）
"""

import re
import time
import logging
from enum import Enum
from typing import Optional, Dict, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """查询类型"""
    SIMPLE_CHAT = "simple_chat"           # 简单对话
    COMPLEX_JSON = "complex_json"         # 复杂JSON输出
    STRUCTURED_DATA = "structured_data"   # 结构化数据提取
    KNOWLEDGE_QA = "knowledge_qa"         # 知识问答
    CODE_GENERATION = "code_generation"   # 代码生成
    SUMMARIZATION = "summarization"       # 摘要生成
    TRANSLATION = "translation"           # 翻译


@dataclass
class ModelConfig:
    """模型配置"""
    name: str
    max_tokens: int = 4096
    temperature: float = 0.3
    use_cases: Set[str] = field(default_factory=set)
    cost_per_1k_tokens: float = 0.0  # 每1000token成本（元）


class ModelRouter:
    """智能模型路由器"""
    
    # JSON输出的关键词模式
    JSON_PATTERNS = [
        r"提取.*实体",
        r"分析.*结构",
        r"生成.*JSON",
        r"生成JSON",
        r"返回.*格式",
        r"表格.*数据",
        r"分类.*标签",
        r"解析.*数据",
        r"转换.*格式",
        r"输出.*列表",
        r"返回.*数组",
    ]
    
    # 简单对话的关键词模式
    SIMPLE_PATTERNS = [
        r"^你好",
        r"^hi",
        r"^hello",
        r"^什么是",
        r"^介绍一下",
        r"^帮我",
        r"^请问",
        r"^谢谢",
        r"^好的",
        r"^明白",
    ]
    
    # 代码生成的关键词模式
    CODE_PATTERNS = [
        r"写.*代码",
        r"编写.*程序",
        r"实现.*函数",
        r"写.*脚本",
        r"编程",
        r"python.*代码",
        r"java.*代码",
        r"sql.*查询",
    ]
    
    # 摘要生成的关键词模式
    SUMMARY_PATTERNS = [
        r"总结",
        r"摘要",
        r"概括",
        r"提炼",
        r"归纳",
    ]
    
    # 翻译的关键词模式
    TRANSLATE_PATTERNS = [
        r"翻译",
        r"translate",
        r"转换成.*文",
        r"译成",
    ]
    
    def __init__(self):
        # 模型配置
        self.models = {
            "mimo-v2.5-pro": ModelConfig(
                name="mimo-v2.5-pro",
                max_tokens=4096,
                temperature=0.3,
                use_cases={"simple_chat", "knowledge_qa", "code_generation", "summarization", "translation"},
                cost_per_1k_tokens=0.02,
            ),
            "mimo-v2.5": ModelConfig(
                name="mimo-v2.5",
                max_tokens=4096,
                temperature=0.3,
                use_cases={"complex_json", "structured_data"},
                cost_per_1k_tokens=0.01,
            ),
        }
        
        # 默认模型映射
        self.model_map = {
            QueryType.SIMPLE_CHAT: "mimo-v2.5-pro",
            QueryType.COMPLEX_JSON: "mimo-v2.5",
            QueryType.STRUCTURED_DATA: "mimo-v2.5",
            QueryType.KNOWLEDGE_QA: "mimo-v2.5-pro",
            QueryType.CODE_GENERATION: "mimo-v2.5-pro",
            QueryType.SUMMARIZATION: "mimo-v2.5-pro",
            QueryType.TRANSLATION: "mimo-v2.5-pro",
        }
        
        # 统计信息
        self.stats = {
            "pro_success": 0,
            "pro_fail": 0,
            "standard_success": 0,
            "standard_fail": 0,
            "total_queries": 0,
            "total_cost": 0.0,
        }
        
        # 查询类型统计
        self.query_type_stats = {qt.value: 0 for qt in QueryType}
        
        # ── P1: 降级冷却机制 ──
        # _degraded_models: {model_name: degraded_until_timestamp}
        self._degraded_models: Dict[str, float] = {}
        self._degraded_cooldown_seconds: float = 60.0  # 失败后60秒冷却
    
    def detect_query_type(self, query: str, context: Optional[Dict] = None) -> QueryType:
        """
        检测查询类型
        
        Args:
            query: 用户查询
            context: 上下文信息（可选）
                - need_json: bool 是否需要JSON输出
                - extract_entities: bool 是否需要提取实体
                - response_format: dict 响应格式
        
        Returns:
            QueryType: 查询类型
        """
        query_lower = query.lower().strip()
        
        # 1. 检查上下文中的显式标记
        if context:
            if context.get("need_json") or context.get("response_format"):
                return QueryType.COMPLEX_JSON
            if context.get("extract_entities"):
                return QueryType.STRUCTURED_DATA
        
        # 2. 检查是否需要JSON输出
        for pattern in self.JSON_PATTERNS:
            if re.search(pattern, query_lower):
                logger.debug(f"检测到JSON模式: {pattern}")
                return QueryType.COMPLEX_JSON
        
        # 3. 检查是否是代码生成
        for pattern in self.CODE_PATTERNS:
            if re.search(pattern, query_lower):
                logger.debug(f"检测到代码模式: {pattern}")
                return QueryType.CODE_GENERATION
        
        # 4. 检查是否是摘要生成
        for pattern in self.SUMMARY_PATTERNS:
            if re.search(pattern, query_lower):
                logger.debug(f"检测到摘要模式: {pattern}")
                return QueryType.SUMMARIZATION
        
        # 5. 检查是否是翻译
        for pattern in self.TRANSLATE_PATTERNS:
            if re.search(pattern, query_lower):
                logger.debug(f"检测到翻译模式: {pattern}")
                return QueryType.TRANSLATION
        
        # 6. 检查是否是简单对话
        for pattern in self.SIMPLE_PATTERNS:
            if re.search(pattern, query_lower):
                logger.debug(f"检测到简单对话模式: {pattern}")
                return QueryType.SIMPLE_CHAT
        
        # 7. 默认使用知识问答
        logger.debug("默认使用知识问答模式")
        return QueryType.KNOWLEDGE_QA
    
    def select_model(self, query: str, context: Optional[Dict] = None) -> str:
        """
        选择模型（P1: 自动跳过降级冷却中的模型）
        
        Args:
            query: 用户查询
            context: 上下文信息
        
        Returns:
            str: 模型名称
        """
        query_type = self.detect_query_type(query, context)
        model = self.model_map[query_type]
        
        # P1: 如果主模型处于降级冷却期，直接使用降级模型
        if self.is_degraded(model):
            fallback = self.get_fallback_model(model)
            logger.info(
                f"查询类型: {query_type.value}, "
                f"主模型 {model} 处于降级冷却期，直接使用降级模型: {fallback}"
            )
            model = fallback
        
        # 更新统计
        self.query_type_stats[query_type.value] += 1
        self.stats["total_queries"] += 1
        
        logger.info(f"查询类型: {query_type.value}, 选择模型: {model}")
        return model
    
    def get_fallback_model(self, primary_model: str) -> str:
        """
        获取降级模型（P1: 带冷却检查）
        
        Args:
            primary_model: 主模型名称
        
        Returns:
            str: 降级模型名称
        """
        if primary_model == "mimo-v2.5-pro":
            return "mimo-v2.5"
        return "mimo-v2.5-pro"
    
    def is_degraded(self, model: str) -> bool:
        """检查模型是否处于降级冷却期"""
        if model in self._degraded_models:
            degraded_until = self._degraded_models[model]
            if time.time() < degraded_until:
                remaining = degraded_until - time.time()
                logger.debug(f"模型 {model} 处于降级冷却期，剩余 {remaining:.1f}s")
                return True
            else:
                # 冷却期已过，自动恢复
                del self._degraded_models[model]
                logger.info(f"模型 {model} 冷却期已过，已恢复")
        return False
    
    def mark_degraded(self, model: str, cooldown_seconds: Optional[float] = None):
        """标记模型进入降级冷却期"""
        cooldown = cooldown_seconds or self._degraded_cooldown_seconds
        self._degraded_models[model] = time.time() + cooldown
        logger.warning(f"模型 {model} 已标记为降级，冷却 {cooldown}s")
    
    def get_degraded_models(self) -> Dict[str, float]:
        """获取当前降级模型信息"""
        now = time.time()
        return {
            model: round(degraded_until - now, 1)
            for model, degraded_until in self._degraded_models.items()
            if now < degraded_until
        }
    
    def record_success(self, model: str, tokens_used: int = 0):
        """记录成功调用"""
        if "pro" in model:
            self.stats["pro_success"] += 1
        else:
            self.stats["standard_success"] += 1
        
        # 计算成本
        if model in self.models:
            cost = (tokens_used / 1000) * self.models[model].cost_per_1k_tokens
            self.stats["total_cost"] += cost
    
    def record_failure(self, model: str):
        """记录失败调用（P1: 触发降级冷却）"""
        if "pro" in model:
            self.stats["pro_fail"] += 1
        else:
            self.stats["standard_fail"] += 1
        
        # P1: 自动标记降级冷却
        self.mark_degraded(model)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        total_pro = self.stats["pro_success"] + self.stats["pro_fail"]
        total_standard = self.stats["standard_success"] + self.stats["standard_fail"]
        
        return {
            "total_queries": self.stats["total_queries"],
            "total_cost": round(self.stats["total_cost"], 4),
            "pro": {
                "total": total_pro,
                "success": self.stats["pro_success"],
                "fail": self.stats["pro_fail"],
                "success_rate": round(self.stats["pro_success"] / total_pro * 100, 2) if total_pro > 0 else 0,
            },
            "standard": {
                "total": total_standard,
                "success": self.stats["standard_success"],
                "fail": self.stats["standard_fail"],
                "success_rate": round(self.stats["standard_success"] / total_standard * 100, 2) if total_standard > 0 else 0,
            },
            "query_type_distribution": self.query_type_stats,
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            "pro_success": 0,
            "pro_fail": 0,
            "standard_success": 0,
            "standard_fail": 0,
            "total_queries": 0,
            "total_cost": 0.0,
        }
        self.query_type_stats = {qt.value: 0 for qt in QueryType}


# 全局路由器实例
_router: Optional[ModelRouter] = None


def get_router() -> ModelRouter:
    """获取全局路由器实例"""
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router
