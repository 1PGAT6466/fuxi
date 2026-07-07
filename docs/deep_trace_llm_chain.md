# 伏羲 v1.50 — LLM 调用链深度全链路追踪

> **追踪方法**：逐行读取实际代码（非 docstring），确认每个函数的真正行为。
> **追踪日期**：2026-07-06
> **代码库**：`E:\easyclaw\伏羲-v1.44\repo`

---

## 1. 核心发现摘要

### 🔴 关键发现 1：两个 LLM 文件完全重复（90% 代码相同）

- `src/services/llm.py` — 头部称 v1.43
- `src/infra/llm.py` — 头部称 v1.50

两个文件是**独立的、完整的、互不调用的副本**。它们各自拥有：
- 自己的 `_call_api()`
- 自己的 `_call_api_stream()`
- 自己的 `call_llm()` / `call_llm_fast()` / `call_llm_stream()`
- 自己的 `call_ai()` / `call_ai_raw()` / `call_deepseek()` / `call_ollama()` / `call_siliconflow()` / `call_mimo_async()`

**差异仅在于**：`infra/llm.py` 多了 `TASK_MODEL_MAP`、`TASK_MAX_TOKENS`、`call_llm_by_task()` 三个新增功能。

### 🔴 关键发现 2：没有 Ollama SDK、没有 DeepSeek SDK

全代码库中：
- **零 import ollama / from ollama**
- **零 import openai / from openai**
- **零 import deepseek / from deepseek**
- 所有 LLM 调用都是**原生 HTTP POST**（aiohttp 或 requests）到 OpenAI 兼容 `/chat/completions` 端点。

### 🔴 关键发现 3：call_ollama / call_deepseek 都是重定向壳

- `call_ollama()` — 直接转发到 `call_llm()` → 实际发 MiMo API
- `call_deepseek()` — 直接转发到 `call_llm()` → 实际发 MiMo API（仅在 MiMo 失败后才会真正调用 DeepSeek API）
- `call_mimo_async()` — 直接转发到 `call_llm()` → 实际发 MiMo API

### 🔴 关键发现 4：services/__init__.py 重新导出的是 infra/llm.py 的版本

```python
# src/services/__init__.py:69
from src.infra.llm import call_ai
```

这意味着 `from src.services import call_ai` 实际拿到的是 `infra/llm.py` 的版本。

---

## 2. 逐函数追踪

### 2.1 `call_llm()` — 统一入口（两个文件均有，逻辑相同）

| 属性 | 值 |
|------|-----|
| 所在文件 | `src/services/llm.py:160` 和 `src/infra/llm.py:151` |
| 实际行为 | 构建 messages → 先调 `_call_api(MiMo)` → 失败后调 `_call_api(DeepSeek)` |
| 降级链 | MiMo 2.5 Pro (重试 2 次) → DeepSeek (尝试 1 次) → 返回空 `""` |
| URL（MiMo） | `https://token-plan-cn.xiaomimimo.com/v1/chat/completions` |
| 模型（MiMo） | `MIMO_MODEL`（默认 `mimo-v2.5`，可参数覆盖） |
| URL（DeepSeek） | `https://api.deepseek.com/chat/completions` |
| 模型（DeepSeek） | `DEEPSEEK_MODEL`（默认 `deepseek-v4-pro`） |

**代码证据**（services/llm.py:168-197）：
```python
# Level 1: MiMo 2.5 Pro
for attempt in range(MAX_RETRIES):
    result = await _call_api(
        MIMO_BASE_URL, MIMO_API_KEY, model or MIMO_MODEL,
        messages, max_tokens, temperature, MIMO_TIMEOUT,
    )
    if result: return result

# Level 2: DeepSeek
if DEEPSEEK_API_KEY:
    result = await _call_api(
        DEEPSEEK_BASE_URL, DEEPSEEK_API_KEY, DEEPSEEK_MODEL,
        messages, max_tokens, temperature, DEEPSEEK_TIMEOUT,
    )
    if result: return result
return ""
```

### 2.2 `_call_api()` — 底层 HTTP 引擎（两个文件均有，逻辑相同）

| 属性 | 值 |
|------|-----|
| 所在文件 | `src/services/llm.py:38` 和 `src/infra/llm.py:28` |
| 请求方式 | `aiohttp.ClientSession().post()` |
| 端点 | `{base_url}/chat/completions`（OpenAI 兼容路径） |
| 重试策略 | 最多 3 次，每次 max_tokens 翻倍：4096→8192→12288 |
| 关键参数 | `enable_thinking: False`（关闭 MiMo 思考模式） |
| 空内容检测 | 如果 content 为空但有 reasoning_content，自动重试扩大 token 预算 |

