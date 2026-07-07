# hypothalamus/organs/  — 伏羲的各个器官智能体
# v1.42: 易理融合 — 先天为体·后天为用
# v1.50: 器官层从扁平 .py 迁移到 <organ>/signal_layer.py 分层结构。
#        旧版扁平的 <organ>.py 文件已标记 DEPRECATED，计划 v1.51 删除。
#        运行时实际生效的代码见各器官目录下的 signal_layer.py。
#
# [DEPRECATION v2.1] 器官层已废弃，功能已迁移至八卦体系 (bagua/)。
#   请使用 src/bagua/ 下的对应卦模块：
#     - 心(HeartAgent) → 坤卦 (bagua/kun.py)
#     - 肺(LungAgent)  → 震卦 (bagua/zhen.py)
#     - 肾(KidneyAgent) → 坎卦 (bagua/kan.py)
#     - 肝(LiverAgent)  → 坎卦 (bagua/kan.py)
#     - 脾(SpleenAgent)→ 坤卦 (bagua/kun.py)
#     - 鼻(NoseAgent)   → 艮卦 (bagua/gen.py)
#     - 皮肤(SkinAgent)→ 巽卦 (bagua/xun.py)
#   器官层保留为归档，不再维护。

import warnings
warnings.warn(
    "src/hypothalamus/organs/ 已废弃 (v2.1)。"
    "功能已迁移至八卦体系 (src/bagua/)。"
    "请使用对应卦模块。",
    DeprecationWarning,
    stacklevel=2,
)

from .organ_base import OrganBase, OrganMetadata, Element, PrenatalBagua, PostnatalBagua, Stem

def get_organ_stats(organ_id: str):
    # 兼容旧版 stats 查询
    return {}
