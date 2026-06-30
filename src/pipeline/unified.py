"""
unified.py — 伏羲统一处理管线
所有来源（上传/装载机/API）的数据，都经过这条管线。
"""
import asyncio
import hashlib
import logging
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from src.models.chunk import Chunk, ChunkType
from src.models.event import Event
from src.models.entity import Entity
from src.pipeline.errors import (
    PipelineError, ParseError, CleanError, ChunkError,
    EmbedError, SaveError, ExtractError
)

logger = logging.getLogger("pipeline")


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


class UnifiedParser:
    """统一解析器 — 合并 stomach.py + ingest.py 的解析逻辑"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

    def parse(self, file_path: str) -> Dict:
        """解析文件，返回 {text, tables, metadata}"""
        path = Path(file_path)
        if not path.exists():
            raise ParseError(f"文件不存在: {file_path}")

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
                return self._parse_markdown(file_path)
            elif ext == ".csv":
                return self._parse_csv(file_path)
            elif ext in (".json",):
                return self._parse_json(file_path)
            elif ext in (".html", ".htm"):
                return self._parse_html(file_path)
            else:
                return self._parse_text(file_path)
        except ParseError:
            raise
        except Exception as e:
            raise ParseError(f"解析失败 ({ext}): {e}")

    def _parse_pdf(self, file_path: str) -> Dict:
        """PDF 解析 — 合并 stomach.py + ingest.py 逻辑"""
        text = ""
        tables = []

        # 方式1: fitz (PyMuPDF) — 中文最优
        try:
            import fitz
            doc = fitz.open(file_path)
            pages_text = []
            for page in doc:
                pages_text.append(page.get_text())
            text = "\n".join(pages_text)
            doc.close()
            if text.strip():
                return {"text": text, "tables": tables, "metadata": {"parser": "fitz"}}
        except Exception:
            pass

        # 方式2: pdfplumber — 表格提取
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                pages_text = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        pages_text.append(page_text)
                    # 提取表格
                    for table in page.extract_tables():
                        if table:
                            tables.append({"headers": table[0] if table else [], "rows": table[1:] if len(table) > 1 else []})
                text = "\n".join(pages_text)
                if text.strip():
                    return {"text": text, "tables": tables, "metadata": {"parser": "pdfplumber"}}
        except Exception:
            pass

        # 方式3: PyPDF2 — 兜底
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            pages_text = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    pages_text.append(page_text)
            text = "\n".join(pages_text)
            return {"text": text, "tables": tables, "metadata": {"parser": "PyPDF2"}}
        except Exception as e:
            raise ParseError(f"PDF解析失败: {e}")

    def _parse_docx(self, file_path: str) -> Dict:
        """DOCX 解析"""
        try:
            from docx import Document
            doc = Document(file_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            tables = []
            for table in doc.tables:
                headers = [cell.text for cell in table.rows[0].cells] if table.rows else []
                rows = [[cell.text for cell in row.cells] for row in table.rows[1:]] if len(table.rows) > 1 else []
                tables.append({"headers": headers, "rows": rows})
            return {"text": "\n".join(paragraphs), "tables": tables, "metadata": {"parser": "python-docx"}}
        except Exception as e:
            raise ParseError(f"DOCX解析失败: {e}")

    def _parse_excel(self, file_path: str) -> Dict:
        """Excel 解析"""
        try:
            import pandas as pd
            df = pd.read_excel(file_path)
            text = df.to_string(index=False)
            tables = [{"headers": list(df.columns), "rows": df.values.tolist()}]
            return {"text": text, "tables": tables, "metadata": {"parser": "pandas"}}
        except Exception as e:
            raise ParseError(f"Excel解析失败: {e}")

    def _parse_text(self, file_path: str) -> Dict:
        """纯文本解析"""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            return {"text": text, "tables": [], "metadata": {"parser": "text"}}
        except Exception as e:
            raise ParseError(f"文本解析失败: {e}")

    def _parse_markdown(self, file_path: str) -> Dict:
        """Markdown 解析"""
        return self._parse_text(file_path)

    def _parse_csv(self, file_path: str) -> Dict:
        """CSV 解析"""
        try:
            import pandas as pd
            df = pd.read_csv(file_path)
            text = df.to_string(index=False)
            tables = [{"headers": list(df.columns), "rows": df.values.tolist()}]
            return {"text": text, "tables": tables, "metadata": {"parser": "pandas"}}
        except Exception as e:
            raise ParseError(f"CSV解析失败: {e}")

    def _parse_json(self, file_path: str) -> Dict:
        """JSON 解析"""
        try:
            import json
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            text = json.dumps(data, ensure_ascii=False, indent=2)
            return {"text": text, "tables": [], "metadata": {"parser": "json"}}
        except Exception as e:
            raise ParseError(f"JSON解析失败: {e}")

    def _parse_html(self, file_path: str) -> Dict:
        """HTML 解析"""
        try:
            from bs4 import BeautifulSoup
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
            text = soup.get_text(separator="\n", strip=True)
            return {"text": text, "tables": [], "metadata": {"parser": "beautifulsoup"}}
        except Exception as e:
            raise ParseError(f"HTML解析失败: {e}")


class UnifiedCleaner:
    """统一清洗器 — 合并三套清洗逻辑"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

    def clean(self, parsed: Dict) -> Dict:
        """清洗文本"""
        text = parsed.get("text", "")
        try:
            text = self._clean_text(text)
            parsed["text"] = text
            return parsed
        except Exception as e:
            raise CleanError(f"清洗失败: {e}")

    def _clean_text(self, text: str) -> str:
        """统一清洗逻辑"""
        import re

        # 去除HTML标签
        text = re.sub(r'<[^>]+>', '', text)

        # 去除URL
        text = re.sub(r'https?://\S+', '', text)

        # 去除邮箱
        text = re.sub(r'\S+@\S+\.\S+', '', text)

        # 去除页眉页脚（数字/页码）
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)

        # 去除多余空白
        text = re.sub(r'\s+', ' ', text)

        # 去除控制字符
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

        return text.strip()