### 2.3 `call_llm_fast()` — 轻量任务快通道

| 属性 | 值 |
|------|-----|
| 实际行为 | 调用 `call_llm(model="mimo-v2.5-turbo")` — **转发壳** |
| 最终 URL | `https://token-plan-cn.xiaomimimo.com/v1/chat/completions` |
| 最终模型 | `mimo-v2.5-turbo` |
| 特点 | max_tokens 默认 500, temperature 默认 0.1 |

### 2.4 `call_llm_stream()` — 流式 Fallback 链

| 属性 | 值 |
|------|-----|
| 实际行为 | 调用 `_call_api_stream(MiMo)` — 只走 MiMo，无 DeepSeek fallback |
| 最终 URL | `https://token-plan-cn.xiaomimimo.com/v1/chat/completions` |
| 最终模型 | `MIMO_MODEL` 或参数覆盖 |

⚠️ **流式调用没有 DeepSeek fallback！**

### 2.5 `call_ai()` — 兼容旧接口（转发壳）

| 属性 | 值 |
|------|-----|
| 实际行为 | **直接转发到 `call_llm(prompt, max_tokens=max_tokens)`** |
| 最终 URL | `https://token-plan-cn.xiaomimimo.com/v1/chat/completions` |

代码证据（infra/llm.py:226-228）：
```python
async def call_ai(prompt: str, max_tokens: int = 300) -> str:
    """兼容旧调用"""
    return await call_llm(prompt, max_tokens=max_tokens)
```

### 2.6 `call_ai_raw()` — 兼容旧接口（转发壳）

| 属性 | 值 |
|------|-----|
| 实际行为 | **直接转发到 `call_llm(prompt, max_tokens=max_tokens)`** |
| 最终 URL | `https://token-plan-cn.xiaomimimo.com/v1/chat/completions` |

代码证据（infra/llm.py:221-223）：
```python
async def call_ai_raw(prompt: str, max_tokens: int = 300) -> str:
    """兼容旧调用"""
    return await call_llm(prompt, max_tokens=max_tokens)
```

### 2.7 `call_deepseek()` — 兼容旧接口（**转发壳，不是直接调 DeepSeek**）

| 属性 | 值 |
|------|-----|
| 实际行为 | **直接转发到 `call_llm(...)`** |
| 最终 URL | 先 `https://token-plan-cn.xiaomimimo.com/v1/chat/completions`，失败后才 `https://api.deepseek.com/chat/completions` |
| **不是**独立 DeepSeek SDK 调用 | ✅ 是转发壳 |

代码证据（infra/llm.py:232-236）：
```python
async def call_deepseek(prompt, system_prompt=None, max_tokens=2048, temperature=0.3, model=None):
    """兼容旧调用，重定向到 call_llm"""
    return await call_llm(prompt, system_prompt, max_tokens, temperature, model)
```

### 2.8 `call_ollama()` — 已弃用的本地调用（**转发壳**）

| 属性 | 值 |
|------|-----|
| 实际行为 | **直接转发到 `call_llm(prompt_text, max_tokens=max_tokens)`** |
| 最终 URL | `https://token-plan-cn.xiaomimimo.com/v1/chat/completions` |
| 无本地 Ollama | ✅ 纯转发，无 ollama SDK 调用 |

代码证据（infra/llm.py:295-297）：
```python
async def call_ollama(prompt_text: str, model: str = None, max_tokens: int = 300) -> Optional[str]:
    """已弃用：重定向到 MiMo API"""
    return await call_llm(prompt_text, max_tokens=max_tokens)
```

### 2.9 `call_siliconflow()` — 独立供应商（**真独立实现**）

| 属性 | 值 |
|------|-----|
| 实际行为 | 使用自己的 `SILICONFLOW_API_KEY` 和 `SILICONFLOW_BASE_URL`，调用 `_call_api()` |
| 最终 URL | `https://api.siliconflow.cn/v1/chat/completions` |
| 默认模型 | `Qwen/Qwen2.5-7B-Instruct` |
| 与 Fallback 链关系 | **完全独立**，不参与 MiMo→DeepSeek 降级 |

代码证据（infra/llm.py:307-313）：
```python
async def call_siliconflow(prompt: str, model: str = "") -> str:
    from src.config import SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL
    sf_key = SILICONFLOW_API_KEY
    sf_url = SILICONFLOW_BASE_URL
    sf_model = model or "Qwen/Qwen2.5-7B-Instruct"
    if not sf_key: return ""
    return await _call_api(sf_url, sf_key, sf_model, [{"role":"user","content":prompt}], 500) or ""
```

