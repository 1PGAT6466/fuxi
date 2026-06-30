"""
errors.py — Pipeline 错误码定义
"""


class PipelineError(Exception):
    """管线基础异常"""
    def __init__(self, code: str, message: str, recoverable: bool = True):
        self.code = code
        self.message = message
        self.recoverable = recoverable
        super().__init__(f"[{code}] {message}")


class ParseError(PipelineError):
    """解析失败 — 不可恢复"""
    def __init__(self, message: str):
        super().__init__("PARSE_ERROR", message, recoverable=False)


class CleanError(PipelineError):
    """清洗失败 — 可恢复"""
    def __init__(self, message: str):
        super().__init__("CLEAN_ERROR", message, recoverable=True)


class ChunkError(PipelineError):
    """分块失败 — 可恢复"""
    def __init__(self, message: str):
        super().__init__("CHUNK_ERROR", message, recoverable=True)


class EmbedError(PipelineError):
    """向量化失败 — 可恢复"""
    def __init__(self, message: str):
        super().__init__("EMBED_ERROR", message, recoverable=True)


class SaveError(PipelineError):
    """存储失败 — 不可恢复"""
    def __init__(self, message: str):
        super().__init__("SAVE_ERROR", message, recoverable=False)


class ExtractError(PipelineError):
    """事件/实体提取失败 — 可恢复"""
    def __init__(self, message: str):
        super().__init__("EXTRACT_ERROR", message, recoverable=True)
