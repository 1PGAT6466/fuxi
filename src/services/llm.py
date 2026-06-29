"""
llm.py — LLM 调用服务（v1.43 MiMo 2.5 Pro + Fallback 链）
调用链：MiMo 2.5 Pro → DeepSeek → 本地（逐级降级）
"""
import os, json, logging, asyncio
from typing import Optional, AsyncGenerator

logger = logging.getLogger(__name__)

# ============ MiMo API 配置 ============
from src.config import MIMO_API_KEY, MIMO_BASE_URL, MIMO_MODEL, MIMO_TIMEOUT

# ============ Fallback: DeepSeek ============
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-pro"
DEEPSEEK_TIMEOUT = 60

# ============ 缓存 ============
_ai_cache: dict = {}
_ai_cache_lock = asyncio.Lock()

# ============ 重试配置 ============
MAX_RETRIES = 2
RETRY_DELAY = 1.0


async def _call_api(
    base_url: str, api_key: str, model: str,
    messages: list, max_tokens: int = 4096,
    temperature: float = 0.3, timeout: int = 60,
    stream: bool = False,
) -> Optional[str]:
    """通用 OpenAI 兼容 API 调用 — 带重试+逐次放大+空内容检测"""
    import aiohttp

    # MiMo reasoning 模型：reasoning token 和 output token 共享 max_tokens 预算
    # 太小 = 思考完没空间输出，所以基础值设大
    base_max = max(max_tokens, 4096)

    for attempt in range(3):
        current_max = base_max * (attempt + 1)  # 4096 → 8192 → 12288

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": current_max,
            "temperature": temperature,
            "stream": stream,
            "enable_thinking": False,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/chat/completions",
                    json=payload, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.warning(f"API {base_url} {resp.status} (attempt {attempt+1}): {text[:200]}")
                        if attempt < 2:
                            import asyncio
                            await asyncio.sleep(1 * (attempt + 1))
                            continue
                        return None

                    data = await resp.json()
                    msg = data["choices"][0]["message"]
                    content = msg.get("content", "")
                    reasoning = msg.get("reasoning_content", "")

                    # 检查空内容
                    if content and content.strip():
                        return content

                    # 思考了但没输出 → max_tokens 不够，重试放大
                    if reasoning and not content:
                        logger.warning(f"MiMo attempt {attempt+1}: reasoning有({len(reasoning)}字)但content为空, max_tokens={current_max}, 重试...")
                        if attempt < 2:
                            import asyncio
                            await asyncio.sleep(1 * (attempt + 1))
                            continue

                    # 无 reasoning 也无 content → 可能是 prompt 问题
                    if not content:
                        logger.warning(f"MiMo attempt {attempt+1}: 空响应, max_tokens={current_max}")
                        if attempt < 2:
                            import asyncio
                            await asyncio.sleep(1 * (attempt + 1))
                            continue

                    return content if content else None

        except Exception as e:
            logger.warning(f"API {base_url} attempt {attempt+1} 异常: {e}")
            if attempt < 2:
                import asyncio
                await asyncio.sleep(2 * (attempt + 1))
                continue
            return None

    return None


async def _call_api_stream(
    base_url: str, api_key: str, model: str,
    messages: list, max_tokens: int = 2048,
    temperature: float = 0.3, timeout: int = 60,
) -> AsyncGenerator[str, None]:
    """通用流式 API 调用"""
    import aiohttp
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}/chat/completions",
                json=payload, headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status != 200:
                    yield f"[API Error {resp.status}]"
                    return
                async for line in resp.content:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            chunk = json.loads(line[6:])
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass
    except Exception as e:
        yield f"[Stream Error: {e}]"


# ============ Fallback 链 ============

