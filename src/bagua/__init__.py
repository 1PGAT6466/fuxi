"""
bagua — 伏羲八卦体系 v2.2

八卦架构入口模块。提供所有八卦子模块的导入桥接。

v2.2 变更:
  - GUA_NAME 统一为英文小写（"qian", "kun", "zhen", "xun", "kan", "li", "gen", "dui", "zhonggong"）
  - 各卦已完成核心能力迁移

八宫卦映射:
  ☰ qian (QianGua):   意识中枢 — 意图决策、调度协调
  ☷ kun  (KunGua):    知识库 — 向量存储、wiki、图谱
  ☳ zhen (ZhenGua):   数据消化 — 解析→清洗→分块→向量化→存储
  ☴ xun  (XunGua):    外部搜索 — Brave API、URL 抓取、本地向量检索
  ☵ kan  (KanGua):    质量控制 — 质量评分、免疫过滤、低质清理
  ☲ li   (LiGua):     知识蒸馏 — 关键词检索、内容蒸馏、摘要
  ☶ gen  (GenGua):    安全修复 — 断路器、异常嗅探、内容安全审核
  ☱ dui  (DuiGua):    对话交互 — 响应格式化、多轮对话、输出对齐
  ⊙ zhonggong (EvolutionGua): 自进化 — 反馈闭环、学习、进化
"""

from src.bagua.config.common_settings import get_meridian

# v2.2: 直接导出所有卦类（方便外部直接引用）
from src.bagua.qian import QianGua
from src.bagua.kun import KunGua
from src.bagua.zhen import ZhenGua
from src.bagua.xun import XunGua
from src.bagua.kan import KanGua
from src.bagua.li import LiGua
from src.bagua.gen import GenGua
from src.bagua.dui import DuiGua

__all__ = [
    "get_meridian",
    "QianGua",
    "KunGua",
    "ZhenGua",
    "XunGua",
    "KanGua",
    "LiGua",
    "GenGua",
    "DuiGua",
]
