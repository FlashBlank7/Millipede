"""
LLM client with multi-provider support.

Supported providers (set DEFAULT_LLM_MODEL in .env):
  - Anthropic:  claude-3-5-sonnet-20241022  (needs ANTHROPIC_API_KEY)
  - OpenAI:     gpt-4o                       (needs OPENAI_API_KEY)
  - DeepSeek:   deepseek/deepseek-chat       (needs DEEPSEEK_API_KEY)
  - 豆包:        volcengine/doubao-pro-32k    (needs VOLCENGINE_API_KEY + DOUBAO_MODEL_ID)
  - 千问:        openai/qwen-max              (needs DASHSCOPE_API_KEY)

json_object response_format:
  - Anthropic, OpenAI, DeepSeek: supported natively
  - 千问 (DashScope): supported via OpenAI-compat layer
  - 豆包 (Doubao): NOT supported — falls back to prompt-based JSON extraction
"""

import json
import logging
import os
import re
from typing import Any, AsyncGenerator

import litellm

from app.config import get_settings

logger = logging.getLogger(__name__)

litellm.set_verbose = False

# Providers that do NOT support response_format={"type": "json_object"}
_NO_JSON_MODE_PREFIXES = ("volcengine/",)

# Provider-specific api_base overrides
_API_BASE_MAP = {
    "openai/qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
}


def _build_kwargs(model: str, settings) -> dict[str, Any]:
    """Return extra litellm kwargs (api_key, api_base) for a given model string."""
    kwargs: dict[str, Any] = {}

    if model.startswith("deepseek/"):
        if settings.deepseek_api_key:
            kwargs["api_key"] = settings.deepseek_api_key

    elif model.startswith("volcengine/"):
        if settings.volcengine_api_key:
            kwargs["api_key"] = settings.volcengine_api_key
        # 豆包需要用 DOUBAO_MODEL_ID 替换模型名中的通用名
        # e.g. volcengine/doubao-pro-32k → 实际发送 ep-xxx endpoint ID
        if settings.doubao_model_id:
            kwargs["model"] = f"volcengine/{settings.doubao_model_id}"

    elif model.startswith("openai/qwen"):
        if settings.dashscope_api_key:
            kwargs["api_key"] = settings.dashscope_api_key
        kwargs["api_base"] = _API_BASE_MAP["openai/qwen"]

    elif model.startswith("claude") or model.startswith("anthropic/"):
        if settings.anthropic_api_key:
            kwargs["api_key"] = settings.anthropic_api_key

    else:
        # Generic OpenAI or other LiteLLM-supported provider
        if settings.openai_api_key:
            kwargs["api_key"] = settings.openai_api_key

    return kwargs


def _supports_json_mode(model: str) -> bool:
    return not any(model.startswith(p) for p in _NO_JSON_MODE_PREFIXES)


def _extract_json_from_text(text: str) -> str:
    """
    Fallback: extract first JSON object from free-form text.
    Used when json_object mode is not available (e.g. Doubao).
    """
    # Try ```json ... ``` block first
    block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if block:
        return block.group(1)
    # Try bare { ... }
    obj = re.search(r"\{.*\}", text, re.DOTALL)
    if obj:
        return obj.group(0)
    return text


async def chat_completion(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    response_format: dict | None = None,
) -> str:
    settings = get_settings()
    model = model or settings.default_llm_model

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        **_build_kwargs(model, settings),
    }

    wants_json = response_format and response_format.get("type") == "json_object"

    if wants_json and _supports_json_mode(model):
        kwargs["response_format"] = response_format
    elif wants_json:
        # Inject JSON instruction into last user message instead
        messages = list(messages)
        messages[-1] = {
            **messages[-1],
            "content": messages[-1]["content"] + "\n\nRespond with valid JSON only. No markdown, no explanation.",
        }
        kwargs["messages"] = messages

    response = await litellm.acompletion(**kwargs)
    content = response.choices[0].message.content

    if wants_json and not _supports_json_mode(model):
        content = _extract_json_from_text(content)

    return content


async def stream_completion(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> AsyncGenerator[str, None]:
    settings = get_settings()
    model = model or settings.default_llm_model

    response = await litellm.acompletion(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
        **_build_kwargs(model, settings),
    )
    async for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
