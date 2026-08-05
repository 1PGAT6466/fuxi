"""

llm.py  LLM 调用服务（v1.44 MiMo 2.5 Pro + Fallback 链）

调用链：MiMo 2.5 Pro  DeepSeek  本地（逐级降级）

P1 优化：
  - 使用 httpx.AsyncClient 连接池替代 aiohttp，支持连接复用、keepalive 和最大连接数限制
  - 检索质量评估与注入（call_llm context 参数）
  - LLM 输出后处理过滤（思考链、代码块提取）

"""

import os, json, logging, asyncio, re

from typing import Optional, AsyncGenerator, List


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
# v1.50: 添加缓存大小限制，防止内存泄漏
_AI_CACHE_MAX_SIZE = 200  # 最大缓存条数，超过时淘汰最早的条目
_ai_cache: dict = {}
_ai_cache_lock = asyncio.Lock()

# 缓存命中率统计
_cache_stats = {
    "hits": 0,
    "misses": 0,
    "total": 0,
}



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


    # 任务4 P0修复：全局开启 enable_thinking
    enable_thinking = True

    for attempt in range(3):

        # P2修复：max_tokens 固定递增而非翻倍（4096→6144→8192），减少浪费
        current_max = base_max + (attempt * 2048)



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

            "enable_thinking": enable_thinking,

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


            # v1.50 fix: reasoning模型返回reasoning_content而非content
            # 如果content为空但reasoning存在，使用reasoning作为回答

            if reasoning and reasoning.strip():
                logger.info(f"MiMo: content为空，使用reasoning_content ({len(reasoning)}字)")
                return reasoning


            # 无 reasoning 也无 content  可能是 prompt 问题

            if not content:
                logger.warning(f"MiMo attempt {attempt+1}: 空响应, max_tokens={current_max}")
                if attempt < 2:
                    await asyncio.sleep(1 * (attempt + 1))
                    continue


            return content if content else None


        except (ConnectionError, TimeoutError, OSError, ValueError, KeyError) as e:

            logger.warning(f"API {base_url} attempt {attempt+1} 异常: {type(e).__name__}: {e}")

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
    """通用流式 API 调用（P0修复：使用 httpx 连接池替代 aiohttp）"""
    import time as _time
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
        "enable_thinking": False,  # 流式禁用thinking，加速首字响应
    }
    _first_token_time = None
    _start_time = _time.time()
    _use_httpx = _HTTPX_AVAILABLE

    try:
        if _use_httpx:
            client = await _get_http_client()
            async with client.stream(
                "POST",
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=timeout,
            ) as resp:
                if resp.status_code != 200:
                    yield f"[API Error {resp.status_code}]"
                    return
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            chunk = json.loads(line[6:])
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                if _first_token_time is None:
                                    _first_token_time = _time.time()
                                    ftl = (_first_token_time - _start_time) * 1000
                                    logger.info(f"[Stream] 首字延迟: {ftl:.0f}ms")
                                yield delta["content"]
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass
        else:
            import aiohttp
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
                                    if _first_token_time is None:
                                        _first_token_time = _time.time()
                                        ftl = (_first_token_time - _start_time) * 1000
                                        logger.info(f"[Stream] 首字延迟: {ftl:.0f}ms")
                                    yield delta["content"]
                            except (json.JSONDecodeError, KeyError, IndexError):
                                pass
    except (ConnectionError, TimeoutError, OSError, ValueError) as e:
        yield f"[Stream Error: {type(e).__name__}: {e}]"

# ============ 后处理 & 工具函数 ============


def _post_process_llm_output(text: str, task_type: str = "general") -> str:
    """后处理LLM输出，过滤思考链等冗余内容"""
    import re

    # 1. 移除思考链标记（<thinking>...</thinking> 或 <reasoning>...</reasoning>）
    text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL)
    text = re.sub(r'<reasoning>.*?</reasoning>', '', text, flags=re.DOTALL)

    # 2. 移除大量重复的解释文字（代码生成场景）
    if task_type == "code":
        # 提取代码块，丢弃解释
        code_blocks = re.findall(r'```[\w]*\n(.*?)```', text, re.DOTALL)
        if code_blocks:
            return '\n\n'.join(code_blocks)

    return text.strip()


