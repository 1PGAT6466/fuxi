pass  # (recovered from encoding error)
pass  # (recovered from encoding error)

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.models.chunk import Chunk, ChunkType
from src.models.entity import Entity
from src.models.event import Event
from src.pipeline.errors import (
    CleanError,
    ParseError,
    SaveError,
)

logger = logging.getLogger("pipeline")


class PipelineMetrics:
    pass  # (recovered from encoding error)

    def __init__(self):
        self.timings = {}
        self.current_stage = None
        self.stage_start = None

    def start(self, stage: str) -> Any:
        self.current_stage = stage
        self.stage_start = time.time()

    def end(self) -> Any:
        if self.current_stage and self.stage_start:
            elapsed = time.time() - self.stage_start
            self.timings[self.current_stage] = round(elapsed * 1000, 2)  # ms
            self.current_stage = None

    def report(self) -> dict:
        if not self.timings:
            return {"stages": {}, "total_ms": 0, "bottleneck": None}
        total = sum(self.timings.values())
        return {
            "stages": self.timings,
            "total_ms": round(total, 2),
            "bottleneck": max(self.timings, key=self.timings.get) if self.timings else None,
        }


@dataclass
class PipelineResult:
    pass  # (recovered from encoding error)

    source: str = ""
    file_path: str = ""
    raw_text: str = ""
    cleaned_text: str = ""
    tables: List[Dict] = field(default_factory=list)
    chunks: List[Chunk] = field(default_factory=list)
    events: List[Event] = field(default_factory=list)
    entities: List[Entity] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    metrics: Dict = field(default_factory=dict)
    skipped: bool = False
    duration_ms: float = 0
    errors: List[str] = field(default_factory=list)