### 2.10 `call_mimo_async()` — 兼容旧接口（转发壳）

| 属性 | 值 |
|------|-----|
| 实际行为 | 调用 `call_llm(query, system_prompt="你是伏羲知识库助手", max_tokens=2048)` |
| 最终 URL | `https://token-plan-cn.xiaomimimo.com/v1/chat/completions` |

### 2.11 `call_llm_by_task()` — 仅 infra/llm.py 有

| 属性 | 值 |
|------|-----|
| 所在文件 | `src/infra/llm.py:285` |
| 实际行为 | 根据 TASK_MODEL_MAP 选模型，再调用 `call_llm()` |
| 任务→模型映射 | extraction/classification→mimo-v2.5, synthesis/reasoning→mimo-v2.5-pro, fast→mimo-v2.5-turbo |

### 2.12 直连 MiMo 的函数（绕过了 services/llm.py）

以下 2 个函数直接 HTTP POST MiMo API，**不经过** services/llm.py 和 infra/llm.py：

| 函数 | 文件 | 方式 | URL | 模型 |
|------|------|------|-----|------|
| `_llm_judge()` | `src/services/evaluator.py:15` | `requests.post()` | `https://token-plan-cn.xiaomimimo.com/v1/chat/completions` | `mimo-v2.5`（硬编码） |
| `llm_classify()` | `src/category_registry.py:412` | `requests.post()` | `https://token-plan-cn.xiaomimimo.com/v1/chat/completions` | `mimo-v2.5`（硬编码） |
| `_call_mimo_fc()` | `src/agents_old/yang_agent.py:212` | 调用 `services/llm._call_api()` | `MIMO_BASE_URL` | `MIMO_MODEL` |
| `_call_mimo_with_tools()` | `src/shaoyin/agentic_rag_v2.py:154` | `aiohttp` 直接 POST | `MIMO_BASE_URL` | `MIMO_MODEL` |

### 2.13 多模态图片转录（走 DeepSeek/SiliconFlow URL）

| 函数 | 文件 | URL | 模型 |
|------|------|-----|------|
| `transcribe_image()` | `src/shaoyang/multimodal.py:90` | `https://api.deepseek.com/v1/chat/completions`（用 DEEPSEEK_API_KEY） | `Qwen/Qwen3-VL-8B-Instruct` |

---

