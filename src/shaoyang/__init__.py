# src/shaoyang/__init__.py
"""少阳·消化 — 知识消化中枢"""
# [Bridge v2.1] 入口功能已桥接到震卦 zhen.py（文件消化管线）
from src.bagua.zhen import ZhenGua as _Bridge
from .pipeline import ShaoyangPipeline  # 保留旧入口兼容
# TODO: migrate — 完整消化管线逻辑待迁移到震卦