class UnifiedChunker:
    """统一分块器 — 表格感知"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.chunk_size = config.get("chunk_size", 1000) if config else 1000
        self.chunk_overlap = config.get("chunk_overlap", 100) if config else 100

    def chunk(self, parsed: Dict, tables: List[Dict] = None) -> List[Chunk]:
        """分块 — 表格独立存储"""
        text = parsed.get("text", "")
        if not text or len(text) < 50:
            return [Chunk(text=text, chunk_index=0)] if text.strip() else []

        chunks = []

        # 文本分块
        text_chunks = self._chunk_text(text)
        for i, ct in enumerate(text_chunks):
            chunk = Chunk(
                text=ct,
                chunk_index=i,
                chunk_type=ChunkType.TEXT,
            )
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


class UnifiedClassifier:
    """统一分类器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

    def classify(self, chunk: Chunk) -> str:
        """分类"""
        try:
            from src.category_registry import match_category
            return match_category(chunk.text, file_ext=chunk.file_type, file_name=chunk.file_name) or "通用办公"
        except Exception:
            return "通用办公"


class UnifiedEmbedder:
    """统一向量化器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

    async def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """批量向量化"""
        try:
            from src.db.vector_store import embed_texts
            return await embed_texts(texts)
        except Exception as e:
            logger.warning(f"[Embedder] 向量化失败: {e}")
            return [None] * len(texts)


class UnifiedSaver:
    """统一存储器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

    async def save(self, chunks: List[Chunk]):
        """存储到 SQLite + ChromaDB"""
        if not chunks:
            return

        try:
            from src.db.memory_store import get_store
            store = get_store()

            # 转换为 dict 格式存储
            chunk_dicts = []
            for chunk in chunks:
                d = chunk.to_dict()
                d["source_file"] = chunk.source_file or chunk.file_name
                chunk_dicts.append(d)

            store.insert_many(chunk_dicts)
            logger.info(f"[Saver] 存储 {len(chunk_dicts)} 个 chunk")
        except Exception as e:
            raise SaveError(f"存储失败: {e}")


