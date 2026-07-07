# hypothalamus/balance/ — 伏羲平衡系统
# [DEPRECATION v2.1] balance/ 已废弃，功能已迁移至八卦体系 (bagua/)。
#   平衡/协调逻辑现已由乾卦(qian.py)的意识中枢 + IntentBus 调度实现。
#   本模块保留为归档，不再维护。
#
#   迁移映射：
#     - Meridian 经络 → IntentBus (bagua/intent_bus.py)
#     - 八卦协调 → 乾卦意图循环 (bagua/qian.py)
#     - 自愈逻辑 → 艮卦 (bagua/gen.py)

import warnings

warnings.warn(
    "src/hypothalamus/balance/ 已废弃 (v2.1)。"
    "平衡/协调逻辑已由八卦体系替代。"
    "请使用 src/bagua/qian.py (乾卦) + src/bagua/intent_bus.py (IntentBus)。",
    DeprecationWarning,
    stacklevel=2,
)
