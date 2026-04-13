"""Construct an OpenAI SDK client for cloud OpenAI, Ollama, or other compatible servers."""

from __future__ import annotations

import os

from openai import OpenAI

from .config import (
    AGENT_LLM_BACKEND,
    AGENT_OPENAI_BASE_URL,
    OLLAMA_BASE_URL,
)


def get_chat_client() -> OpenAI:
    """
    - ``openai`` (default): official API; requires ``OPENAI_API_KEY``.
    - ``ollama``: local server; uses ``OLLAMA_BASE_URL`` (``.../v1``) and a dummy key.
    - If ``AGENT_OPENAI_BASE_URL`` is set, it overrides the default base URL for ``openai`` backend.
    """
    if AGENT_LLM_BACKEND == "ollama":
        base = OLLAMA_BASE_URL.rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return OpenAI(
            base_url=base,
            api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
        )

    kwargs: dict = {}
    if AGENT_OPENAI_BASE_URL:
        kwargs["base_url"] = AGENT_OPENAI_BASE_URL.rstrip("/")
    return OpenAI(**kwargs)
