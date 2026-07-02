"""P2.6 多模态转录 — A: 表格提取增强 + B: SiliconFlow 图片转录"""
import os, base64, json, requests, logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ============================================
# Part A: 表格提取增强
# ============================================

ENHANCED_TABLE_PROMPT = """将以下 PDF 表格数据转换为结构化的 Markdown 表格。要求：
1. 保留所有行列数据
2. 第一行作为表头
3. 数值保留原始精度
4. 空单元格用 - 表示

原始数据:
{raw_table}

Markdown 表格:"""

def enhance_table_extraction(page_text: str, tables: list) -> str:
    """A: 增强表格提取 — 从 pdfplumber 表格数据生成 Markdown 表格"""
    enhanced = page_text or ""
    
    for ti, table in enumerate(tables):
        if not table or len(table) < 2:
            continue
        
        # 过滤纯空行
        table = [row for row in table if any(c for c in row if c and str(c).strip())]
        if len(table) < 2:
            continue
        
        # 构建 Markdown 表格
        md_lines = []
        header = table[0]
        md_lines.append("| " + " | ".join(str(c) if c else "-" for c in header) + " |")
        md_lines.append("|" + "|".join("---" for _ in header) + "|")
        
        for row in table[1:]:
            cells = [str(c).replace("\n", " ").strip() if c else "-" for c in row]
            md_lines.append("| " + " | ".join(cells) + " |")
        
        table_md = f"\n\n### 📊 表格 {ti+1}\n\n" + "\n".join(md_lines) + "\n"
        enhanced += table_md
    
    return enhanced


# ============================================
# Part B: SiliconFlow 多模态图片转录
# ============================================

# SiliconFlow 配置（复用已有 API Key）
DEEPSEEK_BASE = "https://api.deepseek.com/v1"
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

# 多模态模型选择
VISION_MODEL = "Qwen/Qwen3-VL-8B-Instruct"  # SiliconFlow VLM

IMAGE_TRANSCRIPT_PROMPT = """你是一个专业的工程图纸/图表分析助手。请分析这张图片，用中文描述以下内容：

1. **图片类型**：机械图纸 / 电气原理图 / 流程图 / 数据图表 / 表格截图 / 其他
2. **关键信息**：提取所有可见的文字、数字、标注、尺寸
3. **结构描述**：描述图中的结构关系、流向、连接关系
4. **专业术语**：标注图中出现的专业术语（材料型号、零件编号、规格参数等）

要求：
- 50-200 字，简洁精准
- 使用专业术语
- 如果是 CAD 图纸，描述零件名称、材料、关键尺寸

图片描述:"""


def encode_image_base64(image_path: str) -> Optional[str]:
    """将图片编码为 base64"""
    try:
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"图片编码失败: {image_path} — {e}")
        return None


def transcribe_image(image_path: str, api_key: str = None) -> Optional[str]:
    """B: 使用 SiliconFlow 多模态模型转录图片为文字"""
    key = api_key or DEEPSEEK_KEY
    if not key:
        logger.warning("SiliconFlow API Key 未配置，跳过图片转录")
        return None
    
    b64 = encode_image_base64(image_path)
    if not b64:
        return None
    
    # 根据文件类型确定 MIME
    ext = os.path.splitext(image_path)[1].lower()
    mime_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', 
                '.webp': 'image/webp', '.bmp': 'image/bmp'}
    mime_type = mime_map.get(ext, 'image/png')
    
    payload = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
                    {"type": "text", "text": IMAGE_TRANSCRIPT_PROMPT},
                ]
            }
        ],
        "max_tokens": 500,
        "temperature": 0.1,
    }
    
    try:
        r = requests.post(
            f"{DEEPSEEK_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if r.status_code == 200:
            result = r.json()
            return result["choices"][0]["message"]["content"]
        else:
            logger.error(f"图片转录失败 HTTP {r.status_code}: {r.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"图片转录异常: {e}")
        return None


def transcribe_image_from_bytes(image_bytes: bytes, mime_type: str = "image/png", api_key: str = None) -> Optional[str]:
    """B: 从内存中的图片字节转录"""
    key = api_key or DEEPSEEK_KEY
    if not key:
        return None
    
    b64 = base64.b64encode(image_bytes).decode('utf-8')
    
    payload = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
                    {"type": "text", "text": IMAGE_TRANSCRIPT_PROMPT},
                ]
            }
        ],
        "max_tokens": 500,
        "temperature": 0.1,
    }
    
    try:
        r = requests.post(
            f"{DEEPSEEK_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        logger.error(f"图片转录失败 HTTP {r.status_code}")
        return None
    except Exception as e:
        logger.error(f"图片转录异常: {e}")
        return None


# ============================================
# 工具函数：增强 PDF 解析（表格 + 图片）
# ============================================

def enhance_pdf_extraction(file_path: str, extract_images: bool = False, api_key: str = None) -> str:
    """增强版 PDF 提取：表格 Markdown 化 + 图片转录"""
    text = ""
    
    # 先用 pdfplumber 提取文本和表格
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            page_texts = []
            for i, page in enumerate(pdf.pages):
                raw_text = page.extract_text() or ""
                tables = page.extract_tables() or []
                enhanced = enhance_table_extraction(raw_text, tables)
                page_texts.append(f"[Page {i+1}]\n{enhanced}")
            text = "\n\n".join(page_texts)
    except Exception as e:
        logger.warning(f"pdfplumber 提取失败: {e}")
        # 回退 PyMuPDF
        try:
            import fitz
            doc = fitz.open(file_path)
            page_texts = []
            for i in range(doc.page_count):
                page = doc[i]
                page_texts.append(f"[Page {i+1}]\n{page.get_text()}")
            doc.close()
            text = "\n\n".join(page_texts)
        except Exception:
            logger.warning(f"[multimodal] suppressed exception", exc_info=True)
            pass
    
    # 图片提取 + 转录（可选，需要 API Key）
    if extract_images and api_key:
        try:
            import fitz
            doc = fitz.open(file_path)
            image_descriptions = []
            for i in range(doc.page_count):
                page = doc[i]
                images = page.get_images(full=True)
                for j, img in enumerate(images[:3]):  # 每页最多 3 张
                    try:
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        if len(image_bytes) > 50 * 1024:  # 跳过 >50KB 的大图
                            continue
                        desc = transcribe_image_from_bytes(
                            image_bytes,
                            f"image/{base_image.get('ext', 'png')}",
                            api_key
                        )
                        if desc:
                            image_descriptions.append(f"[图片 P{i+1}-{j+1}]: {desc}")
                    except Exception:
                        logger.warning(f"[multimodal] suppressed exception", exc_info=True)
                        pass
            doc.close()
            if image_descriptions:
                text += "\n\n### 📷 图片转录\n\n" + "\n\n".join(image_descriptions)
        except Exception as e:
            logger.warning(f"图片提取失败: {e}")
    
    return text


# 初始化
print("P2.6 多模态转录模块已加载")
print("  A: enhance_table_extraction() — 表格→Markdown")
print("  B: transcribe_image() — 图片→文字 (需 SiliconFlow API Key)")
print("  C: enhance_pdf_extraction() — A+B 一体化")
