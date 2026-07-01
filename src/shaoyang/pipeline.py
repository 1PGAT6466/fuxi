"""
pipeline.py — 少阳·消化 统一处理管线
合并胃(解析)+脾(存储)+肺(呼吸)+小肠(分类)的能力
"""
import asyncio
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from src.models.chunk import Chunk, ChunkType
from src.models.event import Event
from src.models.entity import Entity
from src.infra.symbol_base import SymbolBase

logger = logging.getLogger("shaoyang.pipeline")


@dataclass
class PipelineResult:
    """管线处理结果"""
    source: str = ""
    file_path: str = ""
    raw_text: str = ""
    cleaned_text: str = ""
    tables: List[Dict] = field(default_factory=list)
    chunks: List[Chunk] = field(default_factory=list)
    events: List[Event] = field(default_factory=list)
    entities: List[Entity] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    skipped: bool = False
    duration_ms: float = 0
    errors: List[str] = field(default_factory=list)


class ShaoyangPipeline(SymbolBase):
    """少阳·消化 — 知识消化中枢"""

    def __init__(self, meridian):
        super().__init__(
            meridian=meridian,
            symbol_id="shaoyang",
            name="少阳·消化",
            emoji="🌱",
            description="知识消化中枢：文档进来 → 碎片 + 事件 + 实体出去"
        )
        self._processing = set()
        self._lock = asyncio.Lock()

    async def digest(self, file_path: str, source: str = "upload") -> PipelineResult:
        """统一处理入口"""
        start_time = time.time()
        self._set_status("processing")

        try:
            result = PipelineResult(source=source, file_path=file_path)

            # Step 1: 解析
            parsed = self._parse(file_path)
            result.raw_text = parsed.get("text", "")
            result.tables = parsed.get("tables", [])

            # Step 2: 清洗
            result.cleaned_text = self._clean(result.raw_text)

            # Step 3: 分块
            result.chunks = self._chunk(result.cleaned_text, result.tables)

            # Step 4: 分类
            for chunk in result.chunks:
                chunk.category = self._classify(chunk)

            # Step 5: 设置来源信息
            for chunk in result.chunks:
                chunk.file_hash = self._compute_hash(file_path)
                chunk.file_name = Path(file_path).name
                chunk.file_type = Path(file_path).suffix.lower()
                chunk.source_pipeline = source

            # Step 6: 向量化（如果 embedder 可用）
            await self._vectorize(result.chunks)

            # Step 7: 存储
            await self._save(result.chunks)

            result.duration_ms = (time.time() - start_time) * 1000
            logger.info(f"[少阳] 完成: {file_path} → {len(result.chunks)} chunks, {result.duration_ms:.0f}ms")

            return result

        except Exception as e:
            logger.error(f"[少阳] 处理失败: {file_path} → {e}")
            raise
        finally:
            self._set_status("idle")

    def _parse(self, file_path: str) -> Dict:
        """解析文件"""
        path = Path(file_path)
        ext = path.suffix.lower()

        try:
            if ext == ".pdf":
                return self._parse_pdf(file_path)
            elif ext in (".docx", ".doc"):
                return self._parse_docx(file_path)
            elif ext in (".xlsx", ".xls"):
                return self._parse_excel(file_path)
            elif ext == ".txt":
                return self._parse_text(file_path)
            elif ext == ".md":
                return self._parse_text(file_path)
            else:
                return self._parse_text(file_path)
        except Exception as e:
            raise Exception(f"解析失败 ({ext}): {e}")

    def _parse_pdf(self, file_path: str) -> Dict:
        """PDF 解析"""
        try:
            import fitz
            doc = fitz.open(file_path)
            pages_text = []
            for page in doc:
                pages_text.append(page.get_text())
            doc.close()
            return {"text": "\n".join(pages_text), "tables": [], "metadata": {"parser": "fitz"}}
        except Exception:
            return {"text": "", "tables": [], "metadata": {"parser": "none"}}

    def _parse_docx(self, file_path: str) -> Dict:
        """DOCX 解析"""
        try:
            from docx import Document
            doc = Document(file_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return {"text": "\n".join(paragraphs), "tables": [], "metadata": {"parser": "python-docx"}}
        except Exception:
            return {"text": "", "tables": [], "metadata": {"parser": "none"}}

    def _parse_excel(self, file_path: str) -> Dict:
        """Excel 解析"""
        try:
            import pandas as pd
            df = pd.read_excel(file_path)
            return {"text": df.to_string(index=False), "tables": [], "metadata": {"parser": "pandas"}}
        except Exception:
            return {"text": "", "tables": [], "metadata": {"parser": "none"}}

    def _parse_text(self, file_path: str) -> Dict:
        """纯文本解析"""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return {"text": f.read(), "tables": [], "metadata": {"parser": "text"}}
        except Exception:
            return {"text": "", "tables": [], "metadata": {"parser": "none"}}

    def _clean(self, text: str) -> str:
        """清洗文本"""
        import re
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _chunk(self, text: str, tables: List[Dict]) -> List[Chunk]:
        """分块"""
        if not text or len(text) < 50:
            return [Chunk(text=text, chunk_index=0)] if text.strip() else []

        chunks = []
        chunk_size = 1000
        overlap = 100
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + chunk_size, text_len)
            if end < text_len:
                for sep in ['\n\n', '\n', '。', '；', '.', ';']:
                    last_sep = text.rfind(sep, start + chunk_size // 2, end)
                    if last_sep > start:
                        end = last_sep + len(sep)
                        break

            chunk_text = text[start:end].strip()
            if chunk_text and len(chunk_text) > 20:
                chunks.append(Chunk(text=chunk_text, chunk_index=len(chunks)))

            start = end - overlap if end < text_len else text_len

        for chunk in chunks:
            chunk.total_chunks = len(chunks)

        return chunks

    def _classify(self, chunk: Chunk) -> str:
        """分类"""
        try:
            from src.category_registry import match_category
            return match_category(chunk.text, file_ext=chunk.file_type, file_name=chunk.file_name) or "通用办公"
        except Exception:
            return "通用办公"

    def _compute_hash(self, file_path: str) -> str:
        """计算文件哈希"""
        import hashlib
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    async def _vectorize(self, chunks: List[Chunk]):
        """向量化"""
        try:
            from src.db.vector_store import embed_texts
            embeddings = await embed_texts([c.text for c in chunks])
            if embeddings:
                for chunk, emb in zip(chunks, embeddings):
                    chunk.embedding = emb
        except Exception as e:
            logger.warning(f"[少阳] 向量化失败: {e}")

    async def _save(self, chunks: List[Chunk]):
        """存储"""
        try:
            from src.db.memory_store import get_store
            store = get_store()
            chunk_dicts = [c.to_dict() for c in chunks]
            store.insert_many(chunk_dicts)
            logger.info(f"[少阳] 存储 {len(chunk_dicts)} 个 chunk")
        except Exception as e:
            logger.error(f"[少阳] 存储失败: {e}")
            raise

    def _get_metrics(self) -> dict:
        """返回消化指标"""
        return {
            "stored_total": self._metrics.get("stored_total", 0),
            "wiki_pages": self._metrics.get("wiki_pages", 0),
        }
