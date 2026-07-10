"""
llm.py 鈥?LLM 璋冪敤鏈嶅姟锛坴1.43 MiMo 2.5 Pro + Fallback 閾撅級

璋冪敤閾撅細MiMo 2.5 Pro 鈫?DeepSeek 鈫?鏈湴锛堥€愮骇闄嶇骇锛?

妯″潡缁撴瀯璇存槑锛?
  褰撳墠 src/services/llm 鏄竴涓崟浣?.py 鏂囦欢鑰岄潪鍖呯洰褰曘€?
  鎵€鏈?callers 浣跨敤 `from src.services.llm import ...` 瀵煎叆銆?
  鏈潵濡傞渶鎷嗗垎涓?llm/__init__.py + llm/provider_a.py 绛夊瓙妯″潡锛?
  闇€淇濇寔 `src/services/llm/__init__.py` 閲嶆柊瀵煎嚭褰撳墠 API
  锛坈all_ai, call_ai_raw, call_deepseek, call_llm, call_llm_fast, _call_api锛夛紝
  纭繚鐜版湁 from 瀵煎叆涓嶅彈褰卞搷銆?
  灞婃椂鍒犻櫎鏈枃浠讹紝鍒涘缓鍚屽悕鍖呯洰褰曟浛浠ｃ€?
"""
import os, json, logging, asyncio
from typing import Optional, AsyncGenerator, Dict, Any
import aiohttp

logger = logging.getLogger(__name__)

# ============ MiMo API 閰嶇疆 ============
from src.config import MIMO_API_KEY, MIMO_BASE_URL, MIMO_MODEL, MIMO_TIMEOUT

# ============ Fallback: DeepSeek ============
from src.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, DEEPSEEK_TIMEOUT

# ============ 缂撳瓨 ============
_ai_cache: dict = {}
_ai_cache_lock = asyncio.Lock()

# ============ 鍏ㄥ眬 aiohttp 杩炴帴姹?============
_global_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()


async def _get_session() -> aiohttp.ClientSession:
    """鑾峰彇鍏ㄥ眬 aiohttp 杩炴帴姹?Session锛堝崟渚嬶紝甯﹁繛鎺ラ檺鍒讹級"""
    global _global_session
    if _global_session is None or _global_session.closed:
        async with _session_lock:
            if _global_session is None or _global_session.closed:
                connector = aiohttp.TCPConnector(
                    limit=100,          # 鎬昏繛鎺ユ暟涓婇檺
                    limit_per_host=20,  # 鍗?host 杩炴帴鏁颁笂闄?
                    ttl_dns_cache=300,  # DNS 缂撳瓨 TTL
                    enable_cleanup_closed=True,
                )
                _global_session = aiohttp.ClientSession(connector=connector)
    return _global_session


async def close_session():
    """(see original source)"""
    global _global_session
    if _global_session and not _global_session.closed:
        await _global_session.close()
        _global_session = None

# ============ 閲嶈瘯閰嶇疆 ============
MAX_RETRIES = 2
RETRY_DELAY = 1.0


