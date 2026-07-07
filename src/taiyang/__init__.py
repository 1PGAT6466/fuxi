# src/taiyang/__init__.py
"""太阳·筑基 — 精炼排序中枢"""
# [Bridge v2.1] 检索功能桥接到巽卦 xun.py（外部搜索）+ 坎卦 kan.py（精炼排序）
from src.bagua.xun import XunGua as _BridgeSearch
from src.bagua.kan import KanGua as _BridgeRerank
from .retrieval import hybrid_search, event_search  # 保留旧入口兼容
# TODO: migrate — 完整检索/排序逻辑待迁移到巽卦+坎卦

# Phase B 新增模块（伏羲检索架构融合）
# NOTE(F-1): 模块文件名为 entity_guided_recall（"recall" 体现数据面定位），
# 公开 API 函数名为 entity_guided_search（"search" 体现对外检索语义）。
# 两者命名来自不同抽象层次：recall=架构层、search=API 层。保留此命名差异作为架构文档化的有意设计。
from .entity_guided_recall import entity_guided_search, EntityGuidedRecall  # 任务 2
# 别名：entity_guided_recall 指向同一函数，供内部使用（架构层语义）
from .entity_guided_recall import entity_guided_search as entity_guided_recall
from .sag_pipeline import execute_sag_pipeline, SAGPipeline  # 任务 3
