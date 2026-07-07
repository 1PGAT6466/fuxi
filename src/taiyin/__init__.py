# src/taiyin/__init__.py
"""太阴·显化 — 对外接口中枢"""
# [Bridge v2.1] 安全功能桥接到艮卦 gen.py（稳定性/安全）
#            服务器功能桥接到兑卦 dui.py（对话与交互）
from src.bagua.gen import GenGua as _BridgeSecurity
from src.bagua.dui import DuiGua as _BridgeServer
# TODO: migrate — 安全/服务端逻辑待迁移到艮卦+兑卦