async def _call_api(
    base_url: str, api_key: str, model: str,
    messages: list, max_tokens: int = 4096,
    temperature: float = 0.3, timeout: int = 60,
    stream: bool = False,
    tools: Optional[list] = None,
    tool_choice: Optional[str] = None,
) -> Optional[str]:
    """閫氱敤 OpenAI 鍏煎 API 璋冪敤 鈥?甯﹂噸璇?閫愭鏀惧ぇ+绌哄唴瀹规娴?

    Args:
        tools:       Function calling tools 瀹氫箟鍒楄〃 [{"type":"function","function":{...}}]
        tool_choice: 宸ュ叿閫夋嫨绛栫暐 "auto"|"none"|"required"|"function_name"
    """
    # MiMo reasoning 妯″瀷锛歳easoning token 鍜?output token 鍏变韩 max_tokens 棰勭畻
    # 澶皬 = 鎬濊€冨畬娌＄┖闂磋緭鍑猴紝鎵€浠ュ熀纭€鍊艰澶?
    base_max = max(max_tokens, 4096)

    for attempt in range(3):
        current_max = base_max * (attempt + 1)  # 4096 鈫?8192 鈫?12288

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
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

        try:
            session = await _get_session()
            async with session.post(
                    f"{base_url}/chat/completions",
                    json=payload, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        # v1.50 R4: 鑴辨晱 API 绔偣锛岄槻姝㈡棩蹇楁硠闇叉晱鎰?URL
                        masked_url = base_url.split("//")[0] + "//***" if "//" in base_url else "***"
                        logger.warning(f"API {masked_url} {resp.status} (attempt {attempt+1}): {text[:200]}")
                        if attempt < 2:
                            await asyncio.sleep(1 * (attempt + 1))
                            continue
                        return None

                    data = await resp.json()
                    msg = data["choices"][0]["message"]
                    content = msg.get("content", "")
                    reasoning = msg.get("reasoning_content", "")
                    tool_calls = msg.get("tool_calls", [])

                    # 濡傛灉杩斿洖浜?tool_calls锛屽簭鍒楀寲涓?JSON 杩斿洖
                    if tool_calls and not content:
                        logger.info(
                            f"_call_api: 鏀跺埌 {len(tool_calls)} 涓?tool_calls, "
                            f"序列化返回"
                        )
                        return json.dumps({"tool_calls": tool_calls}, ensure_ascii=False)

                    # 妫€鏌ョ┖鍐呭
                    if content and content.strip():
                        return content

                    # 鎬濊€冧簡浣嗘病杈撳嚭 鈫?max_tokens 涓嶅锛岄噸璇曟斁澶?
                    if reasoning and not content:
                        logger.warning(f"MiMo attempt {attempt+1}: reasoning鏈?{len(reasoning)}瀛?浣哻ontent涓虹┖, max_tokens={current_max}, 閲嶈瘯...")
                        if attempt < 2:
                            await asyncio.sleep(1 * (attempt + 1))
                            continue

                    # 鏃?reasoning 涔熸棤 content 鈫?鍙兘鏄?prompt 闂
                    if not content:
                        logger.warning(f"MiMo attempt {attempt+1}: 绌哄搷搴? max_tokens={current_max}")
                        if attempt < 2:
                            await asyncio.sleep(1 * (attempt + 1))
                            continue

                    return content if content else None

        except (aiohttp.ClientError, OSError, asyncio.TimeoutError) as e:
            # 鑴辨晱 API 绔偣
            masked_url = base_url.split("//")[0] + "//***" if "//" in base_url else "***"
            logger.warning(f"API {masked_url} attempt {attempt+1} 寮傚父: {e}")
            if attempt < 2:
                await asyncio.sleep(2 * (attempt + 1))
                continue
            return None

    return None


# FAKE-ASYNC: 鏈嚱鏁版爣璁?async 浠呬负鎺ュ彛缁熶竴锛屽唴閮ㄥ悓姝ユ墽琛?
async def _call_api_stream(
    base_url: str, api_key: str, model: str,
    messages: list, max_tokens: int = 2048,
    temperature: float = 0.3, timeout: int = 60,
) -> AsyncGenerator[str, None]:
    """閫氱敤娴佸紡 API 璋冪敤"""
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
        session = await _get_session()
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
    except (aiohttp.ClientError, OSError, asyncio.TimeoutError) as e:
        yield f"[Stream Error: {e}]"


# ============ Fallback 閾?============

async def call_llm(
    prompt: str, system_prompt: str = None, max_tokens: int = 2048,
    temperature: float = 0.3, model: str = None,
) -> str:
    """
    LLM Fallback 鎺ｉ摼锛歁iMo 2.5 Pro -> DeepSeek -> 绌哄瓧绗?
    鎵€鏈夌敓鎴愪换鍔＄粺涓€鍏ュ彛

    v1.44 R3: 杞婚噺绾?60s 缁撴€昏秴鏃?   """
    _CHAIN_TIMEOUT = 60.0  # v1.44 R3: 缁撴€昏秴鏃?

    # v1.44 安全修复: System Prompt 硬化 — 注入防御性安全约束
    try:
        from src.services.prompt_guard import get_hardened_system_prompt
        system_prompt = get_hardened_system_prompt(system_prompt)
    except ImportError:
        pass

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt[:8000]})

    async def _fallback_chain() -> str:
        # Level 1: MiMo 2.5 Pro
        if not MIMO_API_KEY:
            logger.warning("MiMo API Key 未配置，跳过 MiMo 直接尝试 DeepSeek")
        else:
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

    # v1.44 R3: 杞婚噺鏈€澶?60 纭?
    try:
        return await asyncio.wait_for(_fallback_chain(), timeout=_CHAIN_TIMEOUT)
    except asyncio.TimeoutError:
        logger.error(f"[call_llm] 鏈€澶勮秴鏃?{_CHAIN_TIMEOUT}s, 鏀惧纯")
        return ""




