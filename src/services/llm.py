"""

llm.py  LLM 调用服务（v1.44 MiMo 2.5 Pro + Fallback 链）

调用链：MiMo 2.5 Pro  DeepSeek  本地（逐级降级）

P1 优化：使用 httpx.AsyncClient 连接池替代 aiohttp，
  支持连接复用、keepalive 和最大连接数限制。

"""

import os, json, logging, asyncio

from typing import Optional, AsyncGenerator


try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    httpx = None
    _HTTPX_AVAILABLE = False


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


# ============ P1 优化: httpx 连接池 ============
# 使用 AsyncClient 替代 aiohttp，支持连接复用

_http_client: Optional["httpx.AsyncClient"] = None
_http_client_lock = asyncio.Lock()

# 连接池配置
HTTPX_MAX_KEEPALIVE = 5       # 最大 keep-alive 连接数
HTTPX_MAX_CONNECTIONS = 20    # 最大连接池大小
HTTPX_TIMEOUT_DEFAULT = 60.0  # 默认超时（秒）


async def _get_http_client() -> "httpx.AsyncClient":
    """获取共享的 httpx AsyncClient（懒初始化 + 连接池）"""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        async with _http_client_lock:
            if _http_client is None or _http_client.is_closed:
                if not _HTTPX_AVAILABLE:
                    raise ImportError("httpx 未安装，请执行: pip install httpx")
                _http_client = httpx.AsyncClient(
                    timeout=httpx.Timeout(HTTPX_TIMEOUT_DEFAULT),
                    limits=httpx.Limits(
                        max_keepalive_connections=HTTPX_MAX_KEEPALIVE,
                        max_connections=HTTPX_MAX_CONNECTIONS,
                    ),
                    http2=True,
                )
                logger.info(
                    f"[HTTP] httpx 客户端已初始化 "
                    f"(keepalive={HTTPX_MAX_KEEPALIVE}, connections={HTTPX_MAX_CONNECTIONS})"
                )
    return _http_client


async def close_http_client():
    """关闭 httpx 客户端（服务关闭时调用）"""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None
        logger.info("[HTTP] httpx 客户端已关闭")


async def _call_api(

    base_url: str, api_key: str, model: str,

    messages: list, max_tokens: int = 4096,

    temperature: float = 0.3, timeout: int = 60,

    stream: bool = False,

) -> Optional[str]:

    """通用 OpenAI 兼容 API 调用  带重试+逐次放大+空内容检测
    
    P1 优化：使用 httpx.AsyncClient 连接池替代 aiohttp，
    连接复用减少 TCP 握手开销。如 httpx 不可用则回退到 aiohttp。
    """

    # MiMo reasoning 模型：reasoning token 和 output token 共享 max_tokens 预算

    # 太小 = 思考完没空间输出，所以基础值设大

    base_max = max(max_tokens, 4096)

    use_httpx = _HTTPX_AVAILABLE

    if use_httpx:
        client = await _get_http_client()


    for attempt in range(3):

        current_max = base_max * (attempt + 1)  # 4096  8192  12288



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

            if use_httpx:
                # P1: 使用 httpx 连接池（连接复用）
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=timeout,
                )
                if resp.status_code != 200:
                    text = resp.text
                    logger.warning(f"API {base_url} {resp.status_code} (attempt {attempt+1}): {text[:200]}")
                    if attempt < 2:
                        await asyncio.sleep(1 * (attempt + 1))
                        continue
                    return None

                data = resp.json()
            else:
                # Fallback: aiohttp
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{base_url}/chat/completions",
                        json=payload, headers=headers,
                        timeout=aiohttp.ClientTimeout(total=timeout),
                    ) as aio_resp:
                        if aio_resp.status != 200:
                            text = await aio_resp.text()
                            logger.warning(f"API {base_url} {aio_resp.status} (attempt {attempt+1}): {text[:200]}")
                            if attempt < 2:
                                await asyncio.sleep(1 * (attempt + 1))
                                continue
                            return None

                        data = await aio_resp.json()


            msg = data["choices"][0]["message"]
            content = msg.get("content", "")
            reasoning = msg.get("reasoning_content", "")


            # 检查空内容

            if content and content.strip():
                return content


            # 思考了但没输出  max_tokens 不够，重试放大

            if reasoning and not content:
                logger.warning(f"MiMo attempt {attempt+1}: reasoning有({len(reasoning)}字)但content为空, max_tokens={current_max}, 重试...")
                if attempt < 2:
                    await asyncio.sleep(1 * (attempt + 1))
                    continue


            # 无 reasoning 也无 content  可能是 prompt 问题

            if not content:
                logger.warning(f"MiMo attempt {attempt+1}: 空响应, max_tokens={current_max}")
                if attempt < 2:
                    await asyncio.sleep(1 * (attempt + 1))
                    continue


            return content if content else None


        except Exception as e:

            logger.warning(f"API {base_url} attempt {attempt+1} 异常: {e}")

            if attempt < 2:

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

    LLM Fallback 链：MiMo 2.5 Pro  DeepSeek  空

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