async def call_llm(
    prompt: str, system_prompt: str = None, max_tokens: int = 2048,
    temperature: float = 0.3, model: str = None,
) -> str:
    """
    LLM Fallback 链：MiMo 2.5 Pro → DeepSeek → 空
    所有生成任务统一入口
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt[:8000]})

    # Level 1: MiMo 2.5 Pro
    for attempt in range(MAX_RETRIES):
        result = await _call_api(
            MIMO_BASE_URL, MIMO_API_KEY, model or MIMO_MODEL,
            messages, max_tokens, temperature, MIMO_TIMEOUT,
        )
        if result:
            logger.info(f"MiMo OK ({len(result)} chars)")
            return result
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(RETRY_DELAY)
    logger.warning("MiMo 失败，尝试 DeepSeek")

    # Level 2: DeepSeek
    if DEEPSEEK_API_KEY:
        result = await _call_api(
            DEEPSEEK_BASE_URL, DEEPSEEK_API_KEY, DEEPSEEK_MODEL,
            messages, max_tokens, temperature, DEEPSEEK_TIMEOUT,
        )
        if result:
            logger.info(f"DeepSeek fallback OK ({len(result)} chars)")
            return result
    logger.warning("DeepSeek 也失败")

    return ""




async def call_llm_fast(
    prompt: str, system_prompt: str = None, max_tokens: int = 500,
    temperature: float = 0.1,
) -> str:
    """轻量任务（分类/关键词提取/简单判断）用 MiMo-fast，成本低速度快"""
    return await call_llm(prompt, system_prompt, max_tokens, temperature, model="mimo-v2.5-turbo")

async def call_llm_stream(
    prompt: str, system_prompt: str = None, max_tokens: int = 2048,
    temperature: float = 0.3, model: str = None,
) -> AsyncGenerator[str, None]:
    """流式 Fallback 链"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt[:8000]})

    async for chunk in _call_api_stream(
        MIMO_BASE_URL, MIMO_API_KEY, model or MIMO_MODEL,
        messages, max_tokens, temperature, MIMO_TIMEOUT,
    ):
        yield chunk


# ============ 兼容旧接口 ============

async def call_ai_raw(prompt: str, max_tokens: int = 300) -> str:
    """兼容旧调用"""
    return await call_llm(prompt, max_tokens=max_tokens)


async def call_ai(prompt: str, max_tokens: int = 300) -> str:
    """兼容旧调用"""
    return await call_llm(prompt, max_tokens=max_tokens)


async def call_deepseek(
    prompt: str, system_prompt: str = None, max_tokens: int = 2048,
    temperature: float = 0.3, model: str = None,
) -> str:
    """兼容旧调用，重定向到 call_llm"""
    return await call_llm(prompt, system_prompt, max_tokens, temperature, model)


async def call_deepseek_stream(
    prompt: str, system_prompt: str = None, max_tokens: int = 2048,
    temperature: float = 0.3, model: str = None,
) -> AsyncGenerator[str, None]:
    """兼容旧流式调用"""
    async for chunk in call_llm_stream(prompt, system_prompt, max_tokens, temperature, model):
        yield chunk


async def call_ollama(prompt_text: str, model: str = None, max_tokens: int = 300) -> Optional[str]:
    """已弃用：重定向到 MiMo API"""
    return await call_llm(prompt_text, max_tokens=max_tokens)


async def call_ollama_stream(prompt_text: str) -> AsyncGenerator[str, None]:
    """已弃用：重定向到 MiMo 流式"""
    async for chunk in call_llm_stream(prompt_text):
        yield chunk


async def call_siliconflow(prompt: str, model: str = "") -> str:
    """SiliconFlow API 调用（用于特殊模型）"""
    sf_key = os.getenv("SILICONFLOW_API_KEY", "")
    sf_url = "https://api.siliconflow.cn/v1"
    sf_model = model or "Qwen/Qwen2.5-7B-Instruct"
    if not sf_key:
        return ""
    return await _call_api(sf_url, sf_key, sf_model, [{"role": "user", "content": prompt}], 500) or ""


async def call_siliconflow_stream(prompt: str, model: str = "") -> AsyncGenerator[str, None]:
    """SiliconFlow 流式"""
    sf_key = os.getenv("SILICONFLOW_API_KEY", "")
    sf_url = "https://api.siliconflow.cn/v1"
    sf_model = model or "Qwen/Qwen2.5-7B-Instruct"
    if not sf_key:
        yield "[SiliconFlow Key 未配置]"
        return
    async for chunk in _call_api_stream(sf_url, sf_key, sf_model, [{"role": "user", "content": prompt}]):
        yield chunk


async def call_mimo_async(query: str, sources: list, messages: list, api_key: str):
    """兼容旧调用"""
    answer = await call_llm(query, system_prompt="你是伏羲知识库助手", max_tokens=2048)
    if answer:
        async with _ai_cache_lock:
            _ai_cache[query] = answer


def get_cached_answer(query: str) -> Optional[str]:
    return _ai_cache.pop(query, None)
