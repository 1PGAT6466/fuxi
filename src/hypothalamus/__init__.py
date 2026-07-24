# hypothalamus/ — 下丘脑：伏羲的中枢神经系统
# [Bridge v2.1] 中枢调度已迁移到乾卦 qian.py（意识中枢）
#              IntentBus 替代 Meridian 经络
#              engine=v1 走旧版 Fuxi，engine=v2 走 QianGua
#
# v1.50 R4: 延迟导入防止循环依赖 — 仅在显式使用时才导入 Bridge
# 同时保留 backward-compat 的 Meridian/Brain 代理模块

# Meridian 已重构为 IntentBus，但保留兼容代理供旧测试使用
# 导入 Meridian 时实际获取 IntentBus 兼容实例
class Meridian:
    """v2.1 Bridge: Meridian → IntentBus 代理
    
    旧代码中 from src.hypothalamus.meridian import Meridian 仍然有效，
    但底层实现已切换到 IntentBus。
    """
    def __init__(self):
        from src.bagua.intent_bus import IntentBus
        self._bus = IntentBus()
        self._symbols = {}
        self._register_core_symbols()
    
    def _register_core_symbols(self):
        """注册核心四象符号"""
        self._symbols = {
            "taiyin": self._create_symbol("taiyin", "太阴·显化"),
            "shaoyin": self._create_symbol("shaoyin", "少阴·决策"),
            "shaoyang": self._create_symbol("shaoyang", "少阳·入库"),
            "taiyang": self._create_symbol("taiyang", "太阳·检索"),
        }
    
    def _create_symbol(self, symbol_id, name):
        """创建符号包装"""
        return _SymbolProxy(symbol_id, name, self._bus)
    
    def get_symbol(self, symbol_id):
        """获取指定符号"""
        return self._symbols.get(symbol_id)
    
    def register_symbol(self, symbol_id, instance):
        """注册符号"""
        self._symbols[symbol_id] = instance
    
    def send_signal(self, source, target, signal_type, payload=None):
        """发送信号（IntentBus 兼容）"""
        return self._bus.dispatch(source, target, signal_type, payload or {})


class _SymbolProxy:
    """符号代理 — 包装 IntentBus 中的卦为 Meridian 符号"""
    def __init__(self, symbol_id, name, bus):
        self.symbol_id = symbol_id
        self.name = name
        self._bus = bus
    
    async def think(self, query, history=None, trace_id=None):
        """思考接口（兼容旧 Brain.think）"""
        return await self._bus.route(symbol_id=self.symbol_id, query=query, 
                                      history=history or [], trace_id=trace_id)


# Signal 兼容类
class Signal:
    """信号协议兼容类"""
    def __init__(self, source="", target="", signal_type="", payload=None):
        self.source = source
        self.target = target
        self.signal_type = signal_type
        self.payload = payload or {}


class SignalPriority:
    """信号优先级枚举"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


# 延迟导入 Bridge（仅在使用时）
def _get_bridge_qian():
    try:
        from src.bagua.qian import QianGua
        return QianGua
    except ImportError:
        return None
