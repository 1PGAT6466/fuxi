# src/shaoyang/__init__.py
"""少阳·消化 — 知识消化中枢

架构说明 (v2.2):
  本模块为少阳的旧入口层，核心消化逻辑已迁移到震卦 (bagua/zhen.py)。
  震卦的 ZhenGua.digest_and_store() 实现了完整的解析→清洗→分块→分类→
  向量化→存储→坤卦同步管线，并带有断路器降级矩阵。

  推荐的使用方式：
    from src.bagua.zhen import ZhenGua
    zhen = ZhenGua()
    zhen.start()
    result = zhen.digest_and_store("/path/to/file.pdf", store_in_kun=True)
    # 批量: result = zhen.batch_digest(["a.pdf", "b.docx"])

  旧代码使用 ShaoyangPipeline 仍可工作，但建议逐步迁移到 ZhenGua。
  差异对比：
    - ShaoyangPipeline: 继承 SymbolBase，依赖 meridian，无断路器
    - ZhenGua:         继承 GuaBase，独立断路器，完整降级矩阵
"""

# [Bridge v2.2] 入口功能已完全桥接到震卦 zhen.py（文件消化管线）
# ZhenGua 已具备完整的 digest_and_store() / batch_digest() 能力
from src.bagua.zhen import ZhenGua

# 别名：DigestBridge 用于代码中明确标识这是桥接
DigestBridge = ZhenGua

from .pipeline import ShaoyangPipeline  # 保留旧入口兼容（逐步废弃）

# 便捷桥接函数：使用震卦消化文件
def digest_file(file_path: str, store_in_kun: bool = True):
    """便捷函数：通过震卦消化单个文件（推荐替代 ShaoyangPipeline.digest()）

    Args:
        file_path: 文件路径
        store_in_kun: 是否同步存入坤卦知识库

    Returns:
        ZhenGua.digest_and_store() 的结果字典
    """
    zhen = ZhenGua()
    zhen.start()
    result = zhen.digest_and_store(file_path, store_in_kun=store_in_kun)
    zhen.stop()
    return result


def batch_digest_files(file_paths: list, store_in_kun: bool = True):
    """便捷函数：通过震卦批量消化文件

    Args:
        file_paths: 文件路径列表
        store_in_kun: 是否同步存入坤卦知识库

    Returns:
        ZhenGua.batch_digest() 的结果字典
    """
    zhen = ZhenGua()
    zhen.start()
    result = zhen.batch_digest(file_paths, store_in_kun=store_in_kun)
    zhen.stop()
    return result


__all__ = [
    "DigestBridge",
    "ShaoyangPipeline",
    "digest_file",
    "batch_digest_files",
]
