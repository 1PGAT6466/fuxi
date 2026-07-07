# src/shaoyin/__init__.py
"""少阴·炼化 — 决策合成中枢"""
# [Bridge v2.1] 推理/决策功能桥接到离卦 li.py（知识蒸馏与推理）
from src.bagua.li import LiGua as _Bridge
from .brain import ShaoyinBrain  # 保留旧入口兼容
# TODO: migrate — 完整推理/合成逻辑待迁移到离卦