class UnifiedExtractor:
    """SAG 式事件/实体提取器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

    async def extract(self, chunks: List[Chunk]) -> tuple:
        """从碎片中提取事件和实体"""
        all_events = []
        all_entities = []

        for i, chunk in enumerate(chunks):
            if chunk.chunk_type == ChunkType.TABLE:
                continue

            try:
                result = await self._extract_single(chunk, i, chunks)
                events = result.get("events", [])
                entities = result.get("entities", [])

                # 构建 Event 对象
                for ev_data in events:
                    event = Event(
                        event_id=self._make_id("ev", ev_data.get("title", "") + chunk.chunk_id),
                        title=ev_data.get("title", ""),
                        summary=ev_data.get("summary", ""),
                        content=ev_data.get("content", ""),
                        keywords=ev_data.get("keywords", []),
                        priority=ev_data.get("priority", "UNKNOWN"),
                        references=ev_data.get("references", []),
                        chunk_ids=[chunk.chunk_id],
                        entity_names=ev_data.get("entities", []),
                        file_hash=chunk.file_hash,
                        file_name=chunk.file_name,
                        level=0,
                    )
                    all_events.append(event)

                # 构建 Entity 对象
                for ent_data in entities:
                    entity = Entity(
                        entity_id=self._make_id("ent", ent_data.get("name", "")),
                        name=ent_data.get("name", ""),
                        entity_type=ent_data.get("type", ""),
                        description=ent_data.get("description", ""),
                        chunk_ids=[chunk.chunk_id],
                        file_hash=chunk.file_hash,
                        file_name=chunk.file_name,
                    )
                    all_entities.append(entity)

            except Exception as e:
                logger.warning(f"[Extractor] 提取失败 chunk {i}: {e}")

        # 实体去重归一化
        all_entities = self._deduplicate_entities(all_entities)

        return all_entities, all_events

    async def _extract_single(self, chunk: Chunk, index: int, all_chunks: List[Chunk]) -> Dict:
        """单个 chunk 提取"""
        try:
            from src.services.llm import call_ai
            from src.services.security import sanitize_user_input

            prev_heading = all_chunks[index - 1].heading if index > 0 else ""
            prev_summary = all_chunks[index - 1].text[:300] if index > 0 else ""

            prompt = f"""从以下文本中提取事件和实体。

文件：{chunk.file_name}
分类：{chunk.category}
片段：第 {chunk.chunk_index + 1}/{chunk.total_chunks} 段
前文标题：{prev_heading}

文本：
{chunk.text[:2000]}