# ============ 智能路由集成 ============

async def call_llm_smart(
    query: str,
    system_prompt: str = None,
    context: dict = None,
    response_format: dict = None,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    """
    智能LLM调用（带自动路由和降级）
    
    根据查询类型自动选择最优模型：
    - 简单对话 → mimo-v2.5-pro
    - 复杂JSON → mimo-v2.5
    - 知识问答 → mimo-v2.5-pro
    - 代码生成 → mimo-v2.5-pro
    
    Args:
        query: 用户查询
        system_prompt: 系统提示
        context: 上下文信息
        response_format: 响应格式（如JSON schema）
        max_tokens: 最大token数
        temperature: 温度参数
    
    Returns:
        str: 响应内容
    """
    from .smart_llm import get_smart_llm
    
    # 检查是否启用智能路由
    from ..config import SMART_ROUTER_ENABLED
    if not SMART_ROUTER_ENABLED:
        # 未启用，使用原有逻辑
        return await call_llm(query, system_prompt, max_tokens, temperature)
    
    smart_llm = get_smart_llm()
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": query})
    
    result = await smart_llm.call(
        messages=messages,
        query=query,
        context=context,
        response_format=response_format,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    
    return result.content if result.success else ""


async def call_llm_smart_stream(
    query: str,
    system_prompt: str = None,
    context: dict = None,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> AsyncGenerator[str, None]:
    """
    智能流式LLM调用
    
    Args:
        query: 用户查询
        system_prompt: 系统提示
        context: 上下文信息
        max_tokens: 最大token数
        temperature: 温度参数
    
    Yields:
        str: 响应内容片段
    """
    from .smart_llm import get_smart_llm
    
    # 检查是否启用智能路由
    from ..config import SMART_ROUTER_ENABLED
    if not SMART_ROUTER_ENABLED:
        # 未启用，使用原有逻辑
        async for chunk in call_llm_stream(query, system_prompt, max_tokens, temperature):
            yield chunk
        return
    
    smart_llm = get_smart_llm()
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": query})
    
    async for chunk in smart_llm.call_stream(
        messages=messages,
        query=query,
        context=context,
        max_tokens=max_tokens,
        temperature=temperature,
    ):
        yield chunk


def get_llm_stats() -> dict:
    """
    获取LLM统计信息
    
    Returns:
        dict: 统计信息
    """
    try:
        from .smart_llm import get_smart_llm
        return get_smart_llm().get_stats()
    except Exception:
        return {"error": "无法获取统计信息"}


def reset_llm_stats():
    """
    重置LLM统计信息
    """
    try:
        from .smart_llm import get_smart_llm
        get_smart_llm().reset_stats()
    except Exception:
        pass

