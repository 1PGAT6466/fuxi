"""
routes.py — AI智能工具服务 API 路由
FastAPI 路由：文本摘要、智能翻译、关键词提取、实体识别、健康检查
"""

import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("services.ai-tools.routes")

router = APIRouter(prefix="/api/ai", tags=["ai-tools"])

# ============ 请求模型 ============

class SummarizeRequest(BaseModel):
    text: str = Field(..., min_length=1, description="需要摘要的文本")
    max_length: int = Field(150, ge=50, le=2000, description="摘要最大长度（字）")


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="需要翻译的文本")
    source_lang: str = Field("zh", description="源语言代码")
    target_lang: str = Field("en", description="目标语言代码")


class KeywordsRequest(BaseModel):
    text: str = Field(..., min_length=1, description="需要提取关键词的文本")


class EntitiesRequest(BaseModel):
    text: str = Field(..., min_length=1, description="需要识别实体的文本")


class ClassifyRequest(BaseModel):
    text: str = Field(..., min_length=1, description="需要分类的文本")
    categories: Optional[list] = Field(None, description="自定义分类类别列表")


# ============ LLM 调用包装 ============

# 语言代码 → 语言名称映射
_LANG_MAP = {
    "zh": "中文", "en": "英语", "ja": "日语", "ko": "韩语",
    "fr": "法语", "de": "德语", "es": "西班牙语", "ru": "俄语",
    "pt": "葡萄牙语", "it": "意大利语", "ar": "阿拉伯语", "vi": "越南语",
    "th": "泰语", "id": "印尼语", "ms": "马来语", "zh-TW": "繁体中文",
}


def _get_lang_name(code: str) -> str:
    return _LANG_MAP.get(code, code)


async def _call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 2048, temperature: float = 0.3) -> str:
    """调用 LLM（优先 MiMo，自动 fallback）"""
    try:
        from src.services.llm import call_llm
        result = await call_llm(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return result or ""
    except Exception as e:
        logger.error(f"LLM 调用失败: {e}", exc_info=True)
        raise HTTPException(502, detail="AI 模型调用失败，请稍后重试")


def _parse_json_response(raw: str) -> dict | list | None:
    """鲁棒 JSON 解析，自动去除 Markdown 代码块"""
    if not raw:
        return None
    raw = re.sub(r"```(?:json)?\s*|```", "", raw).strip()
    raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", " ", raw)
    for _ in range(5):
        try:
            return json.loads(raw, strict=False)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("JSON 解析失败: %s", e, exc_info=True)
        for bracket, end_b in [('[', ']'), ('{', '}')]:
            s = raw.find(bracket)
            if s >= 0:
                e = raw.rfind(end_b) + 1
                if e > s:
                    raw = raw[s:e]
                    break
    return None


# ============ API 端点 ============

@router.get("/health")
def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "service": "ai-tools",
        "version": "1.0.0",
    }


@router.post("/summarize")
async def summarize(req: SummarizeRequest):
    """文本摘要 — 生成简洁摘要"""
    system_prompt = (
        "你是一个专业的文本摘要助手。请对用户提供的文本进行摘要，"
        "保留核心信息和关键数据，语言简洁明了。"
        "请直接返回摘要内容，不要添加额外的解释或标记。"
    )
    user_prompt = (
        f"请为以下文本生成摘要，摘要长度不超过{req.max_length}字：\n\n{req.text}"
    )

    result = await _call_llm(system_prompt, user_prompt, max_tokens=req.max_length * 2, temperature=0.3)
    return {
        "summary": result.strip(),
        "original_length": len(req.text),
        "summary_length": len(result),
    }


@router.post("/translate")
async def translate(req: TranslateRequest):
    """文本翻译 — 支持多语言互译"""
    source_name = _get_lang_name(req.source_lang)
    target_name = _get_lang_name(req.target_lang)

    system_prompt = (
        f"你是一个专业的翻译助手。请将用户提供的{source_name}文本翻译成{target_name}。"
        "翻译应当准确、自然、流畅，保持原文的语气和风格。"
        "请直接返回翻译结果，不要添加额外的解释或标记。"
    )
    user_prompt = f"请将以下文本从{source_name}翻译为{target_name}：\n\n{req.text}"

    result = await _call_llm(system_prompt, user_prompt, max_tokens=4096, temperature=0.2)
    return {
        "translation": result.strip(),
        "source_lang": req.source_lang,
        "target_lang": req.target_lang,
        "original_length": len(req.text),
    }


