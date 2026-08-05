"""
报告生成模块 (Reporter Module)
================================
伏羲自运转 Phase 3：自动化报告生成
  - 日报：每天凌晨1点自动生成
  - 周报：每周一凌晨2点自动生成
  - 7维数据聚合：健康、请求、错误、资源、知识库、自修复、告警
  - 双格式输出：Markdown + HTML
  - 文件系统存储 + SQLite 索引

用法:
    from src.autonomous.reporter import ReportGenerator, get_report_generator

    generator = get_report_generator()
    result = await generator.generate("daily")
"""

from .aggregator import AggregatedData, DataAggregator
from .config import REPORT_DB_PATH, REPORT_DIR
from .generator import ReportGenerator, generate_daily_report, generate_weekly_report, get_report_generator
from .templates import ReportTemplate, get_template, list_templates

__all__ = [
    "ReportGenerator",
    "get_report_generator",
    "generate_daily_report",
    "generate_weekly_report",
    "DataAggregator",
    "AggregatedData",
    "ReportTemplate",
    "list_templates",
    "get_template",
    "REPORT_DIR",
    "REPORT_DB_PATH",
]
