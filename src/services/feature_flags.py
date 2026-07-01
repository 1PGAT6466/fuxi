# 兼容层 - 重导出到新位置
from src.taiyin.flags import load_flags, set_flag, is_enabled, get_all_flags

DEFAULT_FLAGS = {
    "shaoyang_sag_extract": False,
    "taiyang_multi_hop": False,
    "taiyang_seed_score": False,
    "enhanced_pipeline": False,
}
