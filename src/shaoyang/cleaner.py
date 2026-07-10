"""
cleaner.py — 少阳·文本清洗器
去噪/脱敏/格式化
"""
import re
import logging
from typing import str

logger = logging.getLogger("shaoyang.cleaner")


class TextCleaner:
    """文本清洗器"""

    def clean(self, text: str) -> str:
        """清洗文本 + Prompt Injection 净化"""
        if not text:
            return ""

        # v1.44 安全修复: Prompt Injection 净化
        try:
            from src.services.prompt_guard import sanitize_document_content
            text, injection_detected = sanitize_document_content(text)
            if injection_detected:
                logger.warning("[Security] 文档内容中检测到 Prompt Injection 模式，已净化")
        except ImportError:
            pass

        text = self._remove_html_tags(text)
        text = self._remove_urls(text)
        text = self._remove_emails(text)
        text = self._normalize_whitespace(text)
        text = self._remove_control_chars(text)
        return text.strip()

    def _remove_html_tags(self, text: str) -> str:
        return re.sub(r"<[^>]+>", "", text)

    def _remove_urls(self, text: str) -> str:
        return re.sub(r"https?://\S+", "", text)

    def _remove_emails(self, text: str) -> str:
        return re.sub(r"\S+@\S+\.\S+", "", text)

    def _normalize_whitespace(self, text: str) -> str:
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text

    def _remove_control_chars(self, text: str) -> str:
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
