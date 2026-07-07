# PLACEHOLDER: 该服务模块预留扩展，当前无实际逻辑
# v1.50: 已迁移至 src.taiyang.wiki，此文件仅为向后兼容层
# 新代码请直接使用 src.taiyang.wiki 或 from src.services import ...
"""
services/wiki.py — 兼容层（保留：被 sanjiao/signal_layer、spleen/signal_layer、agentic_rag_v2、integrated_search 引用）
v1.50 HIGH 修复：将 import * 改为显式导入。
"""
from src.taiyang.wiki import (
    WikiEngine,
    get_wiki_engine,
    sync_wiki_vectors,
)