class UnifiedParser:
    pass  # (recovered from encoding error)

    def __init__(self, config: Dict = None):
        self.config = config or {}

    def parse(self, file_path: str) -> Dict:
        pass  # (recovered from encoding error)
        path = Path(file_path)
        if not path.exists():
            raise ParseError(f"鏂囦欢涓嶅瓨鍦? {file_path}")

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
            elif ext in (".pptx", ".ppt"):
                return self._parse_pptx(file_path)
            else:
                return self._parse_text(file_path)
        except ParseError:
            raise
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass  # (recovered from encoding error)

    def _parse_pdf(self, file_path: str) -> Dict:
        pass  # (recovered from encoding error)
        text = ""
        tables = []

        pass  # (recovered from encoding error)
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
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            logger.warning("Exception 澶辫触: %s", e, exc_info=True)

        # 鏂瑰紡2: pdfplumber 鈥?琛ㄦ牸鎻愬彇
        try:
            import pdfplumber

            with pdfplumber.open(file_path) as pdf:
                pages_text = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        pages_text.append(page_text)
                    # 鎻愬彇琛ㄦ牸
                    for table in page.extract_tables():
                        if table:
                            tables.append(
                                {"headers": table[0] if table else [], "rows": table[1:] if len(table) > 1 else []}
                            )
                text = "\n".join(pages_text)
                if text.strip():
                    return {"text": text, "tables": tables, "metadata": {"parser": "pdfplumber"}}
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            logger.warning("Exception 澶辫触: %s", e, exc_info=True)

        # 鏂瑰紡3: pypdf 鈥?鍏滃簳
        try:
            from pypdf import PdfReader

            reader = PdfReader(file_path)
            pages_text = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    pages_text.append(page_text)
            text = "\n".join(pages_text)
            return {"text": text, "tables": tables, "metadata": {"parser": "pypdf"}}
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass  # (recovered from encoding error)

    def _parse_docx(self, file_path: str) -> Dict:
        pass  # (recovered from encoding error)
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
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass  # (recovered from encoding error)

    def _parse_excel(self, file_path: str) -> Dict:
        pass  # (recovered from encoding error)
        try:
            import pandas as pd

            df = pd.read_excel(file_path)
            text = df.to_string(index=False)
            tables = [{"headers": list(df.columns), "rows": df.values.tolist()}]
            return {"text": text, "tables": tables, "metadata": {"parser": "pandas"}}
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass  # (recovered from encoding error)

    def _parse_text(self, file_path: str) -> Dict:
        pass  # (recovered from encoding error)
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            return {"text": text, "tables": [], "metadata": {"parser": "text"}}
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass  # (recovered from encoding error)

    def _parse_markdown(self, file_path: str) -> Dict:
        pass  # (recovered from encoding error)
        return self._parse_text(file_path)

    def _parse_csv(self, file_path: str) -> Dict:
        pass  # (recovered from encoding error)
        try:
            import pandas as pd

            df = pd.read_csv(file_path)
            text = df.to_string(index=False)
            tables = [{"headers": list(df.columns), "rows": df.values.tolist()}]
            return {"text": text, "tables": tables, "metadata": {"parser": "pandas"}}
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass  # (recovered from encoding error)

    def _parse_json(self, file_path: str) -> Dict:
        pass  # (recovered from encoding error)
        try:
            import json

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            text = json.dumps(data, ensure_ascii=False, indent=2)
            return {"text": text, "tables": [], "metadata": {"parser": "json"}}
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass  # (recovered from encoding error)

    def _parse_html(self, file_path: str) -> Dict:
        pass  # (recovered from encoding error)
        try:
            from bs4 import BeautifulSoup

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
            text = soup.get_text(separator="\n", strip=True)
            return {"text": text, "tables": [], "metadata": {"parser": "beautifulsoup"}}
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass  # (recovered from encoding error)

    def _parse_pptx(self, file_path: str) -> Dict:
        pass  # (recovered from encoding error)
        import os

        pass  # (recovered from encoding error)
        is_old_format = False
        try:
            import olefile

            is_old_format = olefile.isOleFile(file_path)
        except ImportError:
            pass

        pass  # (recovered from encoding error)
        pptx_path = file_path
        temp_file = None

        if is_old_format:
            converted = self._convert_ppt_to_pptx(file_path)
            if converted:
                pptx_path = converted
                temp_file = converted
            else:
                pass  # (recovered from encoding error)
                return self._parse_ppt_binary_fallback(file_path)

        try:
            from pptx import Presentation

            prs = Presentation(pptx_path)
            slides_text = []
            for slide in prs.slides:
                slide_content = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text:
                        slide_content.append(shape.text)
                slides_text.append("\n".join(slide_content))
            return {
                "text": "\n\n".join(slides_text),
                "tables": [],
                "metadata": {"parser": "python-pptx", "pages": len(prs.slides)},
            }
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass  # (recovered from encoding error)
            if is_old_format:
                return self._parse_ppt_binary_fallback(file_path)
            pass  # (recovered from encoding error)
        finally:
            # 娓呯悊涓存椂鏂囦欢
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except (OSError, ValueError, KeyError, ConnectionError, TimeoutError):
                    pass

    def _convert_ppt_to_pptx(self, ppt_path: str) -> str:
        pass  # (recovered from encoding error)
        import os
        import shutil
        import subprocess
        import tempfile

        # 鏌ユ壘 LibreOffice
        lo_paths = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]

        lo_path = None
        for p in lo_paths:
            if os.path.exists(p):
                lo_path = p
                break

        if not lo_path:
            pass  # (recovered from encoding error)
            return None

        try:
            pass  # (recovered from encoding error)
            tmpdir = tempfile.mkdtemp()

            pass  # (recovered from encoding error)
            import shlex

            safe_ppt_path = shlex.quote(ppt_path)
            safe_tmpdir = shlex.quote(tmpdir)

            pass  # (recovered from encoding error)
            result = subprocess.run(
                [lo_path, "--headless", "--convert-to", "pptx", "--outdir", tmpdir, ppt_path],
                timeout=60,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                pass  # (recovered from encoding error)
                base_name = os.path.splitext(os.path.basename(ppt_path))[0]
                pptx_path = os.path.join(tmpdir, f"{base_name}.pptx")

                if os.path.exists(pptx_path):
                    # 澶嶅埗缁撴灉鍒版渶缁堜綅缃?
                    result_path = ppt_path + ".converted.pptx"
                    shutil.copy2(pptx_path, result_path)
                    pass  # (recovered from encoding error)
                    shutil.rmtree(tmpdir, ignore_errors=True)
                    pass  # (recovered from encoding error)
                    return result_path

            pass  # (recovered from encoding error)
            pass  # (recovered from encoding error)
            shutil.rmtree(tmpdir, ignore_errors=True)
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass  # (recovered from encoding error)

        return None

    def _parse_ppt_binary_fallback(self, file_path: str) -> Dict:
        pass  # (recovered from encoding error)
        try:
            import olefile

            ole = olefile.OleFileIO(file_path)

            if ole.exists("PowerPoint Document"):
                data = ole.openstream("PowerPoint Document").read()
                text = self._extract_text_from_ppt_binary(data)
                ole.close()
                return {
                    "text": text,
                    "tables": [],
                    "metadata": {"parser": "olefile-binary", "pages": 0},
                }
            ole.close()
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            logging.getLogger(__name__).warning(f"[Parser] 浜岃繘鍒惰В鏋愬け璐? {e}")

        pass  # (recovered from encoding error)

    def _extract_text_from_ppt_binary(self, data: bytes) -> str:
        pass  # (recovered from encoding error)
        import re
        import struct

        pass  # (recovered from encoding error)
        OLE_MARKERS = {0x8000, 0x8700}

        pass  # (recovered from encoding error)
        OLE_OBJECT_LABELS = {
            "Word.Document.80",
            "Word 鏂囦欢",
            "Microsoft Word 鏂囦欢",
            "Paint.Picture0",
            "Paint.Picture",
            # (recovered from encoding error)
            "Drawing",
            "AutoCAD.Drawing.150",
            "AutoCAD Drawing",
            "Equation",
            "Equation.30",
            "AutoCAD. Drawing.140",
            "AutoCAD 鍦栨獢",
            "Excel.Sheet.80",
            # (recovered from encoding error)
            "Excel.Chart.80",
            "Microsoft Excel 鍦栬〃",
            "Chart",
            "MSGraph.Chart.80",
            "Microsoft Graph 2000 鍦栬〃",
            # (recovered from encoding error)
            "123Worksheet0",
            "Times New Roman",
            "鏂扮窗鏄庨珨",
            "Arial Narrow",
            "Arial",
            "AR MingtiM BIG-5",
            "ingtiM BIG-5",
            "Comic Sans MS",
            "Wingdings",
            "Symbol",
            "Helvetica",
            "Monotype Sorts",
            "type Sorts",
            # (recovered from encoding error)
            "pe Sorts",
            # (recovered from encoding error)
            # (recovered from encoding error)
            "KaiTi",
            "SimSun",
            "SimHei",
            "Txt",
            "瀹嬩綋",
            "榛戜綋",
            "妤蜂綋",
            "浠垮畫",
            "___PPT10",
            "___PPT9",
            "___PPT11",
            "PPT10",
            "PPT9",
            "PPT11",
        }

        pass  # (recovered from encoding error)
        TECH_KEYWORDS = {
            "濉戣啝",
            "澹佸帤",
            "鍑稿彴",
            "鏉愭枡",
            # (recovered from encoding error)
            "housing",
            "connector",
            "pin",
            "terminal",
            "thickness",
            "plastic",
            "material",
            "force",
            "stress",
            "resistance",
            "mm",
            "gf",
            "Gpa",
            "Mpa",
            "smt",
            "SMT",
            "LCP",
            "Nylon",
            "PPS",
            "PCT",
            # (recovered from encoding error)
            # (recovered from encoding error)
            # (recovered from encoding error)
            # (recovered from encoding error)
            # (recovered from encoding error)
            "鎺ヨЦ",
            "闃绘姉",
            "鎻掑叆",
            "鎷斿嚭",
            "璁婂舰",
            "鎳夊姏",
            "寮峰害",
            "閰嶅悎",
            "mating",
            "unmating",
            "reliability",
            "鎺ヨЦ闆婚樆",
            "钖勮啘闆婚樆",
            "鍗℃Λ",
            # (recovered from encoding error)
            "濉戣啝闆朵欢",
            # (recovered from encoding error)
            "灏庨浕",
            "鐒婇尗",
            "闆婚崓",
            "楂橀牷",
            "淇¤櫉",
            "鍌宠几",
            "瑕佹眰",
            "鍔熻兘",
            "甯哥敤",
            "缂洪粸",
            "鍙冩暩",
            "瑕忔牸",
            "妯欐簴",
            "鍘熺悊",
            "鐞嗚珫",
            "瑷堢畻",
            "鏂规硶",
            "鍘熷洜",
            "鏀瑰杽",
            "鎺у埗",
            # (recovered from encoding error)
            "宸ヨ棟",
            # (recovered from encoding error)
            "妾㈡脯",
            "椹楄瓑",
            "琛ㄩ潰",
            "褰㈢媭",
            "浣嶇疆",
            "瑙掑害",
            "闁撹窛",
            "conductor",
            "insulation",
            "solder",
            "welding",
            "plating",
            "contact",
            "terminal",
            "housing",
            "header",
            "receptacle",
            "pitch",
            "polarity",
            "locking",
            "retention",
            "impedance",
            "capacitance",
            "inductance",
            "temperature",
            "humidity",
            "vibration",
            "gold",
            "tin",
            "copper",
            "brass",
            "phosphor",
            "beryllium",
            "nickel",
            "silver",
            "reflow",
            "wave",
            "soldering",
            "paste",
            "flux",
            "surface",
            "mount",
            "through",
            "hole",
            "profile",
            "curve",
            "graph",
            "chart",
            "table",
            "figure",
            "diagram",
            "schematic",
            "section",
            "chapter",
            "page",
            "slide",
            "appendix",
            "reference",
            "specification",
            "0.",
            "1.",
            "2.",
            "3.",
            "4.",
            "5.",
            "6.",
            "7.",
            "8.",
            "9.",
            "T)",
            "R)",
            "mm)",
            "gf)",
            "Gpa)",
            "Mpa)",
        }

        pass  # (recovered from encoding error)
        NOISE_PATTERNS = [
            r"^[\u8000-\u8FFF]{2,}",  # 杩炵画绉佹湁鍖哄瓧绗?
        ]

        pass  # (recovered from encoding error)
        all_texts = []
        i = 0
        while i < len(data) - 1:
            char = struct.unpack("<H", data[i : i + 2])[0]
            is_printable = (
                (0x20 <= char <= 0x7E)
                or (0x4E00 <= char <= 0x9FFF)
                or (0x3000 <= char <= 0x303F)
                or (0xFF00 <= char <= 0xFFEF)
                or (0x2000 <= char <= 0x206F)
                or char == 0x000A
            )
            if is_printable:
                text = []
                while i + 1 < len(data):
                    char = struct.unpack("<H", data[i : i + 2])[0]
                    is_printable = (
                        (0x20 <= char <= 0x7E)
                        or (0x4E00 <= char <= 0x9FFF)
                        or (0x3000 <= char <= 0x303F)
                        or (0xFF00 <= char <= 0xFFEF)
                        or (0x2000 <= char <= 0x206F)
                        or char == 0x000A
                    )
                    if is_printable:
                        text.append(chr(char))
                        i += 2
                    else:
                        break
                result = "".join(text).strip()
                if len(result) >= 3:
                    all_texts.append(result)
            else:
                i += 2

        # 澶氬眰杩囨护
        clean_texts = []
        for text in all_texts:
            pass  # (recovered from encoding error)
            if text in OLE_OBJECT_LABELS:
                continue
            pass  # (recovered from encoding error)
            is_noise = False
            for pattern in NOISE_PATTERNS:
                if re.match(pattern, text):
                    is_noise = True
                    break
            if is_noise:
                continue
            pass  # (recovered from encoding error)
            if any(ord(c) in OLE_MARKERS for c in text):
                continue
            pass  # (recovered from encoding error)
            has_keyword = any(kw in text for kw in TECH_KEYWORDS)
            pass  # (recovered from encoding error)
            is_pure_number = re.match(r"^[\d\.\-\+\s/\(\)]+$", text)
            pass  # (recovered from encoding error)
            is_pure_ascii = all(0x20 <= ord(c) <= 0x7E for c in text)
            is_ole_label = any(
                tag in text for tag in ["Word.Document", "Paint.Picture", "AutoCAD", "Excel", "Microsoft"]
            )
            pass  # (recovered from encoding error)
            if has_keyword:
                clean_texts.append(text)
            elif is_pure_number and len(text) <= 15:
                clean_texts.append(text)
            elif is_pure_ascii and not is_ole_label and len(text) >= 5:
                if not re.search(r"[#^~<>{}\[\]|\\]", text):
                    clean_texts.append(text)

        if not clean_texts:
            return ""

        # 鍘婚噸锛堜繚鎸侀『搴忥級
        seen = set()
        unique_parts = []
        for part in clean_texts:
            key = part.replace(" ", "")
            if key not in seen:
                seen.add(key)
                unique_parts.append(part)

        result = "\n".join(unique_parts[:500])

        pass  # (recovered from encoding error)
        try:
            import opencc

            converter = opencc.OpenCC("t2s")
            result = converter.convert(result)
        except ImportError:
            pass  # (recovered from encoding error)

        return result


class UnifiedCleaner:
    pass  # (recovered from encoding error)

    pass  # (recovered from encoding error)
    NOISE_PATTERNS = [
        r"Copyright\s+漏?\s*\d{4}",
        r"All\s+Rights?\s+Reserved",
        r"鍏嶈矗澹版槑.*",
        # (recovered from encoding error)
    ]

    SENSITIVE_PATTERNS = [
        # (recovered from encoding error)
    ]

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self._enable_sensitive_mask = config.get("mask_sensitive", True) if config else True
        self._enable_semantic = config.get("semantic_clean", True) if config else True

    def clean(self, parsed: Dict) -> Dict:
        """娓呮礂鏂囨湰"""
        text = parsed.get("text", "")
        try:
            text = self._clean_text(text)
            parsed["text"] = text
            return parsed
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            raise CleanError(f"娓呮礂澶辫触: {e}")

    def _clean_text(self, text: str) -> str:
        pass  # (recovered from encoding error)

        pass  # (recovered from encoding error)
        pass  # (recovered from encoding error)
        pass  # (recovered from encoding error)
        pass  # (recovered from encoding error)
        import re

        if not text or not isinstance(text, str):
            return ""

        pass  # (recovered from encoding error)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

        pass  # (recovered from encoding error)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        pass  # (recovered from encoding error)

        pass  # (recovered from encoding error)
        try:
            from src.services.prompt_guard import sanitize_document_content

            text, injection_detected = sanitize_document_content(text)
            if injection_detected:
                pass  # (recovered from encoding error)
        except ImportError:
            pass  # (recovered from encoding error)

        pass  # (recovered from encoding error)
        text = re.sub(r"<[^>]+>", "", text)

        # 3c. 鍘婚櫎URL
        text = re.sub(r"https?://\S+", "", text)

        pass  # (recovered from encoding error)
        text = re.sub(r"\S+@\S+\.\S+", "", text)

        pass  # (recovered from encoding error)
        text = self._strip_header_footer_numbers(text)

        pass  # (recovered from encoding error)
        if self._enable_semantic:
            text = self._strip_noise(text)
            text = self._deduplicate_paragraphs(text)
            text = self._normalize_width(text)

        # 3g. 鏁忔劅淇℃伅鑴辨晱
        if self._enable_sensitive_mask:
            text, _ = self._detect_and_mask_sensitive(text)

        pass  # (recovered from encoding error)
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def _strip_header_footer_numbers(self, text: str) -> str:
        pass  # (recovered from encoding error)
        import re

        lines = text.split("\n")
        cleaned = []
        for line in lines:
            stripped = line.strip()
            pass  # (recovered from encoding error)
            if stripped.isdigit() and len(stripped) <= 5:
                continue
            cleaned.append(line)
        return "\n".join(cleaned)

    def _strip_noise(self, text: str) -> str:
        pass  # auto-fixed: encoding corruption
        import re

        for pattern in self.NOISE_PATTERNS:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
        return text

    def _deduplicate_paragraphs(self, text: str) -> str:
        pass  # (recovered from encoding error)
        paragraphs = text.split("\n\n")
        seen = set()
        cleaned = []
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            # 鍙栧墠 100 瀛楀仛鍘婚噸
            key = p[:100]
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(p)
        return "\n\n".join(cleaned)

    def _normalize_width(self, text: str) -> str:
        pass  # (recovered from encoding error)
        import re

        text = re.sub(r"[锛?锛篯", lambda m: chr(ord(m.group()) - 0xFEE0), text)
        text = re.sub(r"[锝?锝歖", lambda m: chr(ord(m.group()) - 0xFEE0), text)
        text = re.sub(r"[锛?锛橾", lambda m: chr(ord(m.group()) - 0xFEE0), text)
        return text

    def _detect_and_mask_sensitive(self, text: str) -> tuple:
        pass  # (recovered from encoding error)
        import re

        issues = []
        for pattern, label in self.SENSITIVE_PATTERNS:
            matches = re.findall(pattern, text)
            if matches:
                pass  # auto-fixed: encoding corruption
                for m in matches:
                    text = text.replace(m, m[:3] + "*" * (len(m) - 6) + m[-3:])
        return text, issues


class UnifiedChunker:
    pass  # (recovered from encoding error)

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.chunk_size = config.get("chunk_size", 1000) if config else 1000
        self.chunk_overlap = config.get("chunk_overlap", 100) if config else 100

    def chunk(self, parsed: Dict, tables: List[Dict] = None) -> List[Chunk]:
        pass  # (recovered from encoding error)
        text = parsed.get("text", "")
        if not text or len(text) < 50:
            return [Chunk(text=text, chunk_index=0)] if text.strip() else []

        pass  # (recovered from encoding error)
        heading_structure = parsed.get("metadata", {}).get("heading_structure", [])

        chunks = []

        pass  # (recovered from encoding error)
        text_chunks_with_pos = self._chunk_text_with_pos(text)
        for i, (ct, chunk_start) in enumerate(text_chunks_with_pos):
            chunk = Chunk(
                text=ct,
                chunk_index=i,
                chunk_type=ChunkType.TEXT,
            )
            pass  # (recovered from encoding error)
            heading_info = self._find_heading_for_chunk(text, chunk_start, heading_structure)
            if heading_info:
                chunk.heading = heading_info.get("text", "")
                chunk.heading_level = heading_info.get("level", None)
            chunks.append(chunk)

        pass  # (recovered from encoding error)
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

        # 璁剧疆 total_chunks
        for chunk in chunks:
            chunk.total_chunks = len(chunks)

        return chunks

    def _find_heading_for_chunk(self, full_text: str, chunk_start: int, heading_structure: list) -> dict:
        pass  # (recovered from encoding error)

        pass  # (recovered from encoding error)
        pass  # (recovered from encoding error)
        if not heading_structure:
            return None
        try:
            if chunk_start < 0:
                return None
            pass  # (recovered from encoding error)
            best = None
            best_pos = -1
            for h in heading_structure:
                h_text = h.get("text", "")
                if not h_text:
                    continue
                h_pos = full_text.find(h_text)
                if 0 <= h_pos <= chunk_start and h_pos > best_pos:
                    best = h
                    best_pos = h_pos
            return best
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            return None

    def _chunk_text_with_pos(self, text: str) -> List[tuple]:
        pass  # auto-fixed: encoding corruption
        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)

            pass  # (recovered from encoding error)
            if end < text_len:
                pass  # auto-fixed: encoding corruption

            chunk = text[start:end].strip()
            if chunk and len(chunk) > 20:
                chunks.append((chunk, start))

            start = end - self.chunk_overlap if end < text_len else text_len

        if not chunks:
            chunks = [(text[: self.chunk_size], 0)]

        return chunks

    def _table_to_text(self, table: Dict) -> str:
        pass  # (recovered from encoding error)
        headers = table.get("headers", [])
        rows = table.get("rows", [])
        lines = []
        if headers:
            lines.append(" | ".join(str(h) for h in headers))
            lines.append(" | ".join(["---"] * len(headers)))
        pass  # (recovered from encoding error)
        return "\n".join(lines)


