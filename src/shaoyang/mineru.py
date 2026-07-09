#!/usr/bin/env python3
"""v10.2: Replace MinerU CLI with RAG DataReader API (structured layout output)"""

import tempfile
import logging; logger = logging.getLogger(__name__)


def _extract_pdf_mineru(file_path):
    """PDF via MinerU RAG DataReader: structured layout -> rich Markdown
    
    Returns:
        Markdown with structure hints:
        - ## Heading (for titles)
        - ```
          |col1|col2| (for tables with LaTeX)
        - [Table: <md_path>] (for tables as markdown references)
        - ![Image](<path>) (for embedded images)
        - $$ formula $$ (for interline equations)
    """
    try:
        from magic_pdf.integrations.rag.api import DataReader
        
        with tempfile.TemporaryDirectory() as tmpdir:
            reader = DataReader(file_path, method='ocr', output_dir=tmpdir)
            doc = reader.get_document_result(0)
            if doc is None:
                raise RuntimeError("MinerU DataReader returned None")
            
            lines = []
            for page_reader in doc:
                page = page_reader.pagedata
                pi = page.page_info
                lines.append(f"\n--- Page {pi.page_no + 1} ---")
                
                for node in page_reader:
                    ct = node.category_type.value
                    text = (node.text or '').strip()
                    
                    if ct in ('title',):
                        lines.append(f"\n## {text}")
                    elif ct in ('text', 'image_caption', 'table_caption', 'table_footnote'):
                        if text:
                            lines.append(f"\n{text}")
                    elif ct == 'interline_equation':
                        latex = (node.latex or text).strip()
                        if latex:
                            lines.append(f"\n$$\n{latex}\n$$")
                    elif ct in ('image_body', 'image'):
                        img = node.image_path or ''
                        if img:
                            lines.append(f"\n![Image]({img})")
                    elif ct in ('table_body', 'table'):
                        latex = (node.latex or '').strip()
                        html = (node.html or '').strip()
                        if latex:
                            lines.append(f"\n```latex-table\n{latex}\n```")
                        elif html:
                            lines.append(f"\n```html-table\n{html}\n```")
                        elif text:
                            lines.append(f"\n```text-table\n{text}\n```")
                        else:
                            img = node.image_path or ''
                            if img:
                                lines.append(f"\n![Table]({img})")
            
            md = '\n'.join(lines).strip()
            if len(md) > 50:
                return md
    
    except Exception:  # TODO: Narrow exception type
        logger.warning(f"[mineru] suppressed exception", exc_info=True)
        pass
    
    # Fall back to original (pdfplumber + PyPDF2)
    import src.services.ingest as ingest
    if hasattr(ingest, '_original_extract_pdf_dual'):
        return ingest._original_extract_pdf_dual(file_path)
    return ""


def _extract_text_via_unstructured(file_path, ext=""):
    """Unstructured ETL for non-PDF formats"""
    try:
        from unstructured.partition.auto import partition
        elements = partition(filename=file_path)
        text = "\n\n".join(str(el) for el in elements if str(el).strip())
        if text and len(text.strip()) > 30:
            return text
    except Exception:  # TODO: Narrow exception type
        logger.warning(f"[mineru] suppressed exception", exc_info=True)
        pass
    return ""


def apply_patches():
    """Monkey-patch ingest module with MinerU RAG DataReader + Unstructured dual engine"""
    import src.services.ingest as ingest
    
    # Save originals (idempotent)
    if not hasattr(ingest, '_original_extract_pdf_dual'):
        ingest._original_extract_pdf_dual = ingest._extract_pdf_dual
        ingest._original_extract_text = ingest._extract_text
    
    # Replace PDF extraction with MinerU RAG DataReader
    ingest._extract_pdf_dual = _extract_pdf_mineru
    
    # Enhance text extraction: Unstructured first, then original
    original_extract_text = ingest._original_extract_text
    def enhanced_extract_text(file_path, ext):
        if ext == ".pdf":
            return _extract_pdf_mineru(file_path)
        result = _extract_text_via_unstructured(file_path, ext)
        if result:
            return result
        return original_extract_text(file_path, ext)
    ingest._extract_text = enhanced_extract_text
    
    logger.info("[伏羲·内世界] MinerU RAG DataReader + Unstructured dual engine activated (v10.2)")