async def call_llm_fast(
    prompt: str, system_prompt: str = None, max_tokens: int = 500,
    temperature: float = 0.1,
) -> str:
    """杞婚噺浠诲姟锛堝垎绫?鍏抽敭璇嶆彁鍙?绠€鍗曞垽鏂級鐢?MiMo-fast锛屾垚鏈綆閫熷害蹇?""
    return await call_llm(prompt, system_prompt, max_tokens, temperature, model="mimo-v2.5-turbo")

# FAKE-ASYNC: 鏈嚱鏁版爣璁?async 浠呬负鎺ュ彛缁熶竴锛屽唴閮ㄥ悓姝ユ墽琛?
async def call_llm_stream(
    prompt: str, system_prompt: str = None, max_tokens: int = 2048,
    temperature: float = 0.3, model: str = None,
) -> AsyncGenerator[str, None]:
    """娴佸紡 Fallback 閾?""
    # v1.44 安全修复: 加固 system prompt
    try:
        from src.services.prompt_guard import get_hardened_system_prompt
        system_prompt = get_hardened_system_prompt(system_prompt)
    except ImportError:
        pass

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt[:8000]})

    async for chunk in _call_api_stream(
        MIMO_BASE_URL, MIMO_API_KEY, model or MIMO_MODEL,
        messages, max_tokens, temperature, MIMO_TIMEOUT,
    ):
        yield chunk


# ============ 鍏煎鏃ф帴鍙?============

async def call_ai_raw(prompt: str, max_tokens: int = 300) -> str:
    """鍏煎鏃ц皟鐢?""
    return await call_llm(prompt, max_tokens=max_tokens)


async def call_ai(prompt: str, max_tokens: int = 300) -> str:
    """鍏煎鏃ц皟鐢?""
    return await call_llm(prompt, max_tokens=max_tokens)


async def call_deepseek(
    prompt: str, system_prompt: str = None, max_tokens: int = 2048,
    temperature: float = 0.3, model: str = None,
) -> str:
    """(see original source)"""
    return await call_llm(prompt, system_prompt, max_tokens, temperature, model)


