"""伏羲 AI API — 文本智能处理

提供以下端点：
- POST /api/ai/classify — 文本分类
- POST /api/ai/entities — 实体提取
- POST /api/ai/keywords — 关键词提取
- POST /api/ai/summarize — 文本摘要
- POST /api/ai/translate — 翻译
"""

import logging

from fastapi import APIRouter
from src.api.response import error, success

logger = logging.getLogger(__name__)
router = APIRouter()


async def _call_llm(prompt: str, max_tokens: int = 500) -> str:
    """调用 LLM 服务"""
    try:
        from src.services.llm import get_llm_service

        llm = get_llm_service()
        result = await llm.achat(prompt, max_tokens=max_tokens)
        return result.strip() if result else ""
    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        raise


@router.post("/api/ai/classify")
async def classify_text(body: dict):
    """文本分类"""
    try:
        text = body.get("text", "")
        if not text:
            return error(message="text 不能为空")

        prompt = f"请将以下文本分类到合适的类别中，只返回类别名称，不要其他内容：\n\n{text[:1000]}"
        result = await _call_llm(prompt)

        return success(data={"category": result}, message="分类完成")
    except Exception as e:
        return error(message=f"分类失败: {e}")


@router.post("/api/ai/entities")
async def extract_entities(body: dict):
    """实体提取"""
    try:
        text = body.get("text", "")
        if not text:
            return error(message="text 不能为空")

        prompt = f"""请从以下文本中提取所有命名实体（人名、地名、组织、产品、技术等）。
返回 JSON 数组格式，每个实体包含 text 和 type 字段。
只返回 JSON，不要其他内容。

文本：
{text[:2000]}"""
        result = await _call_llm(prompt, max_tokens=1000)

        import json

        try:
            entities = json.loads(result)
        except json.JSONDecodeError:
            entities = [{"text": result, "type": "unknown"}]

        return success(data={"entities": entities}, message="实体提取完成")
    except Exception as e:
        return error(message=f"实体提取失败: {e}")


@router.post("/api/ai/keywords")
async def extract_keywords(body: dict):
    """关键词提取"""
    try:
        text = body.get("text", "")
        top_k = body.get("top_k", 10)
        if not text:
            return error(message="text 不能为空")

        prompt = f"请从以下文本中提取 {top_k} 个关键词，用逗号分隔，只返回关键词：\n\n{text[:2000]}"
        result = await _call_llm(prompt)

        keywords = [kw.strip() for kw in result.split(",") if kw.strip()]

        return success(data={"keywords": keywords}, message="关键词提取完成")
    except Exception as e:
        return error(message=f"关键词提取失败: {e}")


@router.post("/api/ai/summarize")
async def summarize_text(body: dict):
    """文本摘要"""
    try:
        text = body.get("text", "")
        max_length = body.get("max_length", 200)
        if not text:
            return error(message="text 不能为空")

        prompt = f"请将以下文本总结为不超过 {max_length} 字的摘要：\n\n{text[:5000]}"
        result = await _call_llm(prompt, max_tokens=max_length)

        return success(data={"summary": result}, message="摘要完成")
    except Exception as e:
        return error(message=f"摘要失败: {e}")


@router.post("/api/ai/translate")
async def translate_text(body: dict):
    """翻译"""
    try:
        text = body.get("text", "")
        target_lang = body.get("target_lang", "en")
        if not text:
            return error(message="text 不能为空")

        lang_map = {"en": "英文", "zh": "中文", "ja": "日文", "ko": "韩文"}
        target_name = lang_map.get(target_lang, target_lang)

        prompt = f"请将以下文本翻译为{target_name}，只返回翻译结果：\n\n{text[:3000]}"
        result = await _call_llm(prompt, max_tokens=len(text) * 2)

        return success(data={"translated": result, "target_lang": target_lang}, message="翻译完成")
    except Exception as e:
        return error(message=f"翻译失败: {e}")