def _smart_truncate(text: str, max_len: int = 8000) -> str:
    """智能截断：保留首尾+中间关键段"""
    if len(text) <= max_len:
        return text

    # 首部 40%（通常包含问题和背景）
    head_len = int(max_len * 0.4)
    # 尾部 30%（通常包含结论和要求）
    tail_len = int(max_len * 0.3)
    # 中间 30%（关键段落）
    mid_len = max_len - head_len - tail_len

    head = text[:head_len]
    tail = text[-tail_len:]
    mid_start = head_len + (len(text) - max_len) // 2
    mid = text[mid_start:mid_start + mid_len]

    return head + "\n\n... [中间内容已省略] ...\n\n" + mid + "\n\n... [中间内容已省略] ...\n\n" + tail


# 检索质量提示模板（按评分等级）
_QUALITY_HINT_TEMPLATES = {
    "empty": (
        "[检索质量提示] 未找到相关参考资料，"
        "请基于你的知识回答，并明确说明不确定的部分。"
    ),
    "low": (
        "[检索质量提示] 检索到的相关资料较少，可能会影响回答的完整性。"
        "请基于有限信息回答问题；对于不确定的部分，请明确告知用户并给出参考建议。"
    ),
    "medium": (
        "[检索质量提示] 已检索到部分相关参考资料，请参考这些资料回答。"
        "如资料不足以覆盖用户问题，可结合你的知识补充说明。"
    ),
    "high": (
        "[检索质量提示] 已检索到丰富的参考资料，"
        "请基于以下资料详细、全面地回答用户问题。"
    ),
}


def _inject_quality_hint(query_text: str, context: str) -> str:
    """
    根据检索上下文评估质量并返回对应的提示信息。

    评分基于两个维度：
      - 长度：context 的字符数（<200/200-1000/>1000）
      - 密度：有效段落数（1/2-5/>5）
    """
    if not context or not context.strip():
        return _QUALITY_HINT_TEMPLATES["empty"]

    context_len = len(context)

    # 长度评分
    if context_len < 200:
        length_score = 0  # low
    elif context_len < 1000:
        length_score = 1  # medium
    else:
        length_score = 2  # high

    # 密度评分（按段落分隔符计数）
    paragraphs = [
        p.strip() for p in re.split(r'\n\n+|\n(?=[#\-•])', context) if p.strip()
    ]
    para_count = len(paragraphs)
    if para_count <= 1:
        density_score = 0
    elif para_count <= 5:
        density_score = 1
    else:
        density_score = 2

    total = length_score + density_score

    if total <= 1:
        return _QUALITY_HINT_TEMPLATES["low"]
    elif total <= 3:
        return _QUALITY_HINT_TEMPLATES["medium"]
    else:
        return _QUALITY_HINT_TEMPLATES["high"]


# ============ Fallback 链 ============