# FAKE-ASYNC: 鏈嚱鏁版爣璁?async 浠呬负鎺ュ彛缁熶竴锛屽唴閮ㄥ悓姝ユ墽琛?
async def call_deepseek_stream(
    prompt: str, system_prompt: str = None, max_tokens: int = 2048,
    temperature: float = 0.3, model: str = None,
) -> AsyncGenerator[str, None]:
    """鍏煎鏃ф祦寮忚皟鐢?""
    async for chunk in call_llm_stream(prompt, system_prompt, max_tokens, temperature, model):
        yield chunk


async def call_ollama(prompt_text: str, model: str = None, max_tokens: int = 300) -> Optional[str]:
    """(see original source)"""
    return await call_llm(prompt_text, max_tokens=max_tokens)


# FAKE-ASYNC: 鏈嚱鏁版爣璁?async 浠呬负鎺ュ彛缁熶竴锛屽唴閮ㄥ悓姝ユ墽琛?
async def call_ollama_stream(prompt_text: str) -> AsyncGenerator[str, None]:
    """(see original source)"""
    async for chunk in call_llm_stream(prompt_text):
        yield chunk


async def call_siliconflow(prompt: str, model: str = "") -> str:
    """SiliconFlow API 璋冪敤锛堢敤浜庣壒娈婃ā鍨嬶級"""
    from src.config import SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL
    sf_key = SILICONFLOW_API_KEY
    sf_url = SILICONFLOW_BASE_URL
    sf_model = model or "Qwen/Qwen2.5-7B-Instruct"
    if not sf_key:
        return ""
    return await _call_api(sf_url, sf_key, sf_model, [{"role": "user", "content": prompt}], 500) or ""


# FAKE-ASYNC: 鏈嚱鏁版爣璁?async 浠呬负鎺ュ彛缁熶竴锛屽唴閮ㄥ悓姝ユ墽琛?
async def call_siliconflow_stream(prompt: str, model: str = "") -> AsyncGenerator[str, None]:
    """SiliconFlow 娴佸紡"""
    from src.config import SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL
    sf_key = SILICONFLOW_API_KEY
    sf_url = SILICONFLOW_BASE_URL
    sf_model = model or "Qwen/Qwen2.5-7B-Instruct"
    if not sf_key:
        yield "[SiliconFlow Key 鏈厤缃甝"
        return
    async for chunk in _call_api_stream(sf_url, sf_key, sf_model, [{"role": "user", "content": prompt}]):
        yield chunk


async def call_mimo_async(query: str, sources: list, messages: list, api_key: str):
    """鍏煎鏃ц皟鐢?""
    answer = await call_llm(query, system_prompt="你是伏羲知识库助手", max_tokens=2048)
    if answer:
        async with _ai_cache_lock:
            _ai_cache[query] = answer


# ============ 浠诲姟鈫掓ā鍨嬫槧灏勶紙v1.50 浠?infra/llm.py 鍚堝苟锛?============

TASK_MODEL_MAP = {
    # JSON 杈撳嚭浠诲姟 鈫?闈?pro 鐗?
    "extraction": "mimo-v2.5",
    "classification": "mimo-v2.5",
    "parsing": "mimo-v2.5",
    "validation": "mimo-v2.5",
    "distillation": "mimo-v2.5",

    # 鎺ㄧ悊浠诲姟 鈫?pro 鐗?
    "synthesis": "mimo-v2.5-pro",
    "reflection": "mimo-v2.5-pro",
    "reasoning": "mimo-v2.5-pro",
    "planning": "mimo-v2.5-pro",

    # 杞婚噺浠诲姟 鈫?turbo 鐗?
    "fast_classify": "mimo-v2.5-turbo",
    "fast_extract": "mimo-v2.5-turbo",
}

TASK_MAX_TOKENS = {
    "extraction": 4096,
    "synthesis": 8192,
    "rewrite": 1024,
    "reflection": 4096,
    "validation": 2048,
    "distillation": 2048,
}


