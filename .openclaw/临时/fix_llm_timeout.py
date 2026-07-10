"""Fix LLM timeout wrapper"""
import os

path = os.path.join('src', 'services', 'llm.py')
with open(path, 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Step 1: Add LLM_CHAIN_TIMEOUT config after the imports section
# Find the line "# ============ Fallback"
fallback_marker = "# ============ Fallback"
if fallback_marker not in content:
    print("ERROR: fallback marker not found")
    exit(1)

timeout_config = """
# v1.44 R2: LLM 调用链总超时（最长 60 秒）
LLM_CHAIN_TIMEOUT = int(os.getenv("FUXI_LLM_CHAIN_TIMEOUT", "60"))

"""

content = content.replace(fallback_marker, timeout_config + fallback_marker, 1)
print("Step 1: Added LLM_CHAIN_TIMEOUT config")

# Step 2: Replace call_llm function body with timeout wrapper
# Find the docstring end and inject wrapper
old_docstring_end = '    """\n    messages = []'
new_docstring_end = '''    v1.44 R2: 添加总超时控制（最长 60 秒），防止调用链无限等待
    """
    try:
        return await asyncio.wait_for(
            _call_llm_inner(prompt, system_prompt, max_tokens, temperature, model),
            timeout=LLM_CHAIN_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning(
            f"[LLM] 调用链超时 ({LLM_CHAIN_TIMEOUT}s), "
            f"prompt_len={len(prompt)}, model={model or 'default'}"
        )
        return ""


async def _call_llm_inner(
    prompt: str, system_prompt: str = None, max_tokens: int = 2048,
    temperature: float = 0.3, model: str = None,
) -> str:
    """LLM Fallback 内部实现（由 call_llm 包装超时）"""
    messages = []'''

if old_docstring_end not in content:
    print("ERROR: old_docstring_end not found")
    # Debug: show what's around
    idx = content.find('async def call_llm(')
    if idx >= 0:
        print(repr(content[idx:idx+300]))
    exit(1)

content = content.replace(old_docstring_end, new_docstring_end, 1)
print("Step 2: Wrapped call_llm with timeout")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("File saved successfully")
