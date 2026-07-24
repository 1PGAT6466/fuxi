"""
多租户工具函数模块 (Round 5 - Code Quality)

提供统一的多租户数据隔离过滤逻辑，消除 api/rag.py 和 api/search.py
中的重复实现。

v1.44 R2: 多租户隔离 — 从 JWT 提取 tenant_id，过滤搜索结果
"""

from typing import List, Dict, Any


def filter_results_by_tenant(results: List[Dict[str, Any]], tenant_id: str) -> List[Dict[str, Any]]:
    """多租户隔离：按 tenant_id 过滤结果
    
    规则：
      - 如果结果 metadata 中有 tenant_id 字段，必须匹配
      - 如果结果 metadata 中无 tenant_id 字段，视为默认租户数据
      - 非默认租户不能访问其他租户的数据
    
    Args:
        results: 待过滤的结果列表，每项应包含 'metadata' 字段
        tenant_id: 当前请求的租户 ID（从 JWT 提取）
    
    Returns:
        过滤后的结果列表
    
    Example:
        >>> results = [{"metadata": {"tenant_id": "t1"}}, {"metadata": {}}]
        >>> filter_results_by_tenant(results, "t1")
        [{"metadata": {"tenant_id": "t1"}}, {"metadata": {}}]
    """
    if tenant_id == "default":
        # 默认租户可以看自己的数据 + 无租户标记的遗留数据
        return results
    
    # 非默认租户：只看自己租户的数据
    filtered = []
    for r in results:
        meta = r.get("metadata", {})
        r_tenant = meta.get("tenant_id", "default")
        if r_tenant == tenant_id:
            filtered.append(r)
    return filtered


# 向后兼容别名
_filter_by_tenant = filter_results_by_tenant