async def call_llm_by_task(
    task: str,
    prompt: str,
    system_prompt: Optional[str] = None,
    tools: Optional[list] = None,
    tool_choice: Optional[str] = None,
    **kwargs
) -> str:
    """鏍规嵁浠诲姟绫诲瀷鏅鸿兘閫夋嫨妯″瀷 鈥?缁熶竴璋冪敤 dispatch 閾?

    妯″瀷閫夋嫨閫昏緫:
      - JSON 鎻愬彇/鍒嗙被/瑙ｆ瀽 鈫?闈?pro 鐗?(mimo-v2.5)
      - 鎺ㄧ悊/缁煎悎/鍐崇瓥 鈫?pro 鐗?(mimo-v2.5-pro)
      - 杞婚噺浠诲姟 (fast_*) 鈫?turbo (mimo-v2.5-turbo)

    Args:
        task:          浠诲姟绫诲瀷
        prompt:        鐢ㄦ埛鎻愮ず
        system_prompt: 绯荤粺鎻愮ず锛堝彲閫夛級
        tools:         Function calling tools
        tool_choice:   宸ュ叿閫夋嫨绛栫暐
        **kwargs:      鍏朵粬鍙傛暟浼犻€掔粰 call_llm()

    Returns:
        LLM 杈撳嚭鏂囨湰
    """
    model = TASK_MODEL_MAP.get(task, "mimo-v2.5")
    max_tokens_kw = TASK_MAX_TOKENS.get(task, 4096)

    kwargs["max_tokens"] = kwargs.get("max_tokens", max_tokens_kw)

    # 濡傛灉鎻愪緵浜?tools锛岀洿鎺ヨ皟鐢?_call_api 浠ョ‘淇濆弬鏁版纭紶閫?
    if tools:
        from src.config import MIMO_API_KEY, MIMO_BASE_URL, MIMO_TIMEOUT
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        result = await _call_api(
            base_url=MIMO_BASE_URL,
            api_key=MIMO_API_KEY,
            model=model,
            messages=messages,
            max_tokens=kwargs.get("max_tokens", 4096),
            temperature=kwargs.get("temperature", 0.3),
            timeout=MIMO_TIMEOUT,
            tools=tools,
            tool_choice=tool_choice,
        )
        return result or ""

    return await call_llm(prompt, system_prompt=system_prompt, model=model, **kwargs)


def get_cached_answer(query: str) -> Optional[str]:
    return _ai_cache.pop(query, None)


# ============ TokenBudget 鈥?鎴愭湰浠ょ墝棰勭畻鐔旀柇鍣紙v1.50 鏂规绗?3鏉★級 ============

# Token 浠锋牸鍙傝€冿紙CNY / 1M tokens锛?
# MiMo v2.5 Pro: 杈撳叆 楼4, 杈撳嚭 楼16
# MiMo v2.5:     杈撳叆 楼1, 杈撳嚭 楼4
# MiMo v2.5 Turbo:杈撳叆 楼0.5, 杈撳嚭 楼2
# DeepSeek v4:   杈撳叆 楼1, 杈撳嚭 楼4
MODEL_PRICE_PER_MTOK_IN = {
    "mimo-v2.5-pro":   4.0,
    "mimo-v2.5":       1.0,
    "mimo-v2.5-turbo": 0.5,
    "deepseek-v4-pro": 1.0,
    "deepseek-v4-flash": 0.5,
    "4o-mini":         0.15,
}
MODEL_PRICE_PER_MTOK_OUT = {
    "mimo-v2.5-pro":   16.0,
    "mimo-v2.5":       4.0,
    "mimo-v2.5-turbo": 2.0,
    "deepseek-v4-pro": 4.0,
    "deepseek-v4-flash": 2.0,
    "4o-mini":         0.6,
}

# 浼氳瘽棰勭畻榛樿鍊?楼0.15锛堢害 15 涓?Mimo 鏅€?token锛夛紝鍙€氳繃 FUXI_SESSION_BUDGET 閰嶇疆
_DEFAULT_SESSION_BUDGET: float = float(os.getenv("FUXI_SESSION_BUDGET", "0.15"))
# 璀﹀憡闃堝€硷細80% 棰勭畻
_BUDGET_WARN_THRESHOLD: float = 0.80
# 鐔旀柇闃堝€硷細100% 棰勭畻
_BUDGET_CIRCUIT_THRESHOLD: float = 1.00