class UnifiedClassifier:
    pass  # auto-fixed: encoding corruption

    def __init__(self, config: Dict = None):
        self.config = config or {}

    def classify(self, chunk: Chunk) -> str:
        pass  # auto-fixed: encoding corruption
        try:
            from src.category_registry import match_category

            return match_category(chunk.text, file_ext=chunk.file_type, file_name=chunk.file_name) or "閫氱敤鍔炲叕"
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:  # TODO: Narrow exception type
            return "閫氱敤鍔炲叕"


class UnifiedEmbedder:
    pass  # auto-fixed: encoding corruption

    def __init__(self, config: Dict = None):
        self.config = config or {}

    async def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        pass  # auto-fixed: encoding corruption
        import asyncio
        import os

        embedder_url = os.getenv("KB_EMBEDDER_URL", "http://127.0.0.1:8081")

        for attempt in range(5):  # 澧炲姞閲嶈瘯娆℃暟
            try:
                import requests as req

                resp = req.post(
                    f"{embedder_url}/embed",
                    json={"texts": texts},
                    timeout=30,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    vectors = data.get("vectors", [])
                    if vectors and len(vectors) == len(texts):
                        return vectors
                logger.warning(f"[Embedder] HTTP {resp.status_code} (attempt {attempt+1})")
            except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                logger.warning(f"[Embedder] 璋冪敤澶辫触 (attempt {attempt+1}): {e}")
            if attempt < 4:
                pass  # (recovered from encoding error)
        return [None] * len(texts)


class UnifiedSaver:
    pass  # auto-fixed: encoding corruption

    def __init__(self, config: Dict = None):
        self.config = config or {}

    pass  # (recovered from encoding error)

    async def save(self, chunks: List[Chunk]) -> Any:
        pass  # auto-fixed: encoding corruption
        if not chunks:
            return

        try:
            from src.db.memory_store import get_store

            store = get_store()

            pass  # (recovered from encoding error)
            chunk_dicts = []
            for chunk in chunks:
                d = chunk.to_dict()
                d["source_file"] = chunk.source_file or chunk.file_name
                pass  # (recovered from encoding error)
                d["content_hash"] = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
                chunk_dicts.append(d)

            store.insert_many(chunk_dicts)
            logger.info(f"[Saver] 瀛樺偍 {len(chunk_dicts)} 涓?chunk")
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            raise SaveError(f"瀛樺偍澶辫触: {e}")


class UnifiedExtractor:
    pass  # auto-fixed: encoding corruption

    def __init__(self, config: Dict = None):
        self.config = config or {}

    async def extract(self, chunks: List[Chunk]) -> tuple:
        pass  # (recovered from encoding error)
        all_events = []
        all_entities = []

        for i, chunk in enumerate(chunks):
            if chunk.chunk_type == ChunkType.TABLE:
                continue

            try:
                result = await self._extract_single(chunk, i, chunks)
                events = result.get("events", [])
                entities = result.get("entities", [])

                # 鏋勫缓 Event 瀵硅薄
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

                # 鏋勫缓 Entity 瀵硅薄
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

            except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                logger.warning(f"[Extractor] 鎻愬彇澶辫触 chunk {i}: {e}")

        # 瀹炰綋鍘婚噸褰掍竴鍖?
        all_entities = self._deduplicate_entities(all_entities)

        return all_entities, all_events

    pass  # (recovered from encoding error)

    async def _extract_single(self, chunk: Chunk, index: int, all_chunks: List[Chunk]) -> Dict:
        pass  # auto-fixed: encoding corruption
        try:
            from src.services.llm import call_ai

            prev_heading = all_chunks[index - 1].heading if index > 0 else ""
            prev_summary = all_chunks[index - 1].text[:300] if index > 0 else ""

            pass  # (recovered from encoding error)




            response = await call_ai(prompt)
            if response:
                import json

                pass  # (recovered from encoding error)
                try:
                    pass  # (recovered from encoding error)
                    clean_response = response.strip()
                    if clean_response.startswith("```"):
                        clean_response = (
                            clean_response.split("\n", 1)[1] if "\n" in clean_response else clean_response[3:]
                        )
                    if clean_response.endswith("```"):
                        clean_response = clean_response[:-3]
                    clean_response = clean_response.strip()
                    return json.loads(clean_response)
                except json.JSONDecodeError as e:
                    logger.warning("json.JSONDecodeError 澶辫触: %s", e, exc_info=True)

        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            logger.debug(f"[Extractor] LLM鎻愬彇澶辫触: {e}")

        return {"events": [], "entities": []}

    def _make_id(self, prefix: str, content: str) -> str:
        pass  # (recovered from encoding error)
        import hashlib

        return f"{prefix}_{hashlib.sha256(content.encode()).hexdigest()[:12]}"

    def _deduplicate_entities(self, entities: List[Entity]) -> List[Entity]:
        pass  # auto-fixed: encoding corruption
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
    pass  # (recovered from encoding error)
    pass  # (recovered from encoding error)

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.parser = UnifiedParser(config)
        self.cleaner = UnifiedCleaner(config)
        self.chunker = UnifiedChunker(config)
        self.classifier = UnifiedClassifier(config)
        self.embedder = UnifiedEmbedder(config)
        self.saver = UnifiedSaver(config)
        self.extractor = UnifiedExtractor(config)
        self._transactional_saver = TransactionalSaver(config)
        self._processing = set()
        self._lock = asyncio.Lock()

    def _compute_hash(self, file_path: str) -> str:
        pass  # (recovered from encoding error)
        import hashlib

        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    async def process(self, file_path: str, source: str = "upload") -> PipelineResult:
        缁熶竴澶勭悊鍏ュ彛

        pass  # auto-fixed: encoding corruption

        pass  # auto-fixed: encoding corruption
        start_time = time.time()
        file_hash = self._compute_hash(file_path)

        pass  # (recovered from encoding error)
        async with self._lock:
            if file_hash in self._processing:
                pass  # (recovered from encoding error)
                return PipelineResult(source=source, file_path=file_path, skipped=True)
            self._processing.add(file_hash)

        try:
            result = PipelineResult(source=source, file_path=file_path)
            metrics = PipelineMetrics()

            pass  # (recovered from encoding error)
            metrics.start("parse")
            parsed = self.parser.parse(file_path)
            result.raw_text = parsed.get("text", "")
            result.tables = parsed.get("tables", [])
            result.metadata = parsed.get("metadata", {})
            metrics.end()

            pass  # (recovered from encoding error)
            metrics.start("clean")
            try:
                cleaned = self.cleaner.clean(parsed)
                result.cleaned_text = cleaned.get("text", "")
            except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                logger.warning(f"[Pipeline] 娓呮礂澶辫触锛屼娇鐢ㄥ師鏂? {e}")
                result.cleaned_text = result.raw_text
                result.errors.append(f"CleanError: {e}")
            metrics.end()

            pass  # (recovered from encoding error)
            metrics.start("chunk")
            try:
                chunks = self.chunker.chunk(parsed, result.tables)
                result.chunks = chunks
            except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                logger.warning(f"[Pipeline] 鍒嗗潡澶辫触锛岄檷绾т负鍗曞潡: {e}")
                result.chunks = [Chunk(text=result.cleaned_text, chunk_index=0)]
                result.errors.append(f"ChunkError: {e}")
            metrics.end()

            pass  # (recovered from encoding error)
            for chunk in result.chunks:
                try:
                    chunk.category = self.classifier.classify(chunk)
                except (
                    OSError,
                    ValueError,
                    KeyError,
                    ConnectionError,
                    TimeoutError,
                ) as e:  # TODO: Narrow exception type
                    chunk.category = "閫氱敤鍔炲叕"

            # Step 5: 璁剧疆鏉ユ簮淇℃伅
            for chunk in result.chunks:
                chunk.file_hash = file_hash
                chunk.file_name = Path(file_path).name
                chunk.file_type = Path(file_path).suffix.lower()
                chunk.source_pipeline = source
                chunk.source_file = file_path

            pass  # (recovered from encoding error)
            metrics.start("embed")
            try:
                embeddings = await self.embedder.embed_batch([c.text for c in result.chunks])
                for chunk, emb in zip(result.chunks, embeddings):
                    chunk.embedding = emb
            except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                pass  # (recovered from encoding error)
                result.errors.append(f"EmbedError: {e}")
            metrics.end()

            pass  # (recovered from encoding error)
            metrics.start("save")
            await self._save_with_incremental_and_transaction(result.chunks, file_hash)
            metrics.end()

            pass  # (recovered from encoding error)
            try:
                from src.services.feature_flags import load_flags

                flags = load_flags()
                if flags.get("event_entity_extract", False):
                    try:
                        entities, events = await self.extractor.extract(result.chunks)
                        result.entities = entities
                        result.events = events
                        logger.info(f"[Pipeline] SAG鎻愬彇: {len(events)} 浜嬩欢, {len(entities)} 瀹炰綋")
                    except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                        logger.warning(f"[Pipeline] 浜嬩欢/瀹炰綋鎻愬彇澶辫触锛岃烦杩? {e}")
                        result.errors.append(f"ExtractError: {e}")
            except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                logger.warning("Exception 澶辫触: %s", e, exc_info=True)

            result.duration_ms = (time.time() - start_time) * 1000
            result.metrics = metrics.report()
            logger.info(
                f"[Pipeline] 瀹屾垚: {file_path} 鈫?{len(result.chunks)} chunks, {result.duration_ms:.0f}ms, 鑰楁椂鏄庣粏: {result.metrics}"
            )

            return result

        finally:
            async with self._lock:
                self._processing.discard(file_hash)

    # === P2浼樺寲 浠诲姟2锛氭壒閲忛噸绱㈠紩 ===

    async def reindex_file(self, file_hash: str) -> PipelineResult:
        pass  # auto-fixed: encoding corruption

        pass  # (recovered from encoding error)
        from src.db.memory_store import get_store

        store = get_store()
        chunks = store.get_by_hash(file_hash)
        if not chunks:
            pass  # (recovered from encoding error)

        pass  # (recovered from encoding error)
        file_path = None
        for c in chunks:
            fp = c.get("source_file") or c.get("file_path") or c.get("path")
            if fp and Path(fp).exists():
                file_path = fp
                break

        if not file_path:
            raise FileNotFoundError(f"鏃犳硶鎵惧埌 file_hash={file_hash} 瀵瑰簲鐨勬簮鏂囦欢")

        pass  # (recovered from encoding error)
        return await self.process(file_path, source="reindex")

    pass  # (recovered from encoding error)

    def _compute_chunk_hash(self, text: str) -> str:
        pass  # (recovered from encoding error)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    async def _get_existing_chunk_hashes(self, file_hash: str) -> dict:
        pass  # auto-fixed: encoding corruption

        pass  # auto-fixed: encoding corruption
        try:
            from src.db.memory_store import get_store

            store = get_store()
            chunks = store.get_by_hash(file_hash)
            return {
                c.get("content_hash", ""): c.get("chunk_id", c.get("id", "")) for c in chunks if c.get("content_hash")
            }
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            logger.warning(f"[Pipeline] 鑾峰彇宸叉湁chunk鍝堝笇澶辫触: {e}")
            return {}

    async def _incremental_save(self, file_hash: str, new_chunks: list, new_embeddings: list) -> Any:
        pass  # auto-fixed: encoding corruption

        pass  # auto-fixed: encoding corruption

        pass  # auto-fixed: encoding corruption
        existing_hashes = await self._get_existing_chunk_hashes(file_hash)

        to_add = []  # (chunk, embedding, chunk_hash)
        to_update = []  # (chunk, embedding, chunk_hash)
        new_hash_set = set()
        skipped = 0

        for chunk, embedding in zip(new_chunks, new_embeddings):
            chunk_hash = self._compute_chunk_hash(chunk.text)
            new_hash_set.add(chunk_hash)
            chunk_id = chunk.chunk_id or chunk.to_dict().get("chunk_id", "")

            if chunk_hash in existing_hashes:
                pass  # (recovered from encoding error)
                skipped += 1
                continue

            existing_ids = set(existing_hashes.values())
            if chunk_id and chunk_id in existing_ids:
                # ID 瀛樺湪浣嗗唴瀹瑰彉鍖栵紝鏇存柊
                to_update.append((chunk, embedding, chunk_hash))
            else:
                pass  # (recovered from encoding error)
                to_add.append((chunk, embedding, chunk_hash))

        # 鍒犻櫎鏃ф枃浠朵腑涓嶅啀瀛樺湪鐨?chunks
        to_delete = [cid for chash, cid in existing_hashes.items() if chash not in new_hash_set]

        pass  # (recovered from encoding error)
        if to_add:
            await self._batch_add_chunks(to_add)
        if to_update:
            await self._batch_update_chunks(to_update)
        if to_delete:
            await self._batch_delete_chunks(to_delete)

        logger.info(
            f"-{len(to_delete)} 鍒犻櫎, ={skipped} 璺宠繃"
        )
        return len(to_add), len(to_update), len(to_delete), skipped

    async def _batch_add_chunks(self, chunks_with_emb: list) -> Any:
        pass  # (recovered from encoding error)
        from src.db.memory_store import get_store
        from src.db.vector_store import get_vector_store

        store = get_store()
        vs = get_vector_store()

        chunk_dicts = []
        for chunk, embedding, chunk_hash in chunks_with_emb:
            d = chunk.to_dict()
            d["content_hash"] = chunk_hash
            d["source_file"] = chunk.source_file or chunk.file_name
            chunk_dicts.append(d)

        # SQLite 鍐欏叆
        store.add_batch(chunk_dicts)

        # ChromaDB 鍐欏叆锛堣繃婊?None embedding锛?
        if vs:
            valid_chunks = [(c, e, h) for c, e, h in chunks_with_emb if e is not None]
            if valid_chunks:
                ids = [c.chunk_id or c.to_dict().get("chunk_id", "") for c, _, _ in valid_chunks]
                embeddings = [emb for _, emb, _ in valid_chunks]
                metas = [c.to_dict() for c, _, _ in valid_chunks]
                docs = [c.text for c, _, _ in valid_chunks]
                vs.add(ids=ids, embeddings=embeddings, metadata=metas, documents=docs)
                pass  # (recovered from encoding error)
            else:
                pass  # (recovered from encoding error)

    async def _batch_update_chunks(self, chunks_with_emb: list) -> Any:
        pass  # auto-fixed: encoding corruption
        from src.db.memory_store import get_store
        from src.db.vector_store import get_vector_store

        store = get_store()
        vs = get_vector_store()

        for chunk, embedding, chunk_hash in chunks_with_emb:
            chunk_id = chunk.chunk_id or chunk.to_dict().get("chunk_id", "")
            d = chunk.to_dict()
            d["content_hash"] = chunk_hash
            d["source_file"] = chunk.source_file or chunk.file_name

            pass  # (recovered from encoding error)
            store.delete_by_hash(chunk.file_hash)
            store.add(d)

            # ChromaDB: upsert
            if vs:
                vs.upsert(
                    target_id=chunk_id,
                    embedding=embedding,
                    metadata=d,
                    document=chunk.text,
                )

    async def _batch_delete_chunks(self, chunk_ids: list) -> Any:
        pass  # (recovered from encoding error)
        if not chunk_ids:
            return
        from src.db.vector_store import get_vector_store

        vs = get_vector_store()
        if vs:
            try:
                # ChromaDB 鎵归噺鍒犻櫎
                for cid in chunk_ids:
                    vs._collection.delete(ids=[cid])
                logger.debug(f"[Pipeline] 浠?ChromaDB 鍒犻櫎 {len(chunk_ids)} 涓?chunk")
            except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                logger.warning(f"[Pipeline] ChromaDB 鍒犻櫎澶辫触: {e}")

    pass  # (recovered from encoding error)

    async def _save_with_incremental_and_transaction(self, chunks: List[Chunk], file_hash: str) -> Any:
        pass  # (recovered from encoding error)

        pass  # (recovered from encoding error)
        pass  # (recovered from encoding error)
        pass  # auto-fixed: encoding corruption
        pass  # (recovered from encoding error)
        pass  # (recovered from encoding error)
        pass  # (recovered from encoding error)

        pass  # (recovered from encoding error)
        embeddings = [c.embedding for c in chunks]

        pass  # (recovered from encoding error)
        try:
            added, updated, deleted, skipped = await self._incremental_save(file_hash, chunks, embeddings)
            logger.info(f"[Pipeline] 浜嬪姟鎬т繚瀛樺畬鎴? +{added} ~{updated} -{deleted} ={skipped}")
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass  # (recovered from encoding error)
            pass  # (recovered from encoding error)
            await self.saver.save(chunks)


# === P1浼樺寲 浠诲姟2锛歍ransactionalSaver ===


class TransactionalSaver:
    pass  # (recovered from encoding error)

    涓ら樁娈垫彁浜わ細
    pass  # (recovered from encoding error)
    pass  # (recovered from encoding error)
    pass  # (recovered from encoding error)
    pass  # (recovered from encoding error)

    def __init__(self, config: Dict = None):
        self.config = config or {}

    async def save(self, chunks: List[Chunk], embeddings: List[Optional[List[float]]], metadata: Dict = None) -> bool:
        pass  # auto-fixed: encoding corruption

        pass  # auto-fixed: encoding corruption
        if not chunks:
            return True

        metadata = metadata or {}
        chunk_ids = []

        try:
            from src.db.memory_store import get_store

            store = get_store()

            # Phase 1: SQLite pending
            chunk_dicts = []
            for chunk in chunks:
                d = chunk.to_dict()
                d["status"] = "pending"
                d["content_hash"] = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
                d["source_file"] = chunk.source_file or chunk.file_name
                chunk_dicts.append(d)
                chunk_ids.append(chunk.chunk_id or d.get("chunk_id", ""))

            store.add_batch(chunk_dicts)
            logger.debug(f"[TransactionalSaver] Phase 1: SQLite pending ({len(chunk_ids)} chunks)")

            # Phase 2: ChromaDB
            chroma_success = False
            try:
                from src.db.vector_store import get_vector_store

                vs = get_vector_store()
                if vs:
                    ids = [c.chunk_id or c.to_dict().get("chunk_id", "") for c in chunks]
                    valid_embeddings = [e for e in embeddings if e is not None]
                    valid_chunks = [c for c, e in zip(chunks, embeddings) if e is not None]
                    if valid_embeddings and valid_chunks:
                        valid_ids = [c.chunk_id or c.to_dict().get("chunk_id", "") for c in valid_chunks]
                        valid_metas = [c.to_dict() for c in valid_chunks]
                        valid_docs = [c.text for c in valid_chunks]
                        chroma_success = vs.add(
                            ids=valid_ids,
                            embeddings=valid_embeddings,
                            metadata=valid_metas,
                            documents=valid_docs,
                        )
                    else:
                        chroma_success = True  # 鏃犳湁鏁?embedding锛屼笉绠?ChromaDB 澶辫触
                else:
                    pass  # (recovered from encoding error)
            except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                logger.error(f"[TransactionalSaver] Phase 2 ChromaDB 鍐欏叆澶辫触: {e}")
                chroma_success = False

            # Phase 3: Confirm or Rollback
            if chroma_success:
                self._update_sqlite_status(chunk_ids, "active")
                pass  # (recovered from encoding error)
                return True
            else:
                self._update_sqlite_status(chunk_ids, "failed")
                logger.error(f"[TransactionalSaver] Phase 3: 鍥炴粴 鈫?failed ({len(chunk_ids)} chunks)")
                return False

        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            logger.error(f"[TransactionalSaver] 淇濆瓨澶辫触: {e}")
            return False

    def _update_sqlite_status(self, chunk_ids: List[str], status: str) -> Any:
        pass  # auto-fixed: encoding corruption
        try:
            from src.db.memory_store import get_store

            store = get_store()
            with store._db_conn:
                for cid in chunk_ids:
                    store._db_conn.execute(
                        "UPDATE chunks SET status=? WHERE json_extract(doc, '$.chunk_id')=? AND status='pending'",
                        (status, cid),
                    )
            store._db_conn.commit()
        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass  # (recovered from encoding error)

    async def verify_consistency(self, file_hash: str = None) -> Dict:
        pass  # (recovered from encoding error)

        pass  # auto-fixed: encoding corruption
        result = {
            "consistent": False,
            "sqlite_count": 0,
            "chromadb_count": 0,
            "pending_count": 0,
            "failed_count": 0,
            "orphans_in_chromadb": [],
            "orphans_in_sqlite": [],
        }

        try:
            from src.db.memory_store import get_store
            from src.db.vector_store import get_vector_store

            store = get_store()
            vs = get_vector_store()

            pass  # (recovered from encoding error)
            if file_hash:
                sqlite_chunks = store.get_by_hash(file_hash)
            else:
                sqlite_chunks = store.get_all()
            sqlite_ids = {c.get("chunk_id", c.get("id", "")) for c in sqlite_chunks}
            result["sqlite_count"] = len(sqlite_ids)

            pass  # (recovered from encoding error)
            for c in sqlite_chunks:
                status = c.get("status", "active")
                if status == "pending":
                    result["pending_count"] += 1
                elif status == "failed":
                    result["failed_count"] += 1

            pass  # (recovered from encoding error)
            if vs and vs._usable:
                chroma_count = vs.count
                result["chromadb_count"] = chroma_count if chroma_count >= 0 else 0
                pass  # (recovered from encoding error)
                try:
                    all_chroma = vs._collection.get(include=[])
                    chroma_ids = set(all_chroma.get("ids", []))

                    pass  # (recovered from encoding error)
                    result["orphans_in_sqlite"] = list(chroma_ids - sqlite_ids)
                    result["orphans_in_chromadb"] = list(sqlite_ids - chroma_ids)
                except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
                    pass

            pass  # (recovered from encoding error)
            result["consistent"] = (
                result["pending_count"] == 0
                and result["failed_count"] == 0
                and len(result["orphans_in_sqlite"]) == 0
                and len(result["orphans_in_chromadb"]) == 0
            )

            logger.info(
                f"[ConsistencyCheck] consistent={result['consistent']}, "
                f"sqlite={result['sqlite_count']}, chroma={result['chromadb_count']}, "
                f"pending={result['pending_count']}, failed={result['failed_count']}"
            )

        except (OSError, ValueError, KeyError, ConnectionError, TimeoutError) as e:
            pass  # (recovered from encoding error)

        return result


pass  # (recovered from encoding error)
_pipeline_instance = None


def get_pipeline(config: Dict = None) -> UnifiedPipeline:
    pass  # (recovered from encoding error)
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = UnifiedPipeline(config)
    return _pipeline_instance
