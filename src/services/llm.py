"""
llm.py — LLM 调用服务（v1.43 MiMo 2.5 Pro + Fallback 链）

调用链：MiMo 2.5 Pro → DeepSeek → 本地（逐级降级）

模块结构说明：
  当前 src/services/llm 是一个单体 .py 文件而非包目录。
  所有 callers 使用 `from src.services.llm import ...` 导入。
  未来如需拆分为 llm/__init__.py + llm/provider_a.py 等子模块，
  需保持 `src/services/llm/__init__.py` 重新导出当前 API
  （call_ai, call_ai_raw, call_deepseek, call_llm, call_llm_fast, _call_api），
  确保现有 from 导入不受影响。
  届时删除本文件，创建同名包目录替代。
"""
import os, json, logging, asyncio
from typing import Optional, AsyncGenerator, Dict, Any

logger = logging.getLogger(__name__)

# ============ MiMo API 配置 ============
from src.config import MIMO_API_KEY, MIMO_BASE_URL, MIMO_MODEL, MIMO_TIMEOUT

# ============ Fallback: DeepSeek ============
from src.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, DEEPSEEK_TIMEOUT

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
    tools: Optional[list] = None,
    tool_choice: Optional[str] = None,
) -> Optional[str]:
    """通用 OpenAI 兼容 API 调用 — 带重试+逐次放大+空内容检测

    Args:
        tools:       Function calling tools 定义列表 [{"type":"function","function":{...}}]
        tool_choice: 工具选择策略 "auto"|"none"|"required"|"function_name"
    """
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
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/chat/completions",
                    json=payload, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        # v1.50 R4: 脱敏 API 端点，防止日志泄露敏感 URL
                        masked_url = base_url.split("//")[0] + "//***" if "//" in base_url else "***"
                        logger.warning(f"API {masked_url} {resp.status} (attempt {attempt+1}): {text[:200]}")
                        if attempt < 2:
                            import asyncio
                            await asyncio.sleep(1 * (attempt + 1))
                            continue
                        return None

                    data = await resp.json()
                    msg = data["choices"][0]["message"]
                    content = msg.get("content", "")
                    reasoning = msg.get("reasoning_content", "")
                    tool_calls = msg.get("tool_calls", [])

                    # 如果返回了 tool_calls，序列化为 JSON 返回
                    if tool_calls and not content:
                        logger.info(
                            f"_call_api: 收到 {len(tool_calls)} 个 tool_calls, "
                            f"序列化返回"
                        )
                        return json.dumps({"tool_calls": tool_calls}, ensure_ascii=False)

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

        except (aiohttp.ClientError, OSError, asyncio.TimeoutError) as e:
            # 脱敏 API 端点
            masked_url = base_url.split("//")[0] + "//***" if "//" in base_url else "***"
            logger.warning(f"API {masked_url} attempt {attempt+1} 异常: {e}")
            if attempt < 2:
                import asyncio
                await asyncio.sleep(2 * (attempt + 1))
                continue
            return None

    return None


# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
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
    except (aiohttp.ClientError, OSError, asyncio.TimeoutError) as e:
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




async def call_llm_fast(
    prompt: str, system_prompt: str = None, max_tokens: int = 500,
    temperature: float = 0.1,
) -> str:
    """轻量任务（分类/关键词提取/简单判断）用 MiMo-fast，成本低速度快"""
    return await call_llm(prompt, system_prompt, max_tokens, temperature, model="mimo-v2.5-turbo")

# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
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


# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
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


# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def call_ollama_stream(prompt_text: str) -> AsyncGenerator[str, None]:
    """已弃用：重定向到 MiMo 流式"""
    async for chunk in call_llm_stream(prompt_text):
        yield chunk


async def call_siliconflow(prompt: str, model: str = "") -> str:
    """SiliconFlow API 调用（用于特殊模型）"""
    from src.config import SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL
    sf_key = SILICONFLOW_API_KEY
    sf_url = SILICONFLOW_BASE_URL
    sf_model = model or "Qwen/Qwen2.5-7B-Instruct"
    if not sf_key:
        return ""
    return await _call_api(sf_url, sf_key, sf_model, [{"role": "user", "content": prompt}], 500) or ""


# FAKE-ASYNC: 本函数标记 async 仅为接口统一，内部同步执行
async def call_siliconflow_stream(prompt: str, model: str = "") -> AsyncGenerator[str, None]:
    """SiliconFlow 流式"""
    from src.config import SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL
    sf_key = SILICONFLOW_API_KEY
    sf_url = SILICONFLOW_BASE_URL
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


# ============ 任务→模型映射（v1.50 从 infra/llm.py 合并） ============