class TokenBudgetExceeded(Exception):
    """Token 棰勭畻鐔旀柇寮傚父"""

    def __init__(self, session_id: str, consumed: float, budget: float):
        self.session_id = session_id
        self.consumed = consumed
        self.budget = budget
        super().__init__(
            f"[TokenBudget] Session={session_id} 预算熔断:"
            f"已消费 ¥{consumed:.4f} / ¥{budget:.2f}"
        )


class TokenBudget:
    """Token 鎴愭湰棰勭畻璺熻釜鍣?鈥?浼氳瘽绾ф垚鏈啍鏂?

    璺熻釜鍗曚釜 session 鐨勭疮璁?token 娑堣€楋紙鎸夋ā鍨嬩环鏍兼姌绠?RMB锛夛紝
    鎻愪緵棰勭畻鍛婅鍜岀啍鏂満鍒躲€?

    浠锋牸妯″瀷锛氭寜瀛楃鏁颁及绠?token 鏁帮紙涓枃 ~1.5 char/token锛岃嫳鏂?~4 char/token锛夛紝
    鍐嶄箻浠ユā鍨嬪崟浠枫€?

    Usage::

        budget = TokenBudget(session_id="s1", budget_cny=0.15)

        # 璋冪敤 LLM 鍓?
        budget.warn_if_near_limit()  # 鎺ヨ繎棰勭畻鏃?log warning

        # 璋冪敤 LLM 鍚?
        budget.consume("mimo-v2.5", input_chars, output_chars)

        # 妫€鏌ョ啍鏂?
        if budget.is_tripped():
            raise TokenBudgetExceeded(...)

    Attributes:
        session_id:   浼氳瘽鏍囪瘑
        budget_cny:   棰勭畻涓婇檺锛堜汉姘戝竵鍏冿級
        consumed_cny: 宸叉秷鑰楅噾棰?
        call_count:   绱璋冪敤娆℃暟
    """

    def __init__(
        self,
        session_id: str = "default",
        budget_cny: Optional[float] = None,
    ) -> None:
        self.session_id = session_id
        self.budget_cny = budget_cny if budget_cny is not None else _DEFAULT_SESSION_BUDGET
        self.consumed_cny: float = 0.0
        self.call_count: int = 0
        self._tripped: bool = False
        self._warned: bool = False
        self._created_at: float = time.time()

    # ---- Token 浼扮畻 ----

    @staticmethod
    def estimate_input_tokens(text: str) -> int:
        """浼扮畻杈撳叆 token 鏁?

        绮椾及瑙勫垯锛氫腑鏂?~1.5 char/token锛岃嫳鏂?~4 char/token
        """
        if not text:
            return 0
        # 缁熻涓枃瀛楃鏁?
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return max(1, int(chinese_chars / 1.5 + other_chars / 4.0))

    @staticmethod
    def estimate_output_tokens(text: str) -> int:
        """浼扮畻杈撳嚭 token 鏁帮紙鍚?input 浼扮畻閫昏緫锛?""
        return TokenBudget.estimate_input_tokens(text)

    @staticmethod
    def estimate_cost(
        model: str,
        input_chars: int = 0,
        output_chars: int = 0,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
    ) -> float:
        """浼扮畻鍗曟璋冪敤鎴愭湰锛圕NY锛?

        Args:
            model:        妯″瀷鍚?
            input_chars:  杈撳叆瀛楃鏁帮紙鑻ユ湭鎻愪緵 input_tokens锛?
            output_chars: 杈撳嚭瀛楃鏁帮紙鑻ユ湭鎻愪緵 output_tokens锛?
            input_tokens: 绮剧‘杈撳叆 token 鏁帮紙鍙€夛級
            output_tokens: 绮剧‘杈撳嚭 token 鏁帮紙鍙€夛級

        Returns:
            鎴愭湰浼扮畻锛堝厓锛?
        """
        if input_tokens is None:
            input_tokens = TokenBudget.estimate_input_tokens("x" * input_chars) if input_chars else 0
        if output_tokens is None:
            output_tokens = TokenBudget.estimate_output_tokens("x" * output_chars) if output_chars else 0

        price_in = MODEL_PRICE_PER_MTOK_IN.get(model, 1.0)
        price_out = MODEL_PRICE_PER_MTOK_OUT.get(model, 4.0)

        cost = (input_tokens / 1_000_000) * price_in + (output_tokens / 1_000_000) * price_out
        return round(cost, 6)

    # ---- 鏍稿績鎿嶄綔 ----

    def consume(
        self,
        model: str,
        input_chars: int = 0,
        output_chars: int = 0,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
    ) -> float:
        """璁板綍涓€娆?LLM 璋冪敤鐨?token 娑堣€?

        Args:
            model:         妯″瀷鍚?
            input_chars:   杈撳叆瀛楃鏁?
            output_chars:  杈撳嚭瀛楃鏁?
            input_tokens:  绮剧‘杈撳叆 token 鏁帮紙鍙€夛級
            output_tokens: 绮剧‘杈撳嚭 token 鏁帮紙鍙€夛級

        Returns:
            鏈璋冪敤鎴愭湰锛堝厓锛?

        Raises:
            TokenBudgetExceeded: 瓒呭嚭棰勭畻鏃舵姏鍑?
        """
        cost = self.estimate_cost(
            model=model,
            input_chars=input_chars,
            output_chars=output_chars,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        self.consumed_cny += cost
        self.call_count += 1

        logger.debug(
            "[TokenBudget] Session=%s consumed 楼%.6f (model=%s), "
            "total=楼%.4f/楼%.2f (%.1f%%)",
            self.session_id, cost, model,
            self.consumed_cny, self.budget_cny,
            (self.consumed_cny / self.budget_cny * 100) if self.budget_cny > 0 else 0,
        )

        if self.consumed_cny >= self.budget_cny:
            self._tripped = True
            raise TokenBudgetExceeded(
                session_id=self.session_id,
                consumed=self.consumed_cny,
                budget=self.budget_cny,
            )

        return cost

    def consume_with_actual_tokens(
        self,
        model: str,
        actual_input_tokens: int,
        actual_output_tokens: int,
    ) -> float:
        """浣跨敤 API 杩斿洖鐨勫疄闄?token 鏁拌褰曟秷鑰楋紙浼樺厛浣跨敤姝ゆ柟娉曪級

        Args:
            model:                妯″瀷鍚?
            actual_input_tokens:  API 杩斿洖鐨?prompt_tokens
            actual_output_tokens: API 杩斿洖鐨?completion_tokens

        Returns:
            鎴愭湰锛堝厓锛?
        """
        return self.consume(
            model=model,
            input_tokens=actual_input_tokens,
            output_tokens=actual_output_tokens,
        )

    # ---- 鏌ヨ鏂规硶 ----

    @property
    def is_tripped(self) -> bool:
        """鐔旀柇鍣ㄦ槸鍚﹀凡瑙﹀彂"""
        return self._tripped or self.consumed_cny >= self.budget_cny

    @property
    def usage_ratio(self) -> float:
        """棰勭畻浣跨敤姣斾緥 0.0-1.0"""
        if self.budget_cny <= 0:
            return 1.0
        return min(self.consumed_cny / self.budget_cny, 1.0)

    @property
    def should_warn(self) -> bool:
        """鏄惁杈惧埌鍛婅闃堝€硷紙80%锛?""
        return self.usage_ratio >= _BUDGET_WARN_THRESHOLD

    def warn_if_near_limit(self) -> Optional[str]:
        """鎺ヨ繎棰勭畻鏃惰繑鍥炶鍛婁俊鎭?

        Returns:
            璀﹀憡瀛楃涓叉垨 None
        """
        ratio = self.usage_ratio
        if ratio >= _BUDGET_CIRCUIT_THRESHOLD:
            return (
                f"鈿狅笍 TokenBudget 鐔旀柇锛丼ession={self.session_id} "
                f"宸叉秷鑰?楼{self.consumed_cny:.4f}/楼{self.budget_cny:.2f}"
            )
        if ratio >= _BUDGET_WARN_THRESHOLD and not self._warned:
            self._warned = True
            remaining = self.budget_cny - self.consumed_cny
            logger.warning(
                "[TokenBudget] Session=%s 棰勭畻鍛婅: "
                "宸蹭娇鐢?%.1f%% (楼%.4f/楼%.2f), 鍓╀綑 楼%.4f",
                self.session_id, ratio * 100,
                self.consumed_cny, self.budget_cny, remaining,
            )
            return (
                f"鈿狅笍 TokenBudget 棰勭畻鍛婅: 宸蹭娇鐢?{ratio*100:.0f}% "
                f"(楼{self.consumed_cny:.4f}/楼{self.budget_cny:.2f})"
            )
        return None

    def get_stats(self) -> Dict[str, Any]:
        """(see original source)"""
        return {
            "session_id": self.session_id,
            "budget_cny": self.budget_cny,
            "consumed_cny": round(self.consumed_cny, 6),
            "usage_ratio": round(self.usage_ratio, 4),
            "is_tripped": self.is_tripped,
            "call_count": self.call_count,
            "created_at": self._created_at,
        }

    def reset(self, new_budget: Optional[float] = None) -> None:
        """閲嶇疆棰勭畻璁℃暟鍣?

        Args:
            new_budget: 鏂扮殑棰勭畻涓婇檺锛圢one 琛ㄧず淇濇寔鍘熷€硷級
        """
        if new_budget is not None:
            self.budget_cny = new_budget
        self.consumed_cny = 0.0
        self.call_count = 0
        self._tripped = False
        self._warned = False
        logger.info(
            "[TokenBudget] Session=%s 棰勭畻宸查噸缃?(new_budget=楼%.2f)",
            self.session_id, self.budget_cny,
        )