async def call_llm(

    prompt: str, system_prompt: str = None, max_tokens: int = 2048,

    temperature: float = 0.3, model: str = None,

    context: str = None, query: str = None, task_type: str = "general",

) -> str:

    """

    LLM Fallback 链：MiMo 2.5 Pro  DeepSeek  空

    所有生成任务统一入口

    v1.50 修复: 添加全局超时保护（120秒），防止调用链耗时过长

    P1 优化:
      - context 参数支持检索质量评估与注入
      - 输出后处理过滤思考链等冗余内容

    Args:

        prompt:       用户提示词

        system_prompt: 系统提示词

        max_tokens:   最大输出 token 数

        temperature:  温度参数

        model:        指定模型（可选）

        context:      RAG 检索结果文本（可选，传入时自动评估质量并注入提示）

        query:        用户原始查询（可选，用于质量评估；不传时从 prompt 截取）

        task_type:    任务类型（general/extraction/planning 等，影响后处理策略）

    """

    # 如果传入了 context，注入检索质量提示到 prompt

    effective_prompt = prompt

    if context is not None:

        if context.strip():

            quality_hint = _inject_quality_hint(query or prompt[:200], context)

            effective_prompt = f"{quality_hint}\n\n{prompt}"

        else:

            empty_hint = _QUALITY_HINT_TEMPLATES["empty"]

            effective_prompt = f"{empty_hint}\n\n{prompt}"



    # 构建 messages 用于缓存key
    _messages_for_cache = []
    if system_prompt:
        _messages_for_cache.append({"role": "system", "content": system_prompt})
    _messages_for_cache.append({"role": "user", "content": _smart_truncate(effective_prompt, 8000)})

    # P0修复：检查语义缓存
    cached = await get_cached_response(_messages_for_cache)
    if cached:
        return cached

    async def _inner():
        messages_inner = list(_messages_for_cache)
        # Level 1: MiMo 2.5 Pro
        for attempt in range(MAX_RETRIES):
            result = await _call_api(
                MIMO_BASE_URL, MIMO_API_KEY, model or MIMO_MODEL,
                messages_inner, max_tokens, temperature, MIMO_TIMEOUT,
            )
            if result:
                return _post_process_llm_output(result, task_type)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
        # Level 2: DeepSeek v4 Pro
        if DEEPSEEK_API_KEY:
            result = await _call_api(
                DEEPSEEK_BASE_URL, DEEPSEEK_API_KEY, DEEPSEEK_MODEL,
                messages_inner, max_tokens, temperature, DEEPSEEK_TIMEOUT,
            )
            if result:
                return _post_process_llm_output(result, task_type)
        return ""

    try:
        # P0修复：缓存响应
        _result = await asyncio.wait_for(_inner(), timeout=120)
        if _result:
            await cache_response(_messages_for_cache, _result)
        return _result
    except asyncio.TimeoutError:
        logger.error("[LLM] call_llm 全局超时 (120s)")
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

    messages.append({"role": "user", "content": _smart_truncate(prompt, 8000)})



    async for chunk in _call_api_stream(

        MIMO_BASE_URL, MIMO_API_KEY, model or MIMO_MODEL,

        messages, max_tokens, temperature, MIMO_TIMEOUT,

    ):

        yield chunk



async def call_llm_stream_messages(

    messages: list,

    max_tokens: int = 2048,

    temperature: float = 0.3,

    model: str = None,

) -> AsyncGenerator[str, None]:

    """流式 Fallback 链 — 接受 messages 列表版本

    

    与 call_llm_stream 的区别：直接接受完整的 messages 列表，

    不再内部拼接 system/user prompt，适合已有完整消息历史的场景。

    """

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

            # v1.50: 缓存大小限制，超过上限时淘汰最早的条目
            if len(_ai_cache) >= _AI_CACHE_MAX_SIZE:
                # 淘汰最早写入的条目（FIFO）
                oldest_key = next(iter(_ai_cache))
                _ai_cache.pop(oldest_key, None)
                logger.debug(f"[cache] 缓存已满({_AI_CACHE_MAX_SIZE})，淘汰最早条目")

            _ai_cache[query] = answer





def get_cached_answer(query: str) -> Optional[str]:

    return _ai_cache.pop(query, None)


# ============ 智能路由集成 ============
# 注意：smart_llm.py 在顶层 from .llm import _call_api, _call_api_stream
# 本模块在函数内部延迟导入 smart_llm，形成 模块级 → 模块级 的循环引用路径：
#   llm.py (module-level) ← smart_llm.py (module-level, imports _call_api)
#   llm.py (function-level) → smart_llm.py (lazy import in call_llm_smart)
# Python 通过部分初始化机制处理此循环，只要不在模块顶层互相导入即可。
# 当前设计安全，但新增导入时需注意避免在模块顶层引入反向依赖。

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
    except (ImportError, AttributeError, OSError):
        return {"error": "无法获取统计信息"}