TASK_MODEL_MAP = {
    # JSON 输出任务 → 非 pro 版
    "extraction": "mimo-v2.5",
    "classification": "mimo-v2.5",
    "parsing": "mimo-v2.5",
    "validation": "mimo-v2.5",
    "distillation": "mimo-v2.5",

    # 推理任务 → pro 版
    "synthesis": "mimo-v2.5-pro",
    "reflection": "mimo-v2.5-pro",
    "reasoning": "mimo-v2.5-pro",
    "planning": "mimo-v2.5-pro",

    # 轻量任务 → turbo 版
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
    """根据任务类型智能选择模型 — 统一调用 dispatch 链

    模型选择逻辑:
      - JSON 提取/分类/解析 → 非 pro 版 (mimo-v2.5)
      - 推理/综合/决策 → pro 版 (mimo-v2.5-pro)
      - 轻量任务 (fast_*) → turbo (mimo-v2.5-turbo)

    Args:
        task:          任务类型
        prompt:        用户提示
        system_prompt: 系统提示（可选）
        tools:         Function calling tools
        tool_choice:   工具选择策略
        **kwargs:      其他参数传递给 call_llm()

    Returns:
        LLM 输出文本
    """
    model = TASK_MODEL_MAP.get(task, "mimo-v2.5")
    max_tokens_kw = TASK_MAX_TOKENS.get(task, 4096)

    kwargs["max_tokens"] = kwargs.get("max_tokens", max_tokens_kw)

    # 如果提供了 tools，直接调用 _call_api 以确保参数正确传递
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


# ============ TokenBudget — 成本令牌预算熔断器（v1.50 方案第13条） ============

# Token 价格参考（CNY / 1M tokens）
# MiMo v2.5 Pro: 输入 ¥4, 输出 ¥16
# MiMo v2.5:     输入 ¥1, 输出 ¥4
# MiMo v2.5 Turbo:输入 ¥0.5, 输出 ¥2
# DeepSeek v4:   输入 ¥1, 输出 ¥4
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

# 会话预算默认值 ¥0.15（约 15 万 Mimo 普通 token），可通过 FUXI_SESSION_BUDGET 配置
_DEFAULT_SESSION_BUDGET: float = float(os.getenv("FUXI_SESSION_BUDGET", "0.15"))
# 警告阈值：80% 预算
_BUDGET_WARN_THRESHOLD: float = 0.80
# 熔断阈值：100% 预算
_BUDGET_CIRCUIT_THRESHOLD: float = 1.00


class TokenBudgetExceeded(Exception):
    """Token 预算熔断异常"""

    def __init__(self, session_id: str, consumed: float, budget: float):
        self.session_id = session_id
        self.consumed = consumed
        self.budget = budget
        super().__init__(
            f"[TokenBudget] Session={session_id} 预算熔断！"
            f"已消耗 ¥{consumed:.4f} / ¥{budget:.2f}"
        )


class TokenBudget:
    """Token 成本预算跟踪器 — 会话级成本熔断

    跟踪单个 session 的累计 token 消耗（按模型价格折算 RMB），
    提供预算告警和熔断机制。

    价格模型：按字符数估算 token 数（中文 ~1.5 char/token，英文 ~4 char/token），
    再乘以模型单价。

    Usage::

        budget = TokenBudget(session_id="s1", budget_cny=0.15)

        # 调用 LLM 前
        budget.warn_if_near_limit()  # 接近预算时 log warning

        # 调用 LLM 后
        budget.consume("mimo-v2.5", input_chars, output_chars)

        # 检查熔断
        if budget.is_tripped():
            raise TokenBudgetExceeded(...)

    Attributes:
        session_id:   会话标识
        budget_cny:   预算上限（人民币元）
        consumed_cny: 已消耗金额
        call_count:   累计调用次数
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

    # ---- Token 估算 ----

    @staticmethod
    def estimate_input_tokens(text: str) -> int:
        """估算输入 token 数

        粗估规则：中文 ~1.5 char/token，英文 ~4 char/token
        """
        if not text:
            return 0
        # 统计中文字符数
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return max(1, int(chinese_chars / 1.5 + other_chars / 4.0))

    @staticmethod
    def estimate_output_tokens(text: str) -> int:
        """估算输出 token 数（同 input 估算逻辑）"""
        return TokenBudget.estimate_input_tokens(text)

    @staticmethod
    def estimate_cost(
        model: str,
        input_chars: int = 0,
        output_chars: int = 0,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
    ) -> float:
        """估算单次调用成本（CNY）

        Args:
            model:        模型名
            input_chars:  输入字符数（若未提供 input_tokens）
            output_chars: 输出字符数（若未提供 output_tokens）
            input_tokens: 精确输入 token 数（可选）
            output_tokens: 精确输出 token 数（可选）

        Returns:
            成本估算（元）
        """
        if input_tokens is None:
            input_tokens = TokenBudget.estimate_input_tokens("x" * input_chars) if input_chars else 0
        if output_tokens is None:
            output_tokens = TokenBudget.estimate_output_tokens("x" * output_chars) if output_chars else 0

        price_in = MODEL_PRICE_PER_MTOK_IN.get(model, 1.0)
        price_out = MODEL_PRICE_PER_MTOK_OUT.get(model, 4.0)

        cost = (input_tokens / 1_000_000) * price_in + (output_tokens / 1_000_000) * price_out
        return round(cost, 6)

    # ---- 核心操作 ----

    def consume(
        self,
        model: str,
        input_chars: int = 0,
        output_chars: int = 0,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
    ) -> float:
        """记录一次 LLM 调用的 token 消耗

        Args:
            model:         模型名
            input_chars:   输入字符数
            output_chars:  输出字符数
            input_tokens:  精确输入 token 数（可选）
            output_tokens: 精确输出 token 数（可选）

        Returns:
            本次调用成本（元）

        Raises:
            TokenBudgetExceeded: 超出预算时抛出
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
            "[TokenBudget] Session=%s consumed ¥%.6f (model=%s), "
            "total=¥%.4f/¥%.2f (%.1f%%)",
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
        """使用 API 返回的实际 token 数记录消耗（优先使用此方法）

        Args:
            model:                模型名
            actual_input_tokens:  API 返回的 prompt_tokens
            actual_output_tokens: API 返回的 completion_tokens

        Returns:
            成本（元）
        """
        return self.consume(
            model=model,
            input_tokens=actual_input_tokens,
            output_tokens=actual_output_tokens,
        )

    # ---- 查询方法 ----

    @property
    def is_tripped(self) -> bool:
        """熔断器是否已触发"""
        return self._tripped or self.consumed_cny >= self.budget_cny

    @property
    def usage_ratio(self) -> float:
        """预算使用比例 0.0-1.0"""
        if self.budget_cny <= 0:
            return 1.0
        return min(self.consumed_cny / self.budget_cny, 1.0)

    @property
    def should_warn(self) -> bool:
        """是否达到告警阈值（80%）"""
        return self.usage_ratio >= _BUDGET_WARN_THRESHOLD

    def warn_if_near_limit(self) -> Optional[str]:
        """接近预算时返回警告信息

        Returns:
            警告字符串或 None
        """
        ratio = self.usage_ratio
        if ratio >= _BUDGET_CIRCUIT_THRESHOLD:
            return (
                f"⚠️ TokenBudget 熔断！Session={self.session_id} "
                f"已消耗 ¥{self.consumed_cny:.4f}/¥{self.budget_cny:.2f}"
            )
        if ratio >= _BUDGET_WARN_THRESHOLD and not self._warned:
            self._warned = True
            remaining = self.budget_cny - self.consumed_cny
            logger.warning(
                "[TokenBudget] Session=%s 预算告警: "
                "已使用 %.1f%% (¥%.4f/¥%.2f), 剩余 ¥%.4f",
                self.session_id, ratio * 100,
                self.consumed_cny, self.budget_cny, remaining,
            )
            return (
                f"⚠️ TokenBudget 预算告警: 已使用 {ratio*100:.0f}% "
                f"(¥{self.consumed_cny:.4f}/¥{self.budget_cny:.2f})"
            )
        return None

    def get_stats(self) -> Dict[str, Any]:
        """获取预算统计摘要"""
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
        """重置预算计数器

        Args:
            new_budget: 新的预算上限（None 表示保持原值）
        """
        if new_budget is not None:
            self.budget_cny = new_budget
        self.consumed_cny = 0.0
        self.call_count = 0
        self._tripped = False
        self._warned = False
        logger.info(
            "[TokenBudget] Session=%s 预算已重置 (new_budget=¥%.2f)",
            self.session_id, self.budget_cny,
        )


# ============================================================================
# 会话级 TokenBudget 注册表（线程安全，由 dispatch_llm 使用）
# ============================================================================

_budget_lock = asyncio.Lock()
_session_budgets: Dict[str, TokenBudget] = {}


async def get_session_budget(session_id: str) -> TokenBudget:
    """获取或创建会话级 TokenBudget

    Args:
        session_id: 会话标识

    Returns:
        TokenBudget 实例
    """
    async with _budget_lock:
        if session_id not in _session_budgets:
            _session_budgets[session_id] = TokenBudget(
                session_id=session_id,
                budget_cny=_DEFAULT_SESSION_BUDGET,
            )
            logger.info(
                "[TokenBudget] Session=%s 新建预算 ¥%.2f",
                session_id, _DEFAULT_SESSION_BUDGET,
            )
        return _session_budgets[session_id]


async def cleanup_session_budget(session_id: str) -> None:
    """清理会话预算（会话结束时调用）"""
    async with _budget_lock:
        if session_id in _session_budgets:
            budget = _session_budgets.pop(session_id)
            logger.info(
                "[TokenBudget] Session=%s 已清理, 最终消耗=¥%.4f/¥%.2f",
                session_id, budget.consumed_cny, budget.budget_cny,
            )
