"""
services/__init__.py — 兼容层
所有旧的 from src.services.xxx import yyy 仍然工作
四象重构后，这些 import 会重导出到新的位置
"""

# 少阳（消化）
from src.shaoyang.pipeline import ShaoyangPipeline

# 太阳（精炼）
from src.taiyang.retrieval import hybrid_search, TaiyangRetrieval

# 少阴（决策）
from src.shaoyin.brain import ShaoyinBrain

# 太阴（接口）
from src.taiyin.server import TaiyinServer