@router.post("/keywords")
async def extract_keywords(req: KeywordsRequest):
    """关键词提取 — 提取文本核心关键词"""
    system_prompt = (
        "你是一个专业的关键词提取助手。请从用户提供的文本中提取最重要的关键词和短语。"
        "请严格按照 JSON 格式返回结果：{\"keywords\": [\"关键词1\", \"关键词2\", ...]}。"
        "关键词按重要性排序，通常提取 5-15 个。只返回 JSON，不要添加其他内容。"
    )
    user_prompt = f"请提取以下文本的关键词：\n\n{req.text}"

    result = await _call_llm(system_prompt, user_prompt, max_tokens=1024, temperature=0.1)
    parsed = _parse_json_response(result)
    if parsed and isinstance(parsed, dict) and "keywords" in parsed:
        return {"keywords": parsed["keywords"], "count": len(parsed["keywords"])}
    # 回退：尝试按逗号/换行分割
    raw_keywords = [k.strip().strip('"').strip("'") for k in re.split(r'[,\n]', result) if k.strip()]
    return {"keywords": raw_keywords, "count": len(raw_keywords)}


@router.post("/entities")
async def extract_entities(req: EntitiesRequest):
    """实体识别 — 识别文本中的人名、地名、机构名等"""
    system_prompt = (
        "你是一个专业的命名实体识别（NER）助手。请从用户提供的文本中识别所有实体，"
        "包括人名（PERSON）、地名（LOCATION）、机构名（ORGANIZATION）、时间（TIME）、"
        "数量（QUANTITY）等。"
        "请严格按照 JSON 格式返回结果："
        "{\"entities\": [{\"name\": \"实体名\", \"type\": \"实体类型\", \"description\": \"简要说明\"}, ...]}。"
        "只返回 JSON，不要添加其他内容。"
    )
    user_prompt = f"请识别以下文本中的命名实体：\n\n{req.text}"

    result = await _call_llm(system_prompt, user_prompt, max_tokens=2048, temperature=0.1)
    parsed = _parse_json_response(result)
    if parsed and isinstance(parsed, dict) and "entities" in parsed:
        entities = parsed["entities"]
        # 类型统计
        type_counts = {}
        for e in entities:
            t = e.get("type", "UNKNOWN")
            type_counts[t] = type_counts.get(t, 0) + 1
        return {
            "entities": entities,
            "count": len(entities),
            "type_counts": type_counts,
        }
    return {"entities": [], "count": 0, "type_counts": {}, "raw_result": result}


@router.post("/classify")
async def classify_text(req: ClassifyRequest):
    """文本分类 — 将文本归入预定义或自定义类别"""
    if req.categories and len(req.categories) > 0:
        categories_str = "、".join(req.categories)
        categories_instruction = f"请从以下类别中选择最匹配的一个：{categories_str}"
    else:
        categories_str = "技术、商业、教育、法律、医疗、新闻、文学、娱乐、体育、科技"
        categories_instruction = f'请从以下通用类别中选择最匹配的一个（如都不匹配可返回\u201c其他\u201d）：{categories_str}'

    system_prompt = (
        "你是一个专业的文本分类助手。请根据文本内容判断其所属类别。"
        "请严格按照 JSON 格式返回结果："
        "{\"category\": \"类别名\", \"confidence\": 0.95, \"reason\": \"分类依据的简要说明\"}。"
        "只返回 JSON，不要添加其他内容。"
    )
    user_prompt = f"{categories_instruction}\n\n文本内容：\n{req.text}"

    result = await _call_llm(system_prompt, user_prompt, max_tokens=512, temperature=0.1)
    parsed = _parse_json_response(result)
    if parsed and isinstance(parsed, dict):
        return parsed
    return {"category": "未分类", "confidence": 0.0, "reason": "无法解析模型输出", "raw_result": result}