# ============================================================================
# 浼氳瘽绾?TokenBudget 娉ㄥ唽琛紙绾跨▼瀹夊叏锛岀敱 dispatch_llm 浣跨敤锛?
# ============================================================================

_budget_lock = asyncio.Lock()
_session_budgets: Dict[str, TokenBudget] = {}


async def get_session_budget(session_id: str) -> TokenBudget:
    """鑾峰彇鎴栧垱寤轰細璇濈骇 TokenBudget

    Args:
        session_id: 浼氳瘽鏍囪瘑

    Returns:
        TokenBudget 瀹炰緥
    """
    async with _budget_lock:
        if session_id not in _session_budgets:
            _session_budgets[session_id] = TokenBudget(
                session_id=session_id,
                budget_cny=_DEFAULT_SESSION_BUDGET,
            )
            logger.info(
                "[TokenBudget] Session=%s 鏂板缓棰勭畻 楼%.2f",
                session_id, _DEFAULT_SESSION_BUDGET,
            )
        return _session_budgets[session_id]


async def cleanup_session_budget(session_id: str) -> None:
    """娓呯悊浼氳瘽棰勭畻锛堜細璇濈粨鏉熸椂璋冪敤锛?""
    async with _budget_lock:
        if session_id in _session_budgets:
            budget = _session_budgets.pop(session_id)
            logger.info(
                "[TokenBudget] Session=%s 宸叉竻鐞? 鏈€缁堟秷鑰?楼%.4f/楼%.2f",
                session_id, budget.consumed_cny, budget.budget_cny,
            )
