# PLACEHOLDER: 该服务模块预留扩展，当前无实际逻辑
# v1.50: 已迁移至 src.shaoyang.distiller，此文件仅为向后兼容层
# 新代码请直接使用 src.shaoyang.distiller 或 from src.services import ...
"""
services/distiller.py — 兼容层（保留：被 lung/signal_layer.py 引用）
v1.50 HIGH 修复：将 import * 改为显式导入。
"""
from src.shaoyang.distiller import (
    classify,
    distill_sync,
    distill_batch_async,
    save_batch,
    load_state,
    save_state,
    run_full_async,
    run_full,
    get_distill_state,
)
