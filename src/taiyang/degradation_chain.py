"""
degradation_chain.py — 降级链 (v1.50 R4 兼容代理)

原模块已迁移到 shaoyin 模块中的 query_router。
此文件保留为向后兼容层，供旧测试代码使用。
所有公共 API 签名不变。
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
import logging

logger = logging.getLogger("taiyang.degradation_chain")


@dataclass
class DegradationLevel:
    """降级级别配置"""
    name: str
    top_k: int
    deep_search: bool = False
    multi_hop: bool = False
    use_agent: bool = False
    timeout_ms: int = 5000
    description: str = ""


class DegradationChain:
    """降级链管理器
    
    五层降级策略:
        L1_FAST    — 快速检索 (top_k=5)
        L2_STANDARD — 标准检索 (top_k=10)
        L3_DEEP    — 深度检索 (top_k=20)
        L4_AGENT   — Agent 级别搜索 (top_k=30)
        L5_CRAG    — CRAG 纠正增强 (top_k=50)
    """
    
    DEGRADATION_CONFIG: Dict[str, DegradationLevel] = {
        "L1_FAST": DegradationLevel(
            name="L1_FAST",
            top_k=5,
            timeout_ms=3000,
            description="快速检索：适合简单查询（定义、数值查询）"
        ),
        "L2_STANDARD": DegradationLevel(
            name="L2_STANDARD",
            top_k=10,
            timeout_ms=5000,
            description="标准检索：适合比较、操作指南查询"
        ),
        "L3_DEEP": DegradationLevel(
            name="L3_DEEP",
            top_k=20,
            deep_search=True,
            timeout_ms=10000,
            description="深度检索：适合开放式、多跳查询"
        ),
        "L4_AGENT": DegradationLevel(
            name="L4_AGENT",
            top_k=30,
            multi_hop=True,
            use_agent=True,
            timeout_ms=15000,
            description="Agent 级别：适合复杂多意图查询"
        ),
        "L5_CRAG": DegradationLevel(
            name="L5_CRAG",
            top_k=50,
            deep_search=True,
            multi_hop=True,
            use_agent=True,
            timeout_ms=30000,
            description="CRAG 增强：适合故障恢复和纠正增强"
        ),
    }
    
    def __init__(self, start_level: str = "L1_FAST"):
        """
        Args:
            start_level: 初始降级级别
        """
        self.current_level = start_level
        self._chain_order = ["L1_FAST", "L2_STANDARD", "L3_DEEP", "L4_AGENT", "L5_CRAG"]
        self._level_index = self._chain_order.index(start_level) if start_level in self._chain_order else 0
    
    def get_current_level(self) -> DegradationLevel:
        """获取当前降级级别配置"""
        return self.DEGRADATION_CONFIG.get(self.current_level, self.DEGRADATION_CONFIG["L1_FAST"])
    
    def degrade(self) -> Optional[DegradationLevel]:
        """降级到下一级
        
        Returns:
            新的降级级别，如果已经在最低级别则返回 None
        """
        if self._level_index < len(self._chain_order) - 1:
            self._level_index += 1
            self.current_level = self._chain_order[self._level_index]
            logger.info(f"[Degradation] 降级到 {self.current_level}")
            return self.get_current_level()
        logger.warning("[Degradation] 已达到最低级别 L5_CRAG，无法继续降级")
        return None
    
    def reset(self, level: str = "L1_FAST"):
        """重置降级链到指定级别"""
        if level in self._chain_order:
            self.current_level = level
            self._level_index = self._chain_order.index(level)
            logger.info(f"[Degradation] 重置到 {self.current_level}")
    
    def get_chain_info(self) -> Dict:
        """获取降级链完整信息"""
        return {
            "current_level": self.current_level,
            "chain_order": self._chain_order,
            "current_config": {
                "top_k": self.get_current_level().top_k,
                "timeout_ms": self.get_current_level().timeout_ms,
                "deep_search": self.get_current_level().deep_search,
                "multi_hop": self.get_current_level().multi_hop,
                "use_agent": self.get_current_level().use_agent,
            },
            "all_levels": {
                name: {
                    "top_k": level.top_k,
                    "timeout_ms": level.timeout_ms,
                    "deep_search": level.deep_search,
                    "multi_hop": level.multi_hop,
                    "use_agent": level.use_agent,
                    "description": level.description
                }
                for name, level in self.DEGRADATION_CONFIG.items()
            }
        }
    
    def should_degrade(self, result_confidence: float = 1.0, 
                        elapsed_ms: float = 0, 
                        error_occurred: bool = False) -> bool:
        """判断是否应该降级
        
        Args:
            result_confidence: 结果置信度 (0.0-1.0)
            elapsed_ms: 已用时间 (ms)
            error_occurred: 是否发生错误
        
        Returns:
            是否应该降级
        """
        if error_occurred:
            return True
        if result_confidence < 0.3:
            return True
        if elapsed_ms > self.get_current_level().timeout_ms:
            return True
        return False


# 模块级单例（向后兼容）
_default_chain = None

def get_degradation_chain() -> DegradationChain:
    """获取全局降级链单例"""
    global _default_chain
    if _default_chain is None:
        _default_chain = DegradationChain()
    return _default_chain