def reset_llm_stats():
    """
    重置LLM统计信息
    """
    try:
        from .smart_llm import get_smart_llm
        get_smart_llm().reset_stats()
    except (ImportError, AttributeError, OSError):
        pass


# ============ 语义缓存（优化响应速度） ============
import hashlib
import time as _time

_semantic_cache: dict = {}
_SEMANTIC_CACHE_MAX = 500  # 最大缓存条数
# P2修复：缓存TTL可配置，默认30分钟（避免知识库更新后返回过时结果）
_CACHE_TTL = int(os.getenv("FUXI_CACHE_TTL", "1800"))  # 缓存有效期（秒）

def _get_cache_key(messages: list) -> str:
    """生成缓存键（仅基于 system prompt + 用户最后一条消息，排除 history）"""
    # P0修复：只取 system prompt 和最后一条 user 消息作为 key
    # 同一问题不同 history 不应影响缓存命中
    key_parts = []
    for msg in messages:
        if msg.get('role') == 'system':
            key_parts.append(('system', msg.get('content', '')))
    # 取最后一条 user 消息
    for msg in reversed(messages):
        if msg.get('role') == 'user':
            key_parts.append(('user', msg.get('content', '')))
            break
    content = json.dumps(key_parts, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(content.encode()).hexdigest()

async def get_cached_response(messages: list) -> Optional[str]:
    """获取缓存的响应（精确匹配）"""
    global _cache_stats
    key = _get_cache_key(messages)
    _cache_stats["total"] += 1
    
    if key in _semantic_cache:
        entry = _semantic_cache[key]
        if _time.time() - entry['timestamp'] < _CACHE_TTL:
            _cache_stats["hits"] += 1
            hit_rate = _cache_stats["hits"] / _cache_stats["total"] * 100
            logger.info(f"[Cache] 命中缓存: {key[:8]}... (命中率: {hit_rate:.1f}%)")
            return entry['response']
        else:
            # 缓存过期，删除
            del _semantic_cache[key]
    
    _cache_stats["misses"] += 1
    miss_rate = _cache_stats["misses"] / _cache_stats["total"] * 100
    logger.info(f"[Cache] 缓存未命中: {key[:8]}... (未命中率: {miss_rate:.1f}%)")
    return None

async def cache_response(messages: list, response: str):
    """缓存响应"""
    global _semantic_cache
    key = _get_cache_key(messages)
    _semantic_cache[key] = {
        'response': response,
        'timestamp': _time.time()
    }
    # 限制缓存大小，淘汰最旧的条目
    if len(_semantic_cache) > _SEMANTIC_CACHE_MAX:
        oldest = min(_semantic_cache.keys(), key=lambda k: _semantic_cache[k]['timestamp'])
        del _semantic_cache[oldest]
    logger.info(f"[Cache] 缓存响应: {key[:8]}... (总缓存: {len(_semantic_cache)})")

def clear_cache():
    """清空缓存"""
    global _semantic_cache, _cache_stats
    _semantic_cache.clear()
    _cache_stats = {"hits": 0, "misses": 0, "total": 0}
    logger.info("[Cache] 缓存已清空，统计已重置")

def get_cache_stats() -> dict:
    """获取缓存统计信息"""
    hit_rate = 0.0
    if _cache_stats["total"] > 0:
        hit_rate = _cache_stats["hits"] / _cache_stats["total"] * 100
    
    return {
        "size": len(_semantic_cache),
        "max_size": _SEMANTIC_CACHE_MAX,
        "ttl": _CACHE_TTL,
        "hits": _cache_stats["hits"],
        "misses": _cache_stats["misses"],
        "total": _cache_stats["total"],
        "hit_rate": round(hit_rate, 2)
    }

