"""
smart_llm.py - 智能LLM调用器

功能：
1. 智能路由：自动检测查询类型，选择最优模型
2. 自动降级：主模型失败自动切换备用模型
3. 结果校验：检测JSON schema返回空等异常
4. 统计监控：记录成功率、成本等指标
"""

import json
import logging
import asyncio
import sys
import time
from collections import OrderedDict
from typing import Optional, Dict, Any, AsyncGenerator
from dataclasses import dataclass

from .model_router import ModelRouter, QueryType, get_router
from .llm import _call_api, _call_api_stream
from ..config import MIMO_API_KEY, MIMO_BASE_URL, MIMO_TIMEOUT

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """LLM响应"""
    content: str
    model: str
    query_type: str
    fallback: bool
    success: bool
    tokens_used: int = 0
    error: Optional[str] = None


class SmartLLM:
    """智能LLM调用器（带自动降级）"""
    
    def __init__(self, router: Optional[ModelRouter] = None):
        self.router = router or get_router()
        self.max_retries = 2
        
        # 成本控制配置
        self.daily_limit = 10.0  # 每日限额（元）
        self.per_request_limit = 0.1  # 单次限额（元）
        
        # 缓存配置
        self.cache_enabled = True
        self.cache_ttl = 3600  # 缓存时间（秒）
        self.cache_max_memory = 50 * 1024 * 1024  # 50MB 内存上限
        self._cache: OrderedDict = OrderedDict()  # {key: (response, timestamp)}  LRU有序字典
        self._cache_memory_used = 0  # 当前缓存内存使用量（字节）
        
        # 缓存统计
        self._cache_hits = 0
        self._cache_misses = 0
        self._cache_evictions = 0
    
    def _estimate_size(self, obj) -> int:
        """估算对象内存大小"""
        return sys.getsizeof(obj)
    
    def _get_cache_key(self, messages: list, model: str) -> str:
        """生成缓存键"""
        # 简化：使用消息内容的hash作为缓存键
        import hashlib
        content = json.dumps(messages, sort_keys=True) + model
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[str]:
        """从缓存获取（LRU: 命中时移到末尾）"""
        if not self.cache_enabled:
            return None
        
        if cache_key in self._cache:
            response, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                # LRU: 命中时移到末尾
                self._cache.move_to_end(cache_key)
                self._cache_hits += 1
                logger.debug(f"缓存命中: {cache_key[:8]}...")
                return response
            else:
                # 缓存过期
                item_size = self._estimate_size(self._cache[cache_key])
                self._cache_memory_used = max(0, self._cache_memory_used - item_size)
                del self._cache[cache_key]
        
        self._cache_misses += 1
        return None
    
    def _set_cache(self, cache_key: str, response: str):
        """设置缓存（带LRU淘汰和50MB内存上限）"""
        if not self.cache_enabled:
            return
        
        entry = (response, time.time())
        entry_size = self._estimate_size(entry)
        
        # 如果单条就超过上限，不缓存
        if entry_size > self.cache_max_memory:
            logger.warning(f"单条缓存过大 ({entry_size} bytes)，跳过缓存")
            return
        
        # LRU淘汰：先清理过期条目
        self._cleanup_cache()
        
        # 如果加上新条目会超内存上限，持续淘汰最老的条目
        while (self._cache_memory_used + entry_size > self.cache_max_memory) and self._cache:
            oldest_key, oldest_value = self._cache.popitem(last=False)  # LRU: 淘汰最老的
            oldest_size = self._estimate_size(oldest_value)
            self._cache_memory_used = max(0, self._cache_memory_used - oldest_size)
            self._cache_evictions += 1
            logger.debug(f"LRU淘汰缓存: {oldest_key[:8]}... (释放 {oldest_size} bytes)")
        
        self._cache[cache_key] = entry
        self._cache_memory_used += entry_size
        
        # 额外安全阀：条目数上限10000
        while len(self._cache) > 10000:
            oldest_key, oldest_value = self._cache.popitem(last=False)
            oldest_size = self._estimate_size(oldest_value)
            self._cache_memory_used = max(0, self._cache_memory_used - oldest_size)
            self._cache_evictions += 1
    
    def _cleanup_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self._cache.items()
            if current_time - timestamp > self.cache_ttl
        ]
        for key in expired_keys:
            item_size = self._estimate_size(self._cache[key])
            self._cache_memory_used = max(0, self._cache_memory_used - item_size)
            del self._cache[key]
        if expired_keys:
            logger.debug(f"清理了 {len(expired_keys)} 条过期缓存")
    
    async def call(
        self,
        messages: list,
        query: str = "",
        context: Optional[Dict] = None,
        response_format: Optional[Dict] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        **kwargs
    ) -> LLMResponse:
        """
        智能调用LLM
        
        Args:
            messages: 消息列表
            query: 用户查询（用于路由判断）
            context: 上下文信息
            response_format: 响应格式（如JSON schema）
            max_tokens: 最大token数
            temperature: 温度参数
            **kwargs: 其他参数
        
        Returns:
            LLMResponse: 响应对象
        """
        # 选择主模型
        primary_model = self.router.select_model(query, context)
        query_type = self.router.detect_query_type(query, context)
        
        # 检查缓存
        cache_key = self._get_cache_key(messages, primary_model)
        cached_response = self._get_from_cache(cache_key)
        if cached_response:
            return LLMResponse(
                content=cached_response,
                model=primary_model,
                query_type=query_type.value,
                fallback=False,
                success=True,
            )
        
        # 尝试主模型
        result = await self._try_model(
            model=primary_model,
            messages=messages,
            response_format=response_format,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
        
        if result.success:
            self.router.record_success(primary_model, result.tokens_used)
            self._set_cache(cache_key, result.content)
            return LLMResponse(
                content=result.content,
                model=primary_model,
                query_type=query_type.value,
                fallback=False,
                success=True,
                tokens_used=result.tokens_used,
            )
        
        # 主模型失败，尝试降级
        logger.warning(f"主模型 {primary_model} 失败，尝试降级...")
        fallback_model = self.router.get_fallback_model(primary_model)
        
        result = await self._try_model(
            model=fallback_model,
            messages=messages,
            response_format=response_format,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
        
        if result.success:
            self.router.record_success(fallback_model, result.tokens_used)
            self._set_cache(cache_key, result.content)
            return LLMResponse(
                content=result.content,
                model=fallback_model,
                query_type=query_type.value,
                fallback=True,
                success=True,
                tokens_used=result.tokens_used,
            )
        
        # 两个模型都失败
        self.router.record_failure(fallback_model)
        logger.error(f"两个模型都失败: {primary_model}, {fallback_model}")
        
        return LLMResponse(
            content="抱歉，服务暂时不可用，请稍后重试。",
            model=fallback_model,
            query_type=query_type.value,
            fallback=True,
            success=False,
            error="所有模型都调用失败",
        )
    
    async def _try_model(
        self,
        model: str,
        messages: list,
        response_format: Optional[Dict] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        **kwargs
    ) -> LLMResponse:
        """尝试使用指定模型调用"""
        try:
            # 调用API
            response = await _call_api(
                base_url=MIMO_BASE_URL,
                api_key=MIMO_API_KEY,
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=MIMO_TIMEOUT,
            )
            
            # 检查响应是否有效
            if response and response.strip():
                return LLMResponse(
                    content=response,
                    model=model,
                    query_type="",
                    fallback=False,
                    success=True,
                )
            
            # JSON schema返回空的情况
            if response_format and not response:
                logger.warning(f"模型 {model} JSON schema返回空")
                return LLMResponse(
                    content="",
                    model=model,
                    query_type="",
                    fallback=False,
                    success=False,
                    error="JSON schema返回空",
                )
            
            return LLMResponse(
                content="",
                model=model,
                query_type="",
                fallback=False,
                success=False,
                error="空响应",
            )
            
        except Exception as e:
            logger.error(f"模型 {model} 调用失败: {e}")
            return LLMResponse(
                content="",
                model=model,
                query_type="",
                fallback=False,
                success=False,
                error=str(e),
            )
    
    async def call_stream(
        self,
        messages: list,
        query: str = "",
        context: Optional[Dict] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        流式调用LLM
        
        Args:
            messages: 消息列表
            query: 用户查询
            context: 上下文信息
            max_tokens: 最大token数
            temperature: 温度参数
            **kwargs: 其他参数
        
        Yields:
            str: 响应内容片段
        """
        # 选择模型
        model = self.router.select_model(query, context)
        
        try:
            async for chunk in _call_api_stream(
                base_url=MIMO_BASE_URL,
                api_key=MIMO_API_KEY,
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=MIMO_TIMEOUT,
            ):
                yield chunk
        except Exception as e:
            logger.error(f"流式调用失败: {e}")
            yield f"[错误: {e}]"
    
    def get_stats(self) -> Dict:
        """获取统计信息（包含缓存统计）"""
        stats = self.router.get_stats()
        stats["cache"] = self.get_cache_stats()
        return stats
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        total_requests = self._cache_hits + self._cache_misses
        return {
            "enabled": self.cache_enabled,
            "size": len(self._cache),
            "memory_used_bytes": self._cache_memory_used,
            "memory_used_mb": round(self._cache_memory_used / (1024 * 1024), 2),
            "memory_limit_mb": round(self.cache_max_memory / (1024 * 1024), 2),
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": round(self._cache_hits / total_requests * 100, 2) if total_requests > 0 else 0,
            "evictions": self._cache_evictions,
            "ttl_seconds": self.cache_ttl,
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self.router.reset_stats()


# 全局实例
_smart_llm: Optional[SmartLLM] = None


def get_smart_llm() -> SmartLLM:
    """获取全局SmartLLM实例"""
    global _smart_llm
    if _smart_llm is None:
        _smart_llm = SmartLLM()
    return _smart_llm


# 便捷函数
async def smart_call(
    query: str,
    system_prompt: Optional[str] = None,
    context: Optional[Dict] = None,
    response_format: Optional[Dict] = None,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> LLMResponse:
    """
    便捷的智能LLM调用函数
    
    Args:
        query: 用户查询
        system_prompt: 系统提示
        context: 上下文信息
        response_format: 响应格式
        max_tokens: 最大token数
        temperature: 温度参数
    
    Returns:
        LLMResponse: 响应对象
    """
    smart_llm = get_smart_llm()
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": query})
    
    return await smart_llm.call(
        messages=messages,
        query=query,
        context=context,
        response_format=response_format,
        max_tokens=max_tokens,
        temperature=temperature,
    )