请返回JSON格式：
{{"events": [{{"title": "事项标题", "summary": "一句话摘要", "content": "完整内容", "keywords": ["关键词"], "priority": "HIGH/MEDIUM/LOW", "entities": ["实体名"], "references": [1]}}], "entities": [{{"name": "实体名", "type": "person/organization/product/material/device", "description": "作用描述"}}]}}"""

            response = await call_ai(prompt)
            if response:
                import json
                # 尝试解析JSON
                try:
                    # 清理响应中的markdown代码块标记
                    clean_response = response.strip()
                    if clean_response.startswith("```"):
                        clean_response = clean_response.split("\n", 1)[1] if "\n" in clean_response else clean_response[3:]
                    if clean_response.endswith("```"):
                        clean_response = clean_response[:-3]
                    clean_response = clean_response.strip()
                    return json.loads(clean_response)
                except json.JSONDecodeError:
                    pass

        except Exception as e:
            logger.debug(f"[Extractor] LLM提取失败: {e}")

        return {"events": [], "entities": []}

    def _make_id(self, prefix: str, content: str) -> str:
        """生成唯一ID"""
        import hashlib
        return f"{prefix}_{hashlib.md5(content.encode()).hexdigest()[:12]}"

    def _deduplicate_entities(self, entities: List[Entity]) -> List[Entity]:
        """实体去重归一化"""
        seen = {}
        for e in entities:
            key = e.name.lower().strip()
            if key in seen:
                seen[key].chunk_ids.extend(e.chunk_ids)
                seen[key].mentions += 1
                if e.description and not seen[key].description:
                    seen[key].description = e.description
            else:
                seen[key] = e
        return list(seen.values())


class UnifiedPipeline:
    """
    伏羲统一处理管线
    所有来源（上传/装载机/API）的数据，都经过这条管线。
    """

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.parser = UnifiedParser(config)
        self.cleaner = UnifiedCleaner(config)
        self.chunker = UnifiedChunker(config)
        self.classifier = UnifiedClassifier(config)
        self.embedder = UnifiedEmbedder(config)
        self.saver = UnifiedSaver(config)
        self.extractor = UnifiedExtractor(config)
        self._processing = set()
        self._lock = asyncio.Lock()

    def _compute_hash(self, file_path: str) -> str:
        """计算文件哈希"""
        import hashlib
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    async def process(self, file_path: str, source: str = "upload") -> PipelineResult:
        """
        统一处理入口

        Args:
            file_path: 文件路径
            source: 来源标识 ("upload" / "loader" / "api")

        Returns:
            PipelineResult: 包含 chunks/entities/events
        """
        start_time = time.time()
        file_hash = self._compute_hash(file_path)

        # 并发防护：同一文件不重复处理
        async with self._lock:
            if file_hash in self._processing:
                logger.info(f"[Pipeline] 文件正在处理中，跳过: {file_path}")
                return PipelineResult(source=source, file_path=file_path, skipped=True)
            self._processing.add(file_hash)

        try:
            result = PipelineResult(source=source, file_path=file_path)

            # Step 1: 解析（不可恢复 → 抛出）
            parsed = self.parser.parse(file_path)
            result.raw_text = parsed.get("text", "")
            result.tables = parsed.get("tables", [])
            result.metadata = parsed.get("metadata", {})

            # Step 2: 清洗（可恢复 → 降级为原文）
            try:
                cleaned = self.cleaner.clean(parsed)
                result.cleaned_text = cleaned.get("text", "")
            except Exception as e:
                logger.warning(f"[Pipeline] 清洗失败，使用原文: {e}")
                result.cleaned_text = result.raw_text
                result.errors.append(f"CleanError: {e}")

            # Step 3: 分块（可恢复 → 降级为单块）
            try:
                chunks = self.chunker.chunk(parsed, result.tables)
                result.chunks = chunks
            except Exception as e:
                logger.warning(f"[Pipeline] 分块失败，降级为单块: {e}")
                result.chunks = [Chunk(text=result.cleaned_text, chunk_index=0)]
                result.errors.append(f"ChunkError: {e}")

            # Step 4: 分类（可恢复 → 默认分类）
            for chunk in result.chunks:
                try:
                    chunk.category = self.classifier.classify(chunk)
                except Exception:
                    chunk.category = "通用办公"

            # Step 5: 设置来源信息
            for chunk in result.chunks:
                chunk.file_hash = file_hash
                chunk.file_name = Path(file_path).name
                chunk.file_type = Path(file_path).suffix.lower()
                chunk.source_pipeline = source
                chunk.source_file = file_path

            # Step 6: 向量化（可恢复 → 标记待补）
            try:
                embeddings = await self.embedder.embed_batch([c.text for c in result.chunks])
                for chunk, emb in zip(result.chunks, embeddings):
                    chunk.embedding = emb
            except Exception as e:
                logger.warning(f"[Pipeline] 向量化失败，标记待补: {e}")
                result.errors.append(f"EmbedError: {e}")

            # Step 7: 存储（不可恢复 → 抛出）
            await self.saver.save(result.chunks)

            # Step 8: SAG式提取（可选，可恢复 → 跳过）
            try:
                from src.services.feature_flags import load_flags
                flags = load_flags()
                if flags.get("event_entity_extract", False):
                    try:
                        entities, events = await self.extractor.extract(result.chunks)
                        result.entities = entities
                        result.events = events
                        logger.info(f"[Pipeline] SAG提取: {len(events)} 事件, {len(entities)} 实体")
                    except Exception as e:
                        logger.warning(f"[Pipeline] 事件/实体提取失败，跳过: {e}")
                        result.errors.append(f"ExtractError: {e}")
            except Exception:
                pass

            result.duration_ms = (time.time() - start_time) * 1000
            logger.info(f"[Pipeline] 完成: {file_path} → {len(result.chunks)} chunks, {result.duration_ms:.0f}ms")

            return result

        finally:
            async with self._lock:
                self._processing.discard(file_hash)


# 全局管线实例
_pipeline_instance = None

def get_pipeline(config: Dict = None) -> UnifiedPipeline:
    """获取全局管线实例"""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = UnifiedPipeline(config)
    return _pipeline_instance