## 3. 完整调用关系图（ASCII 图）

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         调用方（Callers）                                 │
├─────────────────────────────────────────────────────────────────────────┤
│  hypothalamus/brain.py       → from src.services.llm import call_ai     │
│  pipeline/unified.py         → from src.services.llm import call_ai     │
│  shaoyin/brain.py            → from src.infra.llm import call_deepseek  │
│  shaoyin/composer.py         → from src.infra.llm import call_llm_by_task│
│  shaoyin/context_compressor  → from src.services.llm import call_deepseek│
│  shaoyin/fact_check.py       → from src.services.llm import call_llm_fast│
│  shaoyin/judge.py            → from src.services.llm import call_deepseek│
│  shaoyin/judge_v2.py         → from src.services.llm import call_llm_fast│
│  shaoyin/query_planner.py    → from src.services.llm import call_llm_fast│
│  shaoyin/query_resolver.py   → from src.services.llm import call_llm    │
│  shaoyin/smart_self_rag.py   → from src.infra.llm import call_ai        │
│  taiyang/crag.py             → from src.services.llm import call_ai_raw │
│  taiyang/l5_crag.py          → from src.infra.llm import call_ai        │
│  taiyang/multi_hop.py        → from src.infra.llm import call_ai        │
│  taiyin/server.py            → from src.infra.llm import call_llm       │
│  ai_tools/routes.py          → from src.services.llm import call_llm    │
│  shaoyang/extractor.py       → from src.infra.llm import call_ai        │
│  shaoyang/kg_extractor.py    → from src.services.llm import call_llm    │
│  shaoyang/long_doc_handler   → from src.services.llm import call_deepseek│
│  shaoyang/wiki_distiller.py  → from src.services.llm import call_llm    │
│  agents_old/generation_agent → from src.services.llm import call_deepseek│
│  agents_old/yin_agent.py     → from src.services.llm import call_deepseek│
│  agents_old/yang_agent.py    → from src.services.llm import _call_api   │
│  services/query_expansion    → from src.services.llm import call_ai_raw │
│  services/table_view.py      → from src.services.llm import call_ai_raw │
│  infra/health_check.py       → from src.infra.llm import call_llm       │
│                                                                         │
│  services/__init__.py        → from src.infra.llm import call_ai        │
│  (re-export: from src.services import call_ai → 实际是 infra 版本)      │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    中转壳层（Shell Layer）                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  call_ai(prompt)           ──→ call_llm(prompt)          [转发壳]       │
│  call_ai_raw(prompt)       ──→ call_llm(prompt)          [转发壳]       │
│  call_deepseek(prompt)     ──→ call_llm(prompt)          [转发壳]       │
│  call_ollama(prompt)       ──→ call_llm(prompt)          [转发壳]       │
│  call_ollama_stream(p)     ──→ call_llm_stream(prompt)   [转发壳]       │
│  call_deepseek_stream(p)   ──→ call_llm_stream(prompt)   [转发壳]       │
│  call_mimo_async(query)    ──→ call_llm(query, sp="...") [转发壳]       │
│  call_llm_fast(prompt)     ──→ call_llm(prompt,          [转发壳]       │
│                                   model="mimo-v2.5-turbo")              │
│  call_llm_by_task(task, p) ──→ call_llm(p, model=MAP[task])[转发壳]    │
│  call_siliconflow(prompt)  ──→ _call_api(SF_URL, SF_KEY) [独立]        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     `call_llm()` — 核心 Fallback 引擎                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Level 1: _call_api(MiMo)                                              │
│    ├── URL:  https://token-plan-cn.xiaomimimo.com/v1/chat/completions  │
│    ├── Model: MIMO_MODEL (default "mimo-v2.5")                         │
│    ├── Retries: 2 (MAX_RETRIES)                                        │
│    ├── Each retry: _call_api internally retries 3x with expanding      │
│    │              max_tokens (4096→8192→12288)                         │
│    └── Failure → go to Level 2                                         │
│                                                                         │
│  Level 2: _call_api(DeepSeek)                     [if DEEPSEEK_API_KEY]│
│    ├── URL:  https://api.deepseek.com/chat/completions                 │
│    ├── Model: deepseek-v4-pro                                          │
│    ├── Retries: 1 (single attempt)                                     │
│    └── Failure → return ""                                             │
│                                                                         │
│  Level 3: 无 — 返回空字符串 ""                                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     `_call_api()` — 底层 HTTP 引擎                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  POST {base_url}/chat/completions                                      │
│                                                                         │
│  Headers:                                                               │
│    Content-Type: application/json                                       │
│    Authorization: Bearer {api_key}                                      │
│                                                                         │
│  Payload:                                                               │
│    model: {model_name}                    ← 来自参数                     │
│    messages: [{role, content}, ...]                                     │
│    max_tokens: 4096/8192/12288           ← 逐次翻倍                     │
│    temperature: {temperature}                                           │
│    stream: false                                                        │
│    enable_thinking: false                ← 关键：关闭 MiMo 思考模式      │
│                                                                         │
│  重试: 最多 3 次 (attempt 0,1,2)                                       │
│  放大: max_tokens = base_max * (attempt+1) → 4096/8192/12288           │
│  检测: content 为空但 reasoning 不为空 → 重试                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. services/llm.py 与 infra/llm.py 对比表

| 函数 | services/llm.py | infra/llm.py | 差异 |
|------|:---:|:---:|------|
| `_call_api()` | ✅ (L:38) | ✅ (L:28) | 完全相同 |
| `_call_api_stream()` | ✅ (L:112) | ✅ (L:124) | 完全相同（infra 版多 logging） |
| `call_llm()` | ✅ (L:160) | ✅ (L:151) | 完全相同 |
| `call_llm_fast()` | ✅ (L:207) | ✅ (L:200) | 完全相同 |
| `call_llm_stream()` | ✅ (L:212) | ✅ (L:206) | 完全相同 |
| `call_ai_raw()` | ✅ (L:230) | ✅ (L:221) | 完全相同 |
| `call_ai()` | ✅ (L:235) | ✅ (L:226) | 完全相同 |
| `call_deepseek()` | ✅ (L:240) | ✅ (L:232) | 完全相同 |
| `call_deepseek_stream()` | ✅ (L:248) | ✅ (L:239) | 完全相同 |
| `call_ollama()` | ✅ (L:260) | ✅ (L:295) | 完全相同 |
| `call_ollama_stream()` | ✅ (L:265) | ✅ (L:301) | 完全相同 |
| `call_siliconflow()` | ✅ (L:272) | ✅ (L:307) | 完全相同 |
| `call_siliconflow_stream()` | ✅ (L:283) | ✅ (L:319) | 完全相同 |
| `call_mimo_async()` | ✅ (L:297) | ✅ (L:332) | 完全相同 |
| `call_llm_by_task()` | ❌ | ✅ (L:285) | **仅 infra 有** |
| `TASK_MODEL_MAP` | ❌ | ✅ (L:251) | **仅 infra 有** |
| `TASK_MAX_TOKENS` | ❌ | ✅ (L:278) | **仅 infra 有** |

