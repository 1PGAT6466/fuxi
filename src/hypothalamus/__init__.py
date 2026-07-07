# hypothalamus/ — 下丘脑：伏羲的中枢神经系统
# [Bridge v2.1] 中枢调度已迁移到乾卦 qian.py（意识中枢）
#              IntentBus 替代 Meridian 经络
#              engine=v1 走旧版 Fuxi，engine=v2 走 QianGua
from src.bagua.qian import QianGua as _BridgeQian
# TODO: migrate — meridian 逻辑待完全替换为 IntentBus
