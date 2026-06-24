"""
llm_stream_patch.py — 流式响应超时修复
========================================
修复内容：
1. DeepSeek 流式调用加 chunk 级超时（防止 API 挂起永久等待）
2. Ollama 调用加超时保护

使用方式：替换 llm.py 中的 call_deepseek_stream 函数
"""

import json
import asyncio
import logging
from typing import AsyncGenerator

import aiohttp

logger = logging.getLogger(__name__)

CHUNK_TIMEOUT = 30.0  # 每个 chunk 的最大等待时间


async def call_deepseek_stream_patched(
    prompt: str, 
    system_prompt: str = None, 
    max_tokens: int = 2048,
    temperature: float = 0.3, 
    model: str = None
) -> AsyncGenerator[str, None]:
    """流式调用 DeepSeek — 带 chunk 级超时保护"""
    import os
    
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        yield "DeepSeek API Key 未配置"
        return
    
    base_url = "https://api.deepseek.com"
    default_model = "deepseek-v4-pro"
    timeout = aiohttp.ClientTimeout(total=90)
    
    try:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt[:4000]})
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}/v1/chat/completions",
                json={
                    "model": model or default_model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True
                },
                headers=headers,
                timeout=timeout,
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    yield f"API 错误 {resp.status}: {text[:200]}"
                    return
                
                buffer = ""
                while True:
                    try:
                        # 关键修复：chunk 级超时
                        chunk = await asyncio.wait_for(
                            resp.content.readany(),
                            timeout=CHUNK_TIMEOUT
                        )
                        if not chunk:  # 连接关闭
                            break
                        
                        buffer += chunk.decode("utf-8", errors="ignore")
                        
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            if line.startswith("data: "):
                                data = line[6:]
                                if data == "[DONE]":
                                    return
                                try:
                                    obj = json.loads(data)
                                    delta = obj.get("choices", [{}])[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                                except json.JSONDecodeError:
                                    pass
                    
                    except asyncio.TimeoutError:
                        logger.warning("[LLM] stream chunk timeout, closing connection")
                        yield "\n[响应超时，已中断]"
                        return
                    except Exception as e:
                        logger.warning(f"[LLM] stream read error: {e}")
                        yield f"\n[读取异常: {str(e)[:50]}]"
                        return
    
    except asyncio.TimeoutError:
        yield "[连接超时]"
    except aiohttp.ClientError as e:
        yield f"[连接异常: {str(e)[:50]}]"
    except Exception as e:
        yield f"[调用失败: {str(e)[:50]}]"


async def call_ollama_patched(
    prompt_text: str, 
    model: str = None, 
    max_tokens: int = 300,
    timeout: float = 90.0
) -> str:
    """调用 Ollama — 带超时保护"""
    try:
        from src.config import OLLAMA_URL, OLLAMA_MODEL
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model or OLLAMA_MODEL,
                    "prompt": prompt_text[:2000],
                    "stream": False,
                    "options": {"num_predict": max_tokens, "temperature": 0.1}
                },
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                if resp.status != 200:
                    try:
                        error_body = await resp.text()
                        logger.warning(f"Ollama {resp.status}: {error_body[:100]}")
                    except Exception:
                        logger.warning(f"Ollama {resp.status}: (no body)")
                    return ""
                data = await resp.json()
                response = data.get("response", "").strip()
                logger.info(f"Ollama({model or OLLAMA_MODEL}) OK ({len(response)} chars)")
                return response
    except asyncio.TimeoutError:
        logger.warning(f"Ollama timeout after {timeout}s")
        return ""
    except Exception as e:
        logger.warning(f"Ollama unavailable: {e}")
        return ""