---

## 5. 真正的供应商关系

### 5.1 供应商依赖（零第三方 SDK）

```
pip install openai       → NO (未使用)
pip install ollama       → NO (未使用)
pip install deepseek     → NO (未使用)
pip install aiohttp      → YES (async HTTP)
pip install requests     → YES (sync HTTP)
```

### 5.2 供应商 URL 汇总

| 供应商 | 默认 URL | 使用函数 |
|--------|----------|---------|
| MiMo | `https://token-plan-cn.xiaomimimo.com/v1` | `_call_api()`, `_call_api_stream()`, `_llm_judge()`, `llm_classify()`, `_call_mimo_fc()`, `_call_mimo_with_tools()` |
| DeepSeek | `https://api.deepseek.com` | `call_llm()` Fallback, `transcribe_image()` |
| SiliconFlow | `https://api.siliconflow.cn/v1` | `call_siliconflow()`, `call_siliconflow_stream()` |

### 5.3 模型名称汇总

| 模型 | 用途 | 供应商 |
|------|------|--------|
| `mimo-v2.5` | 默认模型（JSON 输出任务） | MiMo |
| `mimo-v2.5-pro` | 推理/综合/反思/规划 | MiMo |
| `mimo-v2.5-turbo` | 轻量分类/提取 | MiMo |
| `deepseek-v4-pro` | Fallback 降级 | DeepSeek |
| `Qwen/Qwen2.5-7B-Instruct` | SiliconFlow 通道 | SiliconFlow |
| `Qwen/Qwen3-VL-8B-Instruct` | 多模态图片转录 | SiliconFlow (via DEEPSEEK_BASE) |

---

## 6. 降级/容错链路

```
                             用户请求
                                │
                                ▼
                        ┌───────────────┐
                        │  call_llm()   │
                        │  call_ai()    │
                        │  call_deepseek│
                        │  call_ollama  │  ← 全是转发壳，都到 call_llm
                        │  call_llm_fast│
                        │  call_llm_by_ │
                        │     task()    │
                        └───────┬───────┘
                                │
                    ┌───────────▼───────────┐
                    │ Level 1: MiMo 2.5      │
                    │ URL: xiaomimimo.com    │
                    │ Retry: 2次             │
                    │ 内部 _call_api 再重试  │
                    │ 3次（逐次放大 token）  │
                    └───────────┬───────────┘
                         失败/空  │
                    ┌───────────▼───────────┐
                    │ Level 2: DeepSeek      │
                    │ URL: api.deepseek.com  │
                    │ 尝试: 1次（无重试）     │
                    └───────────┬───────────┘
                         失败/空  │
                    ┌───────────▼───────────┐
                    │ Level 3: 返回 ""       │
                    │ (无本地Ollama, 无模板) │
                    └───────────────────────┘
```

⚠️ **注意**：文件头部注释声称 "MiMo 2.5 Pro → DeepSeek → 本地（逐级降级）"，但实际代码中**没有本地降级**——Level 3 直接返回空字符串。

⚠️ `call_siliconflow()` **不参与此降级链**，它是完全独立的供应商通道。

---

## 7. 重构建议

1. **合并两个重复文件**：保留 `infra/llm.py`（更新版本），删除 `services/llm.py`，在 `services/__init__.py` 中重新导出全部符号。

2. **统一直连 MiMo 的调用**：`evaluator.py` 和 `category_registry.py` 应该通过 `infra/llm.py` 的统一入口调用，而不是自己硬编码 URL 和模型名。

3. **修复流式无降级的问题**：`call_llm_stream()` 只走 MiMo，应该也加 DeepSeek fallback。

4. **修复硬编码 URL**：`evaluator.py:11` 和 `category_registry.py:417` 硬编码了 `https://token-plan-cn.xiaomimimo.com/v1`，应使用 `config.MIMO_BASE_URL`。

5. **修复硬编码模型名**：`evaluator.py:20` 和 `category_registry.py:419` 硬编码了 `mimo-v2.5`，应使用 `config.MIMO_MODEL`。

6. **实现真正的 Level 3 本地降级**：可以回到 Ollama 本地模型，或实现模板拼接回答。

7. **修复 `category_registry.py:427` 的 BUG**：f-string 中 `os.getenv` 调用被放在了引号内，实际发送的 Header 是 `Bearer {os.getenv('MIMO_API_KEY', '')}`（字面字符串），而非实际的 API Key。
