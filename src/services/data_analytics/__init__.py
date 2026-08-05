"""
data_analytics — 数据分析服务
知识库数据分析、统计报表、趋势图生成
"""

from src.services.data_analytics.server import get_router, start_service, stop_service

__all__ = ["start_service", "stop_service", "get_router"]
