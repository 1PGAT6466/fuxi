# src/taiyin/__init__.py
"""太阴·显化 — 对外接口中枢"""
# [Bridge v2.1] 安全功能桥接到艮卦 gen.py（稳定性/安全）
#            服务器功能桥接到兑卦 dui.py（对话与交互）
#
# v1.50 R4: 延迟导入防止循环依赖
# 仅在显式使用时才导入 Bridge

def _get_bridge_security():
    """延迟获取安全桥接"""
    try:
        from src.bagua.gen import GenGua
        return GenGua
    except ImportError:
        return None

def _get_bridge_server():
    """延迟获取服务器桥接"""
    try:
        from src.bagua.dui import DuiGua
        return DuiGua
    except ImportError:
        return None
