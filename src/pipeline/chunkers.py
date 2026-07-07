"""
chunkers.py — 统一分块器
处理文本分块逻辑，支持表格感知。
"""
from typing import List, Dict

from src.models.chunk import Chunk, ChunkType


class UnifiedChunker:
    """统一分块器 — 表格感知"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.chunk_size = config.get("chunk_size", 1000) if config else 1000
        self.chunk_overlap = config.get("chunk_overlap", 100) if config else 100

    def chunk(self, parsed: Dict, tables: List[Dict] = None) -> List[Chunk]:
        """分块 — 表格独立存储，支持标题层级传播"""
        text = parsed.get("text", "")
        if not text or len(text) < 50:
            return [Chunk(text=text, chunk_index=0)] if text.strip() else []

        # 提取标题层级结构（来自 Markdown 解析）
        heading_structure = parsed.get("metadata", {}).get("heading_structure", [])

        chunks = []

        # 文本分块
        text_chunks = self._chunk_text(text)
        for i, ct in enumerate(text_chunks):
            chunk = Chunk(
                text=ct,
                chunk_index=i,
                chunk_type=ChunkType.TEXT,
            )
            # 传播标题层级：找到该 chunk 所归属的最近标题
            heading_info = self._find_heading_for_chunk(text, ct, heading_structure)
            if heading_info:
                chunk.heading = heading_info.get("text", "")
                chunk.heading_level = heading_info.get("level", None)
            chunks.append(chunk)

        # 表格独立存储
        if tables:
            for table in tables:
                if table.get("headers") or table.get("rows"):
                    chunk = Chunk(
                        text=self._table_to_text(table),
                        chunk_index=len(chunks),
                        chunk_type=ChunkType.TABLE,
                        structured_table=table,
                    )
                    chunks.append(chunk)

        # 设置 total_chunks
        for chunk in chunks:
            chunk.total_chunks = len(chunks)

        return chunks

    def _find_heading_for_chunk(self, full_text: str, chunk_text: str, heading_structure: list) -> dict:
        """找到该 chunk 所归属的最近标题"""
        if not heading_structure:
            return None
        try:
            chunk_start = full_text.find(chunk_text)
            if chunk_start < 0:
                return None
            # 遍历标题，找该位置之前最近的
            best = None
            for h in sorted(heading_structure, key=lambda x: full_text.find(x.get("text", "")), reverse=True):
                h_pos = full_text.find(h.get("text", ""))
                if 0 <= h_pos <= chunk_start:
                    best = h
                    break
            return best
        except Exception:
            pass  # 静默：Exception 失败,返回None
            return None

    def _chunk_text(self, text: str) -> List[str]:
        """文本分块"""
        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)

            # 尝试在句子边界断开
            if end < text_len:
                for sep in ['\n\n', '\n', '。', '；', '.', ';']:
                    last_sep = text.rfind(sep, start + self.chunk_size // 2, end)
                    if last_sep > start:
                        end = last_sep + len(sep)
                        break

            chunk = text[start:end].strip()
            if chunk and len(chunk) > 20:
                chunks.append(chunk)

            start = end - self.chunk_overlap if end < text_len else text_len

        return chunks if chunks else [text[:self.chunk_size]]

    def _table_to_text(self, table: Dict) -> str:
        """表格转文本"""
        headers = table.get("headers", [])
        rows = table.get("rows", [])
        lines = []
        if headers:
            lines.append(" | ".join(str(h) for h in headers))
            lines.append(" | ".join(["---"] * len(headers)))
        for row in rows[:50]:  # 最多50行
            lines.append(" | ".join(str(cell) for cell in row))
        return "\n".join(lines)
