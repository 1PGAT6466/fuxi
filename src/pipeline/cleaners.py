"""
cleaners.py — 统一清洗器
处理文本清洗逻辑。集成 chunker_quality.py 的语义清洗和敏感信息脱敏。
"""
import re
from typing import Dict, List, Tuple

from src.pipeline.errors import CleanError

# 来自 chunker_quality.py 的版权声明/免责声明正则
NOISE_PATTERNS = [
    r'版权归.*所有',
    r'Copyright\s+©?\s*\d{4}',
    r'All\s+Rights?\s+Reserved',
    r'未经许可.*不得.*(?:复制|转载|传播)',
    r'免责声明.*',
    r'以上内容仅供参考',
    r'本文件.*最终解释权',
    r'如.*侵权.*请联系',
    r'声明：.*不承担.*责任',
    r'温馨提示：.*投资有风险',
]

SENSITIVE_PATTERNS = [
    (r'1[3-9]\d{9}', '手机号'),
    (r'\d{17}[\dXx]', '身份证号'),
    (r'\d{16,19}', '银行卡号'),
]


class UnifiedCleaner:
    """统一清洗器 — 合并三套清洗逻辑 + chunker_quality 语义清洗"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self._enable_sensitive_mask = config.get("mask_sensitive", True) if config else True
        self._enable_semantic = config.get("semantic_clean", True) if config else True

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
        """统一清洗逻辑 — 包含语义清洗"""
        if not text or not isinstance(text, str):
            return ""

        # 1. 去除HTML标签
        text = re.sub(r'<[^>]+>', '', text)

        # 2. 去除URL
        text = re.sub(r'https?://\S+', '', text)

        # 3. 去除邮箱
        text = re.sub(r'\S+@\S+\.\S+', '', text)

        # 4. 去除页眉页脚（数字/页码）
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)

        # 5. 版权声明去除（来自 chunker_quality.py）
        if self._enable_semantic:
            text = self._strip_noise(text)
            text = self._deduplicate_paragraphs(text)
            text = self._normalize_width(text)

        # 6. 敏感信息脱敏（来自 chunker_quality.py）
        if self._enable_sensitive_mask:
            text, _ = self._detect_and_mask_sensitive(text)

        # 7. 去除控制字符
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

        # 8. 去除多余空白
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def _strip_noise(self, text: str) -> str:
        """去除版权/声明行"""
        for pattern in NOISE_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        return text

    def _deduplicate_paragraphs(self, text: str) -> str:
        """去除重复段落"""
        paragraphs = text.split('\n\n')
        seen = set()
        cleaned = []
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            # 取前 100 字做去重
            key = p[:100]
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(p)
        return '\n\n'.join(cleaned)

    def _normalize_width(self, text: str) -> str:
        """全角字母数字 → 半角"""
        text = re.sub(r'[Ａ-Ｚ]', lambda m: chr(ord(m.group()) - 0xFEE0), text)
        text = re.sub(r'[ａ-ｚ]', lambda m: chr(ord(m.group()) - 0xFEE0), text)
        text = re.sub(r'[０-９]', lambda m: chr(ord(m.group()) - 0xFEE0), text)
        return text

    def _detect_and_mask_sensitive(self, text: str) -> Tuple[str, List[str]]:
        """检测并脱敏敏感信息"""
        issues = []
        for pattern, label in SENSITIVE_PATTERNS:
            matches = re.findall(pattern, text)
            if matches:
                issues.append(f'发现 {len(matches)} 个{label}')
                for m in matches:
                    text = text.replace(m, m[:3] + '*' * (len(m) - 6) + m[-3:])
        return text, issues
